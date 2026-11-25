"""Shared swissALTI3D provider for Switzerland and Liechtenstein."""
import json
import math

from ...geo import bounds, project, srs
from ...target_grid import resolution
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE

ITEMS_URL = 'https://data.geo.admin.ch/api/stac/v1/collections/ch.swisstopo.swissalti3d/items'


def validate_config(config):
    source = config['source']
    if source.get('type') != 'stac' or source.get('epsg') != 2056 or source.get('resolution') != 2:
        raise ValueError('swissALTI3D requires STAC, EPSG:2056 and native 2 m terrain.')
    if not source.get('url') or source.get('vertical_datum') != 'LN02':
        raise ValueError('swissALTI3D requires an items URL and LN02 source height reference.')
    if config.get('region'):
        raise ValueError('swissALTI3D uses a shared national provider; omit region.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('swissALTI3D preparation requires a 5 m EPSG:25832 target.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool or fill.get('enabled'):
        raise ValueError('Hole filling is not supported for swissALTI3D.')
    config['hole_filling'] = {'enabled': False}
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    size = config.get('processed_tile_size_pixels', 1000)
    if type(size) is not int or size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')
    config['processed_tile_size_pixels'] = size
    limit = source.get('page_limit', 100)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('source.page_limit must be an integer from 1 to 100.')


def plan(geometry, config):
    # Same half-cell-diagonal halo as the other 5 m average processors.
    context_m = 5 / math.sqrt(2)
    context = project(geometry, srs(25832)).Buffer(context_m)
    context.AssignSpatialReference(srs(25832))
    query = project(context, srs(4326))
    return {'crs': 'EPSG:2056', 'query_geometry': json.loads(query.ExportToJson()),
            'query_bounds_wgs84': bounds(query), 'items_url': config['source']['url'],
            'discovery_pending': True, 'metadata_requests': 0,
            'resampling_context_m': context_m, 'vertical_datum_note': VERTICAL_NOTE,
            'raster_reprojection': True, 'resampling': 'average', 'attribution': '©swisstopo',
            'source_manifest': config.get('source_manifest')}
