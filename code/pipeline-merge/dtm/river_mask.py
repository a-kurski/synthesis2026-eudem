import argparse
import json
import logging
import os
from pathlib import Path
import time

import geoutils as gu
import numpy as np
from numba import njit
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_window
from rasterio.warp import transform_bounds
from scipy import ndimage
from shapely.geometry import box

from osgeo import gdal

from .geo import read_aoi, write_json
from .process import aoi_mask
from .raster_io import load_file, save_raster

LOG = logging.getLogger("dtm")

# Defaults for settings.river_growing (each region may override keys in its own "river_growing").
RIVER_GROWING = {
    "seed_values": [2, 3],    # values of the water raster that mark water (seed) cells
    "tolerance_m": 0.02,      # max height step between neighbouring cells of one water body
    "seed_buffer_cells": 0,   # dilate the seeds by this many DEM cells
}
MASK_NODATA = -1


def load_seed_mask(dem, seeds_path, seed_values, buffer_pixels=0):
    """Boolean DEM-grid mask, True in every cell containing a seed-raster cell with one of `seed_values`."""
    dem_crs = dem.crs
    dem_transform = dem.transform
    dem_height, dem_width = dem.shape

    with rasterio.open(seeds_path) as source:
        if source.crs is None:
            raise ValueError(f"Seed raster has no CRS: {seeds_path}")
        source_crs = source.crs
        bounds_in_source_crs = transform_bounds(
            dem_crs,
            source_crs,
            *dem.bounds,
            densify_pts=21,
        )
        seed_bounds = tuple(source.bounds)  # left, bottom, right, top
        if (
            bounds_in_source_crs[2] <= seed_bounds[0]
            or bounds_in_source_crs[0] >= seed_bounds[2]
            or bounds_in_source_crs[3] <= seed_bounds[1]
            or bounds_in_source_crs[1] >= seed_bounds[3]
        ):
            raise ValueError(
                f"Seed raster does not overlap the DEM extent: {seeds_path}"
            )

        source_window = geometry_window(
            source,
            [box(*bounds_in_source_crs)],
            pad_x=1,
            pad_y=1,
        ).round_offsets().round_lengths()
        source_window = source_window.intersection(
            rasterio.windows.Window(0, 0, source.width, source.height)
        )
        source_array = source.read(1, window=source_window)
        source_transform = source.window_transform(source_window)

    # Seed cells; each centre, snapped to the DEM cell that contains it.
    rows, cols = np.nonzero(np.isin(source_array, seed_values))
    xs, ys = Transformer.from_crs(source_crs, dem_crs, always_xy=True).transform(
        source_transform.c + (cols + 0.5) * source_transform.a,
        source_transform.f + (rows + 0.5) * source_transform.e,
    )
    dem_cols = np.floor((xs - dem_transform.c) / dem_transform.a)
    dem_rows = np.floor((dem_transform.f - ys) / abs(dem_transform.e))
    inside = (  # comparisons are False for nan/inf, so failed transforms drop out
        (dem_rows >= 0) & (dem_rows < dem_height) & (dem_cols >= 0) & (dem_cols < dem_width)
    )

    mask = np.zeros((dem_height, dem_width), dtype=bool)
    mask[dem_rows[inside].astype(np.intp), dem_cols[inside].astype(np.intp)] = True
    if buffer_pixels:
        mask = ndimage.binary_dilation(
            mask,
            structure=np.ones((3, 3), dtype=bool),
            iterations=buffer_pixels,
        )
    LOG.info(f"Loaded {np.count_nonzero(mask):,} seed cells")
    return mask


def river_mask_on_grid(mask_path, reference, buffer_pixels=0):
    """Boolean mask (True = river) of a river mask raster, resampled to `reference`'s grid."""
    if not mask_path or not os.path.isfile(mask_path):
        LOG.info(f"No river mask {mask_path}, not excluding river cells")
        return np.zeros(reference.shape, dtype=bool)

    river = gu.Raster(mask_path).reproject(reference, resampling="nearest")
    mask = river.data.filled(0) > 0        # region ids > 0; nodata (-1 / outside) counts as not-river
    del river
    if buffer_pixels:
        mask = ndimage.binary_dilation(
            mask, structure=np.ones((3, 3), dtype=bool), iterations=buffer_pixels
        )
    return mask


