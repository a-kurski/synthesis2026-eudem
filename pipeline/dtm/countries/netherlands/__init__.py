"""Netherlands adapter: native AHN acquisition and preparation on the target grid."""
import math

from ...geo import plan_source, project, srs
from .hole_filling import settings
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE


def validate_config(config):
    config['hole_filling'] = settings(config)
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    size = config.get('processed_tile_size_pixels', 1000)
    if type(size) is not int or size <= 0:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')
    config['processed_tile_size_pixels'] = size
    source = config['source']
    if source['epsg'] != 28992 or source['resolution'] != 0.5:
        raise ValueError('Netherlands requires native AHN EPSG:28992 at 0.5 m.')
    if source.get('vertical_datum') != 'NAP':
        raise ValueError('AHN remains in NAP; vertical_datum must be NAP.')
    if not source.get('url') or not source.get('coverage'):
        raise ValueError('AHN source url and coverage are required.')
    size = source['chunk_size_m']
    if not math.isfinite(size) or size <= 0 or not math.isclose(size / 0.5, round(size / 0.5)):
        raise ValueError('AHN chunk_size_m must be a positive multiple of 0.5 m.')


def plan(geometry, config):
    fill = settings(config)
    if not fill['enabled']:
        return plan_source(geometry, config['source'])
    # Fetch context for donors but retain the original polygon for the target
    # grid and final AOI. Raw chunk signatures remain unchanged.
    buffer_m = fill['max_distance_m'] + config['source']['resolution']
    native = project(geometry, srs(28992))
    context = native.Buffer(buffer_m)
    context.AssignSpatialReference(srs(28992))
    result = plan_source(context, config['source'])
    result['context_buffer_m'] = buffer_m
    return result
