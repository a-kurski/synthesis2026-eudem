"""One full-resolution horizontal warp onto the pipeline's exact target grid."""
import logging
from pathlib import Path

import numpy as np
from osgeo import gdal, osr

from ...acquire import write_json
from ...geo import grid, project, read_aoi, srs, verify_alignment
from ...process import aoi_mask, co_args
from ...progress import blocks, gdal_progress
from ...publication import mask_output, publish_tiles

LOG = logging.getLogger('dtm')
SOURCE_BYTES = 40131787860
SOURCE_SHAPE = (114617, 163687)
SOURCE_TRANSFORM = (48880.5, .5, 0, 138809, 0, -.5)
VERTICAL_NOTE = ('Luxembourg LiDAR 2024 MNT vertical reference requires authoritative confirmation. '
                 'Source heights preserved; horizontal EPSG:2169 to EPSG:25832 transformation only. '
                 'No vertical datum harmonisation; automatic vertical shifting disabled.')


def selection(geometry, config):
    country, _, _ = read_aoi(config['country_mask'])
    target = srs(25832)
    selected = project(geometry, target).Intersection(project(country, target))
    selected.AssignSpatialReference(target)
    return selected


def validate_native(path):
    try:
        if Path(path).stat().st_size != SOURCE_BYTES:
            raise ValueError(f'Expected complete original file of {SOURCE_BYTES} bytes')
        with gdal.Open(str(path)) as ds:
            crs = ds.GetSpatialRef()
            if ds.RasterCount != 1:
                raise ValueError(f'Expected one band; found {ds.RasterCount}')
            # The official GeoTIFF declares east/north axes, whereas EPSG:2169
            # declares north/east. WKT1_ESRI omits axis declarations while
            # retaining datum, projection, units and parameters for comparison.
            if (not crs or not crs.IsProjected() or crs.IsCompound()
                    or not osr.SpatialReference(wkt=crs.ExportToWkt(['FORMAT=WKT1_ESRI'])).IsSame(
                        osr.SpatialReference(wkt=srs(2169).ExportToWkt(['FORMAT=WKT1_ESRI'])))):
                raise ValueError(f'Expected EPSG:2169 projection and datum; found {ds.GetProjection()}')
            band = ds.GetRasterBand(1)
            if (ds.RasterXSize, ds.RasterYSize) != SOURCE_SHAPE:
                raise ValueError(f'Expected national dimensions {SOURCE_SHAPE}')
            if not np.allclose(ds.GetGeoTransform(), SOURCE_TRANSFORM, rtol=0, atol=1e-8):
                raise ValueError('Unexpected national origin or 0.5 m pixel grid')
            if band.DataType != gdal.GDT_Float64 or band.GetNoDataValue() != -9999:
                raise ValueError('Expected Float64 elevations and NoData=-9999')
            if ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE') != 'COG':
                raise ValueError('Expected original COG layout')
        return grid(path)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f'Invalid or incomplete Luxembourg national COG: {path}: {exc}. '
                         'Source preserved; inspect its metadata before replacing or downloading it again.') from exc


