"""Native interpolation, provenance, seam and acquisition-mode regressions."""
from pathlib import Path
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal

from test_preparation import PreparationTests, raster
from dtm.acquire import sha256
from dtm.countries.netherlands import plan
from dtm.countries.netherlands.acquisition import download
from dtm.countries.netherlands.hole_filling import fill_holes, settings
from dtm.countries.netherlands.processing import prepare
from dtm.geo import rectangle, srs, verify_alignment
from dtm.process import mosaic
from dtm.target_grid import plan_grid, write_reference


class HoleFillingTests(unittest.TestCase):
    # Use setup helpers without inheriting/discovering another test suite.
    setUp = PreparationTests.setUp
    tearDown = PreparationTests.tearDown

    def enable(self, distance=1):
        self.config['hole_filling'] = {'enabled': True, 'max_distance_m': distance}

    def test_constant_fill_preserves_originals_and_excludes_polygon_hole(self):
        self.enable()
        values = np.full((16, 16), 12, dtype='float32')
        values[3:5, 3:5] = -9999
        values[6:10, 6:10] = -9999  # Deliberate AOI hole.
        values[0, 0] = -9999  # Outside polygon.
        raw = raster(self.root / 'raw.tif', values)
        before = sha256(raw)
        report = fill_holes(raw, self.geometry, self.root / 'fill', self.config)
        with gdal.Open(report['filled_native']) as ds:
            actual = ds.ReadAsArray()
        np.testing.assert_array_equal(actual[values != -9999], values[values != -9999])
        np.testing.assert_array_equal(actual[3:5, 3:5], 12)
        np.testing.assert_array_equal(actual[6:10, 6:10], -9999)
        self.assertEqual(actual[0, 0], -9999)
        self.assertEqual(report['filled_cell_count'], 4)
        self.assertEqual(report['filled_area_m2'], 1)
        self.assertEqual(before, sha256(raw))

    def test_large_gaps_keep_unsupported_centres_and_are_block_size_independent(self):
        self.enable(.5)
        values = np.full((16, 16), 12, dtype='float32')
        values[3:13, 3:13] = -9999
        raw = raster(self.root / 'raw.tif', values)
        geometry = rectangle([200000, 425000, 200008, 425008])
        geometry.AssignSpatialReference(srs(28992))
        first = fill_holes(raw, geometry, self.root / 'first', self.config)
        second = fill_holes(raw, geometry, self.root / 'second', {**self.config, 'block_size': 7})
        with gdal.Open(first['filled_native']) as a, gdal.Open(second['filled_native']) as b:
            np.testing.assert_array_equal(a.ReadAsArray(), b.ReadAsArray())
            self.assertEqual(a.ReadAsArray()[8, 8], -9999)
        self.assertGreater(first['filled_cell_count'], 0)
        self.assertGreater(first['remaining_nodata_cell_count'], 0)

    def test_acquisition_buffer_and_fresh_directory_are_independent_of_filling(self):
        baseline = plan(self.geometry, self.config)
        self.enable(10)
        buffered = plan(self.geometry, self.config)
        self.assertGreater(buffered['chunks'], baseline['chunks'])
        self.assertEqual(buffered['context_buffer_m'], 10.5)
        self.config['hole_filling']['enabled'] = False
        self.assertEqual(plan(self.geometry, self.config), baseline)
        self.config['reuse_cache'] = False
        with patch('dtm.countries.netherlands.acquisition.metadata'), patch('dtm.countries.netherlands.acquisition.download_tile') as acquire:
            download(self.config, baseline, self.root / 'run123')
        expected = Path(self.config['output_root']) / 'netherlands/run123/raw_ahn_tiles'
        self.assertEqual(acquire.call_args.args[3], expected)
        self.assertNotEqual(expected, Path(self.config['cache_root']))

    def test_filled_branch_keeps_baseline_and_fraction_matches_validity(self):
        values = np.arange(256, dtype='float32').reshape(16, 16) / 10
        values[3:6, 3:6] = -9999
        raw = raster(self.root / 'raw.tif', values)
        reference = write_reference(plan_grid(self.geometry, {}), self.root / 'target.vrt')
        before = prepare([raw], self.geometry, reference, self.root / 'disabled', self.config)
        self.enable(2)
        after = prepare([raw], self.geometry, reference, self.root / 'enabled', self.config)
        self.assertEqual(Path(after['prepared_raster']), self.root / 'enabled/ahn_stitched/ahn_unfilled.tif')
        self.assertFalse((self.root / 'enabled/processed_tiles/unfilled').exists())
        self.assertFalse((self.root / 'enabled/ahn_stitched/ahn_unfilled.vrt').exists())
        self.assertEqual(Path(after['fill_fraction']), self.root / 'enabled/ahn_stitched/ahn_fill_fraction.tif')
        self.assertFalse((self.root / 'enabled/processed_tiles/fill_fraction').exists())
        self.assertFalse((self.root / 'enabled/ahn_stitched/ahn_fill_fraction.vrt').exists())
        with gdal.Open(before['prepared_raster']) as a, gdal.Open(after['prepared_raster']) as b:
            np.testing.assert_array_equal(a.ReadAsArray(), b.ReadAsArray())
        with gdal.Open(after['prepared_filled_raster']) as height, gdal.Open(after['fill_fraction']) as fractions:
            values, shares = height.ReadAsArray(), fractions.ReadAsArray()
            np.testing.assert_array_equal(values != -9999, shares != -9999)
            self.assertTrue(np.any((shares > 0) & (shares < 1)))
            self.assertTrue(np.all((shares[shares != -9999] >= 0) & (shares[shares != -9999] <= 1)))
            self.assertEqual(fractions.GetRasterBand(1).GetUnitType(), '1')
        verify_alignment(after['prepared_filled_raster'], reference)
        self.assertEqual(after['comparison_ready_raster'], after['prepared_filled_raster'])

    def test_gap_crossing_tile_seam_matches_single_native_raster(self):
        self.enable(2)
        values = np.arange(256, dtype='float32').reshape(16, 16) / 10
        values[3:6, 6:10] = -9999
        full = raster(self.root / 'full.tif', values)
        left = raster(self.root / 'left.tif', values[:, :8])
        right = raster(self.root / 'right.tif', values[:, 8:], transform=(200004, .5, 0, 425008, 0, -.5))
        merged = mosaic('seam', [left, right], self.root, self.config)
        a = fill_holes(full, self.geometry, self.root / 'full_fill', self.config)
        b = fill_holes(merged, self.geometry, self.root / 'tile_fill', self.config)
        with gdal.Open(a['filled_native']) as x, gdal.Open(b['filled_native']) as y:
            np.testing.assert_array_equal(x.ReadAsArray(), y.ReadAsArray())

    def test_invalid_options_are_rejected(self):
        for supplied in ({'max_distance_m': 0}, {'max_distance_m': float('inf')},
                         {'smoothing_iterations': 1}, {'enabled': 'yes'}, {'method': 'unknown'}):
            with self.assertRaises(ValueError):
                settings({'hole_filling': supplied})

    def test_all_nodata_stays_unfilled_without_valid_donors(self):
        self.enable(20)
        raw = raster(self.root / 'empty.tif', np.full((16, 16), -9999))
        report = fill_holes(raw, self.geometry, self.root / 'empty_fill', self.config)
        self.assertGreater(report['candidate_cell_count'], 0)
        self.assertEqual(report['filled_cell_count'], 0)
        self.assertEqual(report['candidate_cell_count'], report['remaining_nodata_cell_count'])
        with gdal.Open(report['filled_native']) as ds:
            self.assertTrue(np.all(ds.ReadAsArray() == -9999))

    def test_cli_fill_and_cache_overrides_are_saved_in_plan_config(self):
        entry = Path(__file__).resolve().parents[1] / 'main.py'
        for switches, filling, reuse in [(['--fill-holes', '--reuse-cache'], True, True),
                                          (['--no-fill-holes', '--fresh-download'], False, False)]:
            result = subprocess.run([sys.executable, str(entry), str(self.config_path), '--plan', *switches],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run_configs = sorted((self.root / 'logs/preparation/netherlands').glob('*/config.json'),
                                 key=lambda path: path.stat().st_mtime_ns)
            saved = json.loads(run_configs[-1].read_text())
            self.assertEqual(saved['hole_filling']['enabled'], filling)
            self.assertEqual(saved['reuse_cache'], reuse)


# Avoid unittest discovering the imported helper class a second time.
del PreparationTests
