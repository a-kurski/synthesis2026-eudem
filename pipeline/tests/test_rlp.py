"""RLP catalogue, download integrity, compound CRS and shared-processing checks."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from osgeo import gdal, ogr, osr

from dtm.acquire import cached, download_tile, sha256
from dtm.coordinator import execute, load_config
from dtm.countries.germany import rlp
from dtm.countries.germany.rlp.acquisition import download, select_tiles
from dtm.geo import rectangle, srs, validate_tile, verify_alignment
from dtm.paths import scoped_root, raw_directory
from dtm.target_grid import plan_grid, write_reference


class RLPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_rlp_')
        self.root = Path(self.temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'config.germany.rlp.json')
        self.config.update(output_root=str(self.root / 'outputs'), logs_dir=str(self.root / 'logs'),
                           cache_root=str(self.root / 'cache'), request_pause_seconds=0, download_attempts=1)
        self.geometry = rectangle([423005, 5632985, 423015, 5632995])
        self.geometry.AssignSpatialReference(srs(25832))
        self.tile = {'id': 'dgm1_32_423_5632_1_rp_2024', 'bounds': [423000, 5632000, 424000, 5633000],
                     'url': 'https://example.invalid/dgm1_32_423_5632_1_rp_2024.tif',
                     'size': 1, 'sha256': 'a' * 64}
        self.plan = rlp.plan(self.geometry, self.config)

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self, tiles=None):
        entries = ''.join(f'<file name="{t["id"]}.tif"><size>{t["size"]}</size>'
                          f'<hash type="sha-256">{t["sha256"]}</hash><url>{t["url"]}</url></file>'
                          for t in (tiles or [self.tile]))
        return ('<metalink xmlns="urn:ietf:params:xml:ns:metalink">' + entries + '</metalink>').encode()

    def raw(self, vertical=7837):
        path = self.root / 'source.tif'
        crs = osr.SpatialReference()
        crs.SetCompoundCS('UTM32 and heights', srs(25832), srs(vertical))
        rows, cols = np.indices((1000, 1000))
        self.values = (rows * .25 + cols * .5 + 12).astype('float32')
        self.values[5:10, 5:10] = -9999
        with gdal.GetDriverByName('GTiff').Create(str(path), 1000, 1000, 1, gdal.GDT_Float32) as ds:
            ds.SetSpatialRef(crs)
            ds.SetGeoTransform((423000, 1, 0, 5633000, 0, -1))
            ds.GetRasterBand(1).SetNoDataValue(-9999)
            ds.GetRasterBand(1).WriteArray(self.values)
        self.tile.update(size=path.stat().st_size, sha256=sha256(path))
        return path

    def response_session(self, content):
        response = MagicMock()
        response.__enter__.return_value = response
        response.content = content
        response.iter_content.return_value = [content]
        response.headers = {}
        response.url = self.tile['url']
        session = MagicMock()
        session.get.return_value = response
        return session

    def test_catalogue_selection_versions_and_malformed_metadata(self):
        old = {**self.tile, 'id': self.tile['id'].replace('2024', '2023'),
               'url': self.tile['url'].replace('2024', '2023')}
        outside = {**self.tile, 'id': self.tile['id'].replace('_423_', '_424_'),
                   'url': self.tile['url'].replace('_423_', '_424_')}
        selected = select_tiles(self.manifest([old, outside, self.tile, self.tile]), self.plan)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['id'], self.tile['id'])
        self.assertEqual(selected[0]['bounds'], self.tile['bounds'])
        with_sidecar = self.manifest().replace(b'</metalink>', b'<file name="tile.tfw"/></metalink>')
        self.assertEqual(select_tiles(with_sidecar, self.plan), selected)
        for bad in [b'<html/>', self.manifest().replace(b'a' * 64, b'bad'), self.manifest([outside])]:
            with self.assertRaises(ValueError):
                select_tiles(bad, self.plan)

    def test_direct_download_cache_integrity_and_atomic_failure(self):
        raw = self.raw()
        session = self.response_session(raw.read_bytes())
        directory = self.root / 'download'
        directory.mkdir()
        output = download_tile(session, self.config['source'], self.tile, directory, self.config)
        self.assertEqual(session.get.call_args.args[0], self.tile['url'])
        self.assertIsNone(session.get.call_args.kwargs['params'])
        self.assertTrue(cached(output, self.config['source'], self.tile))
        revised = {**self.tile, 'sha256': 'b' * 64}
        self.assertFalse(cached(output, self.config['source'], revised))
        with self.assertRaisesRegex(RuntimeError, 'Metalink size/SHA-256'):
            download_tile(session, self.config['source'], revised, directory, self.config)
        self.assertEqual(sha256(output), self.tile['sha256'])
        self.assertFalse(output.with_suffix('.tif.part').exists())

    def test_compound_crs_nodata_extent_and_resolution_validation(self):
        raw = self.raw()
        self.assertGreater(validate_tile(raw, self.config['source'], self.tile)['valid_cells'], 0)
        with self.assertRaisesRegex(ValueError, 'extent'):
            validate_tile(raw, self.config['source'], {**self.tile, 'bounds': [0, 0, 1000, 1000]})
        with gdal.Open(str(raw), gdal.GA_Update) as ds:
            ds.GetRasterBand(1).SetNoDataValue(-32768)
        with self.assertRaisesRegex(ValueError, 'metadata'):
            validate_tile(raw, self.config['source'], self.tile)
        raw = self.raw(vertical=5783)
        with self.assertRaisesRegex(ValueError, 'vertical CRS'):
            validate_tile(raw, self.config['source'], self.tile)

    def test_processing_exact_means_and_region_outputs_without_warp(self):
        raw = self.raw()
        digest = sha256(raw)
        reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'target.vrt')
        with patch('osgeo.gdal.Warp', side_effect=AssertionError('Unexpected warp')):
            result = rlp.prepare([raw], self.geometry, reference, self.root / 'run', self.config)
        expected = self.values[5:15, 5:15].reshape(2, 5, 2, 5).mean(axis=(1, 3))
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertIn('EPSG:7837', ds.GetMetadataItem('VERTICAL_DATUM_NOTE'))
        self.assertEqual(Path(result['prepared_raster']).name, 'rlp.tif')
        self.assertIn('raw_rlp_tiles', result)
        self.assertEqual(result['valid_cell_count'], 3)
        self.assertEqual(sha256(raw), digest)
        verify_alignment(result['prepared_raster'], reference)

    def test_cache_reuse_and_fresh_download_are_region_scoped(self):
        raw = self.raw()
        previous = raw_directory(self.config)
        previous.mkdir(parents=True)
        output = download_tile(self.response_session(raw.read_bytes()), self.config['source'],
                               self.tile, previous, self.config)
        with patch('dtm.countries.germany.rlp.acquisition.catalogue', return_value=[self.tile]), \
             patch('dtm.countries.germany.rlp.acquisition.download_tile') as fetch:
            self.assertEqual(download(self.config, self.plan, self.root / 'next'), [output])
            fetch.assert_not_called()
            self.config['reuse_cache'] = False
            download(self.config, self.plan, self.root / 'fresh')
            self.assertEqual(fetch.call_args.args[3], raw_directory(self.config))

    def test_coordinator_offline_plan_and_config_validation(self):
        path = self.root / 'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(path)) as ds:
            layer = ds.CreateLayer('rlp', srs(25832), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        self.config['aoi'] = str(path)
        with patch('requests.Session.get') as get:
            result = execute(self.config, 'plan')
        get.assert_not_called()
        self.assertEqual(result['region'], 'rlp')
        self.assertEqual(result['metadata_requests'], 1)
        self.assertTrue(result['source']['catalogue_pending'])
        for key, value in [('target', {'resolution': 1}), ('hole_filling', {'enabled': True})]:
            config = deepcopy(self.config)
            config[key] = value
            with self.assertRaises(ValueError):
                rlp.validate_config(config)
