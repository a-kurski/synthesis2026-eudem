"""One horizontal warp from native LV95 tiles to the common 5 m grid."""
import logging
import math

import numpy as np
from osgeo import gdal

from ...acquire import write_json
from ...geo import grid, srs, verify_alignment, windows
from ...paths import raw_directory
from ...process import aoi_mask, co_args
from ...publication import mask_output, publish_tiles

LOG = logging.getLogger('dtm')
VERTICAL_NOTE = 'swissALTI3D heights remain LN02 (EPSG:5728). Horizontal LV95 to ETRS89/UTM32 transformation only; automatic vertical shifting disabled.'


def validate_native(path, spatial_id=None):
    info = grid(path)
    with gdal.Open(str(path)) as ds:
        crs = ds.GetSpatialRef()
        if crs:
            crs = crs.Clone()
            crs.StripVertical()
        if ds.RasterCount != 1 or not crs or not crs.IsSame(srs(2056)):
            raise ValueError(f'swissALTI3D requires single-band EPSG:2056 input: {path}')
        if ds.GetRasterBand(1).DataType not in (gdal.GDT_Float32, gdal.GDT_Float64):
            raise ValueError(f'swissALTI3D requires floating-point elevations: {path}')
    gt = info['transform']
    if not np.allclose([gt[1], gt[5]], [2, -2], rtol=0, atol=1e-8):
        raise ValueError(f'swissALTI3D requires exact 2 m source spacing: {path}')
    if any(not math.isclose(gt[i] / 2, round(gt[i] / 2), rel_tol=0, abs_tol=1e-8) for i in (0, 3)):
        raise ValueError(f'swissALTI3D source origin is off the 2 m lattice: {path}')
    if spatial_id:
        x, y = (int(part) * 1000 for part in spatial_id.split('-'))
        if not np.allclose(info['extent'], [x, y, x + 1000, y + 1000], rtol=0, atol=1e-7):
            raise ValueError(f'Source footprint differs from spatial tile {spatial_id}: {path}')
    # Actual NoData metadata is retained in the VRT, not replaced with a guess.
    return info


def prepare(tiles, geometry, reference, run_dir, config):
    processed, stitched = run_dir / 'processed', run_dir / 'stitched'
    work = processed / '_work'
    work.mkdir(parents=True, exist_ok=True)
    stitched.mkdir(parents=True, exist_ok=True)
    if not tiles:
        raise ValueError('No swissALTI3D source tiles.')
    occupied = set()
    for path in tiles:
        info = validate_native(path)
        extent = tuple(info['extent'])
        # All downloaded spatial tiles are 1 km squares on the validated lattice.
        if extent in occupied:
            raise ValueError('Overlapping swissALTI3D editions/duplicate source footprints.')
        occupied.add(extent)
    target = grid(reference)
    with gdal.Open(str(reference)) as ref:
        if not ref.GetSpatialRef().IsSame(srs(25832)) or target['transform'][1] != 5 or target['transform'][5] != -5:
            raise ValueError('swissALTI3D target must be the common 5 m EPSG:25832 grid.')
    vrt = work / 'swissalti3d.vrt'
    with gdal.BuildVRT(str(vrt), [str(path) for path in tiles], options=gdal.BuildVRTOptions(
            resolution='highest', strict=True, VRTNodata=config['nodata'])):
        pass
    warped = work / 'swissalti3d_5m.tif'
    options = ['-overwrite', '-s_srs', 'EPSG:2056', '-t_srs', 'EPSG:25832', '-novshift',
               '-ovr', 'NONE', '-et', '0', '-te', *map(str, target['extent']), '-tr', '5', '5',
               '-r', 'average', '-dstnodata', str(config['nodata']), '-ot', 'Float32',
               '-of', 'GTiff', '-wm', '256', *co_args()]
    LOG.info('swissALTI3D warp options: %s', options)
    with gdal.Warp(str(warped), str(vrt), options=gdal.WarpOptions(options=options)):
        pass
    verify_alignment(warped, reference, config['alignment_tolerance_m'])
    mask_path = work / 'aoi_mask.tif'
    with gdal.Open(str(reference)) as ref, aoi_mask(geometry, ref, mask_path) as mask:
        aoi_cells = sum(int(np.count_nonzero(mask.ReadAsArray(*w))) for w in windows(ref, config['block_size']))
    prepared = work / 'swissalti3d_prepared.tif'
    count = mask_output(warped, mask_path, prepared, config, VERTICAL_NOTE)['valid_cell_count']
    coverage = {'aoi_cell_count': aoi_cells, 'valid_cell_count': count,
                'missing_cell_count': aoi_cells - count}
    write_json(processed / 'coverage.json', coverage)
    if coverage['missing_cell_count']:
        LOG.warning('swissALTI3D missing coverage: %d AOI cells remain NoData.', coverage['missing_cell_count'])
    if not count:
        raise RuntimeError('No valid swissALTI3D coverage inside the AOI; see coverage.json.')
    # Metadata is attached to a virtual source before publication, never to a COG.
    with gdal.Translate('', str(prepared), format='VRT') as view:
        view.SetMetadataItem('ATTRIBUTION', '©swisstopo')
        view.SetMetadataItem('SOURCE_VERTICAL_CRS', 'LN02 (EPSG:5728)')
        metadata_source = work / 'publication.vrt'
        with gdal.Translate(str(metadata_source), view, format='VRT'):
            pass
    published = publish_tiles(metadata_source, processed, stitched / 'swissalti3d.tif', config, product='swissalti3d')
    verify_alignment(published['stitched'], reference, config['alignment_tolerance_m'])
    return {'prepared_raster': published['stitched'], 'comparison_ready_raster': published['stitched'],
            'processed_tiles': published, 'raw_swissalti3d_tiles': str(raw_directory(config)),
            'native_mosaic': str(vrt), 'resampled_raster': str(warped), 'aoi_mask': str(mask_path),
            'grid': grid(published['stitched']), **coverage, 'hole_filling_enabled': False,
            'raster_reprojection': True, 'separate_alignment': False, 'resampling': 'average',
            'source_resolution_m': 2, 'target_resolution_m': 5, 'vertical_datum': 'LN02',
            'vertical_datum_note': VERTICAL_NOTE, 'attribution': '©swisstopo'}
