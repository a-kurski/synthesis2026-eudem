"""LGL Baden-Württemberg DGM1 on the shared German target grid."""
import math

from ....geo import bounds, project, read_aoi, srs
from ....target_grid import resolution
from .acquisition import download, prefetch, probe
from .processing import prepare, VERTICAL_NOTE


def validate_config(config):
    source = config['source']
    if (source.get('type') != 'lgl_dgm1' or source.get('epsg') != 25832
            or source.get('resolution') != 1):
        raise ValueError('Baden-Württemberg requires LGL DGM1 XYZ ZIPs, 1 m EPSG:25832.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('Baden-Württemberg requires the common 5 m EPSG:25832 grid.')
    if not config.get('country_mask'):
        raise ValueError('Baden-Württemberg requires country_mask for regional AOI intersection.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool or fill.get('enabled', False):
        raise ValueError('Hole filling is not supported for Baden-Württemberg.')
    config['hole_filling'] = {'enabled': False}
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    size = config.setdefault('processed_tile_size_pixels', 1000)
    if type(size) is not int or size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')


def region_aoi(geometry, config):
    state, _, _ = read_aoi(config['country_mask'])
    clipped = project(geometry, srs(25832)).Intersection(project(state, srs(25832)))
    clipped.AssignSpatialReference(srs(25832))
    return clipped


def plan(geometry, config):
    native = region_aoi(geometry, config)
    result = {'product': 'LGL Baden-Württemberg DGM1', 'crs': 'EPSG:25832',
              'discovery_pending': True, 'metadata_requests': 0,
              'vertical_datum_note': VERTICAL_NOTE, 'resampling': 'average',
              'resampling_context_m': 5 / math.sqrt(2)}
    if native.IsEmpty() or native.GetArea() == 0:
        return {**result, 'skip_reason': 'AOI does not intersect Baden-Württemberg.'}
    context = native.Buffer(result['resampling_context_m'])
    return {**result, 'aoi_extent': bounds(native), 'selection_wkt': context.ExportToWkt(),
            'request_extent': bounds(context)}
