"""Offline real-data check: prepare up to 200 x 200 m from a native NRW tile.

Usage: python scripts/nrw_pilot.py config.germany.nrw.json path/to/nrw_tile.tif
No downloads; results go to logs/preparation/germany/nrw/pilots/<Amsterdam run name>.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    import argparse
    import math

    import numpy as np
    from osgeo import gdal

    from dtm.acquire import sha256, write_json
    from dtm.coordinator import create_log_directory, load_config
    from dtm.paths import scoped_root
    from dtm.countries.germany.nrw.processing import prepare, validate_native
    from dtm.geo import grid, rectangle, srs, valid_values, verify_alignment
    from dtm.target_grid import plan_grid, write_reference

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if config['country'] != 'germany' or config['region'] != 'nrw':
        raise ValueError('The pilot requires a Germany/NRW configuration.')
    source = args.source.resolve()
    validate_native(source)
    checksum = sha256(source)
    info = grid(source)
    x0, y0, x1, y1 = info['extent']
    left, bottom = math.ceil(x0 / 5) * 5, math.ceil(y0 / 5) * 5
    right, top = min(math.floor(x1 / 5) * 5, left + 200), min(math.floor(y1 / 5) * 5, bottom + 200)
    if right <= left or top <= bottom:
        raise ValueError('Source contains no complete 5 m cell.')
    pilot_root = scoped_root(config, 'logs_dir') / 'pilots'
    directory = create_log_directory({**config, 'logs_dir': str(pilot_root),
                                     'country': '', 'region': None})
    geometry = rectangle([left, bottom, right, top])
    geometry.AssignSpatialReference(srs(25832))
    crop = directory / 'native_sample.tif'
    with gdal.Translate(str(crop), str(source), projWin=[left, top, right, bottom]):
        pass
    # The pilot has its own extent, even if production uses a larger reference.
    target = plan_grid(geometry, {'epsg': 25832, 'resolution': 5})
    reference = write_reference(target, directory / 'target_grid.vrt')
    write_json(directory / 'target_grid.json', target)
    result = prepare([crop], geometry, reference, directory / 'prepared', config)
    with gdal.Open(str(crop)) as native, gdal.Open(result['prepared_raster']) as final:
        expected = np.full((final.RasterYSize, final.RasterXSize), -9999, dtype='float32')
        # Independent cell-by-cell oracle, including source masks and NoData.
        for row in range(final.RasterYSize):
            for col in range(final.RasterXSize):
                values, valid = valid_values(native.GetRasterBand(1), (col * 5, row * 5, 5, 5))
                if valid.any():
                    expected[row, col] = values[valid].astype('float64').mean()
        actual = final.ReadAsArray()
        np.testing.assert_array_equal(actual, expected)
    verify_alignment(result['prepared_raster'], reference)
    if sha256(source) != checksum:
        raise RuntimeError('Original source changed during the pilot.')
    report = {'status': 'passed', 'source': str(source), 'source_sha256': checksum,
              'sample_extent': [left, bottom, right, top], 'target_cells': int(expected.size),
              'valid_cells': int((expected != -9999).sum()), 'maximum_absolute_error_m': 0.0,
              'original_source_unchanged': True, 'result': result}
    write_json(directory / 'pilot_report.json', report)
    print(f"Passed: {expected.size} target cells match independent 5x5 means exactly. Report: {directory / 'pilot_report.json'}")


if __name__ == '__main__':
    bootstrap(__file__, 'config.germany.nrw.json')
    main()
