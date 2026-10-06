"""Offline Hessen archive lifecycle, AOI selection and shared-grid integration."""
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
from dtm.countries.germany import hessen
from dtm.countries.germany.hessen import acquisition as acq
from dtm.countries.germany.hessen.processing import validate_native
from dtm.countries.germany.archive import verify_archive
from dtm.geo import rectangle, srs, verify_alignment
from dtm.paths import raw_directory, receipt_path, scoped_root
from dtm.target_grid import plan_grid, write_reference
from test_preparation import raster


class HessenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_hessen_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = load_config(Path(__file__).resolve().parents[1] / 'config.germany.hessen.json')
        self.config.update(cache_root=str(self.root / 'data'), output_root=str(self.root / 'data'),
                           logs_dir=str(self.root / 'logs'), download_attempts=1, block_size=2)
        self.geometry = rectangle([498010, 5554010, 498020, 5554020])
        self.geometry.AssignSpatialReference(srs(25832))
        self.plan = hessen.plan(self.geometry, self.config)
        self.log = self.root / 'run_log'
        self.log.mkdir()

    def raw(self, name='DGM1_32_498_5554_1_he.tif'):
        return raster(self.root / name, np.full((1000, 1000), 42, dtype='float32'),
                      epsg=25832, transform=(498000, 1, 0, 5555000, 0, -1))

    def package(self, entries=None):
        if entries is None:
            source = self.raw()
            entries = [('files/' + source.name, source.read_bytes()),
                       ('files/DGM1_32_600_5554_1_he.tif', b'outside AOI: never opened as raster')]
        path = scoped_root(self.config, 'cache_root') / 'source_archive/dehessen.tar'
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, 'w') as tf:
            for name, content in [('metadata.json', b'{"name":"ATKIS-DGM 1"}'),
                                  ('LICENSE.pdf', b'fixture licence'), *entries]:
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                tf.addfile(entry, io.BytesIO(content))
        self.config['source'].update(size=path.stat().st_size,
                                     md5=hashlib.md5(path.read_bytes()).hexdigest())
        return path

    def test_full_extraction_index_selection_and_offline_reuse_without_archive(self):
        package = self.package()
        with patch('requests.Session.get') as get:
            paths = acq.download(self.config, self.plan, self.log)
            get.assert_not_called()
        self.assertEqual([p.name for p in paths], ['DGM1_32_498_5554_1_he.tif'])
        self.assertEqual(len(list(raw_directory(self.config).iterdir())), 2)
        self.assertTrue(all(p.suffix == '.tif' for p in raw_directory(self.config).iterdir()))
        index = acq.complete_index(self.config)
        self.assertEqual(len(index['tiles']), 2)
        self.assertTrue((package.parent / 'metadata.json').exists())
        self.assertTrue((package.parent / 'LICENSE.pdf').exists())
        package.unlink()
        with patch.object(acq, 'archive') as fetch, patch.object(acq, 'validate_native', wraps=validate_native) as read_header:
            self.assertEqual(acq.download(self.config, self.plan, self.log), paths)
            fetch.assert_not_called()
            read_header.assert_called_once_with(paths[0])
        with gdal.Open(str(paths[0]), gdal.GA_Update) as ds:
            ds.GetRasterBand(1).Fill(3)
        with self.assertRaisesRegex(ValueError, 'differs from its receipt'):
            acq.download(self.config, self.plan, self.log)

    def test_missing_tile_resumes_from_archive_and_probe_never_marks_partial_extraction_complete(self):
        self.package()
        near = acq.probe(self.config, self.plan, self.log)
        far = raw_directory(self.config) / 'DGM1_32_600_5554_1_he.tif'
        self.assertTrue(far.exists())
        far.unlink()
        self.assertIsNone(acq.complete_index(self.config))
        with patch('requests.Session.get') as get:
            self.assertEqual(acq.download(self.config, self.plan, self.log), [near])
            get.assert_not_called()
        self.assertTrue(far.exists())
        other = deepcopy(self.plan)
        other['selection_wkt'] = rectangle([600000, 5554000, 600010, 5554010]).ExportToWkt()
        with self.assertRaises(RuntimeError):
            acq.download(self.config, other, self.log)

    def test_interrupted_extraction_has_no_completion_marker_and_resumes(self):
        self.package()
        original = tarfile.TarFile.extractfile

        def interrupted(package, member):
            if '600_5554' in member.name:
                raise OSError('simulated interruption')
            return original(package, member)

        with patch.object(tarfile.TarFile, 'extractfile', interrupted), self.assertRaises(OSError):
            acq.download(self.config, self.plan, self.log)
        self.assertIsNone(acq.complete_index(self.config))
        self.assertEqual(len(list(raw_directory(self.config).glob('*.tif'))), 1)
        self.assertFalse(list(scoped_root(self.config, 'logs_dir').rglob('*.part')))
        acq.download(self.config, self.plan, self.log)
        self.assertIsNotNone(acq.complete_index(self.config))

    def test_archive_refresh_integrity_failure_preserves_previous_files(self):
        package = self.package()
        paths = acq.download(self.config, self.plan, self.log)
        receipt = receipt_path(paths[0], self.config).read_bytes()
        digest = sha256(paths[0])
        self.config['reuse_cache'] = False
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [b'broken']
        with patch('requests.Session.get', return_value=response), self.assertRaisesRegex(RuntimeError, 'MD5'):
            acq.download(self.config, self.plan, self.log)
        self.assertTrue(verify_archive(package, self.config['source']))
        self.assertEqual(sha256(paths[0]), digest)
        self.assertEqual(receipt_path(paths[0], self.config).read_bytes(), receipt)
        response.iter_content.return_value = [package.read_bytes()]
        with patch('requests.Session.get', return_value=response) as get:
            self.assertEqual(acq.download(self.config, self.plan, self.log), paths)
            get.assert_called_once()

    def test_unsafe_and_duplicate_members_rejected_before_extraction(self):
        for entries in [[('../outside.tif', b'bad')], [('a/tile.tif', b'a'), ('b/TILE.tif', b'b')]]:
            with self.subTest(entries=entries):
                self.package(entries)
                with self.assertRaisesRegex(ValueError, 'Unsafe|Duplicate'):
                    acq.download(self.config, self.plan, self.log)
                self.assertFalse(list(raw_directory(self.config).glob('*.tif')))

    def test_native_metadata_and_filename_bounds_are_enforced(self):
        for label in ('offset', 'resolution', 'crs', 'nodata', 'dtype', 'rotation'):
            with self.subTest(label=label):
                path = self.raw(label + '.tif')
                with gdal.Open(str(path), gdal.GA_Update) as ds:
                    gt = list(ds.GetGeoTransform())
                    if label == 'offset': gt[0] += .5
                    if label == 'resolution': gt[1] = 2
                    if label == 'rotation': gt[2] = .1
                    ds.SetGeoTransform(gt)
                    if label == 'crs': ds.SetSpatialRef(srs(25833))
                    if label == 'nodata': ds.GetRasterBand(1).SetNoDataValue(-1e10)
                if label == 'dtype':
                    other = path.with_name('float64.tif')
                    with gdal.Translate(str(other), str(path), outputType=gdal.GDT_Float64):
                        pass
                    path = other
                with self.assertRaises(ValueError):
                    validate_native(path)
        source = self.raw()
        self.package([('files/DGM1_32_498_5554_1_he.tif', source.read_bytes())])
        with patch.object(acq, 'filename_bounds', return_value=[498000, 5554000, 499001, 5555000]):
            with self.assertRaisesRegex(ValueError, 'bounds differ'):
                acq.download(self.config, self.plan, self.log)

    def test_unknown_names_use_validated_native_bounds_and_links_are_rejected(self):
        source = self.raw('source.tif')
        package = self.package([('files/source.tif', source.read_bytes())])
        paths = acq.download(self.config, self.plan, self.log)
        self.assertEqual(paths[0].name, 'source.tif')
        self.assertEqual(acq.complete_index(self.config)['tiles'][0]['bounds'],
                         [498000, 5554000, 499000, 5555000])
        with tarfile.open(package, 'a') as tf:
            entry = tarfile.TarInfo('linked.tif')
            entry.type = tarfile.SYMTYPE
            entry.linkname = 'files/source.tif'
            tf.addfile(entry)
        with tarfile.open(package) as tf, self.assertRaisesRegex(ValueError, 'Unsafe'):
            acq.members(tf)
        with tarfile.open(self.root / 'missing_metadata.tar', 'w') as tf:
            entry = tarfile.TarInfo('files/source.tif')
            entry.size = 1
            tf.addfile(entry, io.BytesIO(b'x'))
        with tarfile.open(self.root / 'missing_metadata.tar') as tf, self.assertRaisesRegex(ValueError, 'metadata.json'):
            acq.members(tf)

    def test_exact_average_seam_nodata_and_shared_reference(self):
        values = np.arange(100, dtype='float32').reshape(10, 10)
        values[:5, :5] = -9999
        values[0, 5] = -9999
        geometry = rectangle([498010, 5554010, 498020, 5554020])
        geometry.AssignSpatialReference(srs(25832))
        paths = [raster(self.root / 'left.tif', values[:, :5], 25832, (498010, 1, 0, 5554020, 0, -1)),
                 raster(self.root / 'right.tif', values[:, 5:], 25832, (498015, 1, 0, 5554020, 0, -1))]
        original = [sha256(p) for p in paths]
        # The shared reference extends beyond source coverage and AOI.
        larger = rectangle([498005, 5554005, 498025, 5554025])
        larger.AssignSpatialReference(srs(25832))
        ref = write_reference(plan_grid(larger, self.config['target']), self.root / 'target.vrt')
        result = hessen.prepare(paths, geometry, ref, self.root / 'prepared', self.config)
        expected = np.full((4, 4), -9999, dtype='float32')
        for row in range(2):
            for col in range(2):
                block = values[row*5:row*5+5, col*5:col*5+5]
                valid = block[block != -9999]
                if valid.size:
                    expected[row+1, col+1] = valid.mean()
        with gdal.Open(result['prepared_raster']) as ds:
            np.testing.assert_array_equal(ds.ReadAsArray(), expected)
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            self.assertIn('unverified', ds.GetMetadataItem('VERTICAL_DATUM_NOTE'))
        verify_alignment(result['prepared_raster'], ref)
        self.assertEqual([sha256(p) for p in paths], original)
        self.assertIsNone(result['vertical_datum'])
        self.assertFalse(result['separate_alignment'])

    def test_coordinator_plan_and_end_to_end_run_preserve_regional_layout(self):
        self.package()
        aoi = self.root / 'aoi.gpkg'
        with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
            layer = ds.CreateLayer('hessen', srs(25832), ogr.wkbPolygon)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(self.geometry)
            layer.CreateFeature(feature)
        self.config['aoi'] = str(aoi)
        with patch('requests.Session.get') as get:
            plan = execute(self.config, 'plan')
            self.assertEqual(plan['region'], 'hessen')
            self.assertFalse(list(scoped_root(self.config, 'output_root').glob('*/processed')))
            result = execute(self.config, 'yes')
            get.assert_not_called()
        run = scoped_root(self.config, 'output_root') / result['run_id']
        self.assertTrue((run / 'processed/target_grid.json').exists())
        self.assertEqual(Path(result['prepared_raster']), run / 'stitched/hessen.tif')
        latest = scoped_root(self.config, 'logs_dir') / 'latest_run.json'
        self.assertEqual(json.loads(latest.read_text())['run_id'], result['run_id'])
        for change in ({'target': {'resolution': 1}}, {'hole_filling': {'enabled': True}}):
            with self.assertRaises(ValueError):
                hessen.validate_config({**deepcopy(self.config), **change})
