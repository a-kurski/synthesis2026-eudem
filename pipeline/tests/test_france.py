"""France contracts: source integrity, cache recovery and exact final grid/mask."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal, ogr

from dtm.coordinator import load_config, execute
from dtm.countries import france
from dtm.countries.france import acquisition as acq
from dtm.countries.france.processing import prepare, validate_native
from dtm.geo import grid, rectangle, srs, verify_alignment, project
from dtm.paths import raw_directory, receipt_path, scoped_root
from dtm.target_grid import plan_grid, write_reference


def ascii_tile(directory, x=980, y=6730, value=123.25, nodata=-99999):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'RGEALTI_FXX_{x:04}_{y:04}_MNT_LAMB93_IGN69.asc'
    # CreateCopy writes the actual centre-based grid as supplied by IGN.
    with gdal.GetDriverByName('MEM').Create('', 1000, 1000, 1, gdal.GDT_Float32) as ds:
        ds.SetGeoTransform((x * 1000 - 2.5, 5, 0, y * 1000 + 2.5, 0, -5))
        ds.GetRasterBand(1).SetNoDataValue(nodata)
        ds.GetRasterBand(1).Fill(value)
        with gdal.GetDriverByName('AAIGrid').CreateCopy(str(path), ds):
            pass
    return path


class FranceTests(unittest.TestCase):
    def test_department_downloads_overlap_and_preserve_order(self):
        self.config['download_workers'] = 2
        rendezvous = threading.Barrier(2)
        sessions = []
        records = [{'department': '67'}, {'department': '68'}]

        def fetch(session, record, config, **kwargs):
            sessions.append(session)
            rendezvous.wait(timeout=10)  # Fails if downloads run sequentially.
            return Path(record['department'] + '.7z')

        with patch.object(acq, 'acquire_archive', side_effect=fetch):
            paths = acq.acquire_archives(records, self.config)
        self.assertEqual(paths, [Path('67.7z'), Path('68.7z')])
        self.assertIsNot(sessions[0], sessions[1])

    def test_department_download_failure_stops_other_workers(self):
        self.config['download_workers'] = 2
        rendezvous = threading.Barrier(2)

        def fetch(session, record, config, **kwargs):
            rendezvous.wait(timeout=10)
            if record['department'] == '67':
                raise ValueError('bad archive checksum')
            self.assertTrue(kwargs['stop_event'].wait(timeout=10))
            return Path('68.7z')

        with patch.object(acq, 'acquire_archive', side_effect=fetch):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                acq.acquire_archives([{'department': '67'}, {'department': '68'}], self.config)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_france_')
        self.root = Path(self.temp.name)
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.france.json').read_text())
        config.update(aoi='aoi.gpkg', cache_root='data', output_root='data', logs_dir='logs',
                      request_pause_seconds=0, download_attempts=1, processed_tile_size_pixels=32)
        config['source']['departments'] = ['90']
        self.geometry = rectangle([981000, 6727000, 981150, 6727150])
        self.geometry.AssignSpatialReference(srs(2154))
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(self.root / 'aoi.gpkg')) as ds:
            layer = ds.CreateLayer('aoi', srs(2154), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps(config))
        self.config = load_config(config_path)
        self.log = self.root / 'run_log'
        self.log.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def tile(self, **kwargs):
        return ascii_tile(raw_directory(self.config) / '90', **kwargs)

    def test_config_and_department_paths(self):
        self.assertEqual(raw_directory(self.config), self.root / 'data' / 'France' / 'raw_tiles')
        path = self.tile()
        self.assertEqual(receipt_path(path, self.config), self.root / 'logs' / 'france' / 'raw_receipts' / '90' / path.with_suffix('.json').name)
        self.config['source']['departments'] = ['../90']
        with self.assertRaisesRegex(ValueError, 'department'):
            france.validate_config(self.config)

    def test_offline_plan_does_not_contact_ign(self):
        with patch.object(acq.requests.Session, 'get', side_effect=AssertionError('Network call')):
            result = execute(self.config, 'plan')
        self.assertEqual(result['source']['crs'], 'EPSG:2154')
        self.assertFalse(scoped_root(self.config, 'output_root').exists())

    def test_local_reuse_reselects_aoi_and_rejects_altered_receipt(self):
        first = self.tile()
        second = self.tile(x=985)
        source_plan = france.plan(self.geometry, self.config)
        with patch.object(acq.requests.Session, 'get', side_effect=AssertionError('Network call')):
            self.assertEqual(france.download(self.config, source_plan, self.log), [first])
            self.assertEqual(france.download(self.config, source_plan, self.log), [first])
            other = rectangle([986000, 6727000, 986100, 6727100])
            other.AssignSpatialReference(srs(2154))
            self.assertEqual(france.download(self.config, france.plan(other, self.config), self.log), [second])
        self.tile(value=124)
        with self.assertRaisesRegex(ValueError, 'receipt'):
            acq.validate_cached(first, self.config)

    def test_incomplete_coverage_uses_available_tiles(self):
        tile = self.tile()
        bigger = rectangle([981000, 6727000, 986100, 6727100])
        bigger.AssignSpatialReference(srs(2154))
        with patch.object(acq, 'department_codes', return_value=[]):
            self.assertEqual(france.download(self.config, france.plan(bigger, self.config), self.log), [tile])
        manifest = json.loads((self.log / 'rge_alti_manifest.json').read_text())
        self.assertGreater(manifest['missing_source_area_m2'], 0)

    def test_partial_output_preserves_full_grid_and_nodata(self):
        tile = self.tile()
        geometry = rectangle([984950, 6727000, 985050, 6727100])
        geometry.AssignSpatialReference(srs(2154))
        reference = write_reference(plan_grid(geometry, self.config['target']), self.root / 'reference.vrt')
        result = prepare([tile], geometry, reference, self.root / 'output', self.config)
        verify_alignment(result['prepared_raster'], reference)
        self.assertEqual(result['coverage_status'], 'partial')
        self.assertGreater(result['missing_source_area_m2'], 0)
        self.assertGreater(result['valid_cell_count'], 0)
        self.assertGreater(result['nodata_cell_count'], 0)
        with gdal.Open(result['prepared_raster']) as ds:
            values = ds.ReadAsArray()
            self.assertTrue(np.any(values == -9999))
            np.testing.assert_allclose(values[values != -9999], 123.25, atol=1e-5)

    def test_no_available_tiles_publishes_empty_aligned_cog(self):
        with patch.object(acq, 'department_codes', return_value=[]):
            self.assertEqual(france.download(self.config, france.plan(self.geometry, self.config), self.log), [])
            self.assertIsNone(france.probe(self.config, france.plan(self.geometry, self.config), self.log))
        reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'reference.vrt')
        result = prepare([], self.geometry, reference, self.root / 'output', self.config)
        verify_alignment(result['prepared_raster'], reference)
        self.assertEqual(result['coverage_status'], 'empty')
        self.assertIsNone(result['native_mosaic'])
        with gdal.Open(result['prepared_raster']) as ds:
            self.assertTrue(np.all(ds.ReadAsArray() == -9999))
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')

    def test_missing_tile_triggers_archive_recovery(self):
        expected = self.root / 'data' / 'France' / 'raw_tiles' / '90' / 'missing.asc'
        record = {'path': str(expected), 'bounds': [980000, 6725000, 985000, 6730000], 'sha256': 'example'}
        with patch.object(acq, 'department_codes', return_value=['90']), \
             patch.object(acq, 'discover_archive', return_value={'department': '90'}), \
             patch.object(acq, 'acquire_archive', return_value=self.root / 'archive.7z') as fetch, \
             patch.object(acq, 'extract_tiles', return_value=[record]):
            self.assertEqual(france.download(self.config, france.plan(self.geometry, self.config), self.log), [expected])
            fetch.assert_called_once()

    def test_native_validation_reads_payload_and_checks_crs(self):
        path = self.tile()
        info = validate_native(path, read_values=True)
        self.assertEqual(info['extent'], acq.filename_bounds(path.name))
        self.assertEqual(info['nodata'], -99999)
        path.with_suffix('.prj').write_text(srs(25832).ExportToWkt())
        with self.assertRaisesRegex(ValueError, 'EPSG:2154'):
            validate_native(path)
        path.with_suffix('.prj').unlink()
        path.write_text('\n'.join(path.read_text().splitlines()[:10]))
        with self.assertRaises((ValueError, RuntimeError)):
            validate_native(path, read_values=True)

    def test_full_pipeline_retains_heights_grid_mask_and_metadata(self):
        path = self.tile()
        # Add a polygon hole so masking is checked inside the output extent too.
        hole = rectangle([981040, 6727040, 981110, 6727110])
        geometry = self.geometry.Difference(hole)
        geometry.AssignSpatialReference(srs(2154))
        reference = write_reference(plan_grid(geometry, self.config['target']), self.root / 'reference.vrt')
        run = self.root / 'output'
        result = prepare([path], geometry, reference, run, self.config)
        final = result['prepared_raster']
        verify_alignment(final, reference)
        with gdal.Open(final) as ds, gdal.Open(result['aoi_mask']) as mask:
            values = ds.ReadAsArray()
            inside = mask.ReadAsArray() != 0
            self.assertTrue(np.all(values[~inside] == -9999))
            np.testing.assert_allclose(values[inside], 123.25, atol=1e-5)
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            self.assertEqual(ds.GetMetadataItem('SOURCE_VERTICAL_CRS'), 'IGN69')
            self.assertEqual(ds.GetMetadataItem('VERTICAL_HARMONISATION'), 'NOT_APPLIED')
            self.assertIn('bilinear', ds.GetMetadataItem('PREPARATION'))
        converted = run / 'processed' / '_work' / ('90_' + path.stem + '.tif')
        with gdal.Open(str(path)) as original, gdal.Open(str(converted)) as tif:
            np.testing.assert_array_equal(original.ReadAsArray(), tif.ReadAsArray())
        self.assertEqual(grid(converted)['nodata'], -99999)

    def test_no_data_is_preserved_and_reported(self):
        path = self.tile(value=-99999)
        reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'reference.vrt')
        result = prepare([path], self.geometry, reference, self.root / 'output', self.config)
        self.assertEqual(result['coverage_status'], 'empty')
        self.assertEqual(result['valid_cell_count'], 0)

    def test_catalogue_pagination_selects_5m_latest_edition(self):
        title = 'RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D090_2021-01-13'
        feed = f'<feed xmlns="{acq.ATOM[1:-1]}" xmlns:g="{acq.GPF[1:-1]}" g:pagecount="2">'
        pages = [(feed + '<entry><title>RGEALTI_2-0_1M_ASC_LAMB93-IGN69_D090_2025-01-01</title></entry></feed>').encode(),
                 (feed + f'<entry><title>{title}</title><id>https://example.invalid/edition</id></entry></feed>').encode(),
                 (feed + '<entry><link href="https://data.geopf.fr/telechargement/download/tile.7z" g:length="10"/>'
                  '<content>00000000000000000000000000000000</content></entry></feed>').encode()]
        with patch.object(acq, 'get_bytes', side_effect=pages) as fetch:
            result = acq.discover_archive(None, '90', self.config)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(result['edition'], title)
        self.assertEqual(result['size'], 10)
        with patch.object(acq, 'get_bytes', side_effect=AssertionError('Refetched catalogue')):
            self.assertEqual(acq.discover_archive(None, '90', self.config), result)

    def test_archive_checksum_and_failed_refresh_preserve_cache(self):
        record = {'department': '90', 'edition': 'test', 'size': 3,
                  'md5': hashlib.md5(b'old').hexdigest(), 'url': 'https://example.invalid/tile.7z'}
        directory = scoped_root(self.config, 'cache_root') / 'source_archive' / '90'
        directory.mkdir(parents=True)
        path = directory / 'test.7z'
        path.write_bytes(b'old')
        with patch.object(acq.requests.Session, 'get', side_effect=AssertionError('Cache was not reused')):
            self.assertEqual(acq.acquire_archive(acq.requests.Session(), record, self.config), path)
        self.config['reuse_cache'] = False
        with patch.object(acq.requests.Session, 'get', side_effect=acq.requests.ConnectionError('offline')):
            with self.assertRaises(acq.requests.ConnectionError):
                acq.acquire_archive(acq.requests.Session(), record, self.config)
        self.assertEqual(path.read_bytes(), b'old')


if __name__ == '__main__':
    unittest.main()
