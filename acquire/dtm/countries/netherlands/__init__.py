"""Netherlands adapter: native AHN acquisition and preparation on the target grid."""
import math

from ...geo import plan_source, project, srs
from ...target_grid import resolution
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
    # A cell whose centre is inside the AOI may extend outside it. Acquire
    # its full footprint, then add target-grid interpolation context. Neither
    # buffer changes the output grid, fill candidate polygon or final mask.
    resampling_buffer = resolution(config.get('target', {})) / math.sqrt(2)
    # A donor centre may lie up to the search radius beyond a candidate centre.
    # Include the candidate-centre offset and the donor's full pixel footprint.
    fill_context = fill['max_distance_m'] + resampling_buffer if fill['enabled'] else 0
    target_context = project(geometry, srs(25832)).Buffer(resampling_buffer + fill_context)
    target_context.AssignSpatialReference(srs(25832))
    buffer_m = config['source']['resolution']
    native = project(target_context, srs(28992))
    context = native.Buffer(buffer_m)
    context.AssignSpatialReference(srs(28992))
    result = plan_source(context, config['source'])
    result['context_buffer_m'] = buffer_m
    result['resampling_context_m'] = resampling_buffer
    result['fill_context_m'] = fill_context
    return result
