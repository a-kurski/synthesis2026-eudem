"""Merge regional DTMs (countries, states, ...) into one seamless DTM. Everything that differs
between datasets is configured in the pipeline JSON; see README.md.

Stages read and update one JSON file, so a rerun resumes where the last one stopped.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import glob
from itertools import combinations
import json
import logging
import math
import os
from pathlib import Path
import threading
import time

import numpy as np
from osgeo import gdal, ogr, osr

from .geo import bounds, project, read_aoi, srs, valid_values, windows, write_json
from .hole_filling import fill_holes
from .process import MASK_COG_OPTIONS, OPTIONS, aoi_mask, create_raster, write_cog

LOG = logging.getLogger('dtm')


def elapsed(start):
    seconds = int(time.perf_counter() - start)
    return f'{seconds // 3600}h{seconds // 60 % 60:02d}m{seconds % 60:02d}s'


def gdal_progress(label, step=10):
    """GDAL callback logging every `step` percent, so long warps show signs of life."""
    state = {'next': step, 'start': time.perf_counter()}

    def callback(fraction, message, data):
        if fraction * 100 >= state['next']:
            LOG.info('%s: %d%% (%s)', label, state['next'], elapsed(state['start']))
            state['next'] += step
        return 1
    return callback


STAGES = ('vectors', 'rasters', 'rivers', 'overlaps', 'assemble')
DEFAULTS = {'skip_missing': False, 'threads': 'ALL_CPUS', 'region_workers': 1, 'warp_memory_mb': 2048, 'vertical_crs': None, 'interpolation_mask': None, 'river_seeds': None, 'buffer_m': 1000, 'nodata': -9999, 'product_name': 'merged_dtm.tif', 'max_vertical_shift_m': 10,
            'block_size': 512, 'output_dir': 'data/pipeline', 'hole_filling': {}}


def snap(box, res):
    x0, y0, x1, y1 = box
    return [math.floor(x0 / res) * res, math.floor(y0 / res) * res,
            math.ceil(x1 / res) * res, math.ceil(y1 / res) * res]


def crs_name(horizontal, vertical):
    return f'EPSG:{horizontal}+{vertical}' if vertical else f'EPSG:{horizontal}'


def subtract_geoid(dem_path, geoid_path, nodata):
    """Ellipsoidal -> physical heights in place: H = h - N, with geoid undulation N (metres,
    any CRS) resampled bilinearly onto the DEM grid. NoData cells stay NoData."""
    with gdal.Open(str(dem_path), gdal.GA_Update) as dem:
        x0, dx, _, y1, _, dy = dem.GetGeoTransform()
        bounds = (x0, y1 + dy * dem.RasterYSize, x0 + dx * dem.RasterXSize, y1)
        geoid = gdal.Warp('', str(geoid_path), options=gdal.WarpOptions(
            format='VRT', dstSRS=dem.GetSpatialRef(), outputBounds=bounds, width=dem.RasterXSize,
            height=dem.RasterYSize, resampleAlg='bilinear', outputType=gdal.GDT_Float32, dstNodata=float('nan')))
        band, n_band = dem.GetRasterBand(1), geoid.GetRasterBand(1)
        missing = 0
        for window in windows(dem, 2048):
            h, valid = valid_values(band, window)
            n, n_valid = valid_values(n_band, window)
            missing += np.count_nonzero(valid & ~n_valid)
            band.WriteArray(np.where(valid & n_valid, h - n, nodata).astype('float32'), *window[:2])
        geoid = None
    if missing:
        LOG.warning('%s: geoid %s does not cover %d valid cells; set to NoData', dem_path, geoid_path, missing)


def vertical_shift(point, source_horizontal, source_vertical, target_horizontal, target_vertical):
    """Height change (m) the warp applies at `point` (given in the target horizontal CRS),
    using the same source -> target transformation as the warp itself."""
    def crs(text):
        ref = osr.SpatialReference()
        ref.SetFromUserInput(text)
        ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        return ref
    x, y, _ = osr.CoordinateTransformation(crs(f'EPSG:{target_horizontal}'), crs(f'EPSG:{source_horizontal}')) \
        .TransformPoint(point.GetX(), point.GetY(), 0)
    target = crs(crs_name(target_horizontal, target_vertical))
    try:
        source = crs(crs_name(source_horizontal, source_vertical))
        return osr.CoordinateTransformation(source, target).TransformPoint(x, y, 0)[2]
    except RuntimeError:
        # PROJ can't evaluate the full transformation at this point (typically a grid-based
        # horizontal datum shift whose grid isn't installed): test the height part alone.
        source = crs(crs_name(target_horizontal, source_vertical))
        return osr.CoordinateTransformation(source, target).TransformPoint(point.GetX(), point.GetY(), 0)[2]


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
        self.skipped = {}  # region -> reason, filled by preflight()
        self.helper = {'nodata': self.s['nodata'], 'block_size': self.s['block_size'], 'crs': self.s['crs'],
                       'alignment_tolerance_m': 1e-8, 'hole_filling': {**self.s['hole_filling'], 'enabled': True}}

    @property
    def active(self):
        """Regions taking part in this run (skipped ones are retried on the next run)."""
        return {name: r for name, r in self.regions.items() if name not in self.skipped}

    def preflight(self):
        """Check inputs before any work. Global paths must exist; regions with missing inputs
        stop the run, or are skipped with "skip_missing": true. Nothing is recorded for a
        skipped region, so the next run checks it again and processes it once its data exists."""
        for key in ('extent', 'interpolation_mask'):
            if self.s.get(key) and not self.abs(self.s[key]).exists():
                raise FileNotFoundError(f'settings.{key} not found: {self.abs(self.s[key])}')
        self.skipped = {}
        for name, r in self.regions.items():
            if not self.abs(r['vector']).exists():
                self.skipped[name] = f"outline not found: {r['vector']}"
            elif not self.exists('dem', r) and not glob.glob(str(self.abs(r['raster'])), recursive=True):
                self.skipped[name] = f"no rasters match {r['raster']}"
            elif r.get('geoid') and not self.abs(r['geoid']).exists():
                self.skipped[name] = f"geoid raster not found: {r['geoid']}"
        problems = '; '.join(f'{name}: {reason}' for name, reason in self.skipped.items())
        if self.skipped and not self.s['skip_missing']:
            raise FileNotFoundError(f'Missing inputs (set "skip_missing": true to skip these regions): {problems}')
        for name, reason in self.skipped.items():
            LOG.warning('%s: SKIPPED (%s); it will be retried on the next run', name, reason)

    def warp_options(self, threads):
        return {'multithread': True, 'warpMemoryLimit': self.s['warp_memory_mb'] * 1024 ** 2,  # bytes: GDAL reads values < 10000 as MB, larger as bytes
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
        geoms = {name: self.geometry(r['vector']) for name, r in self.active.items()}
        buffered = {name: g.Buffer(self.s['buffer_m']) for name, g in geoms.items()}
        directory = self.out / 'intersections'
        directory.mkdir(exist_ok=True)
        for r in self.regions.values():
            r['intersections'] = []
        self.cfg['overlaps'] = {}
        for a, b in combinations(self.active, 2):
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
            LOG.info('Intersection: %s / %s (%.1f km2)', a, b, zone.GetArea() / 1e6)

    def rasters(self):
        todo = [(name, r) for name, r in self.active.items() if not self.exists('dem', r)]
        # Largest regions first, so a big one never starts last and drags out the run.
        todo.sort(key=lambda item: self.geometry(item[1]['vector']).GetArea(), reverse=True)
        LOG.info('%d of %d regions to process (%d done earlier, %d skipped), %d at a time: %s', len(todo),
                 len(self.regions), len(self.active) - len(todo), len(self.skipped), self.workers,
                 ', '.join(name for name, _ in todo))
        self.finished = 0
        with ThreadPoolExecutor(self.workers) as pool:  # GDAL releases the GIL while working
            futures = {pool.submit(self.raster, name, r): name for name, r in todo}
            for future in futures:
                try:
                    future.result()
                except Exception:
                    LOG.exception('%s: FAILED', futures[future])
                    raise

    def raster(self, name, r):
        s, res = self.s, self.s['resolution']
        start = time.perf_counter()
        directory = self.out / name
        directory.mkdir(exist_ok=True)
        tiles = sorted(glob.glob(str(self.abs(r['raster'])), recursive=True))
        if not tiles:
            raise FileNotFoundError(f'{name}: no rasters match {r["raster"]}')
        LOG.info('%s: started, %d source tiles', name, len(tiles))
        vrt = directory / 'tiles.vrt'
        # Tiles may spell the same CRS differently, or lack one; the region's CRS is
        # declared in the JSON anyway, so don't drop them.
        # Gaps between tiles must be NoData, not 0. Tiles that declare NoData give the VRT their
        # value (fast, direct reads). Only if they don't, force one, otherwise gaps
        # read as 0 m, get the vertical offset added and are averaged into neighbouring cells.
        # `source_nodata` (per region): a value used *inside* the tiles for missing data that the
        # tiles don't declare (e.g. 0); it is then ignored by the warp and its averaging.
        if r.get('source_nodata') is not None:
            vrt_options = {'srcNodata': r['source_nodata'], 'VRTNodata': s['nodata']}
            LOG.info('%s: treating source value %s as NoData', name, r['source_nodata'])
        else:
            with gdal.Open(tiles[0]) as first:
                declared = first.GetRasterBand(1).GetNoDataValue() is not None
            vrt_options = {} if declared else {'VRTNodata': s['nodata']}
            if not declared:
                LOG.info('%s: tiles declare no NoData value; using %s for gaps between tiles', name, s['nodata'])
        with gdal.BuildVRT(str(vrt), tiles, options=gdal.BuildVRTOptions(
                allowProjectionDifference=True, **vrt_options)):
            pass
        area = self.geometry(r['vector'])
        ellipsoidal = s['vertical_crs'] and r.get('geoid')  # ellipsoidal heights: geoid subtracted after the warp
        vertical = s['vertical_crs'] and r.get('vertical_crs') and not ellipsoidal
        if vertical and r['vertical_crs'] != s['vertical_crs']:
            try:  # a diagnostic only: never let it stop the run
                dz = vertical_shift(area.Centroid(), r['crs'], r['vertical_crs'], s['crs'], s['vertical_crs'])
            except RuntimeError as exc:
                dz = None
                LOG.warning('%s: could not test the EPSG:%s -> EPSG:%s height transformation at the region '
                            'centre (%s); check the heights of this region after the warp', name,
                            r['vertical_crs'], s['vertical_crs'], exc)
            if dz is None:
                pass
            elif dz == 0:
                LOG.warning('%s: PROJ has no EPSG:%s -> EPSG:%s transformation here; heights are NOT shifted '
                            '(install the grids or enable PROJ_NETWORK).', name, r['vertical_crs'], s['vertical_crs'])
            elif abs(dz) > s['max_vertical_shift_m']:
                LOG.warning('%s: EPSG:%s -> EPSG:%s shifts heights by %.2f m at the region centre, more than '
                            'max_vertical_shift_m (%g); PROJ is probably mixing ellipsoidal and physical heights. '
                            'Check with: projinfo -s EPSG:%s+%s -t EPSG:%s+%s', name, r['vertical_crs'],
                            s['vertical_crs'], dz, s['max_vertical_shift_m'], r['crs'], r['vertical_crs'],
                            s['crs'], s['vertical_crs'])
            else:
                LOG.info('%s: heights shifted by %.3f m at the region centre (EPSG:%s -> EPSG:%s)',
                         name, dz, r['vertical_crs'], s['vertical_crs'])
        dem = directory / 'dem.tif'
        box = snap(bounds(area.Buffer(s['buffer_m'])), res)
        cols, rows = round((box[2] - box[0]) / res), round((box[3] - box[1]) / res)
        LOG.info('%s: warping to %d x %d cells (%.2f billion) at %g m', name, cols, rows, cols * rows / 1e9, res)
        # Steps 1-3 (CRS/VRS, stitch, resample) in one warp; the extent keeps a
        # buffer_m margin so neighbouring regions overlap.
        with gdal.Warp(str(dem), str(vrt), options=gdal.WarpOptions(
                srcSRS=crs_name(r['crs'], r.get('vertical_crs') if vertical else None),
                dstSRS=crs_name(s['crs'], s['vertical_crs'] if vertical else None),
                outputBounds=box, xRes=res, yRes=res,
                resampleAlg=r.get('resampling', 'average'), errorThreshold=0, overviewLevel='NONE',
                dstNodata=s['nodata'], outputType=gdal.GDT_Float32, creationOptions=OPTIONS,
                **self.warp, callback=gdal_progress(f'{name}: warp'),
                cutlineDSName=str(self.abs(r['vector'])) if r.get('crop') else None)):
            pass
        LOG.info('%s: warp done (%s)', name, elapsed(start))
        if ellipsoidal:
            LOG.info('%s: ellipsoidal heights; subtracting geoid %s', name, r['geoid'])
            subtract_geoid(dem, self.abs(r['geoid']), s['nodata'])
        fill_mask = None
        if r.get('interpolate'):
            LOG.info('%s: filling gaps', name)
            if s['interpolation_mask']:
                area = area.Intersection(self.geometry(s['interpolation_mask']))
                area.AssignSpatialReference(srs(s['crs']))
            report = fill_holes(dem, area, directory / 'hole_filling', self.helper)
            dem, fill_mask = report['filled_raster'], self.rel(report['fill_mask'])
            LOG.info('%s: filled %d of %d gap cells (%d left)', name, report['filled_cell_count'],
                     report['candidate_cell_count'], report['remaining_nodata_cell_count'])
        with self.lock:
            r['fill_mask'], r['dem'] = fill_mask, self.rel(dem)
            self.save()
            self.finished += 1
            LOG.info('%s: done in %s (%d regions finished this run)', name, elapsed(start), self.finished)

    def rivers(self):
        try:
            from .river_mask import create_masks  # xdem/numba only needed for this stage
        except ImportError as exc:
            LOG.warning(f'Skipping river masks ({exc}); run python -m dtm.river_mask pipeline.json in an xdem environment')
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
            if not (self.exists('dem', a) and self.exists('dem', b)):
                LOG.warning('Overlap %s: a region has no DEM (skipped or failed), skipped', key)
                continue
            if not (a.get('fill_mask') or b.get('fill_mask')):
                LOG.info('Overlap %s: nothing interpolated, skipped', key)
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
            LOG.info('Overlap %s: replacements written', key)

    def assemble(self):
        s, res = self.s, self.s['resolution']
        if s.get('extent'):
            basin = self.geometry(s['extent'])
        else:  # no extent: the union of the region outlines
            outlines = [self.geometry(r['vector']) for r in self.active.values()]
            basin = outlines[0]
            for g in outlines[1:]:
                basin = basin.Union(g)
            basin.AssignSpatialReference(srs(s['crs']))
        x0, y0, x1, y1 = snap(bounds(basin), res)
        crs = osr.SpatialReference()
        crs.SetFromUserInput(crs_name(s['crs'], s['vertical_crs']))
        product = self.out / s['product_name']
        work = product.with_name(product.stem + '_work.tif')  # writable GTiff; a COG cannot be updated in place
        ds = gdal.GetDriverByName('GTiff').Create(str(work), round((x1 - x0) / res), round((y1 - y0) / res),
                                                  1, gdal.GDT_Float32, OPTIONS)
        ds.SetGeoTransform([x0, res, 0, y1, 0, -res])
        ds.SetSpatialRef(crs)
        ds.GetRasterBand(1).SetNoDataValue(s['nodata'])
        # Each region inside its own polygon, then measured-over-interpolated overrides on top.
        patches = [(r['dem'], r['vector']) for r in self.active.values() if self.exists('dem', r)]
        patches += [(o['merged'], o['vector']) for o in self.cfg.get('overlaps', {}).values()
                    if self.exists('merged', o) and all(n in self.active for n in o['regions'])]
        LOG.info('Assembling %d x %d cells (%.2f billion) from %d patches', ds.RasterXSize, ds.RasterYSize,
                 ds.RasterXSize * ds.RasterYSize / 1e9, len(patches))
        for i, (raster, cutline) in enumerate(patches, 1):
            start = time.perf_counter()
            gdal.Warp(ds, str(self.abs(raster)), options=gdal.WarpOptions(
                cutlineDSName=str(self.abs(cutline)), resampleAlg='near', **self.warp_all,
                options=['-novshift']))  # heights are already in the product's height system
            LOG.info('Assembled %d/%d: %s (%s)', i, len(patches), raster, elapsed(start))
        write_vector(basin, self.out / 'extent.gpkg')
        gdal.Rasterize(ds, str(self.out / 'extent.gpkg'), options=gdal.RasterizeOptions(
            burnValues=[s['nodata']], inverse=True))
        ds = None
        LOG.info('Writing COG')
        start = time.perf_counter()
        write_cog(work, product)
        LOG.info('COG written (%s)', elapsed(start))
        work.unlink()
        self.cfg['product'] = self.rel(product)
        LOG.info('Product: %s', product)
        self.save()
        self.assemble_rivers([x0, res, 0, y1, 0, -res], round((x1 - x0) / res), round((y1 - y0) / res))

    def assemble_rivers(self, geotransform, cols, rows):
        """Binary river mask on the product grid: 1 = water, 0 = land, 255 = NoData (outside the
        extent, or a region without a river mask). Like the DTM, each region's mask is used
        inside its own outline only; water body ids are dropped."""
        s = self.s
        masks = [(r['river_mask'], r['vector']) for r in self.active.values() if self.exists('river_mask', r)]
        missing = [name for name, r in self.active.items() if not self.exists('river_mask', r)]
        if not masks:
            LOG.info('No river masks recorded; merged river mask skipped')
            return
        if missing:
            LOG.warning('No river mask for %s; NoData there in the merged river mask', ', '.join(missing))
        product = self.out / s['product_name']
        out = product.with_name(product.stem + '_river_mask.tif')
        ids, binary = out.with_name(out.stem + '_ids.tif'), out.with_name(out.stem + '_work.tif')
        options = ['TILED=YES', 'COMPRESS=DEFLATE', 'BIGTIFF=YES']
        start = time.perf_counter()
        # 1. Region masks (ids; -1 = no data) painted into one grid, each clipped to its outline.
        ds = gdal.GetDriverByName('GTiff').Create(str(ids), cols, rows, 1, gdal.GDT_Int32, options)
        ds.SetGeoTransform(geotransform)
        ds.SetSpatialRef(srs(s['crs']))
        ds.GetRasterBand(1).SetNoDataValue(-1)
        for i, (mask, cutline) in enumerate(masks, 1):
            gdal.Warp(ds, str(self.abs(mask)), options=gdal.WarpOptions(
                cutlineDSName=str(self.abs(cutline)), resampleAlg='near', srcNodata=-1, **self.warp_all,
                options=['-novshift']))  # ids, not heights
            LOG.info('River mask %d/%d stitched: %s', i, len(masks), mask)
        gdal.Rasterize(ds, str(self.out / 'extent.gpkg'), options=gdal.RasterizeOptions(burnValues=[-1], inverse=True))
        # 2. Ids -> binary Byte, blockwise.
        dst = gdal.GetDriverByName('GTiff').Create(str(binary), cols, rows, 1, gdal.GDT_Byte, options)
        dst.SetGeoTransform(geotransform)
        dst.SetSpatialRef(srs(s['crs']))
        dst.GetRasterBand(1).SetNoDataValue(255)
        dst.SetMetadataItem('DESCRIPTION', '1 = water, 0 = land, 255 = NoData')
        source, target = ds.GetRasterBand(1), dst.GetRasterBand(1)
        for win in windows(ds, 2048):
            values = source.ReadAsArray(*win)
            target.WriteArray(np.where(values < 0, 255, values > 0).astype('uint8'), win[0], win[1])
        ds = dst = source = target = None
        write_cog(binary, out, MASK_COG_OPTIONS)
        ids.unlink()
        binary.unlink()
        self.cfg['river_product'] = self.rel(out)
        LOG.info('River mask product: %s (%s)', out, elapsed(start))


def main(argv=None):
    parser = argparse.ArgumentParser(description='Merge regional DTMs into one seamless DTM.')
    parser.add_argument('config', nargs='?', default='pipeline.json', type=Path)
    parser.add_argument('--stages', nargs='+', choices=STAGES, default=STAGES,
                        help='Stages to run (default: all). Finished outputs recorded in the JSON are reused.')
    args = parser.parse_args(argv)
    gdal.UseExceptions()
    run = Run(args.config)
    # Log to the terminal and to <output_dir>/pipeline.log (appended across runs).
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S', force=True,
                        handlers=[logging.StreamHandler(), logging.FileHandler(run.out / 'pipeline.log', encoding='utf-8')])
    total = time.perf_counter()
    LOG.info('Run %s: %d regions, stages %s, %s threads over %d region workers, GDAL %s',
             args.config, len(run.regions), ' '.join(args.stages), run.s['threads'], run.workers,
             gdal.VersionInfo('--version'))
    run.preflight()
    for i, stage in enumerate(args.stages, 1):
        start = time.perf_counter()
        LOG.info('== Stage %d/%d: %s', i, len(args.stages), stage)
        getattr(run, stage)()
        run.save()
        LOG.info('== Stage %s finished (%s)', stage, elapsed(start))
    if run.skipped:
        LOG.warning('Run finished (%s) with %d region(s) SKIPPED, rerun once their data is in place: %s',
                    elapsed(total), len(run.skipped), ', '.join(run.skipped))
    else:
        LOG.info('Run finished (%s)', elapsed(total))
