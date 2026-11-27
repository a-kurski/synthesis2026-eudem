"""COG publication preserves terrain values and includes display overviews."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
from osgeo import gdal
from osgeo_utils.samples.validate_cloud_optimized_geotiff import validate

from test_preparation import raster
from dtm.publication import publish_tiles


class CogTests(unittest.TestCase):
    def test_publication_preserves_values_metadata_and_internal_overviews(self):
        with tempfile.TemporaryDirectory(prefix='dtm_cog_') as directory:
            root = Path(directory)
            values = np.arange(600 * 620, dtype='float32').reshape(600, 620) / 13
            values[:20, :20] = -9999
            source = raster(root / 'source.tif', values)
            with gdal.Open(str(source), gdal.GA_Update) as ds:
                ds.SetMetadataItem('VERTICAL_DATUM_NOTE', 'AHN remains NAP')
                ds.GetRasterBand(1).SetUnitType('m')
            result = publish_tiles(source, root / 'tiles', root / 'ahn.tif',
                                   {'nodata': -9999, 'block_size': 256,
                                    'alignment_tolerance_m': 1e-8,
                                    'processed_tile_size_pixels': 550})
            for path in [Path(result['stitched']), *sorted((root / 'tiles').glob('*.tif'))]:
                with gdal.Open(str(path)) as ds:
                    self.assertEqual(ds.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE'), 'COG')
                    self.assertEqual(ds.GetRasterBand(1).GetBlockSize(), [512, 512])
                    self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), -9999)
                    self.assertEqual(ds.GetRasterBand(1).GetUnitType(), 'm')
                    self.assertEqual(ds.GetMetadataItem('VERTICAL_DATUM_NOTE'), 'AHN remains NAP')
                    if max(ds.RasterXSize, ds.RasterYSize) > 512:
                        self.assertGreater(ds.GetRasterBand(1).GetOverviewCount(), 0)
                    warnings, errors, details = validate(ds, full_check=True)
                    self.assertFalse(errors, errors)
            with gdal.Open(result['stitched']) as ds:
                np.testing.assert_array_equal(ds.ReadAsArray(), values)
                overview = ds.GetRasterBand(1).GetOverview(0).ReadAsArray()
                self.assertEqual(overview[0, 0], -9999)
                self.assertAlmostEqual(float(overview[20, 20]),
                                       float(values[40:42, 40:42].mean()), places=3)
            self.assertFalse(list(root.rglob('*.ovr')))
