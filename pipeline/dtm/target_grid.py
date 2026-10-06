"""Define the shared horizontal comparison grid independently of any country."""
import math

from osgeo import gdal, osr

from .geo import bounds, grid, project, srs


def resolution(target):
    value = target.get('resolution', 5)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('target.resolution must be a finite positive number in metres.')
    return float(value)


def plan_grid(geometry, target):
    """Use a German reference raster, or snap to the target UTM32 lattice (5 m default).

    A reference must cover the entire AOI: silently cropping it would discard
    requested terrain. Its pixel values are never used during preparation.
    """
    if target.get('epsg', 25832) != 25832:
        raise ValueError('The current comparison target must be EPSG:25832.')
    step = resolution(target)
    extent = bounds(project(geometry, srs(25832)))
    if target.get('reference_raster'):
        info = grid(target['reference_raster'])
        if not osr.SpatialReference(wkt=info['crs']).IsSame(srs(25832)):
            raise ValueError('The reference raster must use EPSG:25832.')
        if not math.isclose(info['transform'][1], step, abs_tol=1e-8, rel_tol=0) or not math.isclose(info['transform'][5], -step, abs_tol=1e-8, rel_tol=0):
            raise ValueError(f'The reference raster must have {step:g} m pixels.')
        if any(not math.isclose(info['transform'][i], round(info['transform'][i] / step) * step,
                                abs_tol=1e-8, rel_tol=0) for i in (0, 3)):
            raise ValueError(f'The reference origin must align to multiples of {step:g} m.')
        left, bottom, right, top = info['extent']
        x0, y0, x1, y1 = extent
        if x0 < left - 1e-7 or y0 < bottom - 1e-7 or x1 > right + 1e-7 or y1 > top + 1e-7:
            raise ValueError('The reference raster does not cover the whole AOI. Supply a larger reference or set reference_raster to null.')
        return {**info, 'mode': 'reference', 'reference_raster': target['reference_raster']}
    x0, y0 = math.floor(extent[0] / step) * step, math.floor(extent[1] / step) * step
    x1, y1 = math.ceil(extent[2] / step) * step, math.ceil(extent[3] / step) * step
    return {'mode': 'aoi', 'cols': round((x1 - x0) / step), 'rows': round((y1 - y0) / step),
            'transform': [x0, step, 0.0, y1, 0.0, -step],
            'extent': [x0, y0, x1, y1], 'crs': srs(25832).ExportToWkt(),
            'nodata': -9999, 'dtype': 'Float32'}


def write_reference(info, path):
    """Write a tiny geometry-only VRT snapshot; it contains no German heights."""
    with gdal.GetDriverByName('VRT').Create(str(path), info['cols'], info['rows'], 1, gdal.GDT_Float32) as ds:
        ds.SetProjection(info['crs'])
        ds.SetGeoTransform(info['transform'])
        ds.GetRasterBand(1).SetNoDataValue(-9999)
    return path
