"""DTM coverage: omission and commission per region, as a table.

Every cell of the basin extent is classified on a coarse grid (default 50 m) against
the region outlines (who should supply the cell) and the footprints of each region's
source tiles (where data exists):

  omission   no outline     : no region outline covers the cell (basin total only)
             no tiles       : inside the region's outline, no source tile there, product empty
             empty in tiles : inside a source tile, product empty
                              (NoData in the tiles, or lost in processing)
  commission overlap        : cell inside two or more outlines
             no source      : product has a value but no source tile covers it (not gap-filled)
             outside extent : product value outside the basin extent (basin total only)
  gap-filled                : value from hole filling (reported, not counted)

Below the table: the basin area with data in two or more regions' DEMs (before merging, gap-filled
cells excluded), i.e. where data sources overlap.

Run from pipeline-merge:  python check_coverage.py [config.json] [--res 50] [--vrt-dir DIR]
"""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
parser = argparse.ArgumentParser()
parser.add_argument('config', nargs='?', default='pipeline.json')
parser.add_argument('--res', type=float, default=50, help='grid cell size in metres (default 50)')
parser.add_argument('--vrt-dir', help="folder with <region>/tiles.vrt (default: the config's output_dir)")
args = parser.parse_args()
config = Path(args.config).resolve()
cfg = json.loads(config.read_text(encoding='utf-8-sig'))
s, root, res = cfg['settings'], config.parent, args.res
out = root / s['output_dir']
vrt_dir = Path(args.vrt_dir).resolve() if args.vrt_dir else out
product = root / cfg['product'] if cfg.get('product') else out / s.get('product_name', 'merged_dtm.tif')
regions = {n: r for n, r in cfg['regions'].items() if (vrt_dir / n / 'tiles.vrt').exists()}


def srs(epsg):
    ref = osr.SpatialReference()
    ref.ImportFromEPSG(int(epsg))
    ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return ref


# Grid: the product's extent at `res`.
with gdal.Open(str(product)) as p:
    x0, dx, _, y1, _, dy = p.GetGeoTransform()
    width, height = round(p.RasterXSize * dx / res), round(p.RasterYSize * -dy / res)
gt = [x0, res, 0, y1, 0, -res]
cell_km2 = res * res / 1e6


def grid(kind=gdal.GDT_Byte):
    ds = gdal.GetDriverByName('MEM').Create('', width, height, 1, kind)
    ds.SetGeoTransform(gt)
    ds.SetSpatialRef(srs(s['crs']))
    return ds


def burn_file(path):
    """Polygons of a vector file -> boolean grid (reprojected as needed)."""
    ds = grid()
    gdal.Rasterize(ds, str(path), options=gdal.RasterizeOptions(burnValues=[1]))
    return ds.ReadAsArray().astype(bool)


def tile_footprint(name, r):
    """Rectangles of the region's source tiles, from its tiles.vrt -> boolean grid."""
    tree = ET.parse(vrt_dir / name / 'tiles.vrt')
    vx0, vdx, _, vy1, _, vdy = (float(v) for v in tree.findtext('GeoTransform').split(','))
    mem = ogr.GetDriverByName('MEM') or ogr.GetDriverByName('Memory')
    source = mem.CreateDataSource('')  # keep a reference, or the layer dies with it
    layer = source.CreateLayer('tiles', srs(r['crs']), ogr.wkbPolygon)
    for rect in tree.getroot().iter('DstRect'):
        xo, yo, xs, ys = (float(rect.get(k)) for k in ('xOff', 'yOff', 'xSize', 'ySize'))
        ax, bx = vx0 + xo * vdx, vx0 + (xo + xs) * vdx
        ay, by = vy1 + yo * vdy, vy1 + (yo + ys) * vdy
        f = ogr.Feature(layer.GetLayerDefn())
        f.SetGeometry(ogr.CreateGeometryFromWkt(f'POLYGON(({ax} {ay},{bx} {ay},{bx} {by},{ax} {by},{ax} {ay}))'))
        layer.CreateFeature(f)
    ds = grid()
    gdal.RasterizeLayer(ds, [1], layer, burn_values=[1])
    return ds.ReadAsArray().astype(bool)


def warp(path, nodata, resample):
    """A raster resampled onto the grid (uses the file's overviews when it has them)."""
    with gdal.Warp('', str(path), options=gdal.WarpOptions(
            format='MEM', dstSRS=srs(s['crs']).ExportToWkt(), outputBounds=(x0, y1 - height * res, x0 + width * res, y1),
            width=width, height=height, resampleAlg=resample, dstNodata=nodata, outputType=gdal.GDT_Float32,
            options=['-novshift'])) as ds:
        return ds.ReadAsArray()


