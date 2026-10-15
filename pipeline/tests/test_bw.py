"""Offline contracts for LGL inventory, reusable archives and XYZ preparation."""
from copy import deepcopy
from contextlib import closing
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import numpy as np
from osgeo import gdal, ogr
import requests

from dtm.acquire import sha256, write_json
from dtm.coordinator import execute, load_config
from dtm.countries.germany import bw
from dtm.countries.germany.bw import acquisition as acq
from dtm.countries.germany.bw.processing import convert_xyz
from dtm.geo import rectangle, srs, verify_alignment
from dtm.paths import raw_directory, receipt_path, scoped_root
from dtm.target_grid import plan_grid, write_reference
from test_preparation import raster


class BadenWuerttembergTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_bw_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'config.germany.bw.json')
        self.config.update(cache_root=str(self.root / 'data'), output_root=str(self.root / 'data'),
                           logs_dir=str(self.root / 'logs'), download_attempts=1, request_pause_seconds=0)
        self.log = self.root / 'run_log'
        self.log.mkdir()
        self.tile = self.tile_at(557, 5434)
        self.geometry = rectangle([557010, 5434010, 557020, 5434020])
        self.geometry.AssignSpatialReference(srs(25832))
        self.plan = bw.plan(self.geometry, self.config)
        self.metadata = {'Kachelname': 'dgm1_32_557_5434_1_bw_2019', 'Aktualitaet': '2019-02-25',
                         'Fortfuehrung': '2019-02-25', 'Genauigkeit': '0.15',
                         'Koordinatenreferenzsystem_Lage': 'ETRS89_UTM32',
                         'Koordinatenreferenzsystem_Hoehe': 'DE_DHHN2016_NH'}

    def tile_at(self, e, n, available=True):
        name = f'dgm1_32_{e}_{n}_2_bw.zip'
        return {'name': name, 'bounds': acq.filename_bounds(name), 'available': available}

    def index(self, tiles=None):
        extent = [833481, 6025810, 1169271, 6453445]
        record = {'source': acq.LAYERS_URL, 'portal_extent': extent,
                  'index_urls': [acq.GRID_URL.format(z=z, x=x, y=y) for z, x, y in acq.index_tiles(extent)],
                  'discovered_utc': 'fixture', 'tiles': tiles or [self.tile]}
        path = scoped_root(self.config, 'logs_dir') / 'bw_inventory.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, record)
        return record

    def package(self, tile=None, xyz=b'not opened unless selected', entries=None):
        tile = tile or self.tile
        child = tile['name'].replace('_2_bw.zip', '_1_bw_2019')
        csv = ';'.join(self.metadata) + '\n' + ';'.join(self.metadata.values()) + '\n'
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in (entries if entries is not None else [
                (child + '.xyz', xyz), (child + '.csv', csv.encode()),
                ('GOVDATA-Datenlizenz_Deutschland.pdf', b'fixture licence'),
                ('Meta-ATKIS_DGM1_ALS2.txt', b'fixture metadata')]):
                z.writestr('folder/' + name, data)
        return content.getvalue()

    def cache(self, payload, tile=None):
        path = scoped_root(self.config, 'cache_root') / 'source_archive' / (tile or self.tile)['name']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def session(self, payload=b'', status=200):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = status
        response.headers = {}
        response.iter_content.return_value = [payload]
        if status >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(str(status), response=response)
        session = MagicMock()
        session.get.return_value = response
        return session

    def test_inventory_origin_boundaries_and_true_geometry_selection(self):
        record = self.index([self.tile, self.tile_at(559, 5434)])
        acq.validate_inventory(record)
        self.assertEqual(acq.index_tiles(record['portal_extent']), [(7, 66, 43), (7, 66, 44), (7, 67, 43), (7, 67, 44)])
        for extent, expected in [([557000, 5434000, 559000, 5436000], 1),
                                 ([558999, 5434000, 559001, 5434001], 2)]:
            self.assertEqual(sum(acq.intersects(t, rectangle(extent)) for t in record['tiles']), expected)
        hole = ogr.CreateGeometryFromWkt('POLYGON ((556000 5433000,560000 5433000,560000 5437000,556000 5437000,556000 5433000),'
                                        '(557000 5434000,557000 5436000,559000 5436000,559000 5434000,557000 5434000))')
        self.assertFalse(acq.intersects(self.tile, hole))
        record['tiles'].append(self.tile_at(560, 5434))
        with self.assertRaisesRegex(ValueError, 'origin'):
            acq.validate_inventory(record)

    def test_inventory_reused_offline_and_invalid_inventory_rejected(self):
        index = self.index()
        session = self.session()
        self.assertEqual(acq.inventory(self.config, session), index)
        session.get.assert_not_called()
        index['tiles'][0]['bounds'][0] += 1
        with self.assertRaisesRegex(ValueError, 'extent mismatch'):
            acq.validate_inventory(index)

    def test_valid_cache_needs_no_http_and_corrupt_cache_is_repaired(self):
        payload = self.package()
        path = self.cache(payload)
        session = self.session(payload)
        self.assertEqual(acq.cached_archive(session, self.tile, self.config), (path, True))
        session.get.assert_not_called()
        path.write_bytes(b'broken')
        self.assertEqual(acq.cached_archive(session, self.tile, self.config), (path, False))
        self.assertEqual(path.read_bytes(), payload)
        self.assertFalse(list(path.parent.glob('*.part')))

    def test_failed_refresh_preserves_original_archive_and_receipt(self):
        path = self.cache(self.package())
        acq.cached_archive(self.session(), self.tile, self.config)
        receipt = scoped_root(self.config, 'logs_dir') / 'archive_receipts' / (path.name + '.json')
        before = (path.read_bytes(), receipt.read_bytes())
        self.config['reuse_cache'] = False
        with self.assertRaises(RuntimeError):
            acq.cached_archive(self.session(b'broken'), self.tile, self.config)
        self.assertEqual((path.read_bytes(), receipt.read_bytes()), before)

    def test_receipted_zip_is_hashed_without_repeating_full_decompression(self):
        path = self.cache(self.package())
        session = self.session()
        acq.cached_archive(session, self.tile, self.config)
        with patch.object(zipfile.ZipFile, 'testzip', side_effect=AssertionError('Repeated CRC pass')), \
             patch.object(acq, 'sha256', wraps=sha256) as digest:
            self.assertEqual(acq.cached_archive(session, self.tile, self.config), (path, True))
            digest.assert_called_once_with(path)
        session.get.assert_not_called()

    def test_archive_workers_are_concurrent_bounded_and_share_request_pacing(self):
        self.config['download_workers'] = 2
        tiles = [self.tile_at(e, 5434) for e in (557, 559, 561, 563)]
        barrier = threading.Barrier(2)
        gates, threads = [], set()

        def cached(session, tile, config, *, request_gate, stop_event):
            gates.append(request_gate)
            threads.add(threading.get_ident())
            barrier.wait(timeout=5)
            return self.root / tile['name'], True

        with patch.object(acq, 'cached_archive', side_effect=cached):
            with closing(acq.archive_jobs(self.config, tiles, lambda tile, path, reused: tile['name'])) as jobs:
                results = list(jobs)
        self.assertEqual(sorted(results), sorted(t['name'] for t in tiles))
        self.assertEqual(len(threads), 2)
        self.assertTrue(all(g is gates[0] for g in gates))

    def test_worker_failure_stops_scheduling_and_keeps_completed_cache(self):
        tiles = [self.tile, self.tile_at(559, 5434), self.tile_at(561, 5434)]
        self.cache(self.package())
        with patch('requests.Session.get', side_effect=requests.ConnectionError('offline')) as get:
            with closing(acq.archive_jobs(self.config, tiles, lambda tile, path, reused: path)) as jobs:
                self.assertTrue(next(jobs).exists())
                with self.assertRaisesRegex(RuntimeError, '559_5434'):
                    next(jobs)
            self.assertEqual(get.call_count, 1)
        with patch('requests.Session.get') as get:
            self.assertTrue(acq.cached_archive(self.session(), self.tile, self.config)[1])
            get.assert_not_called()

    def test_http_failures_are_not_recorded_as_absent_coverage(self):
        for status in (403, 404, 429, 503):
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, str(status)):
                acq.cached_archive(self.session(status=status), self.tile, self.config)
        self.assertFalse(list(scoped_root(self.config, 'cache_root').rglob('*.zip')))
        self.assertFalse(list(scoped_root(self.config, 'logs_dir').rglob('*.json')))

    def test_stream_failure_retries_and_commits_only_valid_zip(self):
        session = self.session(self.package())
        response = session.get.return_value
        response.iter_content.side_effect = [requests.ConnectionError('interrupted'), [self.package()]]
        self.config['download_attempts'] = 2
        with patch.object(acq.time, 'sleep'):
            path, reused = acq.cached_archive(session, self.tile, self.config)
        self.assertFalse(reused)
        self.assertEqual(session.get.call_count, 2)
        self.assertIsNone(zipfile.ZipFile(path).testzip())

    def test_prefetch_resumes_and_completeness_requires_all_inventory_archives(self):
        other = self.tile_at(559, 5434)
        absent = self.tile_at(561, 5434, False)
        self.index([self.tile, other, absent])
        self.cache(self.package())
        with patch('requests.Session.get', side_effect=requests.ConnectionError('offline')):
            with self.assertRaises(RuntimeError):
                acq.prefetch(self.config, self.log)
        summary = json.loads((self.log / 'bw_prefetch.json').read_text())
        self.assertFalse(summary['complete'])
        self.assertEqual(summary['reused'], 1)
        self.assertEqual(len(summary['failed_requests']), 1)
        self.cache(self.package(other), other)
        with patch('requests.Session.get') as get:
            summary = acq.prefetch(self.config, self.log)
            get.assert_not_called()
        self.assertTrue(summary['complete'])
        self.assertEqual(summary['reused'], 2)
        self.assertEqual(summary['unavailable_candidates'], [absent['name']])
        self.assertFalse(list(self.log.glob('source_tiles/*')))

    def test_unsafe_names_missing_metadata_and_duplicate_coverage_rejected(self):
        stem = self.metadata['Kachelname']
        for entries in [[('../evil.xyz', b'x')], [(stem + '.xyz', b'x')],
                        [(stem + '.xyz', b'x'), (stem.replace('2019', '2022') + '.xyz', b'x')],
                        [(stem.replace('557', '560') + '.xyz', b'x')]]:
            with self.subTest(entries=entries):
                path = self.cache(self.package(entries=entries))
                with self.assertRaises(ValueError):
                    acq.validate_zip(path, self.tile)

    def test_aoi_extracts_only_needed_children_and_keeps_csv_provenance(self):
        self.index()
        stem = self.metadata['Kachelname']
        csv = ';'.join(self.metadata) + '\n' + ';'.join(self.metadata.values()) + '\n'
        entries = [(stem + '.xyz', b'selected'), (stem + '.csv', csv.encode()),
                   (stem.replace('_557_', '_558_') + '.xyz', b'not a raster'),
                   (stem.replace('_557_', '_558_') + '.csv', b'not parsed'),
                   ('licence.pdf', b'licence'), ('metadata.txt', b'metadata')]
        archive = self.cache(self.package(entries=entries))
        digest = sha256(archive)

        def convert(source, destination, extent, metadata, config):
            self.assertEqual(source.read_bytes(), b'selected')
            destination.write_bytes(b'converted')
            return {'source_nodata': None}

        with patch.object(acq, 'convert_xyz', side_effect=convert) as convert, patch('requests.Session.get') as get:
            paths = acq.download(self.config, self.plan, self.log)
            again = self.root / 'again'
            again.mkdir()
            self.assertEqual(acq.download(self.config, self.plan, again), paths)
            self.assertEqual(convert.call_count, 1)
            get.assert_not_called()
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].parent, raw_directory(self.config))
        self.assertEqual(json.loads(receipt_path(paths[0], self.config).read_text())['csv'], self.metadata)
        self.assertEqual(sha256(archive), digest)
        self.assertFalse(list((self.log / 'source_tiles').glob('*.xyz')))

    def test_converted_cache_repairs_missing_changed_or_outdated_tiles_without_http(self):
        self.index()
        self.cache(self.package())

        def convert(source, destination, *args):
            destination.write_bytes(b'converted')
            return {'source_nodata': None}

        with patch.object(acq, 'convert_xyz', side_effect=convert) as convert, patch('requests.Session.get') as get:
            path = acq.download(self.config, self.plan, self.log)[0]
            path.unlink()
            acq.download(self.config, self.plan, self.log)
            path.write_bytes(b'corrupted')
            acq.download(self.config, self.plan, self.log)
            with patch.object(acq, 'CONVERSION_VERSION', acq.CONVERSION_VERSION + 1):
                acq.download(self.config, self.plan, self.log)
            self.assertEqual(convert.call_count, 4)
            get.assert_not_called()

    def test_source_update_invalidates_conversion_and_failed_conversion_preserves_old_cache(self):
        self.index()
        self.cache(self.package())

        def convert(source, destination, *args):
            destination.write_bytes(source.read_bytes())
            return {'source_nodata': None}

        with patch.object(acq, 'convert_xyz', side_effect=convert):
            path = acq.download(self.config, self.plan, self.log)[0]
        before = (path.read_bytes(), receipt_path(path, self.config).read_bytes())
        self.cache(self.package(xyz=b'updated source'))
        archive_receipt = scoped_root(self.config, 'logs_dir') / 'archive_receipts' / (self.tile['name'] + '.json')
        archive_receipt.unlink()  # Simulate adoption of a separately refreshed ZIP.
        with patch.object(acq, 'convert_xyz', side_effect=ValueError('invalid XYZ')), patch('requests.Session.get') as get:
            with self.assertRaisesRegex(RuntimeError, 'invalid XYZ'):
                acq.download(self.config, self.plan, self.log)
            get.assert_not_called()
        self.assertEqual((path.read_bytes(), receipt_path(path, self.config).read_bytes()), before)
        with patch.object(acq, 'convert_xyz', side_effect=convert) as convert:
            acq.download(self.config, self.plan, self.log)
            convert.assert_called_once()
        self.assertEqual(path.read_bytes(), b'updated source')

    def test_xyz_conversion_complete_cell_validation_and_exact_5m_cog(self):
        source = self.root / (self.metadata['Kachelname'] + '.xyz')
        values = np.arange(1000000, dtype='float32').reshape(1000, 1000) / 1000 + 100
        native = raster(self.root / 'fixture.tif', values, 25832, (557000, 1, 0, 5435000, 0, -1))
        with gdal.Translate(str(source), str(native), format='XYZ'):
            pass
        converted = self.root / 'converted.tif'
        info = convert_xyz(source, converted, [557000, 5434000, 558000, 5435000], self.metadata, self.config)
        self.assertIsNone(info['source_nodata'])
        self.assertEqual(info['valid_cells'], 1000000)
        write_json(receipt_path(converted, self.config), {'csv': self.metadata, **info})
        reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'ref.vrt')
        result = bw.prepare([converted], self.geometry, reference, self.root / 'run', self.config)
        with gdal.Open(result['prepared_raster']) as ds:
            expected = values[980:990, 10:20].reshape(2, 5, 2, 5).mean(axis=(1, 3), dtype='float64').astype('float32')
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
        verify_alignment(result['prepared_raster'], reference)
        self.assertEqual(result['vertical_datum'], 'DE_DHHN2016_NH')
        bad_metadata = {**self.metadata, 'Koordinatenreferenzsystem_Hoehe': 'unknown'}
        with self.assertRaisesRegex(ValueError, 'metadata'):
            convert_xyz(source, converted, self.tile['bounds'], bad_metadata, self.config)
        with source.open('r+b') as stream:
            stream.truncate(100)
        with self.assertRaises(ValueError):
            convert_xyz(source, converted, self.tile['bounds'], self.metadata, self.config)

    def test_partial_xyz_preserves_gaps_zero_heights_and_valid_pixel_means(self):
        source = self.root / (self.metadata['Kachelname'] + '.xyz')
        # Deliberately unordered, with holes inside the bounding box and at edges.
        source.write_text('557999.5 5434000.5 99\n557014.5 5434015.5 20\n'
                          '557011.5 5434011.5 nan\n557017.5 5434017.5 30\n'
                          '557010.5 5434019.5 0\n557018.5 5434012.5 inf\n')
        converted = self.root / 'partial.tif'
        info = convert_xyz(source, converted, [557000, 5434000, 558000, 5435000], self.metadata, self.config)
        self.assertEqual(info['source_records'], 6)
        self.assertEqual(info['valid_cells'], 4)
        self.assertEqual(info['absent_cells'], 999994)
        self.assertEqual(info['invalid_elevation_cells'], 2)
        with gdal.Open(str(converted)) as ds:
            self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), -9999)
            self.assertEqual(ds.ReadAsArray(10, 980, 1, 1)[0, 0], 0)
            self.assertEqual(ds.ReadAsArray(999, 999, 1, 1)[0, 0], 99)
            self.assertEqual(ds.ReadAsArray(0, 0, 1, 1)[0, 0], -9999)
        write_json(receipt_path(converted, self.config), info)
        reference = write_reference(plan_grid(self.geometry, self.config['target']), self.root / 'ref.vrt')
        result = bw.prepare([converted], self.geometry, reference, self.root / 'run', self.config)
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), [[10, 30], [-9999, -9999]])
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
        verify_alignment(result['prepared_raster'], reference)

    def test_partial_xyz_rejects_invalid_coordinates_and_duplicates(self):
        source = self.root / (self.metadata['Kachelname'] + '.xyz')
        destination = self.root / 'existing.tif'
        destination.write_bytes(b'previous output')
        for records in ('557010.5 5434010.5 1\n557010.5 5434010.5 2\n',
                        '557010.25 5434010.5 1\n', '558000.5 5434010.5 1\n',
                        '557010.5 5433999.5 1\n', 'nan 5434010.5 1\n',
                        '557010.5 5434010.5 -9999\n', '557010.5 5434010.5\n'):
            with self.subTest(records=records):
                source.write_text(records)
                with self.assertRaises(ValueError):
                    convert_xyz(source, destination, [557000, 5434000, 558000, 5435000], self.metadata, self.config)
                self.assertEqual(destination.read_bytes(), b'previous output')

    def test_recover_legacy_conversions_reuses_cache_and_rejects_corruption(self):
        from scripts.bw_recover_conversions import recover
        source = self.log / (self.metadata['Kachelname'] + '.xyz')
        source.write_text('557010.5 5434019.5 0\n')
        tile = source.with_suffix('.tif')
        info = convert_xyz(source, tile, [557000, 5434000, 558000, 5435000], self.metadata, self.config)
        archive = self.cache(self.package())
        record = {**info, 'source': self.config['source'], 'archive': str(archive),
                  'archive_sha256': sha256(archive), 'member': source.name, 'sha256': sha256(tile)}
        write_json(tile.with_suffix('.json'), record)
        recover(self.config, self.log)
        recover(self.config, self.log)
        destination = raw_directory(self.config) / tile.name
        identity = {'archive_sha256': sha256(archive), 'member': source.name,
                    'conversion_version': acq.CONVERSION_VERSION,
                    'bounds': [557000, 5434000, 558000, 5435000], 'output_nodata': self.config['nodata']}
        self.assertTrue(acq.cached_conversion(destination, identity, self.config))
        self.assertTrue(tile.exists())
        write_json(tile.with_suffix('.json'), {**record, 'sha256': 'invalid'})
        with self.assertRaisesRegex(ValueError, 'differs from receipt'):
            recover(self.config, self.log)

    def test_virtual_preparation_matches_cleaned_mosaic_at_seams_and_gaps(self):
        from dtm.countries.germany.processing import prepare as legacy_prepare
        values = np.arange(200, dtype='float32').reshape(10, 20) - 50
        values[:5, :5] = -9999
        values[2:4, 11:15] = -9999  # Partial NoData across a seam inside a 5 m cell.
        tiles = [raster(self.root / 'left.tif', values[:, :13], 25832,
                        (557000, 1, 0, 5434010, 0, -1)),
                 raster(self.root / 'right.tif', values[:, 13:], 25832,
                        (557013, 1, 0, 5434010, 0, -1))]
        for tile in tiles:
            write_json(receipt_path(tile, self.config), {})
        geometry = rectangle([557000, 5434000, 557020, 5434010])
        geometry.AssignSpatialReference(srs(25832))
        extent = rectangle([556995, 5433995, 557025, 5434015])
        extent.AssignSpatialReference(srs(25832))
        reference = write_reference(plan_grid(extent, self.config['target']), self.root / 'ref.vrt')
        with patch('dtm.countries.germany.processing.clean', side_effect=AssertionError('Redundant cleaning')):
            result = bw.prepare(tiles, geometry, reference, self.root / 'fast', self.config)
        legacy = legacy_prepare(tiles, geometry, reference, self.root / 'legacy', self.config, product='bw')
        with gdal.Open(result['prepared_raster']) as actual, gdal.Open(legacy['prepared_raster']) as expected:
            np.testing.assert_array_equal(actual.ReadAsArray(), expected.ReadAsArray())
            self.assertEqual(actual.GetRasterBand(1).GetNoDataValue(), expected.GetRasterBand(1).GetNoDataValue())
            self.assertEqual(actual.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
        verify_alignment(result['prepared_raster'], reference)
        self.assertEqual(result['valid_cell_count'], legacy['valid_cell_count'])
        self.assertEqual(Path(result['native_mosaic']).suffix, '.vrt')
        self.assertFalse((self.root / 'fast/processed/_work/clean_tiles').exists())
        self.assertFalse(list((self.root / 'fast').rglob('*_merged.tif')))
        with gdal.Open(str(tiles[1]), gdal.GA_Update) as ds:
            ds.SetGeoTransform((557013.5, 1, 0, 5434010, 0, -1))
        with self.assertRaisesRegex(ValueError, 'integer-metre'):
            bw.prepare(tiles, geometry, reference, self.root / 'invalid', self.config)

    def test_config_skip_plan_and_prefetch_does_not_read_aoi(self):
        outside = rectangle([300000, 5800000, 300010, 5800010])
        outside.AssignSpatialReference(srs(25832))
        self.assertIn('skip_reason', bw.plan(outside, self.config))
        for change in ({'target': {'resolution': 1}}, {'hole_filling': {'enabled': True}}):
            with self.assertRaises(ValueError):
                bw.validate_config({**deepcopy(self.config), **change})
        self.index()
        self.cache(self.package())
        self.config['aoi'] = 'does-not-exist.gpkg'
        with patch('requests.Session.get') as get:
            result = execute(self.config, 'prefetch')
            self.assertTrue(result['complete'])
            get.assert_not_called()
