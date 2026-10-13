"""Luxembourg LiDAR 2024 MNT, processed from one persistent national COG."""
from ...geo import bounds
from ...target_grid import resolution
from .acquisition import download, probe, source_path
from .processing import prepare, selection, VERTICAL_NOTE


def validate_config(config):
    source = config['source']
    if (source.get('type') != 'local_cog' or source.get('epsg') != 2169
            or source.get('resolution') != .5):
        raise ValueError('Luxembourg requires the LiDAR 2024 MNT COG, EPSG:2169, native 0.5 m.')
    if not source.get('url') or not source.get('version'):
        raise ValueError('Luxembourg requires source.url and source.version provenance.')
    path = source.get('path', 'MNT_Lidar2024.tif')
    if not isinstance(path, str) or not path or '://' in path or path.startswith('/vsi'):
        raise ValueError('Luxembourg source.path must identify a local cached COG.')
    if config.get('region') or not config.get('country_mask'):
        raise ValueError('Luxembourg requires country_mask and no region.')
    if type(config.get('enabled', True)) is not bool:
        raise ValueError('enabled must be true or false.')
    if config.get('reuse_cache', True) is not True:
        raise ValueError('Luxembourg always reuses its national COG; missing sources download automatically.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('Luxembourg requires the common 5 m EPSG:25832 target.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool or fill.get('enabled'):
        raise ValueError('Hole filling is not supported for Luxembourg.')
    config['hole_filling'] = {'enabled': False}
    size = config.get('processed_tile_size_pixels', 1000)
    if type(size) is not int or size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')


def plan(geometry, config):
    result = {'product': 'Luxembourg LiDAR 2024 MNT', 'crs': 'EPSG:2169',
              'version': config['source']['version'], 'url': config['source']['url'],
              'local_source': str(source_path(config)), 'metadata_requests': 0,
              'resampling': 'average', 'vertical_datum_note': VERTICAL_NOTE}
    if not config.get('enabled', True):
        return {**result, 'skip_reason': 'Luxembourg handler is disabled.'}
    selected = selection(geometry, config)
    if selected.IsEmpty() or selected.GetArea() <= 0:
        return {**result, 'skip_reason': 'AOI does not intersect Luxembourg.'}
    return {**result, 'selection_extent_25832': bounds(selected),
            'acquisition_note': 'Reuse the complete local COG; download the national source if missing.'}
