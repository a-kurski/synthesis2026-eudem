"""Define the shared horizontal comparison grid independently of any country."""
import math

from osgeo import gdal, osr

from .geo import bounds, grid, project, srs


def plan_grid(geometry, target):
    """Use a German reference raster, or snap the AOI to a 1 m UTM32 lattice.

    A reference must cover the entire AOI: silently cropping it would discard
    requested terrain. Its pixel values are never used during preparation.
    """
    if target.get('epsg', 25832) != 25832:
        raise ValueError('The current comparison target must be EPSG:25832.')
    extent = bounds(project(geometry, srs(25832)))
    if target.get('reference_raster'):
        info = grid(target['reference_raster'])
        if not osr.SpatialReference(wkt=info['crs']).IsSame(srs(25832)):
            raise ValueError('The reference raster must use EPSG:25832.')
        if not math.isclose(info['transform'][1], 1, abs_tol=1e-8, rel_tol=0) or not math.isclose(info['transform'][5], -1, abs_tol=1e-8, rel_tol=0):
            raise ValueError('The reference raster must have 1 m pixels.')
        left, bottom, right, top = info['extent']
        x0, y0, x1, y1 = extent
        if x0 < left - 1e-7 or y0 < bottom - 1e-7 or x1 > right + 1e-7 or y1 > top + 1e-7:
            raise ValueError('The reference raster does not cover the whole AOI. Supply a larger reference or set reference_raster to null.')
        return {**info, 'mode': 'reference', 'reference_raster': target['reference_raster']}
    x0, y0 = math.floor(extent[0]), math.floor(extent[1])
    x1, y1 = math.ceil(extent[2]), math.ceil(extent[3])
    return {'mode': 'aoi', 'cols': x1 - x0, 'rows': y1 - y0,
            'transform': [x0, 1.0, 0.0, y1, 0.0, -1.0],
            'extent': [x0, y0, x1, y1], 'crs': srs(25832).ExportToWkt(),
            'nodata': -9999, 'dtype': 'Float32'}


def write_reference(info, path):
    """Write a tiny geometry-only VRT snapshot; it contains no German heights."""
    with gdal.GetDriverByName('VRT').Create(str(path), info['cols'], info['rows'], 1, gdal.GDT_Float32) as ds:
        ds.SetProjection(info['crs'])
        ds.SetGeoTransform(info['transform'])
        ds.GetRasterBand(1).SetNoDataValue(-9999)
    return path
