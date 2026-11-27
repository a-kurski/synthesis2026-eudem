"""Vector reading/reprojection, raster grid checks and small I/O helpers."""
import json
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
ogr.UseExceptions()
osr.UseExceptions()


def srs(epsg):
    result = osr.SpatialReference()
    result.ImportFromEPSG(epsg)
    result.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return result


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def bounds(geom):
    x0, x1, y0, y1 = geom.GetEnvelope()
    return [x0, y0, x1, y1]


def read_aoi(path, layer_name=None):
    ds = ogr.Open(str(path))
    if ds is None:
        raise ValueError(f'Cannot open AOI: {path}')
    if layer_name is None and ds.GetLayerCount() != 1:
        raise ValueError('AOI has multiple layers; set layer in config.json.')
    layer = ds.GetLayerByName(layer_name) if layer_name else ds.GetLayer(0)
    if layer is None or layer.GetSpatialRef() is None:
        raise ValueError('AOI layer missing or has no CRS.')
    crs = layer.GetSpatialRef().Clone()
    crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geometry = None
    for feature in layer:
        g = feature.GetGeometryRef()
        if g is None or g.IsEmpty() or not g.IsValid() or ogr.GT_Flatten(g.GetGeometryType()) not in (ogr.wkbPolygon, ogr.wkbMultiPolygon):
            raise ValueError('AOI must contain nonempty valid Polygon/MultiPolygon geometries.')
        geometry = g.Clone() if geometry is None else geometry.Union(g)
    if geometry is None:
        raise ValueError('AOI is empty.')
    geometry.AssignSpatialReference(crs)
    return geometry, crs, layer.GetName()


def project(geometry, target):
    g = geometry.Clone()
    # Densify before reprojection so long polygon edges follow their original CRS.
    g.Segmentize(100 if g.GetSpatialReference().IsProjected() else 0.001)
    g.Transform(osr.CoordinateTransformation(g.GetSpatialReference(), target))
    g.AssignSpatialReference(target)
    return g


def grid(path):
    ds = gdal.Open(str(path))
    gt = ds.GetGeoTransform()
    if abs(gt[2]) > 1e-12 or abs(gt[4]) > 1e-12 or gt[1] <= 0 or gt[5] >= 0:
        raise ValueError(f'Unsupported rotated or non-north-up raster: {path}')
    return {'cols': ds.RasterXSize, 'rows': ds.RasterYSize, 'transform': list(gt),
            'extent': [gt[0], gt[3] + ds.RasterYSize * gt[5], gt[0] + ds.RasterXSize * gt[1], gt[3]],
            'crs': ds.GetProjection(), 'nodata': ds.GetRasterBand(1).GetNoDataValue(),
            'dtype': gdal.GetDataTypeName(ds.GetRasterBand(1).DataType)}


def verify_alignment(a, b, tolerance=1e-8):
    a, b = grid(a), grid(b)
    ca, cb = osr.SpatialReference(wkt=a['crs']), osr.SpatialReference(wkt=b['crs'])
    if not ca.IsSame(cb):
        raise ValueError('Alignment failed: raster CRS differ.')
    for key in ('cols', 'rows'):
        if a[key] != b[key]:
            raise ValueError(f'Alignment failed: {key} differs ({a[key]} vs {b[key]}).')
    for key in ('transform', 'extent'):
        if not np.allclose(a[key], b[key], rtol=0, atol=tolerance):
            raise ValueError(f'Alignment failed: {key} differs ({a[key]} vs {b[key]}).')
    return a


def windows(ds, size=512):
    for y in range(0, ds.RasterYSize, size):
        for x in range(0, ds.RasterXSize, size):
            yield x, y, min(size, ds.RasterXSize - x), min(size, ds.RasterYSize - y)


def valid_values(band, window):
    values = band.ReadAsArray(*window)
    valid = (band.GetMaskBand().ReadAsArray(*window) != 0) & np.isfinite(values) & (np.abs(values) < 1e20)
    nodata = band.GetNoDataValue()
    if nodata is not None:
        valid &= values != nodata
    return values, valid
