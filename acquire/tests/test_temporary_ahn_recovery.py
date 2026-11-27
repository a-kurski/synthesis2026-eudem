"""One-off recovery: finite search, preserved donors, output alignment and isolation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal

from dtm.acquire import sha256
from dtm.coordinator import load_config
from dtm.geo import grid, rectangle, srs, verify_alignment
from dtm.target_grid import write_reference
from scripts.temporary_ahn_recovery.recover import load_temporary_modules, validate_saved_grid


class TemporaryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ahn_recovery_test_')
        self.root = Path(self.temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'config.netherlands.json')
        self.config['hole_filling']['max_distance_m'] = 10
        self.config['block_size'] = 16
        self.holes, self.processing = load_temporary_modules()
        self.source = self.root / 'aligned.tif'
        self.values = np.full((40, 40), -9999, dtype='float32')
        self.values[:, 10] = np.arange(40, dtype='float32') + 100
        with gdal.GetDriverByName('GTiff').Create(str(self.source), 40, 40, 1, gdal.GDT_Float32) as ds:
            ds.SetGeoTransform((200000, 5, 0, 5800000, 0, -5))
            ds.SetSpatialRef(srs(25832))
            ds.GetRasterBand(1).SetNoDataValue(-9999)
            ds.GetRasterBand(1).WriteArray(self.values)
        self.geometry = rectangle([200015, 5799815, 200185, 5799985])
        self.geometry.AssignSpatialReference(srs(25832))

    def tearDown(self):
        self.temp.cleanup()

    def test_finite_search_leaves_distant_gaps_and_originals_unchanged(self):
        before = sha256(self.source)
        with patch.object(gdal, 'FillNodata', wraps=gdal.FillNodata) as fill:
            report = self.holes.fill_holes(self.source, self.geometry, self.root / 'fill', self.config)
        self.assertEqual(len(fill.call_args_list), 2)
        self.assertEqual([c.args[2] for c in fill.call_args_list], [2, 2])
        self.assertGreater(report['remaining_nodata_cell_count'], 0)
        self.assertFalse(report['complete_aoi_coverage'])
        self.assertEqual(report['nearest_max_distance_m'], 10)
        with gdal.Open(report['filled_raster']) as ds:
            actual = ds.ReadAsArray()
        np.testing.assert_array_equal(actual[:, 10], self.values[:, 10])
        self.assertEqual(actual[20, 30], -9999)
        self.assertEqual(sha256(self.source), before)

    def test_recovery_skips_earlier_stages_and_publishes_aligned_outputs(self):
        before = sha256(self.source)
        info = grid(self.source)
        target = {**info, 'cols': 34, 'rows': 34,
                  'transform': [200015, 5, 0, 5799985, 0, -5]}
        reference = write_reference(target, self.root / 'target.vrt')
        with patch.object(self.processing, 'clean', side_effect=AssertionError('clean repeated')), \
             patch.object(self.processing, 'mosaic', side_effect=AssertionError('mosaic repeated')), \
             patch.object(self.processing, 'align', side_effect=AssertionError('warp repeated')):
            result = self.processing.recover(self.source, self.root / 'unused_mosaic.tif',
                                            self.geometry, reference, self.root / 'run', self.config)
        verify_alignment(result['comparison_ready_raster'], reference)
        self.assertGreater(result['hole_filling']['remaining_nodata_cell_count'], 0)
        self.assertEqual(sha256(self.source), before)

    def test_grid_mismatch_rejected_and_normal_module_not_replaced(self):
        from dtm.countries.netherlands import hole_filling
        self.assertIsNot(self.holes, hole_filling)
        info = grid(self.source)
        validate_saved_grid(info, info)
        with self.assertRaisesRegex(ValueError, 'grid'):
            validate_saved_grid(info, {**info, 'cols': 39})
