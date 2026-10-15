"""Recover completed warps without nearest fallback or upstream processing."""
import math
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal

from test_preparation import PreparationTests, raster
from dtm.acquire import sha256, write_json
from dtm.target_grid import plan_grid
from scripts.recover_ahn import preflight, recover


class RecoveryTests(unittest.TestCase):
    setUp = PreparationTests.setUp
    tearDown = PreparationTests.tearDown

    def saved_run(self):
        self.config['hole_filling'] = {'enabled': True, 'method': 'gdal_idw',
            'max_distance_m': 1, 'nearest_fallback': True}
        source = self.root / 'saved'
        logs = self.root / 'saved_logs'
        aligned = source / 'processed/_work/aligned'
        aligned.mkdir(parents=True)
        logs.mkdir()
        target = plan_grid(self.geometry, self.config['target'])
        padding = math.ceil(1 / target['transform'][1]) + 1
        transform = list(target['transform'])
        transform[0] -= padding * transform[1]
        transform[3] += padding * transform[1]
        values = np.full((target['rows'] + 2 * padding, target['cols'] + 2 * padding),
                         -9999, dtype='float32')
        values[:, padding] = 12
        context = raster(aligned / 'ahn_resampled_with_context.tif', values,
                         epsg=25832, transform=transform)
        write_json(source / 'processed/target_grid.json', target)
        write_json(logs / 'config.json', self.config)
        write_json(logs / 'plan.json', {'target_grid': target,
                                       'aoi_sha256': sha256(self.config['aoi'])})
        (logs / 'processing.log').write_text(f'output={context}\nAlignment verified: completed\n')
        return source, logs, context

    def test_recovery_preserves_source_and_skips_upstream_and_nearest(self):
        source, logs, context = self.saved_run()
        before = sha256(context)
        config_before = sha256(logs / 'config.json')
        with patch('dtm.countries.netherlands.processing.align', side_effect=AssertionError('warp repeated')), \
                patch('dtm.countries.netherlands.processing.clean', side_effect=AssertionError('clean repeated')), \
                patch('dtm.countries.netherlands.hole_filling.fill_remaining', side_effect=AssertionError('nearest called')):
            result = recover(source, logs)
        self.assertEqual(sha256(context), before)
        self.assertEqual(sha256(logs / 'config.json'), config_before)
        self.assertFalse(result['hole_filling']['settings']['nearest_fallback'])
        self.assertEqual(result['hole_filling']['nearest_filled_cell_count'], 0)
        self.assertGreater(result['hole_filling']['remaining_nodata_cell_count'], 0)
        with gdal.Open(result['comparison_ready_raster']) as ds:
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')

    def test_changed_aoi_and_unconfirmed_warp_are_rejected(self):
        source, logs, _ = self.saved_run()
        (logs / 'processing.log').write_text('Warp started but did not finish')
        with self.assertRaisesRegex(ValueError, 'confirm'):
            preflight(source, logs)
        write_json(logs / 'plan.json', {'aoi_sha256': 'changed'})
        with self.assertRaisesRegex(ValueError, 'AOI changed'):
            preflight(source, logs)


del PreparationTests
