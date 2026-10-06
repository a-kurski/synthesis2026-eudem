"""Hessen ATKIS-DGM1 acquisition and preparation on the common German grid."""
import math
import re
from urllib.parse import urlparse

from ....geo import bounds, project, srs
from ....target_grid import resolution
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE


def validate_config(config):
    source = config['source']
    if source.get('epsg') != 25832 or source.get('resolution') != 1 or source.get('type') != 'tar':
        raise ValueError('Hessen requires the native 1 m EPSG:25832 GeoTIFF tar archive.')
    url = urlparse(source.get('url', ''))
    if url.scheme != 'https' or not url.netloc or not re.fullmatch(r'[0-9a-f]{32}', source.get('md5', '')):
        raise ValueError('Hessen requires an HTTPS archive URL and published MD5 checksum.')
    if type(source.get('size')) is not int or source['size'] <= 0:
        raise ValueError('Hessen requires the published archive byte size.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('Hessen preparation requires the common 5 m EPSG:25832 target.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool or fill.get('enabled', False):
        raise ValueError('Hole filling is not supported for Hessen; use --no-fill-holes.')
    config['hole_filling'] = {'enabled': False}
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    size = config.setdefault('processed_tile_size_pixels', 1000)
    if type(size) is not int or size <= 0:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')


def plan(geometry, config):
    native = project(geometry, srs(25832))
    context_m = 5 / math.sqrt(2)
    context = native.Buffer(context_m)
    return {'crs': 'EPSG:25832', 'aoi_extent': bounds(native),
            'selection_wkt': context.ExportToWkt(), 'request_extent': bounds(context),
            'chunks': 1, 'uncompressed_bytes': config['source']['size'],
            'archive_bytes': config['source']['size'], 'metadata_requests': 0,
            'acquisition_note': 'Reuse complete extraction; otherwise download and extract the full archive once.',
            'resampling_context_m': context_m, 'catalogue_pending': True,
            'vertical_datum_note': VERTICAL_NOTE, 'processing': 'native_1m_to_5m_average',
            'raster_reprojection': False, 'separate_alignment': False, 'hole_filling': False}
