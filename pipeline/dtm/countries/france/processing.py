"""Preserve the native ASCII grid, then warp its mosaic directly to the reference."""
import logging
import math

import numpy as np
from osgeo import gdal

from ...acquire import write_json
from ...geo import grid, project, rectangle, srs, verify_alignment, windows
from ...paths import raw_directory, receipt_path
from ...process import OPTIONS, aoi_mask, co_args, create_raster
from ...publication import mask_output, publish_tiles

LOG = logging.getLogger('dtm')
VERTICAL_NOTE = 'IGN RGE ALTI heights retain IGN69. Horizontal EPSG:2154 to EPSG:25832 transformation only; no vertical harmonisation applied.'


def validate_native(path, *, read_values=False):
    """Missing ASC CRS is supplied by the product declaration; conflicting CRS fails."""
    info = grid(path)
    with gdal.Open(str(path)) as ds:
        crs = ds.GetSpatialRef()
        if crs:
            crs = crs.Clone()
            crs.StripVertical()
        if ds.RasterCount != 1 or (crs and not crs.IsSame(srs(2154))):
            raise ValueError(f'RGE ALTI requires one band in EPSG:2154: {path}')
        if (info['cols'] != 1000 or info['rows'] != 1000
                or not np.allclose([info['transform'][1], info['transform'][5]], [5, -5], rtol=0, atol=1e-8)
                or info['nodata'] is None or not math.isfinite(info['nodata'])):
            raise ValueError(f'RGE ALTI requires 1000 x 1000 cells, 5 m spacing and finite declared NoData: {path}')
        if read_values:
            # A header alone cannot detect a truncated ASCII payload.
            band = ds.GetRasterBand(1)
            for window in windows(ds):
                values = band.ReadAsArray(*window)
                if values is None or not np.isfinite(values).all() or np.any(np.abs(values[values != info['nodata']]) >= 1e20):
                    raise ValueError(f'Invalid elevation values in {path}')
                if info['nodata'] != -9999 and np.any(values == -9999):
                    raise ValueError(f'Valid elevation conflicts with target NoData in {path}')
    return info


def missing_coverage(geometry, tiles):
    """Check footprints independently of NoData: holes inside tiles are retained."""
    missing = geometry.Clone()
    for tile in tiles:
        missing = missing.Difference(rectangle(tile['bounds']))
        if missing.IsEmpty():
            break
    return missing


