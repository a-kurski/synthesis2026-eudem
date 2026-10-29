"""Omission and commission of the merged DTM at its own resolution.

Rasterises the basin outline that `assemble` used (<output_dir>/extent.gpkg) on the
product's grid and counts, inside it:
  omission   : outline cells without data in the merged DTM (/ outline cells)
  commission : cells with data in two or more region DEMs, i.e. the border overlaps,
               gap-filled cells not counted (/ data cells)

Run from pipeline-merge:  python check_omission.py [config.json]
"""
import json
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()
config = Path(sys.argv[1] if len(sys.argv) > 1 else 'pipeline.json').resolve()
cfg = json.loads(config.read_text(encoding='utf-8-sig'))
s, root = cfg['settings'], config.parent
out = root / s['output_dir']
product = root / cfg['product'] if cfg.get('product') else out / s.get('product_name', 'merged_dtm.tif')
outline = out / 'extent.gpkg'
if not outline.exists():
    sys.exit(f'{outline} not found; run the assemble stage first')

crs = osr.SpatialReference()
crs.ImportFromEPSG(int(s['crs']))  # horizontal only, so the outline is not shifted vertically
crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)



def valid(band, *window):
    v, nodata = band.ReadAsArray(*window), band.GetNoDataValue()
    return np.isfinite(v) if nodata is None else np.isfinite(v) & (v != nodata)


ROWS = 1024
with gdal.Open(str(product)) as ds:
    band, width, height = ds.GetRasterBand(1), ds.RasterXSize, ds.RasterYSize
    x0, dx, _, y1, _, dy = ds.GetGeoTransform()
    # Region DEMs (and fill masks) sit on the product's lattice: read them by pixel offset.
    dems = []
    for name, r in cfg['regions'].items():
        if not (r.get('dem') and (root / r['dem']).exists()):
            continue
        d = gdal.Open(str(root / r['dem']))
        gx, _, _, gy, _, _ = d.GetGeoTransform()
        ox, oy = (gx - x0) / dx, (gy - y1) / dy
        if abs(ox - round(ox)) > 1e-6 or abs(oy - round(oy)) > 1e-6:
            sys.exit(f'{name}: DEM is not on the product grid')
        fill = gdal.Open(str(root / r['fill_mask'])) if r.get('fill_mask') and (root / r['fill_mask']).exists() else None
        dems.append((d, fill, round(ox), round(oy)))
    inside = data = data_outside = overlap = 0
    for y in range(0, height, ROWS):
        rows = min(ROWS, height - y)
        mem = gdal.GetDriverByName('MEM').Create('', width, rows, 1, gdal.GDT_Byte)
        mem.SetGeoTransform([x0, dx, 0, y1 + y * dy, 0, dy])
        mem.SetSpatialRef(crs)
        gdal.Rasterize(mem, str(outline), options=gdal.RasterizeOptions(burnValues=[1]))
        m = mem.ReadAsArray().astype(bool)
        has = valid(band, 0, y, width, rows)
        inside += np.count_nonzero(m)
        data += np.count_nonzero(m & has)
        data_outside += np.count_nonzero(~m & has)
        sources = np.zeros((rows, width), np.uint8)
        for d, fill, ox, oy in dems:
            r0, r1 = max(y, oy), min(y + rows, oy + d.RasterYSize)
            c0, c1 = max(0, ox), min(width, ox + d.RasterXSize)
            if r0 >= r1 or c0 >= c1:
                continue
            window = (c0 - ox, r0 - oy, c1 - c0, r1 - r0)
            cell = valid(d.GetRasterBand(1), *window)
            if fill:
                cell &= fill.GetRasterBand(1).ReadAsArray(*window) <= 0
            sources[r0 - y:r1 - y, c0:c1] += cell
        overlap += np.count_nonzero(m & (sources >= 2))
        print(f'\r{min(y + rows, height) / height:6.1%}', end='', flush=True)

km2 = abs(dx * dy) / 1e6
omitted = inside - data
print(f'\r{product.name} at {abs(dx):g} m      ')
print(f'Basin outline : {inside * km2:12.2f} km2 ({inside} cells)')
print(f'Data          : {data * km2:12.2f} km2 ({data} cells)')
print(f'Omission rate : {omitted * km2:12.2f} km2, {100 * omitted / inside if inside else 0:.2f} % of the outline')
print(f'Commission    : {overlap * km2:12.2f} km2, {100 * overlap / data if data else 0:.2f} % of the data '
      f'(cells with data in 2+ region DEMs)')
if data_outside:
    print(f'(plus {data_outside * km2:.2f} km2 of data outside the outline, not counted)')