@njit(cache=True)
def _grow_from_seeds(elevation, seeds, tolerance, valid_domain):
    """Flood fill from each seed over 8-connected valid cells whose height differs from the
    cell they are reached from by at most `tolerance` (flat water surfaces)."""
    height, width = elevation.shape
    flat_elevation = elevation.ravel()
    flat_domain = valid_domain.ravel()
    labels = np.zeros(valid_domain.shape, dtype=np.int32)
    flat_labels = labels.ravel()

    # One cell is queued at most once overall, so the queue is reused for every region.
    queue = np.empty(flat_domain.size, dtype=np.int32)  # use int64 if N > 2**31
    region = 0
    for seed in seeds:
        if flat_labels[seed]:
            continue  # seed already consumed by an earlier region
        region += 1
        flat_labels[seed] = region
        queue[0] = seed
        head = 0
        tail = 1
        while head < tail:
            current = queue[head]
            head += 1
            row = current // width
            column = current - row * width
            current_height = flat_elevation[current]

            for row_offset in range(-1, 2):
                neighbor_row = row + row_offset
                if neighbor_row < 0 or neighbor_row >= height:
                    continue
                for column_offset in range(-1, 2):
                    if row_offset == 0 and column_offset == 0:
                        continue
                    neighbor_column = column + column_offset
                    if neighbor_column < 0 or neighbor_column >= width:
                        continue
                    neighbor = neighbor_row * width + neighbor_column
                    if (flat_domain[neighbor] and not flat_labels[neighbor]
                            and abs(flat_elevation[neighbor] - current_height) <= tolerance):
                        flat_labels[neighbor] = region
                        queue[tail] = neighbor
                        tail += 1
    return labels


def grow_water_regions(elevation, seed_mask, tolerance=RIVER_GROWING["tolerance_m"], valid_domain=None):
    """Label water bodies grown from `seed_mask`: 0 = not water, 1..R = region, in seed order.
    Returns (labels, accepted seed indices)."""
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Region-growing tolerance must be finite and non-negative")
    if elevation.shape != seed_mask.shape:
        raise ValueError("DEM and seed mask dimensions do not match")

    if valid_domain is None:
        valid_domain = np.isfinite(elevation)
    elif valid_domain.shape != elevation.shape:
        raise ValueError("DEM and valid-domain dimensions do not match")
    valid_domain = valid_domain & np.isfinite(elevation)
    seeds = np.flatnonzero(seed_mask & valid_domain)  # flat indices, int64
    if seeds.size == 0:
        raise ValueError("Seed mask contains no valid cells")

    LOG.info(f"Growing from {seeds.size:,} seeds (8-connected, tolerance {tolerance:g} m)")
    return _grow_from_seeds(elevation, seeds, tolerance, valid_domain), seeds


