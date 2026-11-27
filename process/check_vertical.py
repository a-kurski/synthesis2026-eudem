"""Compare the height shift applied by GDAL's warp with xdem's to_vcrs, per region.

For every region whose vertical_crs differs from settings.vertical_crs, a 2 x 2 km window
at the region centre is warped from its tiles.vrt twice (with and without the height
transformation). The difference is the shift GDAL applies. The same window is then shifted
with xdem's to_vcrs. Both shifts are printed, plus cells GDAL left empty.

Run from pipeline-merge with the eudem environment:
    python check_vertical.py [config.json] [--vrt-dir DIR]
--vrt-dir: where the <region>/tiles.vrt mosaics are (default: the config's output_dir). The mosaics
don't depend on height settings, so another run's can be used, e.g.
    python check_vertical.py vertical.json --vrt-dir ../../local/data
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import xdem
from affine import Affine
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
parser = argparse.ArgumentParser()
parser.add_argument('config', nargs='?', default='pipeline.json')
parser.add_argument('--vrt-dir', help="folder with <region>/tiles.vrt (default: the config's output_dir)")
args = parser.parse_args()
config = Path(args.config).resolve()
cfg = json.loads(config.read_text(encoding='utf-8-sig'))
s, root = cfg['settings'], config.parent
out = Path(args.vrt_dir).resolve() if args.vrt_dir else root / s['output_dir']
target_h, target_v, res, half = s['crs'], s['vertical_crs'], s['resolution'], 1000


def centre(vector):
    ds = ogr.Open(str(root / vector))
    layer = ds.GetLayer()
    geom = None
    for f in layer:
        g = f.GetGeometryRef().Clone()
        geom = g if geom is None else geom.Union(g)
    ref = layer.GetSpatialRef().Clone()
    ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst = osr.SpatialReference(); dst.ImportFromEPSG(target_h); dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geom.Transform(osr.CoordinateTransformation(ref, dst))
    c = geom.Centroid()
    return round(c.GetX() / res) * res, round(c.GetY() / res) * res


def warp(vrt, src, dst, box):
    with gdal.Warp('', str(vrt), options=gdal.WarpOptions(
            format='MEM', srcSRS=src, dstSRS=dst, outputBounds=box, xRes=res, yRes=res,
            resampleAlg='bilinear', errorThreshold=0, dstNodata=-9999, outputType=gdal.GDT_Float32)) as ds:
        return ds.ReadAsArray().astype('float64'), ds.GetGeoTransform()


def short(exc):
    """First line (cut) plus the last line of an error: PROJ errors embed whole CRS definitions."""
    lines = [l for l in str(exc).splitlines() if l.strip()] or ['']
    first = lines[0] if len(lines[0]) <= 160 else lines[0][:160] + '...'
    return f'{type(exc).__name__}: {first}' + (f' / {lines[-1].strip()}' if len(lines) > 1 else '')


def stats(a):
    a = a[np.isfinite(a)]
    return 'no cells' if not a.size else f'mean {a.mean():+.4f}  min {a.min():+.4f}  max {a.max():+.4f} m'


print(f'Config {config.name}: target EPSG:{target_h}+{target_v}; mosaics from {out}\n')
for name, r in cfg['regions'].items():
    source_v = r.get('vertical_crs')
    if not source_v or source_v == target_v or r.get('geoid'):
        print(f'{name}: no height transformation configured, skipped\n')
        continue
    vrt = out / name / 'tiles.vrt'
    if not vrt.exists():
        print(f'{name}: {vrt} not found (run the rasters stage first), skipped\n')
        continue
    x, y = centre(r['vector'])
    box = (x - half, y - half, x + half, y + half)
    try:
        plain, gt = warp(vrt, f"EPSG:{r['crs']}", f'EPSG:{target_h}', box)
    except Exception as exc:
        print(f'{name}: ERROR: horizontal-only warp failed ({short(exc)}), skipped\n')
        continue
    valid = plain != -9999
    if not valid.any():
        print(f'{name}: no data in the window at the region centre ({x}, {y}), skipped\n')
        continue
    try:  # GDAL's warp with the height transformation, as the pipeline does it
        with_h, _ = warp(vrt, f"EPSG:{r['crs']}+{source_v}", f'EPSG:{target_h}+{target_v}', box)
        dropped = valid & (with_h == -9999)
        gdal_shift = np.where(valid & ~dropped, with_h - plain, np.nan)
        gdal_text, dropped_text = stats(gdal_shift), f'{dropped.sum()} of {valid.sum()}'
    except Exception as exc:
        gdal_shift = np.full(plain.shape, np.nan)
        gdal_text, dropped_text = f'ERROR: {short(exc)}', 'n/a (warp failed)'

    dem = xdem.DEM.from_array(np.where(valid, plain, np.nan), Affine.from_gdal(*gt), target_h,
                              nodata=-9999, vcrs=source_v)  # GDAL geotransform -> rasterio Affine
    try:
        moved = dem.to_vcrs(target_v)
        xdem_shift = np.where(valid, moved.data.filled(np.nan) - plain, np.nan)
        xdem_text = stats(xdem_shift)
        diff_text = stats(np.abs(gdal_shift - xdem_shift))
    except Exception as exc:
        xdem_text, diff_text = f'ERROR: {short(exc)}', 'n/a'

    print(f"{name}: EPSG:{r['crs']}+{source_v} -> EPSG:{target_h}+{target_v}, window around ({x}, {y})")
    print(f'   GDAL warp shift : {gdal_text}')
    print(f'   xdem to_vcrs    : {xdem_text}')
    print(f'   |GDAL - xdem|   : {diff_text}')
    print(f'   cells GDAL left empty but have data: {dropped_text}\n')
