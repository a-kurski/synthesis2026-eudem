"""NRW dispatch, cache provenance and exact native-grid aggregation checks."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal, ogr

from test_preparation import PreparationTests, raster
from dtm.acquire import params, sha256, write_json
from dtm.coordinator import create_log_directory, execute, load_config
from dtm.countries import germany
from dtm.countries.germany.nrw import plan
from dtm.countries.germany.nrw.acquisition import download
from dtm.countries.germany.nrw.processing import aggregate, prepare
from dtm.geo import rectangle, srs, verify_alignment
from dtm.paths import scoped_root, raw_directory, receipt_path
from dtm.target_grid import plan_grid, write_reference


class NRWTests(unittest.TestCase):
    base_setup = PreparationTests.setUp
    tearDown = PreparationTests.tearDown

    def setUp(self):
        self.base_setup()
        self.settings.update(country='germany', region='nrw', target={'epsg': 25832, 'resolution': 5},
                             legacy_cache_roots=['archive/data'])
        self.settings['source'] = {'url': 'https://example.invalid/nrw', 'coverage': 'nw_dgm',
                                  'epsg': 25832, 'resolution': 1.0, 'chunk_size_m': 10,
                                  'vertical_datum': 'DHHN2016/NHN'}
        write_json(self.config_path, self.settings)
        self.config = load_config(self.config_path)
        self.geometry = rectangle([310000, 5740000, 310020, 5740020])
        self.geometry.AssignSpatialReference(srs(25832))
        self.reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'nrw_target.vrt')

    def raw(self, name='raw.tif', values=None, x=310000, y=5740020):
        if values is None:
            rows, cols = np.indices((20, 20))
            values = rows * .25 + cols * .5 + 12
        return raster(self.root / name, values, epsg=25832, transform=(x, 1, 0, y, 0, -1))

    def save_aoi(self):
        path = self.root / 'nrw.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(path)) as ds:
            layer = ds.CreateLayer('nrw', srs(25832), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        self.config['aoi'] = str(path)

    def test_block_means_seams_and_stitched_pixels_without_warp_or_filling(self):
        values = np.arange(400, dtype='float32').reshape(20, 20) * .125
        # A seam inside a 5 m output footprint tests shared-mosaic aggregation.
        left = self.raw('left.tif', values[:, :8])
        right = self.raw('right.tif', values[:, 8:], x=310008)
        checksums = [sha256(left), sha256(right)]
        with patch('dtm.process.align', side_effect=AssertionError('Unexpected align')), \
             patch('osgeo.gdal.Warp', side_effect=AssertionError('Unexpected warp')), \
             patch('dtm.countries.netherlands.hole_filling.fill_holes', side_effect=AssertionError('Unexpected fill')):
            result = prepare([left, right], self.geometry, self.reference, self.root / 'run', self.config)
        with gdal.Open(result['prepared_raster']) as ds:
            expected = values.reshape(4, 5, 4, 5).mean(axis=(1, 3))
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertEqual(ds.GetRasterBand(1).GetUnitType(), 'm')
            self.assertIn('DHHN2016/NHN', ds.GetMetadataItem('VERTICAL_DATUM_NOTE'))
        self.assertEqual(checksums, [sha256(left), sha256(right)])
        self.assertEqual(result['prepared_raster'], result['comparison_ready_raster'])
        self.assertEqual(result['valid_cell_count'], 16)
        verify_alignment(result['prepared_raster'], self.reference)
        manifest = json.loads(Path(result['processed_tiles']['manifest']).read_text())
        assembled = np.zeros((4, 4), dtype='float32')
        coverage = np.zeros((4, 4), dtype='uint8')
        for tile in manifest['tiles']:
            x, y, w, h = [tile[k] for k in ('column', 'row', 'cols', 'rows')]
            self.assertTrue(Path(tile['path']).name.startswith('nrw_'))
            with gdal.Open(tile['path']) as ds:
                assembled[y:y+h, x:x+w] = ds.ReadAsArray()
            coverage[y:y+h, x:x+w] += 1
        np.testing.assert_array_equal(assembled, expected)
        np.testing.assert_array_equal(coverage, 1)
        self.assertFalse((self.root / 'run/processed/_work/hole_filling').exists())

    def test_missing_values_polygon_holes_and_partial_cells(self):
        values = np.full((20, 20), 17, dtype='float32')
        values[:5, :5] = -9999
        values[5, 0] = np.nan
        values[6, 0] = np.inf
        values[7, 0] = np.finfo('float32').max
        values[8, 0] = -9999
        geometry = ogr.CreateGeometryFromWkt(
            'POLYGON ((310002 5740002,310018 5740002,310018 5740018,310002 5740018,310002 5740002),'
            '(310010 5740010,310015 5740010,310015 5740015,310010 5740015,310010 5740010))')
        geometry.AssignSpatialReference(srs(25832))
        result = prepare([self.raw(values=values)], geometry, self.reference, self.root / 'mask', self.config)
        with gdal.Open(result['prepared_raster']) as ds:
            expected = np.full((4, 4), 17, dtype='float32')
            expected[0, 0] = expected[1, 2] = -9999
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
        # Partial boundary footprints retain all native contributions before masking.
        varying = self.raw('varying.tif')
        a = self.root / 'one.tif'
        b = self.root / 'two.tif'
        aggregate(varying, self.reference, a, {**self.config, 'block_size': 1})
        aggregate(varying, self.reference, b, {**self.config, 'block_size': 3})
        with gdal.Open(str(a)) as x, gdal.Open(str(b)) as y:
            np.testing.assert_array_equal(x.ReadAsArray(), y.ReadAsArray())

    def test_shared_reference_outside_source_is_nodata(self):
        larger = rectangle([309995, 5739995, 310025, 5740025])
        larger.AssignSpatialReference(srs(25832))
        reference = write_reference(plan_grid(larger, self.config['target']), self.root / 'large.vrt')
        result = prepare([self.raw(values=np.full((20, 20), 4))], larger, reference, self.root / 'large', self.config)
        with gdal.Open(result['prepared_raster']) as ds:
            expected = np.full((6, 6), -9999, dtype='float32')
            expected[1:5, 1:5] = 4
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
        verify_alignment(result['prepared_raster'], reference)

    def test_shifted_sources_wrong_resolution_and_crs_are_rejected(self):
        for name, epsg, transform in [('shift', 25832, (310000.5, 1, 0, 5740020, 0, -1)),
                                      ('crs', 28992, (310000, 1, 0, 5740020, 0, -1)),
                                      ('step', 25832, (310000, 1.001, 0, 5740020, 0, -1.001))]:
            raw = raster(self.root / f'{name}.tif', np.ones((20, 20)), epsg=epsg, transform=transform)
            with self.assertRaises(ValueError):
                prepare([raw], self.geometry, self.reference, self.root / name, self.config)

    def test_cache_reuse_checksums_fresh_downloads_and_region_isolation(self):
        cache = raw_directory(self.config)
        cache.mkdir(parents=True)
        cached_raw = cache / 'tile.tif'
        cached_raw.write_bytes(self.raw().read_bytes())
        tile = {'id': 'tile', 'bounds': [310000, 5740000, 310020, 5740020]}
        receipt = {'source': self.config['source'], 'request': params(self.config['source'], tile), 'sha256': sha256(cached_raw)}
        record = receipt_path(cached_raw, self.config)
        record.parent.mkdir(parents=True)
        write_json(record, receipt)
        with patch('dtm.countries.germany.nrw.acquisition.metadata'), \
             patch('dtm.countries.germany.nrw.acquisition.download_tile') as fetch:
            self.assertEqual(download(self.config, {'tiles': [tile]}, self.root / 'first'), [cached_raw])
            fetch.assert_not_called()
            self.config['reuse_cache'] = False
            download(self.config, {'tiles': [tile]}, self.root / 'fresh')
            self.assertEqual(fetch.call_args.args[3], cache)
            self.config['reuse_cache'] = True
            receipt['sha256'] = 'corrupt'
            write_json(record, receipt)
            fetch.reset_mock()
            download(self.config, {'tiles': [tile]}, self.root / 'corrupt')
            fetch.assert_called_once()

    def test_offline_plan_context_and_region_paths(self):
        self.save_aoi()
        with patch('requests.Session.get') as get:
            result = execute(self.config, 'plan')
        get.assert_not_called()
        self.assertEqual(result['region'], 'nrw')
        self.assertFalse(result['source']['raster_reprojection'])
        self.assertFalse(result['source']['hole_filling'])
        self.assertEqual(result['target_grid'], plan_grid(self.geometry, {'resolution': 5}))
        extent = result['source']['aoi_extent']
        self.assertLess(extent[0], 310000)
        self.assertGreater(extent[2], 310020)
        # Stable identities match the version 1 request schema.
        self.assertEqual(plan(self.geometry, self.config), plan(self.geometry, self.config))
        now = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
        first = create_log_directory(self.config, now)
        second = create_log_directory({**self.config, 'region': 'future_state'}, now)
        self.assertEqual(first.name, second.name)
        self.assertNotEqual(first.parent, second.parent)

    def test_coordinator_records_region_and_preserves_success_on_failure(self):
        self.save_aoi()
        raw = self.raw()
        write_json(raw.with_suffix('.json'), {'sha256': sha256(raw)})
        with patch('dtm.countries.germany.nrw.download', return_value=[raw]):
            result = execute(self.config, 'yes')
        self.assertEqual(result['region'], 'nrw')
        latest = scoped_root(self.config, 'logs_dir') / 'latest_run.json'
        self.assertEqual(json.loads(latest.read_text())['status'], 'complete')
        saved = latest.read_bytes()
        output = Path(result['prepared_raster'])
        checksum = sha256(output)
        self.assertEqual(output, scoped_root(self.config, 'output_root') / result['run_id'] / 'stitched/nrw.tif')
        self.raw(values=np.full((20, 20), -9999))
        with patch('dtm.countries.germany.nrw.download', return_value=[raw]):
            with self.assertRaisesRegex(RuntimeError, 'No valid NRW coverage'):
                execute(self.config, 'yes')
        self.assertEqual(latest.read_bytes(), saved)
        self.assertEqual(sha256(output), checksum)
        self.assertFalse(Path(self.config['old_runs_root']).exists())

    def test_region_and_filling_validation_including_cli_override(self):
        for key, value in [('region', 'unknown'), ('region', None), ('hole_filling', {'enabled': True}),
                           ('target', {'resolution': 1}), ('reuse_cache', 'true')]:
            config = deepcopy(self.config)
            config[key] = value
            with self.assertRaises(ValueError):
                germany.validate_config(config)
        entry = Path(__file__).resolve().parents[1] / 'main.py'
        result = subprocess.run([sys.executable, str(entry), str(self.config_path), '--plan', '--fill-holes'],
                                capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not supported for NRW', result.stderr)


del PreparationTests
