"""Hessen ATKIS-DGM1 acquisition and preparation on the common German grid."""
import math
import re
from datetime import datetime
from urllib.parse import urlparse

from osgeo import ogr

from ....geo import bounds, project, srs
from ....target_grid import resolution
from .acquisition import download, probe
from .processing import prepare, VERTICAL_NOTE
from .regions import HESSEN_DGM1_REGIONS


def validate_config(config):
    source = config['source']
    if source.get('epsg') != 25832 or source.get('resolution') != 1 or source.get('type') != 'regional_zip':
        raise ValueError('Hessen requires official regional ZIPs with native 1 m EPSG:25832 TIFFs.')
    url = urlparse(source.get('base_url', ''))
    if url.scheme != 'https' or url.netloc != 'gds.hessen.de' or url.path.rstrip('/') != '/downloadcenter':
        raise ValueError('Hessen base_url must be https://gds.hessen.de/downloadcenter.')
    date = source.get('download_date', '')
    if not isinstance(date, str) or not re.fullmatch(r'\d{8}', date):
        raise ValueError('Hessen download_date must be a Downloadcenter YYYYMMDD date.')
    try:
        datetime.strptime(date, '%Y%m%d')
    except ValueError as exc:
        raise ValueError('Hessen download_date is not a valid calendar date.') from exc
    if not source.get('boundary_file'):
        raise ValueError('Hessen requires a local KREIS_LA boundary_file.')
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
    context.AssignSpatialReference(srs(25832))
    source = config['source']
    regions = {}
    with ogr.Open(source['boundary_file']) as ds:
        if ds is None:
            raise ValueError(f'Cannot open Hessen district boundaries: {source["boundary_file"]}')
        layer = ds.GetLayerByName(source['boundary_layer']) if source.get('boundary_layer') else ds.GetLayer(0)
        if layer is None or layer.GetSpatialRef() is None or layer.GetLayerDefn().GetFieldIndex('KREIS_NR') < 0:
            raise ValueError('Hessen boundary layer needs a CRS and KREIS_NR field.')
        selection = project(context, layer.GetSpatialRef())
        for feature in layer:
            district = feature.GetGeometryRef()
            if district is None or district.IsEmpty() or not district.IsValid():
                raise ValueError('Invalid Hessen district boundary geometry.')
            if district.Intersection(selection).GetArea() <= 0:
                continue
            code = str(feature.GetField('KREIS_NR')).strip()
            if code not in HESSEN_DGM1_REGIONS:
                raise ValueError(f'No verified Hessen Downloadcenter mapping for KREIS_NR={code}.')
            regions[code] = {'id': code, 'name': HESSEN_DGM1_REGIONS[code]}
    if not regions:
        raise ValueError('AOI does not intersect any Hessen districts.')
    return {'crs': 'EPSG:25832', 'aoi_extent': bounds(native),
            'selection_wkt': context.ExportToWkt(), 'request_extent': bounds(context),
            'chunks': len(regions), 'metadata_requests': 0, 'discovery_pending': True,
            'product': f'Hessen official DGM1: {len(regions)} complete district ZIP packages',
            'regions': sorted(regions.values(), key=lambda r: r['id']),
            'download_date': source['download_date'], 'boundary_file': source['boundary_file'],
            'resampling_context_m': context_m,
            'vertical_datum_note': VERTICAL_NOTE, 'processing': 'native_1m_to_5m_average',
            'raster_reprojection': False, 'separate_alignment': False, 'hole_filling': False}
