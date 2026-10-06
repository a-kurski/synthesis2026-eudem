"""Direct native-to-5 m aggregation and the shared zero-origin lattice."""
import math
import unittest
from unittest.mock import patch

import numpy as np
from osgeo import gdal, ogr

from test_preparation import PreparationTests, raster
from dtm.acquire import sha256
from dtm.countries.netherlands import plan
from dtm.countries.netherlands.processing import prepare
from dtm.geo import bounds, grid, project, rectangle, srs, verify_alignment
from dtm.process import align
from dtm.target_grid import plan_grid, resolution, write_reference


class FiveMetreTests(unittest.TestCase):
    setUp = PreparationTests.setUp
    tearDown = PreparationTests.tearDown

    def test_invalid_resolution_and_separate_aoi_alignment(self):
        for value in (0, -1, True, '5', float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                resolution({'resolution': value})
        second = self.geometry.Clone()
        second = second.Buffer(17)
        second.AssignSpatialReference(srs(28992))
        a, b = plan_grid(self.geometry, {}), plan_grid(second, {})
        for index in (0, 3):
            self.assertEqual((a['transform'][index]-b['transform'][index]) % 5, 0)

    def test_acquisition_includes_five_metre_boundary_context_without_filling(self):
        self.config['target']['resolution'] = 5
        result = plan(self.geometry, self.config)
        self.assertAlmostEqual(result['resampling_context_m'], 5 / math.sqrt(2))
        self.assertEqual(result['context_buffer_m'], .5)
        old = bounds(project(self.geometry, srs(28992)))
        new = result['aoi_extent']
        self.assertTrue(new[0] < old[0] and new[1] < old[1] and new[2] > old[2] and new[3] > old[3])

    def test_filled_and_unfilled_outputs_match_direct_native_average(self):
        self.config['target']['resolution'] = 5
        self.config['hole_filling'] = {'enabled': True, 'max_distance_m': 20}
        geometry = ogr.CreateGeometryFromWkt(
            'POLYGON ((200005 425005,200035 425005,200035 425035,200005 425035,200005 425005),'
            '(200015 425015,200015 425025,200025 425025,200025 425015,200015 425015))')
        geometry.AssignSpatialReference(srs(28992))
        rows, cols = np.indices((80,80))
        values = (rows*.07 + cols*.11 + (cols%3)*.9).astype('float32')
        values[10:26,10:26] = -9999
        raw = raster(self.root/'native.tif',values,transform=(200000,.5,0,425040,0,-.5))
        checksum = sha256(raw)
        info = plan_grid(geometry, self.config['target'])
        reference = write_reference(info,self.root/'target5.vrt')
        calls=[]
        def checked_align(source, target, destination, config):
            # Exactly one native-to-target warp, before filling.
            self.assertEqual(grid(source)['transform'][1],.5)
            self.assertEqual(grid(target)['transform'][1],5)
            self.assertFalse((self.root/'run/processed/_work/hole_filling/ahn_filled.tif').exists())
            calls.append(str(source))
            return align(source,target,destination,config)
        with patch('dtm.countries.netherlands.processing.align',side_effect=checked_align):
            result=prepare([raw],geometry,reference,self.root/'run',self.config)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['hole_filling']['source_grid']['transform'][1], 5)
        self.assertEqual(result['hole_filling']['max_search_pixels'], 4)
        with gdal.Open(result['aoi_mask']) as mask_ds:
            mask=mask_ds.ReadAsArray()!=0
        self.assertTrue((~mask).any())
        for source, output in [(result['native_mosaic'],result['prepared_raster'])]:
            verify_alignment(output,reference)
            with gdal.Warp('',source,format='MEM',srcSRS='EPSG:28992',dstSRS='EPSG:25832',
                           outputBounds=info['extent'],width=info['cols'],height=info['rows'],
                           resampleAlg='average',srcNodata=-9999,dstNodata=-9999,
                           outputType=gdal.GDT_Float32,errorThreshold=0) as direct, gdal.Open(output) as actual:
                expected=direct.ReadAsArray()
                expected[~mask]=-9999
                np.testing.assert_allclose(actual.ReadAsArray(),expected,rtol=0,atol=1e-5)
        self.assertGreater(result['hole_filling']['filled_cell_count'],0)
        self.assertEqual(sha256(raw),checksum)
        self.assertFalse((self.root/'run/processed/unfilled').exists())
        self.assertFalse((self.root/'run/processed/fill_fraction').exists())
        with gdal.Open(result['fill_fraction']) as ds:
            self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            fractions=ds.ReadAsArray()
            self.assertTrue(np.all(np.isin(fractions[fractions != -9999], [0, 1])))
        with gdal.Open(result['prepared_raster']) as baseline, gdal.Open(result['comparison_ready_raster']) as filled:
            for dataset in (baseline, filled):
                self.assertEqual(dataset.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
            original, actual = baseline.ReadAsArray(), filled.ReadAsArray()
            valid = original != -9999
            np.testing.assert_array_equal(actual[valid], original[valid])
            np.testing.assert_array_equal(fractions == 1, (~valid) & (actual != -9999))
            self.assertTrue(np.any(fractions == 1))
        verify_alignment(result['comparison_ready_raster'], reference)
        verify_alignment(result['fill_fraction'], reference)
        for tile in (self.root/'run/processed').glob('*.tif'):
            g=grid(tile)
            self.assertEqual(g['transform'][1],5)
            self.assertEqual(g['transform'][0]%5,0)
            self.assertEqual(g['transform'][3]%5,0)


del PreparationTests
