"""Check a 200 m AOI across two official BW archives, then prove offline reuse.

Usage: python scripts/bw_pilot.py config.germany.bw.json
Downloads at most two ZIPs into the normal durable cache. No statewide prefetch.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    import argparse
    from unittest.mock import patch

    import numpy as np
    from osgeo import gdal

    from dtm.acquire import sha256, write_json
    from dtm.coordinator import create_log_directory, load_config
    from dtm.countries.germany import bw
    from dtm.geo import rectangle, srs, verify_alignment
    from dtm.paths import receipt_path, region_lock, scoped_root
    from dtm.target_grid import plan_grid, write_reference

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if config['country'] != 'germany' or config['region'] != 'bw':
        raise ValueError('This pilot requires the Germany/BW config.')
    root = scoped_root(config, 'logs_dir') / 'pilots'
    directory = create_log_directory({**config, 'logs_dir': str(root), 'country': '', 'region': None})
    geometry = rectangle([558900, 5434900, 559100, 5435100])
    geometry.AssignSpatialReference(srs(25832))
    plan = bw.plan(geometry, config)
    write_json(directory / 'plan.json', plan)
    with region_lock(config):
        tiles = bw.download(config, plan, directory)
        import json
        receipts = [json.loads(receipt_path(p, config).read_text(encoding='utf-8')) for p in tiles]
        archives = {r['archive']: sha256(r['archive']) for r in receipts}
        repeat = directory / 'offline_repeat'
        repeat.mkdir()
        with patch('requests.Session.get', side_effect=AssertionError('Cached AOI made an HTTP request')), \
                patch('dtm.countries.germany.bw.acquisition.convert_xyz',
                      side_effect=AssertionError('Cached AOI repeated XYZ conversion')):
            repeated = bw.download(config, plan, repeat)
        if [sha256(p) for p in repeated] != [sha256(p) for p in tiles]:
            raise AssertionError('Cached source conversions differ.')
        reference = write_reference(plan_grid(geometry, config['target']), directory / 'target_grid.vrt')
        result = bw.prepare(tiles, geometry, reference, directory / 'prepared', config)
    # Independent, per-cell native mean across the archive seam.
    with gdal.BuildVRT(str(directory / 'oracle.vrt'), [str(p) for p in tiles]) as native:
        gt = native.GetGeoTransform()
        x, y = round((558900 - gt[0]) / gt[1]), round((5435100 - gt[3]) / gt[5])
        values = native.ReadAsArray(x, y, 200, 200)
        expected = np.array([[values[r:r+5, c:c+5].astype('float64').mean()
                              for c in range(0, 200, 5)] for r in range(0, 200, 5)], dtype='float32')
    with gdal.Open(result['prepared_raster']) as final:
        np.testing.assert_array_equal(final.ReadAsArray(), expected)
        if final.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE') != 'COG':
            raise AssertionError('Final raster is not a COG.')
    verify_alignment(result['prepared_raster'], reference)
    if any(sha256(p) != digest for p, digest in archives.items()):
        raise AssertionError('Source archives changed during processing.')
    report = {'status': 'passed', 'archive_count': len(archives), 'selected_xyz_count': len(tiles),
              'offline_repeat_http_requests': 0, 'offline_repeat_xyz_conversions': 0,
              'target_cells': expected.size,
              'maximum_absolute_error_m': 0, 'source_archives_unchanged': True,
              'result': result}
    write_json(directory / 'pilot_report.json', report)
    print(f'BW live pilot passed: {directory / "pilot_report.json"}')


if __name__ == '__main__':
    bootstrap(__file__, 'config.germany.bw.json')
    main()
