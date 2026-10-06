"""Offline STAC, cache and real GDAL checks for the shared Swiss provider."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np
from osgeo import gdal, ogr
from osgeo_utils.samples.validate_cloud_optimized_geotiff import validate
import requests

from dtm.acquire import sha256, write_json
from dtm.coordinator import COUNTRIES, execute, load_config
from dtm.countries.switzerland import plan
from dtm.countries.switzerland.acquisition import (checksum_digest, discover, download_one,
                                                 manifest, retry_delay, select_items, transfer)
from dtm.countries.switzerland.processing import prepare
from dtm.downloads import RequestGate
from dtm.geo import bounds, project, rectangle, srs, verify_alignment
from dtm.paths import raw_directory, receipt_path, region_lock
from dtm.target_grid import plan_grid, write_reference
from test_preparation import raster


def item(year=2026, spatial='2756-1221'):
    identifier = f'swissalti3d_{year}_{spatial}'
    return {'id': identifier, 'properties': {'datetime': f'{year}-01-01T00:00:00Z'},
            'geometry': json.loads(rectangle([9.50, 47.13, 9.51, 47.14]).ExportToJson()),
            'assets': {'terrain': {'gsd': 2, 'proj:epsg': 2056,
                       'type': 'image/tiff; application=geotiff; profile=cloud-optimized',
                       'href': f'https://example.invalid/{identifier}.tif',
                       'file:checksum': '1220' + 'a' * 64}}}


class SwissTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_swiss_')
        self.root = Path(self.temp.name)
        self.geometry = rectangle([2756100, 1221100, 2756900, 1221900])
        self.geometry.AssignSpatialReference(srs(2056))
        aoi = self.root / 'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
            layer = ds.CreateLayer('aoi', srs(2056), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        settings = json.loads((Path(__file__).resolve().parents[1] / 'config.switzerland.json').read_text())
        settings.update(aoi=str(aoi), request_pause_seconds=0, download_attempts=1,
                        cache_root=str(self.root / 'data'), output_root=str(self.root / 'data'),
                        logs_dir=str(self.root / 'logs'))
        write_json(self.root / 'config.json', settings)
        self.config = load_config(self.root / 'config.json')
        self.area = json.loads(rectangle([9.49, 47.12, 9.53, 47.16]).ExportToJson())

    def tearDown(self):
        self.temp.cleanup()

    def native(self, name='source.tif', value=-12):
        return raster(self.root / name, np.full((500, 500), value), epsg=2056,
                      transform=(2756000, 2, 0, 1222000, 0, -2))

    def test_latest_selection_order_assets_and_footprint(self):
        older, newer, other = item(2019), item(), item(2025, '2757-1221')
        older['properties']['updated'] = '2099-01-01T00:00:00Z'
        newer['assets']['half'] = {**newer['assets']['terrain'], 'gsd': .5}
        newer['assets']['xyz'] = {**newer['assets']['terrain'], 'type': 'application/x.ascii-xyz+zip'}
        outside = item(2026, '2758-1221')
        outside['geometry'] = json.loads(rectangle([10, 48, 11, 49]).ExportToJson())
        first = select_items([older, newer, other, outside], self.area)
        self.assertEqual(first, select_items([outside, other, newer, older], self.area))
        self.assertEqual([t['item_id'] for t in first], [newer['id'], other['id']])
        self.assertEqual(first[0]['asset_name'], 'terrain')
        del newer['assets']['terrain']
        with self.assertRaisesRegex(ValueError, 'Newest edition lacks'):
            select_items([older, newer], self.area)

    def test_schema_ties_checksum_validation(self):
        for value in ('xyz', '1320' + 'a' * 64, '1220abcd'):
            with self.assertRaises(ValueError):
                checksum_digest(value)
        self.assertEqual(checksum_digest('1220' + 'A' * 64), 'a' * 64)
        self.assertIsNone(checksum_digest(None))
        bad = item()
        bad['properties']['datetime'] = '2025-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'year/date'):
            select_items([bad], self.area)
        conflict = item()
        conflict['assets']['terrain']['href'] += '?different'
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            select_items([item(), conflict], self.area)
        bad['id'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            select_items([bad], self.area)

    def test_pagination_matches_single_page(self):
        source = {'items_url': 'https://example.invalid/items', 'query_geometry': self.area,
                  'query_bounds_wgs84': [9.49, 47.12, 9.53, 47.16]}
        pages = [{'type': 'FeatureCollection', 'features': [item()],
                  'links': [{'rel': 'next', 'href': '?cursor=opaque'}]},
                 {'type': 'FeatureCollection', 'features': [item(2019)], 'links': []}]
        with patch('dtm.countries.switzerland.acquisition.transfer', side_effect=pages) as fetch:
            selected = discover(Mock(), source, self.config)
        self.assertEqual(selected, select_items([item(2019), item()], self.area))
        self.assertEqual(fetch.call_args_list[1].args[1], 'https://example.invalid/items?cursor=opaque')
        self.assertIsNone(fetch.call_args_list[1].kwargs['params'])

    def test_manifest_resume_freezes_editions_and_rejects_other_aoi(self):
        source = plan(self.geometry, self.config)
        source['query_geometry'] = self.area
        with patch('dtm.countries.switzerland.acquisition.discover', return_value=select_items([item(2019)], self.area)):
            saved = manifest(self.config, source, self.root)
        resume = {**self.config, 'source_manifest': str(self.root / 'swissalti3d_manifest.json')}
        with patch('requests.Session.get') as get:
            self.assertEqual(manifest(resume, source, self.root), saved)
        get.assert_not_called()
        with patch('dtm.countries.switzerland.acquisition.discover', return_value=select_items([item()], self.area)):
            self.assertNotEqual(manifest(self.config, source, self.root), saved)
        source['query_bounds_wgs84'][0] += 1
        with self.assertRaisesRegex(ValueError, 'does not match'):
            manifest(resume, source, self.root)

    def test_offline_plan_and_shared_cache_lock(self):
        with patch('requests.Session.get') as get:
            result = execute(self.config, 'plan')
        get.assert_not_called()
        self.assertTrue(result['source']['discovery_pending'])
        other = {**self.config, 'country': 'liechtenstein'}
        self.assertIs(COUNTRIES['switzerland'], COUNTRIES['liechtenstein'])
        self.assertEqual(raw_directory(self.config), raw_directory(other))
        with region_lock(self.config):
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                with region_lock(other):
                    pass

    def test_download_checksum_atomicity_and_cross_country_reuse(self):
        source = self.native()
        record = item()
        record['assets']['terrain']['file:checksum'] = '1220' + sha256(source)
        tile = select_items([record], self.area)[0]
        directory = raw_directory(self.config)
        directory.mkdir(parents=True)
        gate, stopped = RequestGate(0), threading.Event()
        response = Mock()
        response.iter_content.return_value = [source.read_bytes()]
        with patch('dtm.countries.switzerland.acquisition.transfer', side_effect=lambda s, u, c, consume, **kw: consume(response)) as fetch:
            path = download_one(tile, directory, self.config, gate, stopped)
            other = {**self.config, 'country': 'liechtenstein'}
            self.assertEqual(download_one(tile, directory, other, gate, stopped), path)
            fetch.assert_called_once()
        self.assertEqual(receipt_path(path, self.config), receipt_path(path, other))
        before = path.read_bytes()
        response.iter_content.return_value = [b'corrupt']
        with patch('dtm.countries.switzerland.acquisition.transfer', side_effect=lambda s, u, c, consume, **kw: consume(response)):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                download_one(tile, directory, {**self.config, 'reuse_cache': False}, gate, stopped)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(path.with_suffix('.tif.part').exists())

    def test_retry_after_and_permanent_http_error(self):
        self.assertEqual(retry_delay(Mock(headers={'Retry-After': '7'}), 1), 7)
        session = Mock()
        bad, good = Mock(status_code=429, headers={'Retry-After': '3'}), Mock(status_code=200)
        bad.raise_for_status.side_effect = requests.HTTPError('busy')
        session.get.return_value.__enter__ = Mock(side_effect=[bad, good])
        session.get.return_value.__exit__ = Mock(return_value=False)
        with patch('time.sleep') as sleep:
            transfer(session, 'https://example.invalid', {**self.config, 'download_attempts': 2}, lambda r: 'ok')
        sleep.assert_called_once_with(3)
        bad.status_code = 404
        session.get.return_value.__enter__ = Mock(return_value=bad)
        with patch('time.sleep') as sleep:
            with self.assertRaises(requests.HTTPError):
                transfer(session, 'https://example.invalid', {**self.config, 'download_attempts': 2}, lambda r: 'ok')
        sleep.assert_not_called()

    def test_processing_grid_nodata_heights_overviews_and_cog(self):
        source = self.native()
        with gdal.Open(str(source), gdal.GA_Update) as ds:
            values = ds.ReadAsArray()
            values[100:200, 100:200] = -32768
            values[250:350, 250:350] = 0
            ds.GetRasterBand(1).SetNoDataValue(-32768)
            ds.GetRasterBand(1).WriteArray(values)
            ds.BuildOverviews('NEAREST', [2])
            ds.GetRasterBand(1).GetOverview(0).Fill(12345)
        original = sha256(source)
        target = write_reference(plan_grid(self.geometry, {'resolution': 5}), self.root / 'target.vrt')
        result = prepare([source], self.geometry, target, self.root / 'run', self.config)
        verify_alignment(result['prepared_raster'], target)
        self.assertEqual(sha256(source), original)
        self.assertGreater(result['missing_cell_count'], 0)
        self.assertTrue(result['native_mosaic'].endswith('.vrt'))
        with gdal.Open(result['prepared_raster']) as ds:
            values = ds.ReadAsArray()
            valid = values != -9999
            self.assertEqual(ds.GetRasterBand(1).DataType, gdal.GDT_Float32)
            self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), -9999)
            self.assertEqual(ds.GetMetadataItem('COMPRESSION', 'IMAGE_STRUCTURE'), 'DEFLATE')
            self.assertEqual(ds.GetMetadataItem('ATTRIBUTION'), '©swisstopo')
            self.assertTrue(np.any(values == 0))
            self.assertAlmostEqual(float(values[valid].min()), -12, places=5)
            self.assertLessEqual(float(values[valid].max()), 0)
            self.assertFalse(validate(ds, full_check=True)[1])
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            prepare([source, source], self.geometry, target, self.root / 'duplicate', self.config)
