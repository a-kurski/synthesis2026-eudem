"""Validate Hessen's native grid, then reuse the shared German processor."""
from ....geo import grid, verify_alignment
from ..processing import prepare as prepare_native, validate_native as validate_grid

VERTICAL_NOTE = ('Hessen source heights are retained without vertical transformation. '
                 'Vertical datum is unverified; EPSG:25832 is horizontal only.')


def validate_native(path):
    validate_grid(path)
    info = grid(path)
    if info['dtype'] != 'Float32' or info['nodata'] != -9999:
        raise ValueError(f'Hessen requires Float32 and NoData -9999: {path}')
    return info


def prepare(tiles, geometry, reference, run_dir, config):
    result = prepare_native(tiles, geometry, reference, run_dir, config, product='hessen',
                            vertical_note=VERTICAL_NOTE, validate=validate_native)
    info = verify_alignment(result['prepared_raster'], reference, config['alignment_tolerance_m'])
    if info['dtype'] != 'Float32' or info['nodata'] != -9999:
        raise ValueError('Hessen publication must retain Float32 and NoData -9999.')
    result.update(vertical_datum=None, vertical_datum_verified=False, native_grid_offset_m=0,
                  producer=config['source']['producer'], distributor='Mapterhorn',
                  license=config['source']['license'])
    return result