def prepare(tiles, geometry, reference, run_dir, config):
    work = run_dir / 'processed' / '_work'
    work.mkdir(parents=True, exist_ok=True)
    native_aoi = project(geometry, srs(2154))
    converted, records, footprints = [], [], set()
    first = None
    for path in tiles:
        info = validate_native(path, read_values=True)
        extent = tuple(info['extent'])
        if native_aoi.Intersection(rectangle(extent)).GetArea() <= 0:
            raise ValueError(f'Non-AOI tile passed to France processing: {path}')
        if extent in footprints:
            raise ValueError(f'Duplicate RGE ALTI footprint: {path}')
        footprints.add(extent)
        gt = info['transform']
        if first and any(not math.isclose((gt[k] - first[k]) / 5, round((gt[k] - first[k]) / 5),
                                         rel_tol=0, abs_tol=1e-8) for k in (0, 3)):
            raise ValueError(f'RGE ALTI source grids do not share one lattice: {path}')
        first = gt
        destination = work / f'{path.parent.name}_{path.stem}.tif'
        # No size, extent or resolution options: this is a format conversion only.
        with gdal.Translate(str(destination), str(path), format='GTiff',
                            outputSRS='EPSG:2154', creationOptions=OPTIONS):
            pass
        after = grid(destination)
        for key in ('cols', 'rows', 'transform', 'nodata'):
            if after[key] != info[key]:
                raise RuntimeError(f'ASCII conversion changed {key}: {path}')
        converted.append(str(destination))
        records.append({'path': str(path), 'bounds': info['extent'],
                        'receipt': str(receipt_path(path, config))})
    missing = missing_coverage(native_aoi, records)
    if missing.GetArea() > 1e-4:
        LOG.warning('France: %.2f square metres lack source tiles; preserving the full target grid with NoData.',
                    missing.GetArea())
    vrt = work / 'rge_alti_native.vrt'
    if converted:
        with gdal.BuildVRT(str(vrt), converted, options=gdal.BuildVRTOptions(
                resolution='highest', strict=True, VRTNodata=config['nodata'])):
            pass
    target = grid(reference)
    with gdal.Open(str(reference)) as ref:
        if not ref.GetSpatialRef().IsSame(srs(25832)) or target['transform'][1] != 5 or target['transform'][5] != -5:
            raise ValueError('France target must be the common 5 m EPSG:25832 grid.')
    warped = work / 'rge_alti_aligned.tif'
    options = ['-overwrite', '-s_srs', 'EPSG:2154', '-t_srs', 'EPSG:25832', '-novshift',
               '-ovr', 'NONE', '-et', '0', '-te', *map(str, target['extent']),
               '-ts', str(target['cols']), str(target['rows']), '-r', 'bilinear',
               '-dstnodata', str(config['nodata']), '-ot', 'Float32', '-of', 'GTiff',
               '-wm', '256', *co_args()]
    if converted:
        with gdal.Warp(str(warped), str(vrt), options=gdal.WarpOptions(options=options)):
            pass
    else:
        # A completely out-of-coverage AOI still gets a correctly aligned product.
        with gdal.Open(str(reference)) as ref, create_raster(warped, ref, config['nodata'], VERTICAL_NOTE) as dst:
            dst.GetRasterBand(1).Fill(config['nodata'])
    verify_alignment(warped, reference, config['alignment_tolerance_m'])
    mask_path = work / 'aoi_mask.tif'
    with gdal.Open(str(reference)) as ref, aoi_mask(geometry, ref, mask_path) as mask:
        aoi_cells = sum(int(np.count_nonzero(mask.ReadAsArray(*w))) for w in windows(ref, config['block_size']))
    prepared = work / 'rge_alti_masked.tif'
    count = mask_output(warped, mask_path, prepared, config, VERTICAL_NOTE)['valid_cell_count']
    coverage = {'aoi_cell_count': aoi_cells, 'valid_cell_count': count,
                'nodata_cell_count': aoi_cells - count, 'missing_source_area_m2': missing.GetArea(),
                'coverage_status': 'empty' if not count else 'partial' if count < aoi_cells else 'complete'}
    write_json(run_dir / 'processed' / 'coverage.json', coverage)
    if not count:
        LOG.warning('No valid French elevations inside the AOI; publishing an all-NoData raster. See coverage.json.')
    elif aoi_cells != count:
        LOG.warning('France: %d AOI cells remain NoData; see coverage.json.', aoi_cells - count)
    publication = work / 'publication.vrt'
    with gdal.Translate(str(publication), str(prepared), format='VRT') as ds:
        ds.SetMetadataItem('PREPARATION', 'One bilinear horizontal warp to reference grid; pixel-centre AOI mask')
        ds.SetMetadataItem('SOURCE_PRODUCT', 'IGN RGE ALTI 5 m')
        ds.SetMetadataItem('SOURCE_VERTICAL_CRS', 'IGN69')
        ds.SetMetadataItem('VERTICAL_HARMONISATION', 'NOT_APPLIED')
        ds.SetMetadataItem('ATTRIBUTION', 'IGN; Licence Ouverte 2.0')
        ds.SetMetadataItem('COVERAGE_STATUS', coverage['coverage_status'])
    published = publish_tiles(publication, run_dir / 'processed', run_dir / 'stitched' / 'rge_alti.tif',
                              config, product='rge_alti')
    verify_alignment(published['stitched'], reference, config['alignment_tolerance_m'])
    return {'prepared_raster': published['stitched'], 'comparison_ready_raster': published['stitched'],
            'processed_tiles': published, 'grid': grid(published['stitched']),
            'raw_rge_alti_tiles': str(raw_directory(config)), 'source_tiles': records,
            'native_mosaic': str(vrt) if converted else None, 'resampled_raster': str(warped), 'aoi_mask': str(mask_path),
            **coverage, 'hole_filling_enabled': False, 'resampling': 'bilinear',
            'source_resolution_m': 5, 'target_resolution_m': 5, 'raster_reprojection': True,
            'vertical_datum': 'IGN69', 'vertical_harmonisation_applied': False,
            'vertical_datum_note': VERTICAL_NOTE}
