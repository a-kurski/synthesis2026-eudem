"""Regression checks for official RLP 1001-sample and mixed-grid tiles."""
import numpy as np
from osgeo import gdal

import test_rlp
from dtm.acquire import cached, download_tile, sha256
from dtm.countries.germany import rlp
from dtm.geo import rectangle, srs, validate_tile, verify_alignment
from dtm.target_grid import plan_grid, write_reference


class RLPLayoutTests(test_rlp.RLPTests):
    def nodes(self, name='nodes.tif', x=423000, value=None):
        path = self.root / name
        rows, cols = np.indices((1001, 1001))
        values = (rows * .25 + cols * cols * .001 + 12).astype('float32')
        if value is not None:
            values.fill(value)
        with gdal.GetDriverByName('GTiff').Create(str(path), 1001, 1001, 1, gdal.GDT_Float32) as ds:
            ds.SetSpatialRef(srs(25832))
            ds.SetGeoTransform((x - .5, 1, 0, 5633000.5, 0, -1))
            ds.GetRasterBand(1).SetNoDataValue(-1e10)
            ds.GetRasterBand(1).WriteArray(values)
        return path, values

    def output(self, paths, extent, run='run'):
        geometry = rectangle(extent)
        geometry.AssignSpatialReference(srs(25832))
        reference = write_reference(plan_grid(geometry, self.config['target']), self.root / (run + '.vrt'))
        result = rlp.prepare(paths, geometry, reference, self.root / run, self.config)
        verify_alignment(result['prepared_raster'], reference)
        with gdal.Open(result['prepared_raster']) as ds:
            values = ds.ReadAsArray()
        return values, result

    def test_nodes_validation_download_cache_and_raw_preservation(self):
        raw, values = self.nodes()
        info = validate_tile(raw, self.config['source'], self.tile)
        self.assertEqual(info['valid_cells'], 1002001)
        self.tile.update(size=raw.stat().st_size, sha256=sha256(raw))
        directory = self.root / 'downloads'
        directory.mkdir()
        output = download_tile(self.response_session(raw.read_bytes()), self.config['source'],
                               self.tile, directory, self.config)
        self.assertEqual(sha256(output), sha256(raw))
        self.assertTrue(cached(output, self.config['source'], self.tile))
        bad_source = {**self.config['source'], 'metalink_url': 'https://example.invalid/tiles'}
        with self.assertRaisesRegex(ValueError, 'vertical CRS'):
            validate_tile(raw, bad_source, self.tile)
        with self.assertRaisesRegex(ValueError, 'extent'):
            validate_tile(raw, self.config['source'], {**self.tile, 'bounds': [0, 0, 1000, 1000]})
        with gdal.Open(str(raw), gdal.GA_Update) as ds:
            ds.SetGeoTransform((422999.25, 1, 0, 5633000.5, 0, -1))
        with self.assertRaisesRegex(ValueError, 'lattice'):
            validate_tile(raw, self.config['source'], self.tile)

    def test_nodes_weighted_mean_nodata_and_raw_checksum(self):
        raw, values = self.nodes()
        values[0:6, 0:6] = -1e10
        values[1, 6] = -1e10
        with gdal.Open(str(raw), gdal.GA_Update) as ds:
            ds.GetRasterBand(1).WriteArray(values)
        before = sha256(raw)
        actual, result = self.output([raw], [423000, 5632990, 423010, 5633000])
        weights = np.outer([.5, 1, 1, 1, 1, .5], [.5, 1, 1, 1, 1, .5])
        expected = np.full((2, 2), -9999., dtype='float32')
        for y in range(2):
            for x in range(2):
                block = values[y*5:y*5+6, x*5:x*5+6]
                valid = block != np.float32(-1e10)
                if valid.any():
                    expected[y, x] = (block[valid] * weights[valid]).sum() / weights[valid].sum()
        np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-5)
        self.assertEqual(sha256(raw), before)
        self.assertTrue(result['separate_alignment'])
        self.assertNotIn('native_mosaic', result)

    def test_mixed_lattice_seam_and_order_independence(self):
        left, values = self.nodes()
        right = self.raw()
        with gdal.Open(str(right), gdal.GA_Update) as ds:
            ds.SetGeoTransform((424000, 1, 0, 5633000, 0, -1))
        hashes = [sha256(left), sha256(right)]
        extent = [423995, 5632990, 424005, 5633000]
        actual, result = self.output([left, right], extent)
        reverse, _ = self.output([right, left], extent, 'reverse')
        expected = np.empty((2, 2), dtype='float32')
        weights = np.outer([.5, 1, 1, 1, 1, .5], [.5, 1, 1, 1, 1, .5])
        for y in range(2):
            expected[y, 0] = (values[y*5:y*5+6, 995:1001] * weights).sum() / 25
            expected[y, 1] = self.values[y*5:y*5+5, :5].mean(dtype='float64')
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-4)
        np.testing.assert_array_equal(actual, reverse)
        self.assertEqual([sha256(left), sha256(right)], hashes)

    def test_adjacent_node_borders_have_single_kilometre_ownership(self):
        left, _ = self.nodes(value=10)
        right, _ = self.nodes('right.tif', x=424000, value=100)
        actual, _ = self.output([left, right], [423995, 5632995, 424005, 5633000])
        np.testing.assert_array_equal(actual, [[10, 100]])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.output([left, left], [423995, 5632995, 424005, 5633000], 'duplicate')
