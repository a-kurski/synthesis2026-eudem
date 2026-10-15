"""Offline checks: merge rules plus a two-region end-to-end run (rivers stage skipped).

Run: python -m unittest discover tests
"""
import json
from pathlib import Path
import importlib.util
import tempfile
import unittest

import numpy as np
from osgeo import gdal, ogr

from dtm.geo import srs
from dtm.pipeline import main, merge, write_vector

gdal.UseExceptions()


def box(x0, y0, x1, y1):
    g = ogr.CreateGeometryFromWkt(f'POLYGON (({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))')
    g.AssignSpatialReference(srs(25832))
    return g


def tile(path, x0, y1, values, res=2.5):
    ds = gdal.GetDriverByName('GTiff').Create(str(path), values.shape[1], values.shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform([x0, res, 0, y1, 0, -res])
    ds.SetSpatialRef(srs(25832))
    ds.GetRasterBand(1).SetNoDataValue(-9999)
    ds.GetRasterBand(1).WriteArray(values)
    ds = None


class MergeRules(unittest.TestCase):
    def test_rules(self):
        za, zb = np.full((1, 4), 10.), np.full((1, 4), 13.)
        yes, no = np.ones((1, 4), bool), np.zeros((1, 4), bool)
        in_a = np.array([[1, 1, 0, 0]], bool)
        # No interpolation: no overrides at all (owners keep their data, big difference or not).
        self.assertTrue(np.isnan(merge(za, yes, zb, yes, in_a, ~in_a, no, no)).all())
        # A interpolated everywhere, B measured: A's cells take B; B's cells untouched.
        np.testing.assert_array_equal(merge(za, yes, zb, yes, in_a, ~in_a, yes, no), [[13, 13, np.nan, np.nan]])
        # Both interpolated, or the neighbour has no data: no override.
        self.assertTrue(np.isnan(merge(za, yes, zb, yes, in_a, ~in_a, yes, yes)).all())
        self.assertTrue(np.isnan(merge(za, yes, zb, no, in_a, ~in_a, yes, no)).all())


class EndToEnd(unittest.TestCase):
    def test_two_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            x0, y0, mid, x1, y1 = 300000, 5600000, 304000, 308000, 5604000
            write_vector(box(x0, y0, mid, y1), root / 'a.gpkg')
            write_vector(box(mid, y0, x1, y1), root / 'b.gpkg')
            write_vector(box(x0 - 500, y0 - 500, x1 + 500, y1 + 500), root / 'basin.gpkg')
            (root / 'a').mkdir()
            (root / 'b').mkdir()
            # A: 100 m everywhere with a hole; extends 1.5 km into B.
            a = np.full((1600, 2200), 100, 'float32')
            a[200:220, 200:220] = -9999  # hole far from B
            a[200:220, 1720:1740] = -9999  # hole 150-200 m inside A, where B is measured
            tile(root / 'a/t1.tif', x0 - 500, y1, a[:, :1100])
            tile(root / 'a/t2.tif', x0 - 500 + 1100 * 2.5, y1, a[:, 1100:])
            # B: 100.3 m except a 110 m block inside A's side of the overlap.
            b = np.full((1600, 2200), 100.3, 'float32')
            b[400:600, 0:600] = 110
            tile(root / 'b/t1.tif', mid - 1500, y1, b)
            region = {'point_clouds': None, 'crs': 25832, 'vertical_crs': None, 'crop': False}
            config = {'settings': {'crs': 25832, 'vertical_crs': None, 'resolution': 5, 'extent': 'basin.gpkg',
                                   'buffer_m': 1000, 'output_dir': 'out', 'hole_filling': {'max_distance_m': 100, 'nearest_fallback': False}},
                      'regions': {'a': {**region, 'vector': 'a.gpkg', 'raster': 'a/*.tif', 'interpolate': True},
                                  'b': {**region, 'vector': 'b.gpkg', 'raster': 'b/*.tif', 'interpolate': False}}}
            path = root / 'pipeline.json'
            path.write_text(json.dumps(config))
            main([str(path), '--stages', 'vectors', 'rasters', 'overlaps', 'assemble'])
            result = json.loads(path.read_text())
            self.assertEqual(result['regions']['a']['intersections'], ['b'])
            self.assertIn('a__b', result['overlaps'])
            self.assertTrue((root / result['regions']['a']['fill_mask']).exists())
            with gdal.Open(str(root / result['product'])) as ds:
                self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
                product = ds.ReadAsArray()
            at = lambda x, y: product[int((y1 + 500 - y) / 5), int((x - x0 + 500) / 5)]
            self.assertEqual(at(x0 - 250, y0), -9999)                    # outside every region polygon
            self.assertAlmostEqual(at(x0 + 1000, y0 + 1000), 100, 3)     # A interior
            self.assertAlmostEqual(at(x0 + 25, y1 - 525), 100, 3)        # A hole, interpolated
            self.assertAlmostEqual(at(mid - 175, y1 - 525), 100.3, 3)    # A hole, B measured -> B
            self.assertAlmostEqual(at(x1 - 1000, y0 + 1000), 100.3, 3)   # B interior
            self.assertAlmostEqual(at(mid - 5, y0 + 1000), 100, 3)       # A side of the border: A
            self.assertAlmostEqual(at(mid + 5, y0 + 1000), 100.3, 3)     # B side of the border: B
            self.assertAlmostEqual(at(mid - 500, y1 - 1250), 100, 3)     # big difference, both measured -> owner


@unittest.skipUnless(importlib.util.find_spec('xdem'), 'river masks need xdem')
class RiverMask(unittest.TestCase):
    def test_grows_from_seed_point(self):
        from dtm.river_mask import create_masks
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dem = np.full((20, 20), 100, 'float32')
            dem[:, 2:5] = 95  # channel inside the region
            dem[:, 14:17] = 90  # channel outside the region
            tile(root / 'dem.tif', 300000, 5600100, dem, res=5)
            seeds = np.ones((20, 20), 'float32')
            seeds[10, 3] = seeds[10, 15] = 2  # a seed in each channel
            tile(root / 'seeds.tif', 300000, 5600100, seeds, res=5)
            config = root / 'pipeline.json'
            write_vector(box(300000, 5600000, 300050, 5600100), root / 'region.gpkg')  # left half
            config.write_text(json.dumps({'settings': {'output_dir': 'out', 'crs': 25832},
                                          'regions': {'a': {'dem': 'dem.tif', 'vector': 'region.gpkg',
                                                            'river_seeds': 'seeds.tif'}}}))
            create_masks(config)
            path = json.loads(config.read_text())['regions']['a']['river_mask']
            self.assertEqual(path, 'out/a/dem_river_mask.tif')
            mask = gdal.Open(str(root / path)).ReadAsArray()
            self.assertTrue((mask[:, 2:5] == 1).all())  # grown from the seed inside the region
            self.assertTrue((mask[:, 5:] == 0).all() and (mask[:, :2] == 0).all())  # outside seed ignored


@unittest.skipUnless(importlib.util.find_spec('xdem'), 'comparison needs xdem')
class ComparisonStatistics(unittest.TestCase):
    def test_threshold_counts(self):
        from dtm.comparison import difference_statistics
        stats = difference_statistics(np.array([0.5, -0.5, 2.0, np.nan]), 5 / 3)
        self.assertEqual((stats['valid_cells'], stats['cells_above_threshold']), (3, 1))
        self.assertAlmostEqual(stats['rmse'], np.sqrt((0.25 + 0.25 + 4) / 3))

if __name__ == '__main__':
    unittest.main()