print(f'Coverage of {product.name} at {res:g} m ({width} x {height} cells), mosaics from {vrt_dir}')
if s.get('extent'):
    extent = burn_file(root / s['extent'])
else:  # no extent: the union of the outlines
    extent = np.zeros((height, width), bool)
    for r in regions.values():
        extent |= burn_file(root / r['vector'])
valid = warp(product, -9999, 'near') != -9999
filled = np.zeros_like(valid)
for r in cfg['regions'].values():
    if r.get('fill_mask'):
        filled |= warp(root / r['fill_mask'], -1, 'max') > 0  # -1, not 0: GDAL would nudge 0 to a tiny non-zero

outlines = {n: burn_file(root / r['vector']) for n, r in regions.items()}
count = np.sum(list(outlines.values()), axis=0, dtype=np.uint8)
km2 = lambda m: np.count_nonzero(m) * cell_km2

rows = []
for name, r in regions.items():
    tiles = tile_footprint(name, r)
    owned = extent & outlines[name]
    single = owned & (count == 1)
    rows.append({
        'region': name,
        'area': km2(owned), 'valid': km2(owned & valid),
        'no tiles': km2(owned & ~tiles & ~valid),
        'empty in tiles': km2(owned & tiles & ~valid),
        'overlap': km2(owned & (count >= 2)),
        'no source': km2(single & valid & ~tiles & ~filled),
        'gap-filled': km2(owned & valid & filled),
    })
    del tiles

basin = {
    'region': 'BASIN', 'area': km2(extent), 'valid': km2(extent & valid),
    'no outline': km2(extent & (count == 0) & ~valid),
    'no tiles': sum(r['no tiles'] for r in rows), 'empty in tiles': sum(r['empty in tiles'] for r in rows),
    'overlap': km2(extent & (count >= 2)),  # each overlap cell once
    'no source': sum(r['no source'] for r in rows), 'outside extent': km2(~extent & valid),
    'gap-filled': km2(extent & valid & filled),
}

head = ['region', 'area', 'valid', 'no outline', 'no tiles', 'empty in tiles', 'omission %',
        'overlap', 'no source', 'outside extent', 'commission %', 'gap-filled']
print('\nAreas in km2. Omission % = omitted / area; commission % = commission / valid area.\n')
print(f'{head[0]:18s}' + ''.join(f'{h:>15s}' for h in head[1:]))
for r in rows + [basin]:
    omitted = r.get('no outline', 0) + r['no tiles'] + r['empty in tiles']
    commission = r['overlap'] + r['no source'] + r.get('outside extent', 0)
    values = [r['area'], r['valid'], r.get('no outline'), r['no tiles'], r['empty in tiles'],
              100 * omitted / r['area'] if r['area'] else 0, r['overlap'], r['no source'], r.get('outside extent'),
              100 * commission / r['valid'] if r['valid'] else 0, r['gap-filled']]
    cells = ''.join(f'{"-":>15s}' if v is None else f'{v:15.2f}' for v in values)
    print(f"{r['region']:18s}{cells}")
print('\nRegion rows count overlap cells for each region involved; the BASIN row counts them once.')
omitted = basin['no outline'] + basin['no tiles'] + basin['empty in tiles']
print(f"\nOmission rate: {omitted:.2f} km2, {100 * omitted / basin['area'] if basin['area'] else 0:.2f} %")

# Overlapping data sources: cells with data in two or more region DEMs (before clipping to outlines).
sources = np.zeros((height, width), np.uint8)
for name, r in cfg['regions'].items():
    if r.get('dem') and (root / r['dem']).exists():
        data = warp(root / r['dem'], s.get('nodata', -9999), 'near') != s.get('nodata', -9999)
        if r.get('fill_mask'):
            data &= ~(warp(root / r['fill_mask'], -1, 'max') > 0)
        sources += data
covered = km2(extent & (sources >= 1))
print('\nData sources per cell (basin extent, gap-filled cells excluded):')
for n in range(1, int(sources[extent].max(initial=0)) + 1):
    a = km2(extent & (sources == n))
    print(f'  {n} source{"s" if n > 1 else " "} : {a:12.2f} km2  ({100 * a / covered if covered else 0:5.2f} % of the area with data)')
multi = km2(extent & (sources >= 2))
print(f'  2 or more : {multi:12.2f} km2  ({100 * multi / covered if covered else 0:5.2f} % of the area with data, '
      f'{100 * multi / km2(extent):.2f} % of the basin)')
