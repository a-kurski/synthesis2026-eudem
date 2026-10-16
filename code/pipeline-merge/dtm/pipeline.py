"""Rhine-basin DTM merge pipeline (see pipeline.md). Downloads and point clouds are out of scope.

Stages read and update one JSON file, so a rerun resumes where the last one stopped.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import glob
from itertools import combinations
import json
import math
import os
from pathlib import Path
import threading

import numpy as np
from osgeo import gdal, ogr, osr

from .geo import bounds, project, read_aoi, srs, valid_values, windows, write_json
from .hole_filling import fill_holes
from .process import OPTIONS, aoi_mask, create_raster, write_cog

STAGES = ('vectors', 'rasters', 'rivers', 'overlaps', 'assemble')
DEFAULTS = {'threads': 'ALL_CPUS', 'region_workers': 1, 'warp_memory_mb': 2048, 'vertical_crs': None, 'interpolation_mask': None, 'river_seeds': None, 'buffer_m': 1000, 'nodata': -9999,
            'block_size': 512, 'output_dir': 'data/pipeline', 'hole_filling': {}}


def snap(box, res):
    x0, y0, x1, y1 = box
    return [math.floor(x0 / res) * res, math.floor(y0 / res) * res,
            math.ceil(x1 / res) * res, math.ceil(y1 / res) * res]


def crs_name(horizontal, vertical):
    return f'EPSG:{horizontal}+{vertical}' if vertical else f'EPSG:{horizontal}'


def zero_vertical_shift(point, horizontal, source, target):
    """True if PROJ only knows a ballpark (no-op) source -> target height transformation."""
    a, b = (osr.SpatialReference() for _ in range(2))
    for crs, vertical in ((a, source), (b, target)):
        crs.SetFromUserInput(crs_name(horizontal, vertical))
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(a, b).TransformPoint(point.GetX(), point.GetY(), 0)[2] == 0


def write_vector(geometry, path):
    """Save the polygonal part of a geometry as a one-feature GeoPackage."""
    polygons = ogr.Geometry(ogr.wkbMultiPolygon)
    single = ogr.GT_Flatten(geometry.GetGeometryType()) == ogr.wkbPolygon
    parts = [geometry] if single else [geometry.GetGeometryRef(i) for i in range(geometry.GetGeometryCount())]
    for part in parts:
        kind = ogr.GT_Flatten(part.GetGeometryType())
        if kind == ogr.wkbPolygon:
            polygons.AddGeometry(part)
        elif kind == ogr.wkbMultiPolygon:
            for i in range(part.GetGeometryCount()):
                polygons.AddGeometry(part.GetGeometryRef(i))
    Path(path).unlink(missing_ok=True)
    ds = gdal.GetDriverByName('GPKG').Create(str(path), 0, 0, 0, gdal.GDT_Unknown)
    layer = ds.CreateLayer(Path(path).stem, geometry.GetSpatialReference(), ogr.wkbMultiPolygon)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(polygons)
    layer.CreateFeature(feature)
    ds = None
    return polygons


def merge(za, va, zb, vb, in_a, in_b, filled_a, filled_b):
    """Overrides for one overlap zone; NaN = no override (keep the owner's own data).

    Each region owns the cells inside its polygon. An owner cell that was
    interpolated is replaced by the neighbour's measured (valid, not interpolated)
    value. No averaging, no feathering.
    """
    out = np.full(za.shape, np.nan)
    use_b = in_a & filled_a & vb & ~filled_b
    use_a = in_b & ~in_a & filled_b & va & ~filled_a
    out[use_b], out[use_a] = zb[use_b], za[use_a]
    return out


class Run:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.root = self.path.parent
        self.cfg = json.loads(self.path.read_text(encoding='utf-8-sig'))
        self.s = {**DEFAULTS, **self.cfg['settings']}
        self.regions = self.cfg['regions']
        self.out = self.abs(self.s['output_dir'])
        self.out.mkdir(parents=True, exist_ok=True)
        # Settings shared with hole_filling / process helpers.
        # Thread budget: `threads` in total, split evenly over `region_workers` parallel regions.
        total = os.cpu_count() if self.s['threads'] == 'ALL_CPUS' else int(self.s['threads'])
        self.workers = max(1, int(self.s['region_workers']))
        per_region = max(1, total // self.workers)
        gdal.SetConfigOption('GDAL_NUM_THREADS', str(per_region))  # compression, COG, overviews
        self.warp = self.warp_options(per_region)  # rasters stage (one warp per region worker)
        self.warp_all = self.warp_options(total)   # assemble stage (one warp at a time)
        self.lock = threading.Lock()  # guards the shared JSON while regions run in parallel
        self.helper = {'nodata': self.s['nodata'], 'block_size': self.s['block_size'], 'crs': self.s['crs'],
                       'alignment_tolerance_m': 1e-8, 'hole_filling': {**self.s['hole_filling'], 'enabled': True}}

    def warp_options(self, threads):
        return {'multithread': True, 'warpMemoryLimit': self.s['warp_memory_mb'],
                'warpOptions': [f'NUM_THREADS={threads}']}

    def abs(self, path):
        return self.root / path

    def rel(self, path):
        try:
            return Path(os.path.relpath(path, self.root)).as_posix()
        except ValueError:  # different Windows drive
            return str(path)

    def exists(self, key, entry):
        return bool(entry.get(key)) and self.abs(entry[key]).exists()

    def save(self):
        write_json(self.path, self.cfg)

    def geometry(self, path):
        g = project(read_aoi(self.abs(path))[0], srs(self.s['crs']))
        g.AssignSpatialReference(srs(self.s['crs']))
        return g

    def view(self, path, box):
        """Window of a raster on the shared lattice: no resampling happens."""
        if not path:
            return None
        res = self.s['resolution']
        return gdal.BuildVRT('', [str(self.abs(path))], options=gdal.BuildVRTOptions(
            outputBounds=box, xRes=res, yRes=res))

    # --- stages -------------------------------------------------------------

    def vectors(self):
        geoms = {name: self.geometry(r['vector']) for name, r in self.regions.items()}
        buffered = {name: g.Buffer(self.s['buffer_m']) for name, g in geoms.items()}
        directory = self.out / 'intersections'
        directory.mkdir(exist_ok=True)
        for r in self.regions.values():
            r['intersections'] = []
        self.cfg['overlaps'] = {}
        for a, b in combinations(self.regions, 2):
            zone = buffered[a].Intersection(buffered[b])
            if zone.IsEmpty() or zone.GetArea() <= 0:
                continue
            # Never paint merged data over a third region or the sea.
            zone = zone.Intersection(geoms[a].Union(geoms[b]))
            zone.AssignSpatialReference(srs(self.s['crs']))
            path = directory / f'{a}__{b}.gpkg'
            write_vector(zone, path)
            self.regions[a]['intersections'].append(b)
            self.regions[b]['intersections'].append(a)
            self.cfg['overlaps'][f'{a}__{b}'] = {'regions': [a, b], 'vector': self.rel(path), 'merged': None}
            print(f'Intersection: {a} / {b}')

    def rasters(self):
        todo = [(name, r) for name, r in self.regions.items() if not self.exists('dem', r)]
        # Largest regions first, so a big one never starts last and drags out the run.
        todo.sort(key=lambda item: self.geometry(item[1]['vector']).GetArea(), reverse=True)
        with ThreadPoolExecutor(self.workers) as pool:  # GDAL releases the GIL while working
            for future in [pool.submit(self.raster, name, r) for name, r in todo]:
                future.result()  # re-raise the first error

    def raster(self, name, r):
        s, res = self.s, self.s['resolution']
        directory = self.out / name
        directory.mkdir(exist_ok=True)
        tiles = sorted(glob.glob(str(self.abs(r['raster'])), recursive=True))
        if not tiles:
            raise FileNotFoundError(f'{name}: no rasters match {r["raster"]}')
        print(f'{name}: {len(tiles)} tiles')
        vrt = directory / 'tiles.vrt'
        with gdal.BuildVRT(str(vrt), tiles):
            pass
        area = self.geometry(r['vector'])
        vertical = s['vertical_crs'] and r.get('vertical_crs')
        if (vertical and r['vertical_crs'] != s['vertical_crs']
                and zero_vertical_shift(area.Centroid(), s['crs'], r['vertical_crs'], s['vertical_crs'])):
            print(f"WARNING {name}: PROJ has no EPSG:{r['vertical_crs']} -> EPSG:{s['vertical_crs']} "
                  'transformation here; heights are NOT shifted (install the grids or enable PROJ_NETWORK).')
        dem = directory / 'dem.tif'
        # Steps 1-3 (CRS/VRS, stitch, resample) in one warp; the extent keeps a
        # buffer_m margin so neighbouring regions overlap.
        with gdal.Warp(str(dem), str(vrt), options=gdal.WarpOptions(
                srcSRS=crs_name(r['crs'], r.get('vertical_crs') if vertical else None),
                dstSRS=crs_name(s['crs'], s['vertical_crs'] if vertical else None),
                outputBounds=snap(bounds(area.Buffer(s['buffer_m'])), res), xRes=res, yRes=res,
                resampleAlg=r.get('resampling', 'average'), errorThreshold=0, overviewLevel='NONE',
                dstNodata=s['nodata'], outputType=gdal.GDT_Float32, creationOptions=OPTIONS,
                **self.warp,
                cutlineDSName=str(self.abs(r['vector'])) if r.get('crop') else None)):
            pass
        fill_mask = None
        if r.get('interpolate'):
            if s['interpolation_mask']:
                area = area.Intersection(self.geometry(s['interpolation_mask']))
                area.AssignSpatialReference(srs(s['crs']))
            report = fill_holes(dem, area, directory / 'hole_filling', self.helper)
            dem, fill_mask = report['filled_raster'], self.rel(report['fill_mask'])
        with self.lock:
            r['fill_mask'], r['dem'] = fill_mask, self.rel(dem)
            self.save()
        print(f'{name}: done')

    def rivers(self):
        try:
            from .river_mask import create_masks  # xdem/numba only needed for this stage
        except ImportError as exc:
            print(f'Skipping river masks ({exc}); run python -m dtm.river_mask pipeline.json in an xdem environment')
            return
        self.save()
        create_masks(self.path)  # writes each region's river_mask path into the JSON
        self.cfg = json.loads(self.path.read_text(encoding='utf-8-sig'))
        self.regions = self.cfg['regions']

    def overlaps(self):
        s, res = self.s, self.s['resolution']
        for key, o in self.cfg.get('overlaps', {}).items():
            if self.exists('merged', o):
                continue
            a, b = (self.regions[n] for n in o['regions'])
            if not (a.get('fill_mask') or b.get('fill_mask')):
                continue  # nothing interpolated: each region simply keeps its own cells
            box = snap(bounds(self.geometry(o['vector'])), res)
            directory = self.out / 'overlaps' / key
            directory.mkdir(parents=True, exist_ok=True)
            dem_a, dem_b = self.view(a['dem'], box), self.view(b['dem'], box)
            owners = [aoi_mask(self.geometry(r['vector']), dem_a, directory / f'{k}_mask.tif', epsg=s['crs'])
                      for k, r in (('a', a), ('b', b))]
            fills = [self.view(r.get('fill_mask'), box) for r in (a, b)]
            merged = directory / 'merged.tif'
            dst = create_raster(merged, dem_a, s['nodata'], f'Measured-over-interpolated overrides for {key}')
            band = dst.GetRasterBand(1)
            band.Fill(s['nodata'])
            for win in windows(dem_a, 2048):
                in_a, in_b = (m.GetRasterBand(1).ReadAsArray(*win) != 0 for m in owners)
                filled_a, filled_b = (np.zeros(in_a.shape, bool) if f is None else f.GetRasterBand(1).ReadAsArray(*win) > 0
                                      for f in fills)
                za, va = valid_values(dem_a.GetRasterBand(1), win)
                zb, vb = valid_values(dem_b.GetRasterBand(1), win)
                out = merge(za, va, zb, vb, in_a, in_b, filled_a, filled_b)
                band.WriteArray(np.where(np.isnan(out), s['nodata'], out).astype('float32'), win[0], win[1])
            dst = owners = None
            o['merged'] = self.rel(merged)
            self.save()
            print(f'Overrides written: {key}')

    def assemble(self):
        s, res = self.s, self.s['resolution']
        if s.get('extent'):
            basin = self.geometry(s['extent'])
        else:  # no extent: the union of the region outlines
            outlines = [self.geometry(r['vector']) for r in self.regions.values()]
            basin = outlines[0]
            for g in outlines[1:]:
                basin = basin.Union(g)
            basin.AssignSpatialReference(srs(s['crs']))
        x0, y0, x1, y1 = snap(bounds(basin), res)
        crs = osr.SpatialReference()
        crs.SetFromUserInput(crs_name(s['crs'], s['vertical_crs']))
        product = self.out / 'rhine_dtm.tif'
        work = self.out / 'rhine_dtm_work.tif'  # writable GTiff; a COG cannot be updated in place
        ds = gdal.GetDriverByName('GTiff').Create(str(work), round((x1 - x0) / res), round((y1 - y0) / res),
                                                  1, gdal.GDT_Float32, OPTIONS)
        ds.SetGeoTransform([x0, res, 0, y1, 0, -res])
        ds.SetSpatialRef(crs)
        ds.GetRasterBand(1).SetNoDataValue(s['nodata'])
        # Each region inside its own polygon, then measured-over-interpolated overrides on top.
        patches = [(r['dem'], r['vector']) for r in self.regions.values()]
        patches += [(o['merged'], o['vector']) for o in self.cfg.get('overlaps', {}).values() if o.get('merged')]
        for raster, cutline in patches:
            print(f'Assembling {raster}')
            gdal.Warp(ds, str(self.abs(raster)), options=gdal.WarpOptions(
                cutlineDSName=str(self.abs(cutline)), resampleAlg='near', **self.warp_all))
        write_vector(basin, self.out / 'extent.gpkg')
        gdal.Rasterize(ds, str(self.out / 'extent.gpkg'), options=gdal.RasterizeOptions(
            burnValues=[s['nodata']], inverse=True))
        ds = None
        write_cog(work, product)
        work.unlink()
        self.cfg['product'] = self.rel(product)
        print(f'Product: {product}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Merge regional DTMs into one Rhine-basin DTM.')
    parser.add_argument('config', nargs='?', default='pipeline.json', type=Path)
    parser.add_argument('--stages', nargs='+', choices=STAGES, default=STAGES,
                        help='Stages to run (default: all). Finished outputs recorded in the JSON are reused.')
    args = parser.parse_args(argv)
    gdal.UseExceptions()
    run = Run(args.config)
    for stage in args.stages:
        print(f'== {stage}')
        getattr(run, stage)()
        run.save()
