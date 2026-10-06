"""Small, offline integration checks for country preparation and grid contracts."""
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal, ogr

from dtm.acquire import params, sha256, write_json
from dtm.paths import raw_directory, receipt_path
from dtm.coordinator import create_log_directory, execute, load_config
from dtm.countries.netherlands.acquisition import download
from dtm.countries.netherlands.processing import prepare
from dtm.geo import bounds, project, rectangle, srs, verify_alignment
from dtm.process import align, clean
from dtm.target_grid import plan_grid, write_reference


def raster(path, values, epsg=28992, transform=(200000, .5, 0, 425008, 0, -.5)):
    values = np.asarray(values, dtype='float32')
    with gdal.GetDriverByName('GTiff').Create(str(path), values.shape[1], values.shape[0], 1, gdal.GDT_Float32) as ds:
        ds.SetProjection(srs(epsg).ExportToWkt())
        ds.SetGeoTransform(transform)
        ds.GetRasterBand(1).SetNoDataValue(-9999)
        ds.GetRasterBand(1).WriteArray(values)
    return path


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_prepare_')
        self.root = Path(self.temp.name)
        self.geometry = ogr.CreateGeometryFromWkt(
            'POLYGON ((200001 425001,200007 425001,200007 425007,200001 425007,200001 425001),'
            '(200003 425003,200003 425005,200005 425005,200005 425003,200003 425003))')
        self.geometry.AssignSpatialReference(srs(28992))
        aoi = self.root / 'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
            layer = ds.CreateLayer('study_area', srs(28992), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        self.config_path = self.root / 'config.json'
        self.settings = {'country': 'netherlands', 'aoi': 'aoi.gpkg', 'target': {'reference_raster': None, 'resolution': 1},
                         'source': {'url': 'https://example.invalid/wcs', 'coverage': 'dtm_05m',
                                    'epsg': 28992, 'resolution': .5, 'chunk_size_m': 8, 'vertical_datum': 'NAP'},
                         'hole_filling': {'enabled': False},
                         'processed_tile_size_pixels': 3,
                         'block_size': 2, 'request_pause_seconds': 0}
        write_json(self.config_path, self.settings)
        self.config = load_config(self.config_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_readable_run_names_use_amsterdam_time_and_avoid_collisions(self):
        summer = datetime(2026, 9, 27, 18, 49, 10, tzinfo=timezone.utc)
        first = create_log_directory(self.config, summer)
        self.assertEqual(first.name, '2026-09-27_20-49-10')
        self.assertEqual(create_log_directory(self.config, summer).name, first.name + '_02')
        winter = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(create_log_directory(self.config, winter).name, '2026-01-01_13-00-00')
        existing_output = Path(self.config['output_root']) / 'netherlands' / (first.name + '_03')
        existing_output.mkdir(parents=True)
        self.assertEqual(create_log_directory(self.config, summer).name, first.name + '_04')

    def test_default_grid_covers_polygon_and_has_five_metre_edges(self):
        info = plan_grid(self.geometry, {})
        x0, y0, x1, y1 = bounds(project(self.geometry, srs(25832)))
        left, bottom, right, top = info['extent']
        self.assertLessEqual(left, x0)
        self.assertLessEqual(bottom, y0)
        self.assertGreaterEqual(right, x1)
        self.assertGreaterEqual(top, y1)
        self.assertTrue(all(value % 5 == 0 for value in info['extent']))
        self.assertEqual(info['cols'] * 5, right - left)
        self.assertEqual(info['rows'] * 5, top - bottom)
        self.assertEqual(info['transform'][1:], [5, 0, top, 0, -5])
        self.assertEqual(info, plan_grid(self.geometry, {}))
        reference = write_reference(info, self.root / 'target.vrt')
        self.assertLess(reference.stat().st_size, 10000)

    def test_reference_rejects_wrong_crs_and_incomplete_extent(self):
        wrong_crs = raster(self.root / 'wrong.tif', np.ones((4, 4)))
        with self.assertRaisesRegex(ValueError, 'EPSG:25832'):
            plan_grid(self.geometry, {'reference_raster': str(wrong_crs)})
        small = raster(self.root / 'small.tif', np.ones((1, 1)), epsg=25832, transform=(0, 5, 0, 5, 0, -5))
        with self.assertRaisesRegex(ValueError, 'whole AOI'):
            plan_grid(self.geometry, {'reference_raster': str(small)})
        target = write_reference(plan_grid(self.geometry, {}), self.root / 'target.vrt')
        self.assertEqual(plan_grid(self.geometry, {'reference_raster': str(target)})['mode'], 'reference')
        old = write_reference(plan_grid(self.geometry, {'resolution': 1}), self.root / 'old_1m.vrt')
        with self.assertRaisesRegex(ValueError, '5 m pixels'):
            plan_grid(self.geometry, {'reference_raster': str(old)})
        shifted = raster(self.root / 'shifted.tif', np.ones((2, 2)), epsg=25832, transform=(1, 5, 0, 11, 0, -5))
        with self.assertRaisesRegex(ValueError, 'origin'):
            plan_grid(self.geometry, {'reference_raster': str(shifted)})

    def test_plan_has_no_network_calls_and_resolves_relative_paths(self):
        with patch('requests.Session.get') as get:
            plan = execute(self.config, 'plan')
        get.assert_not_called()
        self.assertEqual(plan['country'], 'netherlands')
        self.assertEqual(plan['metadata_requests'], 2)
        self.assertEqual(Path(self.config['cache_root']), self.root / 'data')
        self.assertFalse((self.root / 'logs/preparation/netherlands/latest_run.json').exists())

    def test_download_adapter_uses_only_country_raw_cache(self):
        directory = raw_directory(self.config)
        directory.mkdir(parents=True)
        raw = raster(directory / 'tile.tif', np.ones((16, 16)))
        tile = {'id': 'tile', 'bounds': [200000, 425000, 200008, 425008]}
        source = self.config['source']
        receipt = receipt_path(raw, self.config)
        receipt.parent.mkdir(parents=True)
        write_json(receipt, {'source': source, 'request': params(source, tile), 'sha256': sha256(raw)})
        with patch('dtm.countries.netherlands.acquisition.metadata'), patch('dtm.countries.netherlands.acquisition.download_tile') as fetch:
            self.assertEqual(download(self.config, {'tiles': [tile]}, self.root / 'newrun'), [raw])
            fetch.assert_not_called()
            self.config['reuse_cache'] = False
            download(self.config, {'tiles': [tile]}, self.root / 'freshrun')
            self.assertEqual(fetch.call_args.args[3], directory)
        self.assertEqual(list(directory.iterdir()), [raw])

    def test_defaults_enable_twenty_metre_filling(self):
        self.settings.pop('hole_filling')
        self.settings['target'].pop('resolution')
        write_json(self.config_path, self.settings)
        config = load_config(self.config_path)
        self.assertTrue(config['hole_filling']['enabled'])
        self.assertEqual(config['hole_filling']['max_distance_m'], 100)
        self.assertTrue(config['hole_filling']['nearest_fallback'])
        self.assertEqual(config['target']['resolution'], 5)

    def test_preparation_matches_existing_warp_and_masks_holes(self):
        values = np.arange(256, dtype='float32').reshape(16, 16) / 10 - 5
        values[:4, :4] = np.finfo('float32').max
        values[12:, 12:] = -9999
        raw = raster(self.root / 'raw.tif', values)
        before = sha256(raw)
        target = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'target.vrt')
        run = self.root / 'run'
        result = prepare([raw], self.geometry, target, run, self.config)
        self.assertEqual(Path(result['comparison_ready_raster']), run / 'stitched/ahn.tif')
        self.assertGreater(result['processed_tiles']['count'], 1)
        manifest = json.loads(Path(result['processed_tiles']['manifest']).read_text())
        with gdal.Open(result['comparison_ready_raster']) as stitched:
            assembled = np.full((stitched.RasterYSize, stitched.RasterXSize), -9999, dtype='float32')
            coverage = np.zeros(assembled.shape, dtype='uint8')
            for item in manifest['tiles']:
                x, y, w, h = [item[key] for key in ('column', 'row', 'cols', 'rows')]
                with gdal.Open(item['path']) as piece:
                    assembled[y:y+h, x:x+w] = piece.ReadAsArray()
                    gt = stitched.GetGeoTransform()
                    self.assertEqual(piece.GetGeoTransform(), (gt[0]+x, 1, 0, gt[3]-y, 0, -1))
                coverage[y:y+h, x:x+w] += 1
            np.testing.assert_array_equal(assembled, stitched.ReadAsArray())
            self.assertTrue(np.all(coverage == 1))
        verify_alignment(result['prepared_raster'], target)
        # Independently reproduce the old clean -> warp -> clean sequence.
        cleaned, warped, final = [self.root / name for name in ('clean.tif', 'warp.tif', 'final.tif')]
        clean(raw, cleaned, self.config)
        align(cleaned, target, warped, self.config)
        clean(warped, final, self.config)
        with gdal.Open(str(final)) as expected_ds, gdal.Open(result['prepared_raster']) as prepared_ds, gdal.Open(result['aoi_mask']) as mask_ds:
            actual = prepared_ds.ReadAsArray()
            expected = expected_ds.ReadAsArray()
            mask = mask_ds.ReadAsArray()
            expected[mask == 0] = -9999
            np.testing.assert_array_equal(actual, expected)
            self.assertGreater(result['valid_cell_count'], 0)
            self.assertEqual(result['valid_cell_count'], int((actual != -9999).sum()))
            self.assertTrue(np.any(mask == 0))
            # The hole centre must remain outside even after reprojection.
            centre = rectangle([200004, 425004, 200004.1, 425004.1])
            centre.AssignSpatialReference(srs(28992))
            x, y, _, _ = bounds(project(centre, srs(25832)))
            gt = prepared_ds.GetGeoTransform()
            row, col = int((gt[3] - y) / -gt[5]), int((x - gt[0]) / gt[1])
            self.assertEqual(mask[row, col], 0)
            self.assertEqual(actual[row, col], -9999)
            self.assertIn('NAP', prepared_ds.GetMetadataItem('VERTICAL_DATUM_NOTE'))
        self.assertEqual(before, sha256(raw))
        self.assertFalse((run / 'output/ahn_minus_nrw.tif').exists())

    def test_coordinator_keeps_separate_runs_and_preserves_success_on_failure(self):
        raw = raster(self.root / 'raw.tif', np.full((16, 16), 12))
        write_json(raw.with_suffix('.json'), {'sha256': sha256(raw)})
        with patch('dtm.countries.netherlands.download', return_value=[raw]), patch('requests.Session.get') as get:
            result = execute(self.config, 'yes')
        get.assert_not_called()
        self.assertEqual(result['stage'], 'prepared')
        latest = self.root / 'logs/preparation/netherlands/latest_run.json'
        saved = latest.read_bytes()
        self.assertEqual(json.loads(saved)['status'], 'complete')
        first_output = Path(result['prepared_raster'])
        first_hash = sha256(first_output)
        scope = Path(self.config['output_root']) / 'netherlands'
        self.assertEqual(first_output, scope / result['run_id'] / 'stitched/ahn.tif')
        with patch('dtm.countries.netherlands.download', return_value=[raw]):
            second = execute(self.config, 'yes')
        self.assertNotEqual(second['run_id'], result['run_id'])
        self.assertTrue((scope / second['run_id'] / 'processed/result.json').is_file())
        self.assertEqual(sha256(first_output), first_hash)
        saved = latest.read_bytes()
        raster(raw, np.full((16, 16), -9999))
        with patch('dtm.countries.netherlands.download', return_value=[raw]):
            with self.assertRaisesRegex(RuntimeError, 'No valid AHN coverage'):
                execute(self.config, 'yes')
        self.assertEqual(latest.read_bytes(), saved)
        self.assertEqual(sha256(first_output), first_hash)
        self.assertTrue(Path(second['prepared_raster']).is_file())
        self.assertFalse(Path(self.config['old_runs_root']).exists())
        self.assertTrue((Path(result['log_directory']) / 'result.json').is_file())

    def test_reject_unsupported_country_and_invalid_native_resolution(self):
        settings = {**self.settings, 'country': 'unimplemented'}
        write_json(self.config_path, settings)
        with self.assertRaisesRegex(ValueError, 'Unsupported country'):
            load_config(self.config_path)
        settings = {**self.settings, 'source': {**self.settings['source'], 'resolution': 1}}
        write_json(self.config_path, settings)
        with self.assertRaisesRegex(ValueError, 'native AHN'):
            load_config(self.config_path)


if __name__ == '__main__':
    unittest.main()
