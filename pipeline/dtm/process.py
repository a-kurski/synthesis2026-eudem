"""Blockwise cleaning/comparison and GDAL CLI mosaicking and single-step warp."""
import json
import logging
import math
from pathlib import Path
import shutil
import subprocess

import numpy as np
from osgeo import gdal, ogr

from .acquire import write_json
from .geo import grid, project, srs, valid_values, verify_alignment, windows

LOG = logging.getLogger('dtm')
OPTIONS = ['TILED=YES', 'COMPRESS=DEFLATE', 'PREDICTOR=3', 'BIGTIFF=YES']
VERTICAL_NOTE = 'No vertical datum harmonisation: AHN remains NAP; NRW remains DHHN2016/NHN. Differences also reflect acquisition epoch and production methods.'


def command(args):
    executable = shutil.which(args[0])
    if not executable:
        raise RuntimeError(f'{args[0]} not found. Set qgis_root or run from an OSGeo4W shell.')
    args = [executable, *map(str, args[1:])]
    LOG.info('COMMAND argv=%s', json.dumps(args))
    LOG.info('COMMAND %s', subprocess.list2cmdline(args))
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.stdout:
        LOG.info('%s', result.stdout.strip())
    if result.stderr:
        LOG.info('%s', result.stderr.strip())
    if result.returncode:
        raise RuntimeError(f'{Path(executable).name} failed ({result.returncode}): {result.stderr}')
    return result.stdout


def co_args():
    return [arg for option in OPTIONS for arg in ('-co', option)]


def create_raster(path, reference, nodata=-9999, vertical_note=VERTICAL_NOTE):
    ds = gdal.GetDriverByName('GTiff').Create(str(path), reference.RasterXSize, reference.RasterYSize, 1, gdal.GDT_Float32, OPTIONS)
    ds.SetGeoTransform(reference.GetGeoTransform())
    ds.SetProjection(reference.GetProjection())
    ds.GetRasterBand(1).SetNoDataValue(nodata)
    ds.SetMetadataItem('VERTICAL_DATUM_NOTE', vertical_note)
    ds.GetRasterBand(1).SetUnitType('m')
    return ds


def clean(source, destination, config, vertical_note=VERTICAL_NOTE):
    LOG.info('Clean metadata NoData, masks, NaN/Inf and abs(value)>=1e20: %s -> %s', source, destination)
    src = gdal.Open(str(source))
    temp = destination.with_suffix('.part.tif')
    dst = create_raster(temp, src, config['nodata'], vertical_note)
    for w in windows(src, config['block_size']):
        values, mask = valid_values(src.GetRasterBand(1), w)
        dst.GetRasterBand(1).WriteArray(np.where(mask, values, config['nodata']).astype('float32'), w[0], w[1])
    dst.FlushCache()
    dst = src = None
    temp.replace(destination)


def mosaic(name, tiles, directory, config):
    # VRT only includes this run's manifest, never a wildcard over old AOIs.
    if not tiles:
        raise ValueError(f'No source tiles for {name}')
    # Refuse shifts/mixed source grids; gdalbuildvrt otherwise resamples/skips silently.
    first = grid(tiles[0])
    dx, dy = first['transform'][1], first['transform'][5]
    for tile in tiles[1:]:
        other = grid(tile)
        if not np.allclose([dx, dy], [other['transform'][1], other['transform'][5]], rtol=0, atol=1e-8):
            raise ValueError(f'{name} source tile pixel sizes differ: {tile}')
        for k, step in ((0, dx), (3, dy)):
            offset = (other['transform'][k] - first['transform'][k]) / step
            if not math.isclose(offset, round(offset), rel_tol=0, abs_tol=1e-6):
                raise ValueError(f'{name} source tiles do not share one lattice: {tile}')
    listing = directory / f'{name}_tiles.txt'
    listing.write_text(''.join(str(Path(p).resolve()) + '\n' for p in tiles), encoding='utf-8')
    vrt = directory / f'{name}.vrt'
    command(['gdalbuildvrt', '-strict', '-overwrite', '-resolution', 'highest', '-vrtnodata', str(config['nodata']), '-input_file_list', listing, vrt])
    merged = directory / f'{name}_merged.tif'
    command(['gdal_translate', '-of', 'GTiff', '-ot', 'Float32', *co_args(), vrt, merged])
    LOG.info('%s merged grid: %s', name, json.dumps(grid(merged)))
    return merged


def align(ahn, nrw, output, config):
    reference = grid(nrw)
    command(['gdalwarp', '-overwrite', '-s_srs', 'EPSG:28992', '-t_srs', 'EPSG:25832',
             '-novshift', '-et', '0', '-te', *map(str, reference['extent']),
             '-ts', str(reference['cols']), str(reference['rows']), '-r', 'average',
             '-srcnodata', str(config['nodata']), '-dstnodata', str(config['nodata']),
             '-ot', 'Float32', '-of', 'GTiff', '-wm', '256', *co_args(), ahn, output])
    verify_alignment(output, nrw, config['alignment_tolerance_m'])
    LOG.info('Alignment verified: %s', json.dumps(grid(output)))


