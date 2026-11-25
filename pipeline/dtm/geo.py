"""AOI handling, deterministic acquisition planning, raster grid checks."""
import hashlib
import json
import math
import logging
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


def rectangle(box):
    x0, y0, x1, y1 = box
    return ogr.CreateGeometryFromWkt(f'POLYGON (({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))')


def plan_source(geometry, source):
    geometry = project(geometry, srs(source['epsg']))
    extent = bounds(geometry)
    size, res = source['chunk_size_m'], source['resolution']
    if size <= 0 or res <= 0 or not math.isclose(size / res, round(size / res)):
        raise ValueError('chunk_size_m must be a positive multiple of resolution.')
    # Stable kilometre lattice for reusable tiles; only request AOI-intersecting chunks.
    tiles = []
    for ix in range(math.floor(extent[0] / size), math.ceil(extent[2] / size)):
        for iy in range(math.floor(extent[1] / size), math.ceil(extent[3] / size)):
            box = [ix * size, iy * size, (ix + 1) * size, (iy + 1) * size]
            if not geometry.Intersection(rectangle(box)).GetArea() > 0:
                continue
            signature = hashlib.sha256(json.dumps({'source': source, 'bounds': box, 'request_schema': 2}, sort_keys=True).encode()).hexdigest()[:20]
            tiles.append({'id': signature, 'bounds': box})
    return {'crs': f"EPSG:{source['epsg']}", 'aoi_extent': extent,
            'request_extent': [min(t['bounds'][0] for t in tiles), min(t['bounds'][1] for t in tiles),
                               max(t['bounds'][2] for t in tiles), max(t['bounds'][3] for t in tiles)],
            'chunks': len(tiles), 'uncompressed_bytes': int(len(tiles) * (size / res) ** 2 * 4), 'tiles': tiles}


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


def is_official_rlp(source):
    return (source.get('type') == 'metalink'
            and source.get('metalink_url') ==
            'https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4'
            and source.get('epsg') == 25832 and source.get('vertical_epsg') == 7837
            and source.get('resolution') == 1)


def rlp_nominal_bounds(info):
    """Return the kilometre footprint, retaining the actual raster geotransform."""
    shape = (info['cols'], info['rows'])
    box = np.asarray(info['extent'], dtype=float)
    if shape == (1001, 1001):
        box = box + [.5, .5, -.5, -.5]
    elif shape != (1000, 1000):
        raise ValueError('RLP DGM1 requires 1000 x 1000 or 1001 x 1001 native pixels.')
    if (not np.allclose([info['transform'][1], info['transform'][5]], [1, -1], rtol=0, atol=1e-8)
            or not np.allclose(box / 1000, np.round(box / 1000), rtol=0, atol=1e-10)
            or not np.allclose(box[2:] - box[:2], [1000, 1000], rtol=0, atol=1e-7)):
        raise ValueError(f'Unexpected RLP kilometre lattice: {info}')
    return box.tolist()


def validate_tile(path, source, tile):
    # Explicit close even on validation errors, so Windows can remove a failed
    # partial download while the exception traceback is still alive.
    with gdal.Open(str(path)) as ds:
        if ds.RasterCount != 1 or ds.RasterXSize < 1 or ds.RasterYSize < 1:
            raise ValueError(f'Expected a one-band elevation raster: {path}')
        if ds.GetRasterBand(1).DataType not in (gdal.GDT_Float32, gdal.GDT_Float64):
            raise ValueError(f'Expected floating-point elevations: {path}')
        crs = ds.GetSpatialRef()
        if source.get('vertical_epsg'):
            expected = str(source['vertical_epsg'])
            actual = crs.GetAuthorityCode('VERT_CS') if crs else None

            # RLP declares the height datum at dataset level.
            # Some official TIFFs contain only the horizontal CRS.
            rlp_horizontal_only = (
                crs is not None
                and crs.IsProjected()
                and not crs.IsCompound()
                and crs.GetAttrValue('VERT_CS') is None
                and is_official_rlp(source)
                and expected == '7837'
            )

            if actual != expected:
                if not rlp_horizontal_only:
                    raise ValueError(f'Wrong or missing source vertical CRS: {path}')
                logging.getLogger('dtm').warning(
                    'No embedded vertical CRS in %s; using the official '
                    'RLP DGM1 dataset declaration: DHHN2016, EPSG:7837.',
                    path,
                )

            crs = crs.Clone()
            crs.StripVertical()
        if not crs or not crs.IsSame(srs(source['epsg'])):
            raise ValueError(f'Wrong source CRS: {path}')
        info = grid(path)
        nominal = source['resolution']
        comparison_extent = info['extent']
        if is_official_rlp(source):
            comparison_extent = rlp_nominal_bounds(info)
        if source.get('type') == 'metalink':
            allowed_nodata = (-9999,)
            if is_official_rlp(source) and info['cols'] == 1001:
                allowed_nodata = (-9999, -10000000000.0)
            if (info['dtype'] != 'Float32' or info['nodata'] not in allowed_nodata
                    or not np.allclose([info['transform'][1], -info['transform'][5]], nominal, rtol=0, atol=1e-8)):
                raise ValueError(f'Unexpected native DGM1 metadata: {info}')
        if not np.allclose([info['transform'][1], -info['transform'][5]], nominal, rtol=0.01, atol=1e-8):
            raise ValueError(f'Unexpected source resolution: {info}')
        # Reject shifted/short responses: they would leave seams between chunks.
        a, b = comparison_extent, tile['bounds']
        if not np.allclose(a, b, rtol=0, atol=1e-7):
            raise ValueError(f'Returned extent differs from requested tile: {a} vs {b}')
        valid_count = 0
        for w in windows(ds):
            _, mask = valid_values(ds.GetRasterBand(1), w)
            valid_count += int(mask.sum())
        return {'grid': info, 'valid_cells': valid_count}
