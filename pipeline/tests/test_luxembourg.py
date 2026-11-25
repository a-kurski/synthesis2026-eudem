"""Offline national-cache checks and small real-GDAL Luxembourg processing runs."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import requests
from osgeo import gdal, ogr
from osgeo_utils.samples.validate_cloud_optimized_geotiff import validate

from dtm.acquire import sha256, write_json
from dtm.coordinator import execute, load_config
from dtm.countries.luxembourg import plan, validate_config
from dtm.countries.luxembourg.acquisition import download, source_path
from dtm.countries.luxembourg.processing import prepare, validate_native
from dtm.geo import project, rectangle, srs, verify_alignment
from dtm.paths import raw_directory, receipt_path
from dtm.target_grid import plan_grid, write_reference

MODULE = 'dtm.countries.luxembourg.processing.'
TRANSFORM = (70000, .5, 0, 100300, 0, -.5)


class LuxembourgTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_luxembourg_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.geometry = ogr.CreateGeometryFromWkt(
            'POLYGON ((70030 100030,70280 100030,70280 100280,70030 100280,70030 100030),'
            '(70060 100060,70060 100090,70090 100090,70090 100060,70060 100060))')
        self.geometry.AssignSpatialReference(srs(2169))
        country = rectangle([70000, 100000, 70200, 100300])
        country.AssignSpatialReference(srs(2169))
        self.vector('aoi.gpkg', self.geometry)
        self.vector('country.gpkg', country)
        settings = json.loads((Path(__file__).resolve().parents[1] / 'config.luxembourg.json').read_text())
        settings.update(aoi='aoi.gpkg', country_mask='country.gpkg', block_size=32,
                        processed_tile_size_pixels=32)
        write_json(self.root / 'config.json', settings)
        self.config = load_config(self.root / 'config.json')

    def vector(self, name, geometry):
        path = self.root / name
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(path)) as ds:
            layer = ds.CreateLayer('area', geometry.GetSpatialReference(), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(geometry)
            layer.CreateFeature(feature)
        return path

    def native(self, *, dtype=gdal.GDT_Float64, epsg=2169, nodata=-9999,
               transform=TRANSFORM, cog=True):
        path = source_path(self.config)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gdal.GetDriverByName('GTiff').Create(str(self.root / 'native.tif'), 600, 600, 1, dtype) as ds:
            ds.SetProjection(srs(epsg).ExportToWkt())
            ds.SetGeoTransform(transform)
            values = np.full((600, 600), -12., dtype='float64')
            values[100:200, 100:200] = nodata
            values[300:400, 100:200] = 0
            ds.GetRasterBand(1).SetNoDataValue(nodata)
            ds.GetRasterBand(1).WriteArray(values)
            ds.BuildOverviews('NEAREST', [2])
            ds.GetRasterBand(1).GetOverview(0).Fill(12345)
        with gdal.Translate(str(path), str(self.root / 'native.tif'), format='COG' if cog else 'GTiff'):
            pass
        return path

    def fixture_contract(self, path):
        # Only the national size/extent contract is scaled for fixtures. GDAL
        # opening, dtype/CRS/NoData/COG validation and processing all run normally.
        stack = ExitStack()
        stack.enter_context(patch(MODULE + 'SOURCE_BYTES', path.stat().st_size))
        stack.enter_context(patch('dtm.countries.luxembourg.acquisition.SOURCE_BYTES', path.stat().st_size))
        stack.enter_context(patch(MODULE + 'SOURCE_SHAPE', (600, 600)))
        stack.enter_context(patch(MODULE + 'SOURCE_TRANSFORM', TRANSFORM))
        return stack

    def test_offline_plan_and_paths(self):
        with patch('requests.Session.get') as network, patch(MODULE + 'gdal.Open') as source:
            result = execute(self.config, 'plan')
        network.assert_not_called()
        source.assert_not_called()
        self.assertEqual(source_path(self.config), raw_directory(self.config) / 'MNT_Lidar2024.tif')
        self.assertEqual(result['metadata_requests'], 0)
        self.assertEqual(self.config['country_mask'], str(self.root / 'country.gpkg'))
        self.assertEqual(result['target_grid']['transform'][1], 5)

    def test_nonintersection_and_disabled_skip_before_source_or_reference_access(self):
        outside = rectangle([80000, 100000, 80100, 100100])
        outside.AssignSpatialReference(srs(2169))
        config = deepcopy(self.config)
        config['aoi'] = str(self.vector('outside.gpkg', outside))
        config['target']['reference_raster'] = str(self.root / 'missing_reference.tif')
        for mode in ('yes', 'probe', 'plan'):
            with self.subTest(mode=mode), patch(MODULE + 'gdal.Open') as source, patch('dtm.coordinator.command') as command:
                result = execute(config, mode)
                self.assertTrue(result.get('status') == 'skipped' or result['source']['skip_reason'])
                source.assert_not_called()
                command.assert_not_called()
        config.update(enabled=False, aoi=self.config['aoi'], country_mask='missing_country.gpkg')
        self.assertEqual(execute(config, 'yes')['status'], 'skipped')
        self.assertFalse((self.root / 'data').exists())

    def test_configuration_rejects_remote_sources_filling_and_fresh_download(self):
        for key, value in [('reuse_cache', False), ('enabled', 'false'),
                           ('hole_filling', {'enabled': True}), ('processed_tile_size_pixels', 0)]:
            config = {**self.config, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(config)
        for path in ('/vsicurl/https://example.invalid/a.tif', 'https://example.invalid/a.tif'):
            config = deepcopy(self.config)
            config['source']['path'] = path
            with self.assertRaisesRegex(ValueError, 'local cached COG'):
                validate_config(config)

    def test_missing_incomplete_and_wrong_source_metadata(self):
        path = self.native()
        with self.assertRaisesRegex(ValueError, 'complete original file'):
            validate_native(path)
        with self.fixture_contract(path):
            self.assertEqual(validate_native(path)['dtype'], 'Float64')
            with patch(MODULE + 'SOURCE_SHAPE', (601, 600)), self.assertRaisesRegex(ValueError, 'dimensions'):
                validate_native(path)
            with path.open('r+b') as stream:
                stream.truncate(path.stat().st_size - 1)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                validate_native(path)
        for kwargs, reason in [({'dtype': gdal.GDT_Float32}, 'Float64'),
                               ({'nodata': -32768}, 'NoData'), ({'epsg': 25832}, 'EPSG:2169'),
                               ({'transform': (70001, .5, 0, 100300, 0, -.5)}, 'pixel grid'),
                               ({'cog': False}, 'COG layout')]:
            with self.subTest(kwargs=kwargs):
                path = self.native(**kwargs)
                with self.fixture_contract(path), self.assertRaisesRegex(ValueError, reason):
                    validate_native(path)
        path.write_bytes(b'not a TIFF')
        with self.fixture_contract(path), self.assertRaisesRegex(ValueError, 'Invalid or incomplete'):
            validate_native(path)

    def test_missing_source_downloads_validates_and_is_reused(self):
        path = self.native()
        payload = path.read_bytes()
        source_plan = plan(self.geometry, self.config)
        response = Mock()
        response.iter_content.return_value = [payload[:100], payload[100:]]
        with self.fixture_contract(path), patch('requests.Session.get') as get:
            path.unlink()
            get.return_value.__enter__.return_value = response
            self.assertEqual(download(self.config, source_plan, self.root), [path])
            self.assertEqual(download(self.config, source_plan, self.root), [path])
        get.assert_called_once_with(self.config['source']['url'], stream=True,
                                    timeout=(30, self.config['timeout_seconds']))
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse(path.with_suffix('.tif.part').exists())
        self.assertTrue(receipt_path(path, self.config).is_file())

    def test_download_retries_truncation_and_preserves_failed_or_interrupted_transfers(self):
        path = self.native()
        payload = path.read_bytes()
        source_plan = plan(self.geometry, self.config)
        response = Mock()
        response.iter_content.side_effect = [[payload[:100]], [payload]]
        config = {**self.config, 'download_attempts': 2}
        with self.fixture_contract(path), patch('requests.Session.get') as get, patch('time.sleep'):
            path.unlink()
            get.return_value.__enter__.return_value = response
            self.assertEqual(download(config, source_plan, self.root), [path])
            self.assertEqual(get.call_count, 2)
        for failure in (requests.ConnectionError('disconnected'), KeyboardInterrupt()):
            path.unlink(missing_ok=True)
            def interrupted(chunk_size):
                yield payload[:100]
                raise failure
            response.iter_content.side_effect = interrupted
            with self.subTest(failure=type(failure).__name__), patch('requests.Session.get') as get, patch('time.sleep'):
                get.return_value.__enter__.return_value = response
                expected = KeyboardInterrupt if isinstance(failure, KeyboardInterrupt) else RuntimeError
                with self.assertRaises(expected):
                    download(config, source_plan, self.root)
                self.assertEqual(get.call_count, 1 if expected is KeyboardInterrupt else 2)
            self.assertFalse(path.exists())
            self.assertEqual(path.with_suffix('.tif.part').read_bytes(), payload[:100])

    def test_complete_download_validation_failure_preserved_and_reused_after_fix(self):
        path = self.native()
        payload = path.read_bytes()
        response = Mock()
        response.iter_content.return_value = [payload]
        source_plan = plan(self.geometry, self.config)
        with self.fixture_contract(path), patch('requests.Session.get') as get:
            path.unlink()
            get.return_value.__enter__.return_value = response
            with patch('dtm.countries.luxembourg.acquisition.validate_native', side_effect=ValueError('CRS mismatch')):
                with self.assertRaisesRegex(ValueError, 'CRS mismatch'):
                    download(self.config, source_plan, self.root)
                self.assertEqual(get.call_count, 1)
                self.assertEqual(path.with_suffix('.tif.part').read_bytes(), payload)
                # Even a second invocation must not overwrite the complete part.
                with self.assertRaisesRegex(ValueError, 'CRS mismatch'):
                    download(self.config, source_plan, self.root)
                self.assertEqual(get.call_count, 1)
            self.assertEqual(download(self.config, source_plan, self.root), [path])
            self.assertEqual(get.call_count, 1)
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse(path.with_suffix('.tif.part').exists())

    def test_official_crs_axis_order_is_accepted_but_wrong_parameters_rejected(self):
        # Captured from the actual public national COG, not exported from EPSG.
        from osgeo import osr
        wkt = (Path(__file__).parent / 'fixtures/luxembourg_source.wkt').read_text(encoding='utf-8-sig')
        actual = osr.SpatialReference(wkt=wkt)
        self.assertFalse(actual.IsSame(srs(2169)))
        path = self.native()
        info = gdal.Open(str(path))
        source = Mock(wraps=info)
        source.RasterCount, source.RasterXSize, source.RasterYSize = 1, 600, 600
        source.GetSpatialRef.return_value = actual
        source.GetProjection.return_value = wkt
        # Avoid the GeoTIFF writer normalizing the captured CRS back to EPSG.
        with self.fixture_contract(path), patch(MODULE + 'gdal.Open') as opened, patch(MODULE + 'grid', return_value={}):
            opened.return_value.__enter__.return_value = source
            opened.return_value.GetGeoTransform.return_value = TRANSFORM
            validate_native(path)
            actual.SetProjParm('false_easting', 90000)
            with self.assertRaisesRegex(ValueError, 'projection and datum'):
                validate_native(path)
        info.Close()

    def test_unavailable_source_and_skipped_acquisition(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError('404 Not Found')
        with patch('requests.Session.get') as get:
            self.assertEqual(download(self.config, {'skip_reason': 'outside'}, self.root), [])
            get.assert_not_called()
            get.return_value.__enter__.return_value = response
            with self.assertRaisesRegex(RuntimeError, 'Failed to download Luxembourg.*404'):
                download({**self.config, 'download_attempts': 1}, plan(self.geometry, self.config), self.root)
        self.assertFalse(source_path(self.config).exists())
        self.assertFalse(receipt_path(source_path(self.config), self.config).exists())

    def test_two_aoi_runs_reuse_one_source_and_keep_receipts_in_logs(self):
        path = self.native()
        # An externally populated cache is used in place, without sidecar writes.
        external = self.root / 'external' / path.name
        external.parent.mkdir()
        path.replace(external)
        self.config['source']['path'] = str(external)
        original = sha256(external)
        with self.fixture_contract(external), patch('requests.Session.get') as network:
            first = execute(self.config, 'yes')
            smaller = rectangle([70110, 100110, 70160, 100160])
            smaller.AssignSpatialReference(srs(2169))
            config = {**self.config, 'aoi': str(self.vector('smaller.gpkg', smaller))}
            second = execute(config, 'yes')
        network.assert_not_called()
        self.assertEqual(first['cached_source'], second['cached_source'])
        self.assertNotEqual(first['prepared_raster'], second['prepared_raster'])
        self.assertNotEqual(first['grid']['cols'], second['grid']['cols'])
        self.assertEqual(sha256(external), original)
        self.assertEqual(list(external.parent.iterdir()), [external])
        receipt = receipt_path(external, self.config)
        self.assertTrue(receipt.is_relative_to(self.root / 'logs'))
        self.assertFalse(json.loads(receipt.read_text())['checksum_verified'])
        manifest = json.loads((Path(second['log_directory']) / 'source_manifest.json').read_text())
        self.assertEqual(len(manifest['tiles']), 1)

    def test_exact_reference_mask_nodata_heights_and_cog(self):
        path = self.native()
        original = sha256(path)
        # Reference has deliberate padding: output must retain its exact bounds.
        padded = self.geometry.Buffer(20)
        padded.AssignSpatialReference(srs(2169))
        reference = write_reference(plan_grid(padded, {'resolution': 5}), self.root / 'reference.vrt')
        with self.fixture_contract(path), patch(MODULE + 'gdal.Warp', wraps=gdal.Warp) as warp:
            result = prepare([path], self.geometry, reference, self.root / 'run', self.config)
        warp.assert_called_once()
        verify_alignment(result['prepared_raster'], reference)
        self.assertEqual(original, sha256(path))
        self.assertGreater(result['missing_cell_count'], 0)
        self.assertGreater(result['processed_tiles']['count'], 1)
        with gdal.Open(result['prepared_raster']) as ds, gdal.Open(result['aoi_mask']) as mask:
            values = ds.ReadAsArray()
            valid = values != -9999
            self.assertEqual(ds.GetRasterBand(1).DataType, gdal.GDT_Float32)
            self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), -9999)
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            self.assertEqual(ds.GetMetadataItem('SOURCE_VERSION'), self.config['source']['version'])
            self.assertEqual(ds.GetMetadataItem('VERTICAL_HARMONISATION'), 'none')
            self.assertFalse(validate(ds, full_check=True)[1])
            self.assertTrue(np.all(values[mask.ReadAsArray() == 0] == -9999))
            # Valid negative/zero elevations survive, NoData does not contaminate
            # averages, and deliberately poisoned source overviews are ignored.
            self.assertAlmostEqual(float(values[valid].min()), -12, places=5)
            self.assertEqual(float(values[valid].max()), 0)
            for x, y in [(70250, 100150), (70075, 100075), (70010, 100150)]:
                point = ogr.CreateGeometryFromWkt(f'POINT ({x} {y})')
                point.AssignSpatialReference(srs(2169))
                point = project(point, srs(25832))
                gt = ds.GetGeoTransform()
                col, row = int((point.GetX() - gt[0]) / 5), int((gt[3] - point.GetY()) / 5)
                self.assertEqual(values[row, col], -9999)


if __name__ == '__main__':
    unittest.main()
