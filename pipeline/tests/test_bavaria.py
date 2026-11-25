"""Offline DGM5 acceptance checks: catalogue, cache, XYZ and final COG pixels."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
from concurrent.futures import CancelledError
import unittest
from unittest.mock import MagicMock, patch
import zipfile

import numpy as np
from osgeo import gdal, ogr
import requests

from dtm.acquire import sha256
from dtm.coordinator import execute, load_config
from dtm.countries.germany import bavaria
from dtm.countries.germany.bavaria import acquisition as acq, processing as proc
from dtm.geo import project, rectangle, srs, verify_alignment
from dtm.paths import receipt_path, scoped_root
from dtm.target_grid import plan_grid, write_reference
from test_preparation import raster


class BavariaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='dtm_bavaria_')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'config.germany.bavaria.json')
        self.config.update(cache_root=str(self.root / 'data'), output_root=str(self.root / 'data'),
                           logs_dir=str(self.root / 'logs'), download_attempts=1, request_pause_seconds=0)
        self.log = self.root / 'run_log'
        self.log.mkdir()
        self.values = (np.arange(40000).reshape(200, 200) / 100).astype('float32')
        self.geometry = rectangle([745000, 5413990, 745010, 5414000])
        self.geometry.AssignSpatialReference(srs(25832))
        self.mask = self.root / 'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(self.mask)) as ds:
            layer = ds.CreateLayer('aoi', srs(25832), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(rectangle([744000, 5412000, 748000, 5415000]))
            layer.CreateFeature(feature)
        self.config.update(country_mask=str(self.mask), aoi=str(self.mask))

    def xyz(self, e=745, n=5413):
        x, y = np.meshgrid(e * 1000 + 2.5 + 5 * np.arange(200), n * 1000 + 997.5 - 5 * np.arange(200))
        return np.column_stack((x.ravel(), y.ravel(), self.values.ravel()))

    def package(self, e=745, n=5413, entries=None):
        text = io.StringIO()
        np.savetxt(text, self.xyz(e, n), fmt='%.2f')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as package:
            for name, data in entries or [(f'folder/{e}_{n}.txt', text.getvalue()), ('readme.txt', 'source metadata')]:
                package.writestr(name, data)
        data = stream.getvalue()
        name = f'{e}_{n}.zip'
        return data, {'name': name, 'bounds': acq.filename_bounds(name), 'size': len(data),
                      'sha256': hashlib.sha256(data).hexdigest(),
                      'urls': [f'https://download{i}.bayernwolke.de/a/dgm/dgm5xyz/{name}' for i in (1, 2)]}

    def index(self, tiles):
        content = '<metalink xmlns="urn:ietf:params:xml:ns:metalink"><published>fixture</published>'
        for t in tiles:
            content += (f'<file name="{t["name"]}"><size>{t["size"]}</size>'
                        f'<hash type="sha-256">{t["sha256"]}</hash>' +
                        ''.join(f'<url>{u}</url>' for u in t['urls']) + '</file>')
        content += '</metalink>'
        path = scoped_root(self.config, 'logs_dir') / '09.meta4'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def response(self, payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {'Content-Length': str(len(payload))}
        response.iter_content.return_value = [payload]
        return response

    def session(self, payload):
        session = MagicMock()
        session.get.return_value = self.response(payload)
        return session

    def convert(self):
        data, tile = self.package()
        archive = acq.cached_archive(self.session(data), tile, self.config)
        return acq.converted_tile(archive, tile, self.config), archive, tile

    def test_catalogue_namespace_sample_and_unsafe_records(self):
        _, tile = self.package()
        tile.update(size=185437, sha256='3f6536cec0a7927eda8c8fd69947c9bdcb19b3188395c666e45f51807844b3aa')
        path = self.index([tile])
        self.assertEqual(acq.parse_catalogue(path)['tiles'][tile['name']], tile)
        self.assertEqual(tile['bounds'], [745000, 5413000, 746000, 5414000])
        original = path.read_text()
        for text in (original.replace('urn:ietf:params:xml:ns:metalink', 'wrong'),
                     original.replace('download1.bayernwolke.de', 'example.com'),
                     original.replace('745_5413.zip', '../745_5413.zip'),
                     '<!DOCTYPE metalink []>' + original):
            path.write_text(text)
            with self.assertRaises(ValueError):
                acq.parse_catalogue(path)

    def test_selection_holes_multipart_boundaries_negative_indices_and_gaps(self):
        _, a = self.package()
        _, b = self.package(746)
        index = {'tiles': {t['name']: t for t in (a, b)}}
        selected, absent = acq.select_tiles(rectangle(a['bounds']), index)
        self.assertEqual(selected, [a])
        self.assertFalse(absent)
        hole = rectangle([744000, 5412000, 747000, 5415000]).Difference(rectangle(a['bounds']))
        selected, absent = acq.select_tiles(hole, index)
        self.assertEqual(selected, [b])
        self.assertIn('744_5413.zip', absent)
        multipart = rectangle(a['bounds']).Union(rectangle([747000, 5413000, 748000, 5414000]))
        self.assertEqual(acq.select_tiles(multipart, index)[1], ['747_5413.zip'])
        self.assertEqual(acq.select_tiles(rectangle([-1000, -1000, 0, 0]), index)[1], ['-1_-1.zip'])

    def test_catalogue_cache_refresh_and_offline_fallback(self):
        _, tile = self.package()
        path = self.index([tile])
        session = self.session(b'bad')
        self.assertEqual(acq.catalogue(self.config, session)['tiles'][tile['name']], tile)
        session.get.assert_not_called()
        self.config['catalogue_refresh'] = True
        session.get.side_effect = requests.ConnectionError('offline')
        self.assertEqual(acq.catalogue(self.config, session)['published'], 'fixture')
        session.get.side_effect = None
        session.get.return_value = self.response(path.read_bytes().replace(b'fixture', b'updated'))
        self.assertEqual(acq.catalogue(self.config, session)['published'], 'updated')
        self.assertFalse(path.with_name('09.meta4.part').exists())

    def test_mirror_fallback_corruption_and_content_length(self):
        data, tile = self.package()
        session = self.session(data)
        session.get.side_effect = [requests.ConnectionError('primary failed'), self.response(data)]
        gate, stopped = MagicMock(), threading.Event()
        archive = acq.cached_archive(session, tile, self.config, request_gate=gate, stop_event=stopped)
        self.assertEqual(gate.wait.call_count, 2)  # Mirrors share the same pacing gate.
        self.assertEqual([c.args[0] for c in session.get.call_args_list], tile['urls'])
        self.assertEqual(sha256(archive), tile['sha256'])
        session = self.session(b'broken')
        acq.cached_archive(session, tile, self.config)
        session.get.assert_not_called()
        self.config['reuse_cache'] = False
        with self.assertRaises(RuntimeError):
            acq.cached_archive(session, tile, self.config)
        self.assertEqual(sha256(archive), tile['sha256'])
        session = self.session(data)
        session.get.return_value.headers['Content-Length'] = '1'
        with self.assertRaises(RuntimeError):
            acq.cached_archive(session, tile, self.config)
        self.assertFalse(list(archive.parent.glob('*.part')))

    def test_safe_zip_structure(self):
        for entries in [[('../745_5413.txt', 'x')], [('folder/other.txt', 'x')],
                        [('745_5413.txt', 'x'), ('folder/745_5413.txt', 'x')],
                        [('745_5413.txt', 'x'), ('746_5413.txt', 'x')]]:
            data, tile = self.package(entries=entries)
            archive = self.root / tile['name']
            archive.write_bytes(data)
            with self.assertRaises(ValueError):
                acq.validate_zip(archive, tile)

    def test_conversion_precision_reuse_and_changed_source_invalidation(self):
        path, archive, tile = self.convert()
        with gdal.Open(str(path)) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), self.values)
            self.assertEqual(ds.GetGeoTransform(), (745000, 5, 0, 5414000, 0, -5))
            self.assertEqual(ds.GetRasterBand(1).DataType, gdal.GDT_Float32)
        with patch.object(acq, 'convert_xyz', side_effect=AssertionError('reparsed')):
            self.assertEqual(acq.converted_tile(archive, tile, self.config), path)
        old_digest = sha256(path)
        self.values += 10
        data, changed = self.package()
        self.index([changed])
        with patch('requests.Session.get', return_value=self.response(data)) as get:
            paths = acq.download(self.config, bavaria.plan(self.geometry, self.config), self.log)
            self.assertEqual(get.call_count, 1)
        self.assertNotEqual(sha256(paths[0]), old_digest)
        self.assertEqual(json.loads(receipt_path(path, self.config).read_text())['archive_sha256'], changed['sha256'])
        # Even a failed newer-source acquisition must never return old converted data.
        self.values += 1
        _, newer = self.package()
        self.index([newer])
        with patch('requests.Session.get', side_effect=requests.ConnectionError('offline')):
            with self.assertRaises(RuntimeError):
                acq.download(self.config, bavaria.plan(self.geometry, self.config), self.log)

    def test_larger_aoi_only_downloads_additional_tiles(self):
        a, ta = self.package()
        b, tb = self.package(746)
        self.index([ta, tb])
        plan = bavaria.plan(self.geometry, self.config)
        with patch('requests.Session.get', return_value=self.response(a)) as get:
            acq.download(self.config, plan, self.log)
            self.assertEqual(get.call_count, 1)
        with patch('requests.Session.get') as get, patch.object(acq, 'convert_xyz') as convert:
            acq.download(self.config, plan, self.log)
            get.assert_not_called()
            convert.assert_not_called()
        larger = rectangle([745000, 5413990, 746010, 5414000])
        larger.AssignSpatialReference(srs(25832))
        with patch('requests.Session.get', return_value=self.response(b)) as get:
            paths = acq.download(self.config, bavaria.plan(larger, self.config), self.log)
            self.assertEqual(get.call_count, 1)
            self.assertEqual(len(paths), 2)
            self.assertEqual(get.call_args.args[0], tb['urls'][0])

    def test_parallel_transfers_private_sessions_and_ordered_cache_reuse(self):
        a, ta = self.package()
        b, tb = self.package(746)
        self.index([ta, tb])
        self.config['download_workers'] = 2
        geometry = rectangle([745000, 5413990, 746010, 5414000])
        geometry.AssignSpatialReference(srs(25832))
        plan = bavaria.plan(geometry, self.config)
        barrier = threading.Barrier(2, timeout=10)
        sessions = []

        def get(session, url, **kwargs):
            sessions.append(session)
            barrier.wait()  # Fails if acquisition regresses to serial requests.
            return self.response(a if url.endswith(ta['name']) else b)

        with patch('requests.Session.get', autospec=True, side_effect=get):
            paths = acq.download(self.config, plan, self.log)
        self.assertEqual(len({id(s) for s in sessions}), 2)
        self.assertEqual([p.stem for p in paths], ['745_5413', '746_5413'])
        for path in paths:
            with gdal.Open(str(path)) as ds:
                np.testing.assert_array_equal(ds.ReadAsArray(), self.values)
        self.config['download_workers'] = 1
        with patch('requests.Session.get', side_effect=AssertionError('Unexpected download')):
            self.assertEqual(acq.download(self.config, plan, self.log), paths)

    def test_cancelled_transfer_removes_partial_and_preserves_archive(self):
        data, tile = self.package()
        archive = acq.cached_archive(self.session(data), tile, self.config)
        self.config['reuse_cache'] = False
        stopped = threading.Event()
        session = self.session(data)

        def chunks(size):
            stopped.set()
            yield data[:20]

        session.get.return_value.iter_content.side_effect = chunks
        with self.assertRaises(CancelledError):
            acq.cached_archive(session, tile, self.config, request_gate=MagicMock(), stop_event=stopped)
        self.assertEqual(sha256(archive), tile['sha256'])
        self.assertFalse(list(archive.parent.glob('*.part')))

    def test_bad_xyz_and_explicit_nodata(self):
        self.config['source'].pop('nodata', None)
        self.config['source'].pop('nodata_evidence', None)
        source, dest = self.root / 'tile.txt', self.root / 'tile.tif'
        extent = [745000, 5413000, 746000, 5414000]
        xyz = self.xyz()
        for bad in (xyz[:-1], xyz[::-1], np.vstack((xyz[1], xyz[1:]))):
            np.savetxt(source, bad)
            with self.assertRaises(ValueError):
                proc.convert_xyz(source, dest, extent, self.config)
        for value in (float('nan'), float('inf'), -9999):
            bad = xyz.copy()
            bad[0, 2] = value
            np.savetxt(source, bad)
            with self.assertRaises(ValueError):
                proc.convert_xyz(source, dest, extent, self.config)
        source.write_text('malformed X Y Z')
        with self.assertRaises(ValueError):
            proc.convert_xyz(source, dest, extent, self.config)
        xyz[1, 2] = -9999
        np.savetxt(source, xyz)
        self.config['source'].update(nodata=-9999, nodata_evidence='test fixture explicitly declares this marker')
        info = proc.convert_xyz(source, dest, extent, self.config)
        self.assertEqual(info['explicit_nodata_cells'], 1)
        self.assertEqual(info['valid_cells'], 39999)  # Zero remains a valid elevation.

    def test_default_config_handles_padding_and_all_nodata_tiles(self):
        self.assertEqual(self.config['source']['nodata'], -9999)
        self.assertTrue(self.config['source']['nodata_evidence'])
        self.values[10:40, :] = -9999
        self.values[40, :100] = -9999
        path, _, _ = self.convert()
        with gdal.Open(str(path)) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), self.values)
            self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), -9999)
            self.assertEqual(ds.ReadAsArray()[0, 0], 0)
        record = json.loads(receipt_path(path, self.config).read_text())
        self.assertEqual(record['explicit_nodata_cells'], 6100)
        self.assertEqual(record['valid_cells'], 33900)
        self.values[:] = -9999
        path, _, _ = self.convert()
        record = json.loads(receipt_path(path, self.config).read_text())
        self.assertEqual(record['valid_cells'], 0)
        self.assertEqual(record['explicit_nodata_cells'], 40000)

    def test_partial_shifted_native_rectangle_preserves_coordinates_and_values(self):
        x, y = np.meshgrid(745569.5 + 5 * np.arange(87), 5413997.5 - 5 * np.arange(68))
        values = (np.arange(5916).reshape(68, 87) / 100 + 395).astype('float32')
        values[0, 0] = -9999
        source, destination = self.root / 'partial.txt', self.root / 'partial.tif'
        xyz = np.column_stack((x.ravel(), y.ravel(), values.ravel()))
        np.savetxt(source, xyz, fmt='%.2f')
        extent = [745000, 5413000, 746000, 5414000]
        info = proc.convert_xyz(source, destination, extent, self.config)
        self.assertEqual(info['absent_cells'], 34084)
        self.assertEqual(info['explicit_nodata_cells'], 1)
        self.assertEqual(info['source_grid']['transform'], [745567, 5, 0, 5414000, 0, -5])
        with gdal.Open(str(destination)) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), values)
        for bad in (xyz[:-1], xyz[::-1], np.vstack((xyz[1], xyz[1:]))):
            np.savetxt(source, bad)
            with self.assertRaises(ValueError):
                proc.convert_xyz(source, destination, extent, self.config)

    def test_mixed_lattices_align_once_without_snapping_sources(self):
        # Both native groups meet at x=746000; shifted pixel edges extend 2 m across it.
        shifted = raster(self.root / 'shifted_native.tif', np.array([[10, 20], [30, 40]]),
                         25832, (745992, 5, 0, 5414000, 0, -5))
        normal = raster(self.root / 'normal_native.tif', np.array([[100, 200], [300, 400]]),
                        25832, (746000, 5, 0, 5414000, 0, -5))
        geometry = rectangle([745990, 5413990, 746010, 5414000])
        geometry.AssignSpatialReference(srs(25832))
        reference = write_reference(plan_grid(geometry, self.config['target']), self.root / 'ref.vrt')
        # Conversion receipts are not needed to test mosaic placement and weighting.
        for path in (normal, shifted):
            receipt_path(path, self.config).write_text('{}')
        with patch.object(proc, 'align', wraps=proc.align) as warp:
            result = bavaria.prepare([normal, shifted], geometry, reference, self.root / 'mixed', self.config)
            self.assertEqual(warp.call_count, 1)
            self.assertEqual(len(warp.call_args.args[0]), 2)
        self.assertEqual(len(result['native_mosaics']), 2)
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), [[10, 16, 100, 200], [30, 36, 300, 400]])
        verify_alignment(result['prepared_raster'], reference)

    def test_aligned_cog_preserves_values_masks_holes_and_pads_coverage(self):
        path, _, _ = self.convert()
        geometry = rectangle([744995, 5413980, 745020, 5414005]).Difference(
            rectangle([745005, 5413990, 745010, 5413995]))
        geometry.AssignSpatialReference(srs(25832))
        reference = write_reference(plan_grid(geometry, self.config['target']), self.root / 'ref.vrt')
        with patch.object(proc, 'align', side_effect=AssertionError('unnecessary warp')):
            result = bavaria.prepare([path], geometry, reference, self.root / 'run', self.config)
        expected = np.full((5, 5), -9999, dtype='float32')
        expected[1:, 1:] = self.values[:4, :4]
        expected[2, 2] = -9999
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            self.assertEqual(ds.GetMetadataItem('LICENSE'), 'CC BY 4.0')
            self.assertIn('without interpolation', ds.GetMetadataItem('PREPARATION'))
        verify_alignment(result['prepared_raster'], reference)
        self.assertEqual(result['source_resolution_m'], 5)

    def test_shifted_reference_uses_one_average_alignment(self):
        path, _, _ = self.convert()
        ref = raster(self.root / 'shifted.tif', np.zeros((2, 2)), 25832, (745002.5, 5, 0, 5413997.5, 0, -5))
        target = {**self.config['target'], 'reference_raster': str(ref)}
        geom = rectangle([745003, 5413988, 745012, 5413997])
        geom.AssignSpatialReference(srs(25832))
        info = plan_grid(geom, target, allow_shifted_origin=True)
        self.assertEqual(info['transform'][0], 745002.5)
        with patch.object(proc, 'align', wraps=proc.align) as warp:
            result = bavaria.prepare([path], geom, ref, self.root / 'shifted_run', self.config)
            self.assertEqual(warp.call_count, 1)
        expected = sum(self.values[y:y+2, x:x+2].astype('float64') for y in (0, 1) for x in (0, 1)) / 4
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), expected.astype('float32'))
        verify_alignment(result['prepared_raster'], ref)

    def test_plan_reprojects_and_skips_outside_region(self):
        native = bavaria.plan(self.geometry, self.config)
        geographic = bavaria.plan(project(self.geometry, srs(4326)), self.config)
        np.testing.assert_allclose(native['aoi_extent'], geographic['aoi_extent'], atol=1e-4, rtol=0)
        outside = rectangle([0, 0, 10, 10])
        outside.AssignSpatialReference(srs(25832))
        self.assertIn('skip_reason', bavaria.plan(outside, self.config))
        with patch('requests.Session.get') as get:
            execute(self.config, 'plan')
            get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
