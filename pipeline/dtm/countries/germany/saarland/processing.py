"""Align Saarland's half-metre native edges directly to the shared 5 m grid."""
import math

from osgeo import gdal

from ....geo import grid, srs
from ....process import align
from ..processing import prepare as prepare_native

VERTICAL_NOTE = ('Saarland source heights are retained without vertical transformation. '
                 'Vertical datum is unverified; EPSG:25832 is horizontal only.')


def validate_native(path):
    info = grid(path)
    with gdal.Open(str(path)) as ds:
        if ds.RasterCount != 1 or not ds.GetSpatialRef() or not ds.GetSpatialRef().IsSame(srs(25832)):
            raise ValueError('Saarland requires single-band EPSG:25832 terrain.')
    gt = info['transform']
    if (info['dtype'] != 'Float32' or info['nodata'] is None or not math.isfinite(info['nodata'])
            or not math.isclose(gt[1], 1, abs_tol=1e-8, rel_tol=0)
            or not math.isclose(gt[5], -1, abs_tol=1e-8, rel_tol=0)
            or any(not math.isclose(gt[i] % 1, .5, abs_tol=1e-8, rel_tol=0) for i in (0, 3))):
        raise ValueError('Saarland requires Float32 1 m pixels, half-metre edges and declared NoData.')
    return info


def resample(native, reference, destination, config, *, product, vertical_note):
    # Cleaning has read the actual source sentinel/mask and normalised to -9999.
    align(native, reference, destination, config, source_epsg=25832, label='Saarland')
    with gdal.Open(str(destination), gdal.GA_Update) as ds:
        ds.SetMetadataItem('VERTICAL_DATUM_NOTE', vertical_note)
        ds.SetMetadataItem('RESAMPLING', 'Area-weighted average directly from native 1 m to common 5 m grid')


def prepare(tiles, geometry, reference, run_dir, config):
    result = prepare_native(tiles, geometry, reference, run_dir, config, product='saarland',
                            vertical_note=VERTICAL_NOTE, validate=validate_native, resample=resample)
    result.update(vertical_datum=None, vertical_datum_verified=False, separate_alignment=True,
                  native_grid_offset_m=.5, producer=config['source']['producer'],
                  distributor='Mapterhorn', license=config['source']['license'])
    return result
