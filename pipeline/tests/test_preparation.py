"""Small, offline integration checks for country preparation and grid contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal, ogr

from dtm.acquire import params, sha256, write_json
from dtm.coordinator import execute, load_config
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
        self.settings = {'country': 'netherlands', 'aoi': 'aoi.gpkg', 'target': {'reference_raster': None},
                         'source': {'url': 'https://example.invalid/wcs', 'coverage': 'dtm_05m',
                                    'epsg': 28992, 'resolution': .5, 'chunk_size_m': 8, 'vertical_datum': 'NAP'},
                         'hole_filling': {'enabled': False},
                         'processed_tile_size_pixels': 3,
                         'block_size': 2, 'request_pause_seconds': 0}
        write_json(self.config_path, self.settings)
        self.config = load_config(self.config_path)

    def tearDown(self):
        self.temp.cleanup()

    def test_aoi_grid_covers_polygon_and_has_integer_metre_edges(self):
        info = plan_grid(self.geometry, {})
        x0, y0, x1, y1 = bounds(project(self.geometry, srs(25832)))
        left, bottom, right, top = info['extent']
        self.assertLessEqual(left, x0)
        self.assertLessEqual(bottom, y0)
        self.assertGreaterEqual(right, x1)
        self.assertGreaterEqual(top, y1)
        self.assertTrue(all(value == int(value) for value in info['extent']))
        self.assertEqual(info['cols'], right - left)
        self.assertEqual(info['rows'], top - bottom)
        self.assertEqual(info['transform'][1:], [1, 0, top, 0, -1])
        self.assertEqual(info, plan_grid(self.geometry, {}))
        reference = write_reference(info, self.root / 'target.vrt')
        self.assertLess(reference.stat().st_size, 10000)

    def test_reference_rejects_wrong_crs_and_incomplete_extent(self):
        wrong_crs = raster(self.root / 'wrong.tif', np.ones((4, 4)))
        with self.assertRaisesRegex(ValueError, 'EPSG:25832'):
            plan_grid(self.geometry, {'reference_raster': str(wrong_crs)})
        small = raster(self.root / 'small.tif', np.ones((1, 1)), epsg=25832, transform=(0, 1, 0, 1, 0, -1))
        with self.assertRaisesRegex(ValueError, 'whole AOI'):
            plan_grid(self.geometry, {'reference_raster': str(small)})
        target = write_reference(plan_grid(self.geometry, {}), self.root / 'target.vrt')
        self.assertEqual(plan_grid(self.geometry, {'reference_raster': str(target)})['mode'], 'reference')

    def test_plan_has_no_network_calls_and_resolves_relative_paths(self):
        with patch('requests.Session.get') as get:
            plan = execute(self.config, 'plan')
        get.assert_not_called()
        self.assertEqual(plan['country'], 'netherlands')
        self.assertEqual(plan['metadata_requests'], 2)
        self.assertEqual(Path(self.config['cache_root']), self.root / 'data')
        self.assertFalse((self.root / 'data/prepared/netherlands/latest_run.json').exists())

    def test_download_adapter_selects_only_ahn_and_existing_cache_layout(self):
        directory = self.root / 'data/ahn_tiles'
        directory.mkdir(parents=True)
        raw = raster(directory / 'legacy.tif', np.ones((16, 16)))
        tile = {'id': 'legacy', 'bounds': [200000, 425000, 200008, 425008]}
        source = self.config['source']
        write_json(raw.with_suffix('.json'), {'source': source, 'request': params(source, tile), 'sha256': sha256(raw)})
        with patch('dtm.countries.netherlands.acquisition.metadata'), patch('dtm.countries.netherlands.acquisition.download_tile') as fetch:
            result = download(self.config, {'tiles': [tile]}, self.root / 'newrun')
            self.assertEqual(result, [raw])
            fetch.assert_not_called()
            # A later run also finds raw tiles saved in the new layout.
            new_cache = Path(self.config['output_root']) / 'netherlands/previous/raw_ahn_tiles'
            new_cache.mkdir(parents=True)
            moved = new_cache / raw.name
            moved.write_bytes(raw.read_bytes())
            moved.with_suffix('.json').write_bytes(raw.with_suffix('.json').read_bytes())
            result = download(self.config, {'tiles': [tile]}, self.root / 'next')
            self.assertEqual(result, [moved])
            fetch.assert_not_called()
            self.config['reuse_cache'] = False
            download(self.config, {'tiles': [tile]}, self.root / 'freshrun')
            self.assertEqual(fetch.call_args.args[3], Path(self.config['output_root']) / 'netherlands/freshrun/raw_ahn_tiles')

    def test_defaults_enable_twenty_metre_filling(self):
        self.settings.pop('hole_filling')
        write_json(self.config_path, self.settings)
        config = load_config(self.config_path)
        self.assertTrue(config['hole_filling']['enabled'])
        self.assertEqual(config['hole_filling']['max_distance_m'], 20)

    def test_preparation_matches_existing_warp_and_masks_holes(self):
        values = np.arange(256, dtype='float32').reshape(16, 16) / 10 - 5
        values[:4, :4] = np.finfo('float32').max
        values[12:, 12:] = -9999
        raw = raster(self.root / 'raw.tif', values)
        before = sha256(raw)
        target = write_reference(plan_grid(self.geometry, {}), self.root / 'target.vrt')
        run = self.root / 'run'
        result = prepare([raw], self.geometry, target, run, self.config)
        self.assertEqual(Path(result['comparison_ready_raster']), run / 'ahn_stitched/ahn.tif')
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

    def test_coordinator_completion_and_empty_coverage_preserve_latest_success(self):
        raw = raster(self.root / 'raw.tif', np.full((16, 16), 12))
        write_json(raw.with_suffix('.json'), {'sha256': sha256(raw)})
        with patch('dtm.countries.netherlands.download', return_value=[raw]), patch('requests.Session.get') as get:
            result = execute(self.config, 'yes')
        get.assert_not_called()
        self.assertEqual(result['stage'], 'prepared')
        latest = self.root / 'data/prepared/netherlands/latest_run.json'
        saved = latest.read_bytes()
        self.assertEqual(json.loads(saved)['status'], 'complete')
        raster(raw, np.full((16, 16), -9999))
        with patch('dtm.countries.netherlands.download', return_value=[raw]):
            with self.assertRaisesRegex(RuntimeError, 'No valid AHN coverage'):
                execute(self.config, 'yes')
        self.assertEqual(latest.read_bytes(), saved)

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
