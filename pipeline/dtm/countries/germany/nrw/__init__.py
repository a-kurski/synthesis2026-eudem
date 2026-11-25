"""NRW DGM1: native UTM32 acquisition and direct 5 m aggregation."""
import math

from ....geo import plan_source, project, srs
from ....target_grid import resolution
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE


def validate_config(config):
    source = config['source']
    if source['epsg'] != 25832 or source['resolution'] != 1:
        raise ValueError('NRW requires native EPSG:25832 terrain at 1 m.')
    if source.get('vertical_datum') != 'DHHN2016/NHN':
        raise ValueError('NRW vertical_datum must be DHHN2016/NHN.')
    if not source.get('url') or not source.get('coverage'):
        raise ValueError('NRW source url and coverage are required.')
    size = source.get('chunk_size_m')
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0 or size % 5:
        raise ValueError('NRW chunk_size_m must be a positive multiple of 5 m.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('NRW preparation requires a 5 m EPSG:25832 target.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or type(fill.get('enabled', False)) is not bool:
        raise ValueError('hole_filling.enabled must be true or false.')
    if fill.get('enabled', False):
        raise ValueError('Hole filling is not supported for NRW; use --no-fill-holes.')
    config['hole_filling'] = {'enabled': False}
    if type(config.get('reuse_cache', True)) is not bool:
        raise ValueError('reuse_cache must be true or false.')
    size = config.get('processed_tile_size_pixels', 1000)
    if type(size) is not int or size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')
    config['processed_tile_size_pixels'] = size


def plan(geometry, config):
    # Only the AOI geometry may need projection. The DTM itself stays in UTM32.
    # Include the footprint of every 5 m cell whose centre lies inside the AOI.
    context_m = 5 / math.sqrt(2)
    native = project(geometry, srs(25832))
    context = native.Buffer(context_m)
    context.AssignSpatialReference(srs(25832))
    result = plan_source(context, config['source'])
    result.update(resampling_context_m=context_m, context_buffer_m=0,
                  vertical_datum_note=VERTICAL_NOTE,
                  processing='native_1m_to_5m_average', hole_filling=False,
                  raster_reprojection=False, separate_alignment=False)
    return result
