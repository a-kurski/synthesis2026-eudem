"""Rheinland-Pfalz DGM1 from the official GeoTIFF Metalink catalogue."""
from urllib.parse import urlparse

from ....target_grid import resolution
from ..nrw import plan as native_plan
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE


def validate_config(config):
    source = config['source']
    if (source.get('type') != 'metalink' or source.get('epsg') != 25832
            or source.get('vertical_epsg') != 7837 or source.get('resolution') != 1
            or source.get('chunk_size_m') != 1000 or source.get('vertical_datum') != 'DHHN2016/NHN'):
        raise ValueError('RLP requires Metalink DGM1, EPSG:25832 + EPSG:7837, 1 m pixels and 1 km tiles.')
    url = urlparse(source.get('metalink_url', ''))
    if url.scheme != 'https' or not url.netloc:
        raise ValueError('RLP source.metalink_url must be an HTTPS URL.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('RLP preparation requires a 5 m EPSG:25832 target.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool:
        raise ValueError('hole_filling.enabled must be true or false.')
    if fill.get('enabled', False):
        raise ValueError('Hole filling is not supported for RLP; use --no-fill-holes.')
    config['hole_filling'] = {'enabled': False}
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    size = config.setdefault('processed_tile_size_pixels', 1000)
    if type(size) is not int or size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')


def plan(geometry, config):
    result = native_plan(geometry, config)
    result.update(vertical_datum_note=VERTICAL_NOTE, metadata_requests=1,
                  catalogue_pending=True, metalink_url=config['source']['metalink_url'],
                  tile_count_note='Offline candidate count; acquisition selects available catalogue tiles.')
    return result