def aoi_mask(geometry, reference, path, epsg=25832):
    geometry = project(geometry, srs(epsg))
    memory = ogr.GetDriverByName('Memory').CreateDataSource('')
    layer = memory.CreateLayer('aoi', srs(epsg), ogr.wkbUnknown)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(geometry)
    layer.CreateFeature(feature)
    ds = gdal.GetDriverByName('GTiff').Create(str(path), reference.RasterXSize, reference.RasterYSize, 1, gdal.GDT_Byte,
                                            ['TILED=YES', 'COMPRESS=DEFLATE', 'BIGTIFF=IF_SAFER'])
    ds.SetProjection(reference.GetProjection())
    ds.SetGeoTransform(reference.GetGeoTransform())
    ds.GetRasterBand(1).Fill(0)
    gdal.RasterizeLayer(ds, [1], layer, burn_values=[1])
    ds.FlushCache()
    return ds


def difference(ahn, nrw, output, geometry, config):
    verify_alignment(ahn, nrw, config['alignment_tolerance_m'])
    a, b = gdal.Open(str(ahn)), gdal.Open(str(nrw))
    mask = aoi_mask(geometry, b, output.parent / 'aoi_mask.tif') if geometry is not None else None
    dst = create_raster(output, b, config['nodata'])
    dst.SetMetadataItem('DIFFERENCE', 'AHN minus NRW in metres; common valid coverage within AOI; pixel-centre AOI mask')
    values_file = output.parent / 'statistics_values.float32.tmp'
    n, mean, m2, abs_sum, sq_sum = 0, 0., 0., 0., 0.
    minimum, maximum = math.inf, -math.inf
    with values_file.open('wb') as stream:
        for w in windows(b, config['block_size']):
            av, am = valid_values(a.GetRasterBand(1), w)
            bv, bm = valid_values(b.GetRasterBand(1), w)
            valid = am & bm
            if mask is not None:
                valid &= mask.GetRasterBand(1).ReadAsArray(*w) != 0
            out = np.full(av.shape, config['nodata'], dtype='float32')
            out[valid] = (av[valid].astype('float64') - bv[valid].astype('float64')).astype('float32')
            if np.any(out[valid] == config['nodata']):
                raise ValueError('A valid difference equals the NoData sentinel -9999; refusing an ambiguous output.')
            dst.GetRasterBand(1).WriteArray(out, w[0], w[1])
            vals = out[valid].astype('float64')
            if not vals.size:
                continue
            vals.astype('float32').tofile(stream)
            count, block_mean = vals.size, float(vals.mean())
            delta = block_mean - mean
            m2 += float(np.sum((vals - block_mean) ** 2)) + delta * delta * n * count / (n + count)
            mean += delta * count / (n + count)
            n += count
            abs_sum += float(np.abs(vals).sum())
            sq_sum += float(np.square(vals).sum())
            minimum, maximum = min(minimum, float(vals.min())), max(maximum, float(vals.max()))
    dst.FlushCache()
    dst = a = b = mask = None
    result = {'valid_cell_count': n, 'mean_difference': None, 'median': None, 'mae': None,
              'rmse': None, 'standard_deviation': None, 'min': None, 'max': None,
              'p05': None, 'p25': None, 'p75': None, 'p95': None,
              'units': 'metres', 'standard_deviation_convention': 'population (ddof=0)',
              'quantile_method': 'exact linear interpolation (NumPy default)', 'vertical_datum_note': VERTICAL_NOTE}
    if n:
        # Disk-backed order statistics: no full raster / common-coverage array in RAM.
        values = np.memmap(values_file, dtype='float32', mode='r+', shape=(n,))
        quantiles = np.percentile(values, [5, 25, 50, 75, 95], overwrite_input=True, method='linear')
        del values
        result.update(mean_difference=mean, median=float(quantiles[2]), mae=abs_sum/n,
                      rmse=math.sqrt(sq_sum/n), standard_deviation=math.sqrt(max(0, m2/n)),
                      min=minimum, max=maximum, p05=float(quantiles[0]), p25=float(quantiles[1]),
                      p75=float(quantiles[3]), p95=float(quantiles[4]))
    values_file.unlink()
    write_json(output.parent / 'statistics.json', result)
    (output.parent / 'statistics.txt').write_text('\n'.join(f'{k}: {v}' for k, v in result.items()) + '\n', encoding='utf-8')
    LOG.info('Difference statistics: %s', json.dumps(result))
    if not n:
        raise RuntimeError('No common valid AHN/NRW coverage within the AOI. All-NoData raster and zero-count statistics were saved.')
    return result


def process(tiles, config, root, run_id, geometry):
    mosaics, aligned, output = [root / name / run_id for name in ('mosaics', 'aligned', 'output')]
    for directory in (mosaics, aligned, output):
        directory.mkdir(parents=True, exist_ok=True)
    # Clean derivatives before VRT/average; original downloaded bytes remain untouched.
    sources = {}
    for name in ('ahn', 'nrw'):
        cleaned = mosaics / f'{name}_clean_tiles'
        cleaned.mkdir()
        paths = []
        for tile in tiles[name]:
            target = cleaned / tile.name
            clean(tile, target, config)
            paths.append(target)
        sources[name] = mosaic(name, paths, mosaics, config)
    warped = aligned / 'ahn_aligned_to_nrw.tif'
    align(sources['ahn'], sources['nrw'], warped, config)
    ahn_clean = aligned / 'ahn_aligned_clean.tif'
    clean(warped, ahn_clean, config)
    verify_alignment(ahn_clean, sources['nrw'], config['alignment_tolerance_m'])
    stats = difference(ahn_clean, sources['nrw'], output / 'ahn_minus_nrw.tif', geometry, config)
    return {'outputs': str(output), 'reference_grid': grid(sources['nrw']), 'statistics': stats}
