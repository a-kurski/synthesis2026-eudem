"""Saarland archive integrity, native-grid discovery and weighted alignment."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from osgeo import gdal, ogr

from dtm.acquire import sha256
from dtm.coordinator import execute, load_config
from dtm.countries.germany import saarland
from dtm.countries.germany.saarland.acquisition import archive, download, select_tiles, verify_archive
from dtm.countries.germany.saarland.processing import validate_native
from dtm.geo import rectangle, srs, verify_alignment
from dtm.paths import scoped_root, raw_directory, receipt_path
from dtm.target_grid import plan_grid, write_reference


class SaarlandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_saarland_')
        self.root = Path(self.temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'config.germany.saarland.json')
        self.config.update(output_root=str(self.root / 'outputs'), logs_dir=str(self.root / 'logs'),
                           cache_root=str(self.root / 'cache'), download_attempts=1)
        self.geometry = rectangle([375000, 5480000, 375010, 5480010])
        self.geometry.AssignSpatialReference(srs(25832))
        self.plan = saarland.plan(self.geometry, self.config)
        self.reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'target.vrt')

    def tearDown(self):
        self.temp.cleanup()

    def raw(self, name='native.tif', values=None, left=374999.5):
        if values is None:
            rows, cols = np.indices((11, 11))
            values = (rows ** 2 + cols * 3 + 10).astype('float32')
        path = self.root / name
        with gdal.GetDriverByName('GTiff').Create(str(path), values.shape[1], values.shape[0], 1, gdal.GDT_Float32) as ds:
            ds.SetSpatialRef(srs(25832))
            ds.SetGeoTransform((left, 1, 0, 5480010.5, 0, -1))
            ds.GetRasterBand(1).SetNoDataValue(-1e10)
            ds.GetRasterBand(1).WriteArray(values)
        return path

    def package(self, members):
        path = scoped_root(self.config, 'cache_root') / 'source_archive/desaarland.tar'
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, 'w') as tf:
            for name, content in members:
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                tf.addfile(entry, io.BytesIO(content))
        self.config['source'].update(size=path.stat().st_size, md5=hashlib.md5(path.read_bytes()).hexdigest())
        return path

    def test_half_pixel_alignment_uses_area_weights_and_source_nodata(self):
        rows, cols = np.indices((11, 11))
        values = (rows ** 2 + cols * 3 + 10).astype('float32')
        values[:6, :6] = -1e10
        raw = self.raw(values=values)
        digest = sha256(raw)
        result = saarland.prepare([raw], self.geometry, self.reference, self.root / 'run', self.config)
        weights = np.outer([.5, 1, 1, 1, 1, .5], [.5, 1, 1, 1, 1, .5])
        expected = np.full((2, 2), -9999, dtype='float32')
        for row in range(2):
            for col in range(2):
                block = values[row * 5:row * 5 + 6, col * 5:col * 5 + 6]
                valid = block != -1e10
                if valid.any():
                    expected[row, col] = (block[valid] * weights[valid]).sum() / weights[valid].sum()
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), -9999)
            self.assertIn('unverified', ds.GetMetadataItem('VERTICAL_DATUM_NOTE'))
        self.assertEqual(sha256(raw), digest)
        self.assertIsNone(result['vertical_datum'])
        self.assertFalse(result['raster_reprojection'])
        self.assertTrue(result['separate_alignment'])
        verify_alignment(result['prepared_raster'], self.reference)

    def test_overlapping_border_pixels_match_single_mosaic(self):
        rows, cols = np.indices((11, 11))
        values = (rows ** 2 + cols * 3 + 10).astype('float32')
        single = saarland.prepare([self.raw(values=values)], self.geometry, self.reference, self.root / 'single', self.config)
        left = self.raw('left.tif', values[:, :6])
        right = self.raw('right.tif', values[:, 5:], left=375004.5)
        split = saarland.prepare([left, right], self.geometry, self.reference, self.root / 'split', self.config)
        with gdal.Open(single['prepared_raster']) as a, gdal.Open(split['prepared_raster']) as b:
            np.testing.assert_array_equal(a.ReadAsArray(), b.ReadAsArray())

    def test_archive_selection_extraction_cache_and_metadata(self):
        near, far = self.raw(), self.raw('far.tif', left=400000.5)
        package = self.package([('files/near.tif', near.read_bytes()), ('files/far.tif', far.read_bytes()),
                                ('metadata.json', b'{"producer":"LVGL"}')])
        log = self.root / 'first'
        log.mkdir()
        with patch('requests.Session.get') as get:
            paths = download(self.config, self.plan, log)
            get.assert_not_called()
        self.assertEqual([p.name for p in paths], ['near.tif'])
        self.assertTrue((log / 'metadata.json').exists())
        self.assertTrue(verify_archive(package, self.config['source']))
        next_log = self.root / 'next'
        next_log.mkdir()
        self.assertEqual(download(self.config, self.plan, next_log), paths)
        paths[0].write_bytes(b'corrupted')
        with self.assertRaises(RuntimeError):
            download(self.config, self.plan, next_log)
        paths[0].unlink()
        repaired = download(self.config, self.plan, next_log)
        self.assertEqual(sha256(repaired[0]), sha256(near))
        self.assertEqual(repaired[0], paths[0])

    def test_manual_local_tiffs_need_neither_receipts_nor_archive(self):
        raw = raw_directory(self.config)
        raw.mkdir(parents=True)
        near = raw / 'near.tif'
        near.write_bytes(self.raw().read_bytes())
        (raw / 'far.tif').write_bytes(self.raw('far.tif', left=400000.5).read_bytes())
        log = self.root / 'local_run'
        log.mkdir()
        with patch('dtm.countries.germany.saarland.acquisition.archive') as get_archive, \
             patch('requests.Session.get') as get:
            self.assertEqual(download(self.config, self.plan, log), [near])
            self.assertEqual(download(self.config, self.plan, log), [near])
            get_archive.assert_not_called()
            get.assert_not_called()
        receipt = json.loads(receipt_path(near, self.config).read_text())
        self.assertFalse(receipt['archive_verified'])
        self.assertEqual(receipt['sha256'], sha256(near))
        with gdal.Open(str(near), gdal.GA_Update) as ds:
            ds.GetRasterBand(1).Fill(42)
        with self.assertRaisesRegex(ValueError, 'differs from its receipt'):
            download(self.config, self.plan, log)

    def test_fresh_archive_download_and_checksum_failure(self):
        package = self.package([('files/source.tif', self.raw().read_bytes())])
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [package.read_bytes()]
        self.config['reuse_cache'] = False
        with patch('requests.Session.get', return_value=response) as get:
            path = archive(self.config, self.root / 'fresh')
            get.assert_called_once()
        self.assertEqual(path, package)
        self.assertTrue(verify_archive(path, self.config['source']))
        response.iter_content.return_value = [b'bad']
        with patch('requests.Session.get', return_value=response), self.assertRaisesRegex(RuntimeError, 'MD5'):
            archive(self.config, self.root / 'bad')
        self.assertTrue(verify_archive(package, self.config['source']))

    def test_unsafe_archive_and_unexpected_native_grid_are_rejected(self):
        raw = self.raw()
        package = self.package([('../outside.tif', raw.read_bytes())])
        with tarfile.open(package) as tf, self.assertRaisesRegex(ValueError, 'Unsafe'):
            select_tiles(tf, package, self.plan)
        shifted = self.raw('integer.tif', left=375000)
        with self.assertRaisesRegex(ValueError, 'half-metre'):
            validate_native(shifted)
        with gdal.Open(str(raw), gdal.GA_Update) as ds:
            ds.GetRasterBand(1).DeleteNoDataValue()
        with self.assertRaisesRegex(ValueError, 'NoData'):
            validate_native(raw)

    def test_offline_plan_and_common_target_validation(self):
        aoi = self.root / 'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
            layer = ds.CreateLayer('saarland', srs(25832), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        self.config['aoi'] = str(aoi)
        with patch('requests.Session.get') as get:
            result = execute(self.config, 'plan')
            get.assert_not_called()
        self.assertEqual(result['region'], 'saarland')
        for key, value in [('target', {'resolution': 1}), ('hole_filling', {'enabled': True})]:
            config = deepcopy(self.config)
            config[key] = value
            with self.assertRaises(ValueError):
                saarland.validate_config(config)
