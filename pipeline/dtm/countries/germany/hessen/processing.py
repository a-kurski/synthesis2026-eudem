"""Validate Hessen's native grid, then reuse the shared German processor."""
import logging
from pathlib import Path
import re

from osgeo import gdal

from ....geo import grid, verify_alignment
from ..processing import prepare as prepare_native, validate_native as validate_grid

VERTICAL_NOTE = ('Hessen source heights are retained without vertical transformation. '
                 'Vertical datum is unverified; EPSG:25832 is horizontal only.')


def validate_native(path):
    info = grid(path)
    if info['crs']:
        validate_grid(path)
    else:
        # Some official TIFF/TFW deliveries omit the CRS. Only accept the
        # configured Hessen CRS when a complete 1 km tile matches its zone-32
        # filename exactly; never override an existing contradictory CRS.
        match = re.search(r'(?:^|_)dgm1_32_(\d{3})_(\d{4})_1_he\.{1,2}tiff?$',
                          Path(path).name, re.IGNORECASE)
        with gdal.Open(str(path)) as ds:
            bands = ds.RasterCount
        x, y = (int(v)*1000 for v in match.groups()) if match else (None, None)
        if (not match or bands != 1 or info['cols'] != 1000 or info['rows'] != 1000
                or info['transform'] != [x, 1, 0, y+1000, 0, -1]):
            raise ValueError(f'Hessen missing CRS requires a matching zone-32 filename and exact 1 km grid: {path}')
    # Official packages include fully populated tiles without a NoData tag.
    # Source missing-data conventions are handled by the shared cleaner using
    # the declared NoData, GDAL mask and non-finite/extreme-value checks. -9999
    # is our output convention, not a requirement on the source metadata.
    if info['dtype'] != 'Float32':
        raise ValueError(f'Hessen requires Float32 elevations; got {info["dtype"]}: {path}')
    return info


def prepare(tiles, geometry, reference, run_dir, config):
    sources, assigned = [], []
    for tile in tiles:
        info = validate_native(tile)
        source = tile
        if not info['crs']:
            if config['source']['epsg'] != 25832:
                raise ValueError('Missing Hessen CRS can only use configured EPSG:25832.')
            directory = run_dir/'processed'/'_work'/'source_crs'
            directory.mkdir(parents=True, exist_ok=True)
            # Retain the unique TIFF basename for the shared cleaner. This is
            # an explicitly created VRT descriptor, not a rewritten source TIFF.
            source = directory/Path(tile).name
            with gdal.Translate(str(source), str(Path(tile).resolve()),
                                format='VRT', outputSRS='EPSG:25832'):
                pass
            assigned.append(str(tile))
            logging.getLogger('dtm').info('Assigned configured EPSG:25832 in processing VRT after filename/grid check: %s', tile)
        sources.append(source)
    result = prepare_native(sources, geometry, reference, run_dir, config, product='hessen',
                            vertical_note=VERTICAL_NOTE, validate=validate_native)
    info = verify_alignment(result['prepared_raster'], reference, config['alignment_tolerance_m'])
    if info['dtype'] != 'Float32' or info['nodata'] != -9999:
        raise ValueError('Hessen publication must retain Float32 and NoData -9999.')
    result.update(vertical_datum=None, vertical_datum_verified=False, native_grid_offset_m=0,
                  source_crs_assigned_from_config=assigned,
                  producer=config['source']['producer'], distributor='Hessen Geodaten online (HVBG)',
                  license=config['source']['license'])
    return result
