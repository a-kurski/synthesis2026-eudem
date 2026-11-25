"""IGN RGE ALTI 5 m, with reusable department caches and one horizontal warp."""
from ...geo import bounds, project, srs
from ...target_grid import resolution
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE

DEPARTMENTS = ['25', '54', '55', '57', '67', '68', '70', '88', '90']


def validate_config(config):
    source = config['source']
    if (source.get('type') != 'ign_rge_alti' or source.get('epsg') != 2154
            or source.get('resolution') != 5 or source.get('vertical_datum') != 'IGN69'):
        raise ValueError('France requires IGN RGE ALTI 5 m ASCII grids in EPSG:2154 / IGN69.')
    if config.get('region'):
        raise ValueError('France uses source.departments; omit region.')
    departments = source.setdefault('departments', DEPARTMENTS.copy())
    if (not isinstance(departments, list) or not departments
            or any(not isinstance(d, str) or len(d) != 2 or not d.isascii()
                   or not d.isdigit() or not 1 <= int(d) <= 95 or d == '20' for d in departments)
            or len(set(departments)) != len(departments)):
        raise ValueError('source.departments must contain unique mainland department strings, e.g. ["25", "90"].')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('France requires the common 5 m EPSG:25832 target.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool or fill.get('enabled', False):
        raise ValueError('Hole filling is not supported for France.')
    config['hole_filling'] = {'enabled': False}
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    if type(config.get('processed_tile_size_pixels', 1000)) is not int or config.get('processed_tile_size_pixels', 1000) < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')


def plan(geometry, config):
    native = project(geometry, srs(2154))
    return {'product': 'IGN RGE ALTI 5 m', 'crs': 'EPSG:2154',
            'aoi_extent': bounds(native), 'selection_wkt': native.ExportToWkt(),
            'departments': config['source']['departments'], 'metadata_requests': 0,
            'discovery_pending': True, 'resampling_context_m': 0,
            'vertical_datum_note': VERTICAL_NOTE, 'resampling': 'bilinear',
            'acquisition_note': 'Local ASC tiles first; missing coverage uses cached or downloaded department archives.'}
