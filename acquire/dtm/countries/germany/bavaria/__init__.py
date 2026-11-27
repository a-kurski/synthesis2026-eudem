"""Bavarian DGM5: catalogue-backed AOI acquisition at native 5 m resolution."""
import math

from ....geo import bounds, project, read_aoi, srs
from ....target_grid import resolution
from .acquisition import CATALOGUE_URL, download, probe
from .processing import prepare, VERTICAL_NOTE


def validate_config(config):
    source = config['source']
    if (source.get('type') != 'bavaria_dgm5' or source.get('epsg') != 25832
            or source.get('resolution') != 5):
        raise ValueError('Bavaria requires DGM5 XYZ ZIPs, 5 m EPSG:25832.')
    if config['target'].get('epsg', 25832) != 25832 or resolution(config['target']) != 5:
        raise ValueError('Bavaria requires the common 5 m EPSG:25832 target.')
    if not config.get('country_mask'):
        raise ValueError('Bavaria requires country_mask for regional AOI intersection.')
    fill = config.get('hole_filling', {})
    if not isinstance(fill, dict) or fill.get('enabled', False) is not False:
        raise ValueError('Hole filling is not supported for Bavaria.')
    config['hole_filling'] = {'enabled': False}
    for key in ('reuse_cache', 'catalogue_refresh'):
        if type(config.setdefault(key, key == 'reuse_cache')) is not bool:
            raise ValueError(f'{key} must be true or false.')
    age = config.setdefault('catalogue_max_age_days', 30)
    if age is not None and (type(age) not in (int, float) or not math.isfinite(age) or age < 0):
        raise ValueError('catalogue_max_age_days must be null or a nonnegative number.')
    size = config.setdefault('processed_tile_size_pixels', 1000)
    if type(size) is not int or size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')
    # Only an explicitly documented source marker may become NoData.
    marker = source.get('nodata')
    if marker is not None and (type(marker) not in (int, float) or not math.isfinite(marker)
                               or not source.get('nodata_evidence')):
        raise ValueError('A source nodata marker requires a finite value and nodata_evidence.')


def region_aoi(geometry, config):
    state, _, _ = read_aoi(config['country_mask'])
    native = project(geometry, srs(25832)).Intersection(project(state, srs(25832)))
    native.AssignSpatialReference(srs(25832))
    return native


def plan(geometry, config):
    native = region_aoi(geometry, config)
    result = {'product': 'Bavaria DGM5', 'crs': 'EPSG:25832', 'discovery_pending': True,
              'metadata_requests': 1, 'catalogue': CATALOGUE_URL,
              'vertical_datum_note': VERTICAL_NOTE, 'resampling_context_m': 0,
              'allow_shifted_target_origin': True,
              'resampling': 'copy aligned cells; otherwise one average alignment of the mosaic'}
    if native.IsEmpty() or native.GetArea() == 0:
        return {**result, 'skip_reason': 'AOI does not intersect Bavaria.'}
    return {**result, 'aoi_extent': bounds(native), 'selection_wkt': native.ExportToWkt()}