def prepare(tiles, geometry, reference, run_dir, config):
    if len(tiles) != 1:
        raise ValueError('Luxembourg requires exactly one cached national COG.')
    validate_native(tiles[0])
    target = grid(reference)
    with gdal.Open(str(reference)) as ref:
        if not ref.GetSpatialRef().IsSame(srs(25832)) or target['transform'][1] != 5 or target['transform'][5] != -5:
            raise ValueError('Luxembourg target must be the common 5 m EPSG:25832 grid.')
    selected = selection(geometry, config)
    if selected.IsEmpty() or selected.GetArea() <= 0:
        raise ValueError('AOI does not intersect Luxembourg.')
    processed, stitched = run_dir / 'processed', run_dir / 'stitched'
    work = processed / '_work'
    work.mkdir(parents=True, exist_ok=True)
    warped = work / 'mnt_lidar2024_5m.tif'
    # GDAL bounds local reads per warp chunk, including the averaging footprint.
    # Keep the national source uncut: SAMPLE_GRID and SOURCE_EXTRA add conservative
    # source-window sampling and a 20-source-pixel (10 m) read margin at borders.
    options = ['-overwrite', '-s_srs', 'EPSG:2169', '-t_srs', 'EPSG:25832', '-novshift',
               '-ovr', 'NONE', '-et', '0', '-te', *map(str, target['extent']),
               '-ts', str(target['cols']), str(target['rows']), '-r', 'average',
               '-srcnodata', '-9999', '-dstnodata', str(config['nodata']), '-ot', 'Float32',
               '-wo', 'SAMPLE_GRID=YES', '-wo', 'SOURCE_EXTRA=20',
               '-of', 'GTiff', '-wm', '256', *co_args()]
    LOG.info('Luxembourg warp options: %s', options)
    with gdal_progress('Luxembourg reprojection / 5 m averaging') as callback:
        with gdal.Warp(str(warped), str(tiles[0]), options=gdal.WarpOptions(options=options, callback=callback)):
            pass
    verify_alignment(warped, reference, config['alignment_tolerance_m'])
    LOG.info('Luxembourg warp complete; creating AOI/country mask.')
    mask_path = work / 'aoi_mask.tif'
    with gdal.Open(str(reference)) as ref, aoi_mask(selected, ref, mask_path) as mask:
        aoi_cells = sum(int(np.count_nonzero(mask.ReadAsArray(*w)))
                        for w in blocks(ref, config['block_size'], 'Luxembourg AOI cell count'))
    prepared = work / 'mnt_lidar2024_prepared.tif'
    count = mask_output(warped, mask_path, prepared, config, VERTICAL_NOTE)['valid_cell_count']
    coverage = {'aoi_cell_count': aoi_cells, 'valid_cell_count': count, 'missing_cell_count': aoi_cells - count}
    write_json(processed / 'coverage.json', coverage)
    if coverage['missing_cell_count']:
        LOG.warning('Luxembourg missing coverage: %d AOI/country cells remain NoData.', coverage['missing_cell_count'])
    if not count:
        raise RuntimeError('No valid Luxembourg coverage inside the AOI/country mask; see coverage.json.')
    metadata_source = work / 'publication.vrt'
    with gdal.Translate(str(metadata_source), str(prepared), format='VRT') as view:
        view.SetMetadata({'SOURCE_PRODUCT': 'Luxembourg LiDAR 2024 MNT',
                          'SOURCE_VERSION': config['source']['version'], 'SOURCE_URL': config['source']['url'],
                          'SOURCE_CRS': 'EPSG:2169', 'TARGET_CRS': 'EPSG:25832',
                          'RESAMPLING': 'average', 'SOURCE_OVERVIEWS': 'NONE',
                          'TRANSFORMATION': 'horizontal_only', 'VERTICAL_HARMONISATION': 'none',
                          'VERTICAL_DATUM_NOTE': VERTICAL_NOTE})
    published = publish_tiles(metadata_source, processed, stitched / 'mnt_lidar2024.tif', config, product='mnt_lidar2024')
    final = verify_alignment(published['stitched'], reference, config['alignment_tolerance_m'])
    if final['dtype'] != 'Float32' or final['nodata'] != config['nodata']:
        raise ValueError('Luxembourg output data type or NoData differs from the target conventions.')
    return {'prepared_raster': published['stitched'], 'comparison_ready_raster': published['stitched'],
            'processed_tiles': published, 'cached_source': str(tiles[0]),
            'resampled_raster': str(warped), 'aoi_mask': str(mask_path), 'grid': final,
            **coverage, 'hole_filling_enabled': False, 'raster_reprojection': True,
            'separate_alignment': False, 'resampling': 'average',
            'source_resolution_m': .5, 'target_resolution_m': 5,
            'vertical_datum': 'unconfirmed', 'vertical_datum_note': VERTICAL_NOTE}