def process_dem(dem_path, seeds_path, out_dir, epsg, region=None, growing=None):
    """Grow river regions from seed-raster cells; returns the river mask path (0 = no river, 1..R = region id).

    `growing`: settings as in RIVER_GROWING (missing keys take the defaults); `epsg`: CRS of `region`.

    With `region` (an OGR polygon) only seeds inside it are used; regions may
    still grow beyond it within the DEM, e.g. along a border river.
    """
    LOG.info(f"Processing {dem_path}")
    dem, _ = load_file(dem_path)
    growing = {**RIVER_GROWING, **(growing or {})}
    water_mask = load_seed_mask(dem, seeds_path, growing["seed_values"], growing["seed_buffer_cells"])
    if region is not None:
        with gdal.Open(dem_path) as reference, \
                aoi_mask(region, reference, os.path.join(out_dir, "region_mask.tif"), epsg) as inside:
            water_mask &= inside.ReadAsArray() != 0
        LOG.info(f"{np.count_nonzero(water_mask):,} seed cells inside the region")
    dem_values = np.asarray(dem.data.filled(np.nan), dtype=np.float32)
    dem_valid = np.isfinite(dem_values)
    elevation = np.where(dem_valid, dem_values, 0.0).astype(np.float32, copy=False)

    labels, seeds = grow_water_regions(
        elevation, water_mask, tolerance=growing["tolerance_m"], valid_domain=dem_valid
    )

    basename = os.path.splitext(os.path.basename(dem_path))[0]
    output = lambda name: os.path.join(out_dir, name)  # noqa: E731
    river_mask_path = output(f"{basename}_river_mask.tif")
    river_mask = labels
    river_mask[~dem_valid] = MASK_NODATA
    save_raster(
        river_mask,
        river_mask_path,
        dem.transform,
        dem.crs,
        MASK_NODATA,
        dtype="int32",
        resampling="NEAREST",  # region ids must not be averaged in overviews
    )
    LOG.info(
        f"Saved river mask: {seeds.size:,} seeds in {int(river_mask.max()):,} regions: {river_mask_path}"
    )
    return river_mask_path


LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def _mask_job(name, dem, seeds, out_dir, vector, epsg, growing):
    start = time.perf_counter()
    LOG.info(f"{name}: river mask started")
    path = process_dem(dem, seeds, out_dir, epsg, region=read_aoi(vector)[0], growing=growing)
    LOG.info(f"{name}: river mask done ({time.perf_counter() - start:.0f} s)")
    return path


def create_masks(config_path):
    """Create a river mask for every region in the pipeline JSON and record its path there.

    Seeds: each region's own water raster `river_seeds` (cells with one of the
    `river_growing.seed_values`), cropped to the region's `vector`; region growing runs
    separately on each region's DEM. `river_growing` comes from the settings, with
    per-region overrides.
    Regions run one after another (in parallel they ran out of memory).
    Regions whose mask already exists are skipped, so reruns resume.
    """
    config_path = Path(config_path).resolve()
    root = config_path.parent
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    settings = config["settings"]
    out = root / settings.get("output_dir", "data/pipeline")
    jobs = {}
    for name, region in config["regions"].items():
        mask, seeds = region.get("river_mask"), region.get("river_seeds")
        if mask and (root / mask).exists():
            continue
        if not region.get("dem") or not (root / region["dem"]).exists():
            LOG.info(f"{name}: no DEM yet, skipping river mask")
            continue
        if not seeds or not (root / seeds).exists():
            LOG.info(f"{name}: water raster river_seeds missing ({seeds}), skipping river mask")
            continue
        (out / name).mkdir(parents=True, exist_ok=True)
        growing = {**RIVER_GROWING, **settings.get("river_growing", {}), **region.get("river_growing", {})}
        jobs[name] = (str(root / region["dem"]), str(root / seeds), str(out / name),
                      str(root / region["vector"]), settings["crs"], growing)
    if not jobs:
        return
    LOG.info(f"River masks for {len(jobs)} region(s), one at a time: {', '.join(jobs)}")
    failed = []
    for i, (name, args) in enumerate(jobs.items(), 1):
        LOG.info(f"River mask {i}/{len(jobs)}: {name}")
        try:
            path = _mask_job(name, *args)
        except Exception:
            LOG.exception(f"{name}: river mask FAILED")
            failed.append(name)
            continue
        config["regions"][name]["river_mask"] = Path(os.path.relpath(path, root)).as_posix()
        write_json(config_path, config)
    if failed:
        raise RuntimeError(f"River masks failed for: {', '.join(failed)} (finished ones are recorded; rerun to retry)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create river masks for the regions in a pipeline JSON.")
    parser.add_argument("config", nargs="?", default="pipeline.json")
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    create_masks(parser.parse_args().config)
