import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import logging
import multiprocessing
import os
from pathlib import Path
import time

import geopandas as gpd
import geoutils as gu
import numpy as np
import pandas as pd
import rasterio
import shapely
import xdem
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.features import shapes
from rasterio.warp import transform_bounds
from shapely.geometry import box, shape

from .geo import write_json
from .river_mask import river_mask_on_grid
from . import raster_io
from .raster_io import load_file, result_path, save_raster

LOG = logging.getLogger(__name__)


def load_pyplot():
    import matplotlib.pyplot as pyplot

    return pyplot


def dem_files_overlap(path_1, path_2):
    with rasterio.open(path_1) as dem_1, rasterio.open(path_2) as dem_2:
        bounds_1 = dem_1.bounds
        bounds_2 = dem_2.bounds
        if CRS.from_user_input(dem_1.crs) != CRS.from_user_input(dem_2.crs):
            bounds_2 = Transformer.from_crs(
                dem_2.crs,
                dem_1.crs,
                always_xy=True,
            ).transform_bounds(*bounds_2, densify_pts=21)

    return (
        max(bounds_1[0], bounds_2[0]) < min(bounds_1[2], bounds_2[2])
        and max(bounds_1[1], bounds_2[1]) < min(bounds_1[3], bounds_2[3])
    )


def save_vector(vector, filename):
    vector.to_file(filename)


def nanmean(values):
    return np.nanmean(values)


def nanrmse(values):
    return np.sqrt(np.nanmean(np.asarray(values) ** 2))


MASK_NODATA_U8 = 255
# Defaults for settings.comparison in the pipeline JSON.
COMPARISON = {
    "threshold_fraction": 1 / 3,       # problem threshold = resolution * this (INSPIRE: resolution / 3)
    "river_buffer_cells": 1,           # river masks are dilated by this many cells before exclusion
    "max_distance_m": 2000,            # x-axis extent of the distance plots (correlation, border strips)
    "border_strip_m": 50,              # width of the distance-to-border strips
    "local_rmse_tile_m": 50,           # tile size of the local RMSE raster
    "problem_min_area_m2": 200,        # smallest problem region kept
    "problem_merge_distance_m": 60,    # problem cells closer than this are merged into one region
    # Uncertainty (xdem, Hugonnet et al. 2022): heteroscedasticity + spatial correlation + propagation
    "uncertainty": True,               # false skips the whole uncertainty analysis (it is the slowest step)
    "precision_of_other": "same",      # "same": both DEMs equally precise; "finer": the first DEM is much better
    "uncertainty_variables": ["slope", "max_curvature"],  # terrain attributes that explain error variability
    "variogram_models": ["Gaussian", "Spherical"],         # summed models = several correlation ranges
    "workers": 1,                      # pairs compared at the same time (one process each)
}
CFG = dict(COMPARISON)  # active settings, set by run_all_analyses


def threshold_for(raster):
    return abs(raster.transform.a) * CFG["threshold_fraction"]


def difference_statistics(values, threshold):
    """Statistics of elevation differences (NaN = excluded) for one border pair."""
    values = values[np.isfinite(values)].astype("float64")
    if not values.size:
        return {"valid_cells": 0, "threshold_m": threshold}
    rmse = float(np.sqrt(np.mean(values**2)))
    above = int(np.count_nonzero(np.abs(values) > threshold))
    return {
        "valid_cells": values.size,
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "std": float(np.std(values)),
        "rmse": rmse,
        "mae": float(np.mean(np.abs(values))),
        "nmad": float(gu.stats.nmad(values)),
        "le90": float(np.percentile(np.abs(values), 90)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "threshold_m": threshold,
        "cells_above_threshold": above,
        "percent_above_threshold": 100 * above / values.size,
        "INSPIRE_target%": rmse / threshold * 100,
    }


def analyze_dem(dem_1, dem_2, name_1, name_2, mask_1=None, mask_2=None, river_buffer=None, fill_1=None, fill_2=None):
    bounds = transform_bounds(dem_2.crs, dem_1.crs, *dem_2.bounds, densify_pts=21)
    try:
        dem_1 = dem_1.crop(bounds)
    except rasterio.errors.WindowError:
        LOG.info(f"No overlap between {name_1} and {name_2} after loading, skipping")
        return None
    dem_2 = dem_2.reproject(dem_1)

    river_buffer = CFG["river_buffer_cells"] if river_buffer is None else river_buffer
    river = river_mask_on_grid(mask_1, dem_1, river_buffer) | river_mask_on_grid(mask_2, dem_1, river_buffer)
    LOG.info(f"Excluding {np.count_nonzero(river):,} river cells")
    # Interpolated (hole-filled) cells of either DEM; same lattice as the DEMs, so nearest = exact.
    interpolated = np.zeros(dem_1.shape, dtype=bool)
    for fill in (fill_1, fill_2):
        if fill:
            interpolated |= river_mask_on_grid(fill, dem_1)  # generic: any raster > 0 on dem_1's grid
    LOG.info(f"{np.count_nonzero(interpolated):,} interpolated cells (reported separately)")

    if not (
        ~np.ma.getmaskarray(dem_1.data)
        & ~np.ma.getmaskarray(dem_2.data)
        & np.isfinite(dem_1.data.data)
        & np.isfinite(dem_2.data.data)
    ).any():
        LOG.info(
            f"Skipping comparison for {name_1} and "
            f"{name_2}: no shared valid elevation pixels.")
        return None

    # Nuth & Kaab only: horizontal shift + vertical offset. Used for the systematic-offset
    # numbers and the uncertainty estimate; everything spatial uses the raw difference.
    # (A 2nd-order deramp is poorly constrained on thin border strips and was dropped.)
    coreg = xdem.coreg.NuthKaab()
    coreg.fit(dem_1, dem_2, inlier_mask=~river)
    dem_2_aligned = coreg.apply(dem_2)
    shift_x, shift_y, shift_z = (float(v) for v in coreg.to_matrix()[:3, 3])
    LOG.info(f"Nuth & Kaab shift applied to {name_2}: x {shift_x:.3f} m, y {shift_y:.3f} m, z {shift_z:.3f} m")

    dh = dem_1 - dem_2  # raw difference, as merged
    dh.set_mask(river)
    dh_aligned = dem_1 - dem_2_aligned
    dh_aligned.set_mask(river)

    # Random-error model on stable terrain (no water, no gap-filled cells), after coregistration.
    model = None
    if CFG["uncertainty"]:
        try:  # optional: needs enough valid cells for the binning and variogram fit
            model = uncertainty_model(dem_1, dh_aligned, river | interpolated, name_1, name_2)
        except Exception as exc:
            load_pyplot().close("all")
            LOG.info(f"Uncertainty estimate skipped for {name_1} and {name_2}: {type(exc).__name__}: "
                     f"{str(exc).splitlines()[0] if str(exc) else ''}")

    # Border consistency on the raw difference (before coregistration), river cells excluded.
    threshold = threshold_for(dh)
    raw = dh.data.filled(np.nan)
    # Interpolated cells are not judged: they are overridden by measured data where the neighbour has it.
    exceeds = np.where(np.isfinite(raw) & ~interpolated, np.abs(raw) > threshold, MASK_NODATA_U8).astype("uint8")
    save_raster(
        exceeds,
        result_path(f"exceeds_threshold_{name_1}_{name_2}.tif"),
        dh.transform,
        dh.crs,
        MASK_NODATA_U8,
        dtype="uint8",
        resampling="NEAREST",
        tags={"meaning": f"1 = |{name_1} - {name_2}| > {threshold:g} m (resolution * {CFG['threshold_fraction']:g}), 0 = within, "
                         f"{MASK_NODATA_U8} = no common data, river or interpolated; before coregistration"},
    )
    # Statistics with all compared cells, and with interpolated cells excluded (measured only).
    shift = {"shift_x_m": shift_x, "shift_y_m": shift_y, "shift_z_m": shift_z}
    rows = []
    for stage, values, extra in (("before_coregistration", raw, {}),
                                 ("after_coregistration", dh_aligned.data.filled(np.nan), shift)):
        measured = values.copy()
        measured[interpolated] = np.nan
        for cells, selected in (("all", values), ("measured_only", measured)):
            rows.append({"reference_dem": name_1, "comparison_dem": name_2, "stage": stage, "cells": cells,
                         **difference_statistics(selected, threshold),
                         **(mean_uncertainty(model, np.isfinite(selected), dh) if model else {}), **extra})
    pd.DataFrame(rows).to_csv(result_path(f"statistics_{name_1}_{name_2}.csv"), index=False)
    stats = rows[0]
    save_raster(
        dh,
        result_path(f"dh_{name_1}_{name_2}.tif"),
    )
    return {
        "coreg": coreg,
        "dem_2": dem_2,
        "dh": dh,
        "interpolated": interpolated,
        "dem_1": dem_1,
        "name_1": name_1,
        "name_2": name_2,
        "statistics": rows,
        **stats,
    }


def uncertainty_model(dem, dh, unstable, name_1, name_2):
    """xdem's uncertainty workflow (Hugonnet et al., 2022) on the coregistered difference `dh`:

    1. heteroscedasticity: error (NMAD) binned by terrain attributes on stable terrain -> error map;
    2. spatial correlation: variogram of the standardized differences, fitted with summed models;
    3. propagation (see mean_uncertainty): error of a mean over an area via the number of
       effective samples.
    Writes the error map, binning and variogram plots. Returns what mean_uncertainty needs.
    """
    import xdem.spatialstats as ss

    plt = load_pyplot()
    scale = np.sqrt(2) if CFG["precision_of_other"] == "same" else 1.0  # dh error -> error of one DEM
    names = list(CFG["uncertainty_variables"])
    variables = [getattr(xdem.terrain, name)(dem) for name in names]
    sig_dh, binning, _ = ss.infer_heteroscedasticity_from_stable(
        dh, list_var=variables, list_var_names=names, unstable_mask=unstable)
    for name in names:
        ss.plot_1d_binning(binning, name, "nmad", label_var=name.replace("_", " "),
                           label_statistic="NMAD of dh (m)", out_fname=result_path(f"heteroscedasticity_{name}_{name_1}_{name_2}.png"))
        plt.close("all")

    empirical, params, correlation = ss.infer_spatial_correlation_from_stable(
        dh, list_models=list(CFG["variogram_models"]), unstable_mask=unstable, errors=sig_dh, random_state=42)
    ss.plot_variogram(empirical, list_fit_fun=[ss.get_variogram_model_func(params)],
                      list_fit_fun_label=["model"], xscale="log",
                      out_fname=result_path(f"variogram_{name_1}_{name_2}.png"))
    plt.close("all")
    LOG.info("Error correlation ranges: " + ", ".join(
        f"{row.model} {row.range:.0f} m (psill {row.psill:.2f})" for row in params.itertuples()))

    sig_dem = sig_dh / scale
    save_raster(sig_dem, result_path(f"uncertainty_{name_1}_{name_2}.tif"))
    values = sig_dem.data.compressed()
    vmin, vmax = np.nanpercentile(values, [2, 98]) if values.size else (None, None)
    sig_dem.plot(cmap="Purples", vmin=vmin, vmax=vmax, cbar_title=r"Error in elevation (1$\sigma$, m)")
    plt.savefig(result_path(f"uncertainty_{name_1}_{name_2}.png"), dpi=300, bbox_inches="tight")
    plt.close("all")

    x = np.linspace(0, CFG["max_distance_m"], 201)
    plt.plot(x, correlation(x))
    plt.xlabel("Distance [m]")
    plt.ylabel("Error correlation (0-1)")
    plt.savefig(result_path(f"Correlation_{name_1}_{name_2}.png"), dpi=300, bbox_inches="tight")
    plt.close("all")
    return {"sig_dh": sig_dh.data.filled(np.nan), "params": params, "scale": scale,
            "correlation_1km": float(correlation(1000))}


def mean_uncertainty(model, cells, dh):
    """1-sigma error of the mean difference over `cells`: mean error / sqrt(number of effective samples).

    The area is passed as a number, which xdem treats as a disk: for thin border strips this
    gives fewer effective samples than the true shape, i.e. a conservative (larger) error."""
    import xdem.spatialstats as ss

    cells = cells & np.isfinite(model["sig_dh"])
    if not cells.any():
        return {}
    area = np.count_nonzero(cells) * abs(dh.transform.a * dh.transform.e)
    n_eff = float(ss.number_effective_samples(area=area, params_variogram_model=model["params"]))
    mean_error = float(np.nanmean(model["sig_dh"][cells]))
    return {"mean_sigma_dh_m": mean_error, "n_effective": n_eff,
            "mean_dh_sigma_m": mean_error / np.sqrt(max(n_eff, 1.0)),
            "error_correlation_1km": model["correlation_1km"]}


def local_inspire_rmse_analysis(dh, name, tile_size_m=None):
    tile_size_m = CFG["local_rmse_tile_m"] if tile_size_m is None else tile_size_m
    data = dh.data.filled(np.nan)
    crs = CRS.from_user_input(dh.crs)
    unit_to_meters = crs.axis_info[0].unit_conversion_factor
    pixel_x = abs(dh.transform.a) * unit_to_meters
    pixel_y = abs(dh.transform.e) * unit_to_meters
    resolution = np.sqrt(pixel_x * pixel_y)
    tile_rows = max(1, round(tile_size_m / pixel_y))
    tile_cols = max(1, round(tile_size_m / pixel_x))
    rmse_raster = np.full(data.shape, np.nan, dtype=np.float32)

    for row in range(0, dh.height, tile_rows):
        for col in range(0, dh.width, tile_cols):
            row_end = min(row + tile_rows, dh.height)
            col_end = min(col + tile_cols, dh.width)
            tile = data[row:row_end, col:col_end]
            valid = np.isfinite(tile)
            values = tile[valid]
            if not values.size:
                continue
            rmse_raster[row:row_end, col:col_end][valid] = np.sqrt(
                np.mean(values**2)
            )

    rmse_dem = dh.copy(new_array=rmse_raster)
    save_raster(
        rmse_raster,
        result_path(f"local_inspire_rmse_{name}.tif"),
        dh.transform,
        dh.crs,
        np.nan,
        dtype="float32",
        tags={
            "metric": "Local RMSE of elevation differences",
            "tile_size_m": str(tile_size_m),
            "pixel_resolution_m": str(resolution),
            "inspire_rmse_threshold_m": str(resolution * CFG["threshold_fraction"]),
            "pass_condition": "RMSE <= inspire_rmse_threshold_m",
        },
    )
    return rmse_dem


def std_analysis(dh, name):
    save_raster(
        dh - nanmean(dh.data.filled(np.nan)),
        result_path(f"dh_std_{name}.tif"),
    )


def histogram_analysis(dh, name):
    plt = load_pyplot()
    values = dh.data.compressed()

    plt.figure(figsize=(8, 5))
    plt.hist(values, bins=100, log=True)
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Count (log scale)")
    plt.title("DEM Difference Histogram")
    plt.grid(True, which="both", alpha=0.3)
    plt.savefig(result_path(f"histogram_{name}.png"), dpi=200, bbox_inches="tight")
    plt.close()


def cdf_analysis(dh, name):
    plt = load_pyplot()
    values = np.sort(dh.data.compressed())
    plt.figure(figsize=(8, 5))
    plt.plot(values, np.arange(len(values)) / len(values))
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Cumulative probability")
    plt.title("DEM Difference CDF")
    plt.grid()
    plt.savefig(result_path(f"cdf_{name}.png"))
    plt.close()


def aspect_difference_analysis(dem_1, dem_2, name_1, name_2):
    difference = dem_1.aspect() - dem_2.reproject(dem_1).aspect()
    save_raster(
        difference,
        result_path(f"aspect_difference_{name_1}_{name_2}.tif")
    )


def slope_error_analysis(dem_1, dh, name):
    plt = load_pyplot()
    slopes = dem_1.slope().data.filled(np.nan)
    differences = dh.data.filled(np.nan)
    bins = np.arange(0, 55, 5)
    rmses = [
        nanrmse(differences[(slopes >= lo) & (slopes < hi)])
        for lo, hi in zip(bins[:-1], bins[1:])
    ]
    plt.figure(figsize=(8, 5))
    plt.plot(bins[:-1], rmses, marker="o")
    plt.xlabel("Slope (deg)")
    plt.ylabel("RMSE (m)")
    plt.title("RMSE versus Slope")
    plt.savefig(result_path(f"slope_rmse_{name}.png"))
    plt.close()


def border_strip_analysis(dh, border_vector, name):
    strips = range(0, int(CFG["max_distance_m"]) + 1, int(CFG["border_strip_m"]))
    z = dh.data.filled(np.nan)
    unit_to_meters = border_vector.crs.axis_info[0].unit_conversion_factor
    max_distance = strips[-1] / unit_to_meters
    bounds = Transformer.from_crs(
        dh.crs,
        border_vector.crs,
        always_xy=True,
    ).transform_bounds(*dh.bounds, densify_pts=21)
    search_area = box(
        bounds[0] - max_distance,
        bounds[1] - max_distance,
        bounds[2] + max_distance,
        bounds[3] + max_distance,
    )
    nearby = border_vector.ds.loc[
        border_vector.ds.geometry.intersects(search_area)
    ].copy()
    nearby.geometry = nearby.geometry.intersection(search_area)
    nearby = nearby.loc[~nearby.geometry.is_empty]
    local_borders = gu.Vector(nearby).reproject(crs=dh.crs)
    pad_columns = int(np.ceil(strips[-1] / abs(dh.transform.a)))
    pad_rows = int(np.ceil(strips[-1] / abs(dh.transform.e)))
    proximity_grid = gu.Raster.from_array(
        np.zeros(
            (dh.height + 2 * pad_rows, dh.width + 2 * pad_columns),
            dtype=np.uint8,
        ),
        transform=dh.transform * Affine.translation(-pad_columns, -pad_rows),
        crs=dh.crs,
    )
    distances = proximity_grid.proximity(
        local_borders,
        geometry_type="geometry",
    ).crop(dh).data.filled(np.nan)
    rows = []
    for lo, hi in zip(strips[:-1], strips[1:]):
        strip = z[(distances >= lo) & (distances < hi) & np.isfinite(z)]
        rows.append([lo, hi, nanmean(strip), nanrmse(strip)])
    df = pd.DataFrame(rows, columns=["min_dist", "max_dist", "mean", "rmse"])
    df.to_csv(result_path(f"border_strips_{name}.csv"), index=False)
    return df


def load_border_vector(vector_path, crs):
    """Border lines; files without a CRS are assumed to be in the pipeline CRS."""
    with rasterio.Env(SHAPE_RESTORE_SHX="YES"):
        border_vector = gu.Vector(vector_path)
    border_vector.ds = border_vector.ds.set_crs(
        border_vector.crs or CRS.from_epsg(crs)
    )
    return border_vector


def border_trend_plot(csv_file, name):
    plt = load_pyplot()
    df = pd.read_csv(csv_file)
    plt.figure(figsize=(8, 5))
    plt.plot(df["max_dist"], df["rmse"], marker="o")
    plt.xlabel("Distance from border (m)")
    plt.ylabel("RMSE (m)")
    plt.title("Border Effect")
    plt.grid()
    plt.savefig(result_path(f"border_effect_{name}.png"), dpi=300)
    plt.close()


def top_problem_regions(dh, name, threshold=None, min_area=None, merge_distance=None, exclude=None):
    """Polygons of clustered cells with |dh| > threshold; `exclude` (bool array) cells are ignored."""
    threshold = threshold_for(dh) if threshold is None else threshold
    min_area = CFG["problem_min_area_m2"] if min_area is None else min_area
    merge_distance = CFG["problem_merge_distance_m"] if merge_distance is None else merge_distance
    dh_array = np.array(dh.data.filled(np.nan), dtype=float)  # copy: edited below
    if exclude is not None:
        dh_array[exclude] = np.nan
    mask = (np.abs(dh_array) > threshold).astype(np.uint8)
    exceedance_count = int(np.count_nonzero(mask))
    geometries = [
        shape(geometry)
        for geometry, _ in shapes(
            mask,
            mask=mask.astype(bool),
            transform=dh.transform,
        )
    ]
    candidate_count = len(geometries)
    dem_crs = CRS.from_user_input(dh.crs)
    unit_to_meters = dem_crs.axis_info[0].unit_conversion_factor
    merge_radius = merge_distance / unit_to_meters / 2
    buffered_geometries = shapely.buffer(geometries, merge_radius)
    buffered_regions = gpd.GeoSeries(buffered_geometries, crs=dem_crs)
    merge_zones = shapely.get_parts(shapely.union_all(buffered_geometries))
    spatial_index = buffered_regions.sindex
    merged_records = []

    for merged_geometry in merge_zones:
        members = spatial_index.query(merged_geometry, predicate="intersects")
        area_m2 = (
            sum(shapely.area(geometries[index]) for index in members)
            * unit_to_meters**2
        )
        if area_m2 >= min_area:
            merged_records.append(
                {"area_m2": area_m2, "geometry": merged_geometry}
            )

    regions = gpd.GeoDataFrame(
        merged_records,
        columns=["area_m2", "geometry"],
        geometry="geometry",
        crs=dem_crs,
    )
    regions["severity"] = regions["area_m2"] / 1000
    regions = regions.sort_values("severity", ascending=False).reset_index(drop=True)
    regions["rank"] = regions.index + 1
    regions = gu.Vector(regions)
    save_vector(regions, result_path(f"problem_regions_{name}.gpkg"))
    LOG.info(
        f"Problem regions: {exceedance_count} cells exceed {threshold} m; "
        f"{candidate_count} initial regions merged, {len(regions.ds)} retained "
        f"above {min_area} m²."
    )
    return regions


def _init_worker(cfg, log_file):
    """Comparison worker process: same settings and log format as the parent, prefixed with the pair."""
    os.environ.setdefault("MPLBACKEND", "Agg")
    CFG.clear()
    CFG.update(cfg)
    handlers = [logging.StreamHandler()]
    if log_file and os.path.isdir(os.path.dirname(log_file)):
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(processName)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S", handlers=handlers, force=True)


def compare_pair(first_name, second_name, first, second, out_dir, border_path, crs):
    """Run every analysis for one pair; `first`/`second` are (dem, river_mask, fill_mask) paths.

    Writes into `out_dir` and returns the statistics rows and the statistics CSV path,
    or None if the DEMs share no valid cells."""
    if multiprocessing.parent_process() is not None:
        multiprocessing.current_process().name = f"{first_name}__{second_name}"  # shows up in the log
    raster_io.RESULTS_DIR = str(out_dir)
    started = time.perf_counter()
    # Pipeline DEMs already share the target CRS/VRS: load as-is.
    dem_1, dem_2 = load_file(first[0])[0], load_file(second[0])[0]
    analysis = analyze_dem(dem_1, dem_2, first_name, second_name, first[1], second[1],
                           fill_1=first[2], fill_2=second[2])
    if analysis is None:
        return None
    dh, dem_1_crop = analysis["dh"], analysis["dem_1"]
    name = f"{first_name}_{second_name}"
    local_inspire_rmse_analysis(dh, name)
    std_analysis(dh, name)
    histogram_analysis(dh, name)
    cdf_analysis(dh, name)
    slope_error_analysis(dem_1_crop, dh, name)
    aspect_difference_analysis(dem_1_crop, analysis["dem_2"], first_name, second_name)
    top_problem_regions(dh, name, exclude=analysis["interpolated"])
    if border_path:
        border_strip_analysis(dh, load_border_vector(border_path, crs), name)
        border_trend_plot(result_path(f"border_strips_{name}.csv"), name)
    LOG.info(f"Comparison done for {first_name} and {second_name} ({time.perf_counter() - started:.0f} s)")
    return analysis["statistics"], result_path(f"statistics_{name}.csv")


def run_all_analyses(config_path="pipeline.json"):
    """Compare every overlapping pair of region DEMs listed in the pipeline JSON.

    DEM and river mask paths come from each region's `dem` and `river_mask`
    entries (written by the pipeline and river_mask.create_masks). Up to
    `settings.comparison.workers` pairs run at once, each in its own process.
    """
    analysis_start = time.perf_counter()
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    regions = config["regions"]
    unknown = set(config["settings"].get("comparison", {})) - set(COMPARISON)
    if unknown:
        raise ValueError(f"Unknown settings.comparison keys: {sorted(unknown)}")
    CFG.clear()
    CFG.update({**COMPARISON, **config["settings"].get("comparison", {})})
    # Results go to <output_dir>/comparison next to the pipeline outputs.
    results = config_path.parent / config["settings"].get("output_dir", "data/pipeline") / "comparison"
    raster_io.RESULTS_DIR = str(results)
    resolve = lambda path: str(config_path.parent / path) if path else None  # noqa: E731
    dems = {name: (resolve(r["dem"]), resolve(r.get("river_mask")), resolve(r.get("fill_mask")))
            for name, r in regions.items() if r.get("dem")}
    if not dems:
        raise FileNotFoundError(f"No region DEMs recorded in {config_path}; run the pipeline first")
    names = list(dems)

    statistics = []
    failed_pairs = []
    pair_count = len(names) * (len(names) - 1) // 2

    # Border lines for the distance-from-border analysis (optional): settings.borders.
    border_setting = config["settings"].get("borders")
    border_path = str(config_path.parent / border_setting) if border_setting else None
    if border_path and not os.path.isfile(border_path):
        LOG.warning(f"settings.borders not found: {border_path}")
        border_path = None
    if border_path is None:
        LOG.info("No border lines (settings.borders), skipping border analyses")

    # Resume: finished pairs are recorded in the JSON under "comparisons" (pair -> statistics CSV);
    # a pair is skipped while that file exists and is newer than both DEMs. Delete the entry or
    # the file to redo a pair.
    done = config.setdefault("comparisons", {})
    LOG.info(f"Checking {pair_count} DEM combinations for overlap...")
    attempted = reused = 0
    todo = []
    for first_index, first_name in enumerate(names):
        for second_name in names[first_index + 1 :]:
            attempted += 1
            first_path, second_path = dems[first_name][0], dems[second_name][0]
            pair_name = f"{first_name} and {second_name}"
            progress = f"[{attempted}/{pair_count}]"
            # Recorded, file present and newer than both DEMs (a reprocessed region is compared again).
            newest_dem = max(os.path.getmtime(first_path), os.path.getmtime(second_path))
            key = next((k for k in (f"{first_name}__{second_name}", f"{second_name}__{first_name}")
                        if done.get(k) and (config_path.parent / done[k]).is_file()
                        and os.path.getmtime(config_path.parent / done[k]) >= newest_dem), None)
            if key:  # also catches the reversed name, e.g. after reordering regions in the JSON
                LOG.info(f"{progress} Already compared: {pair_name} ({done[key]}), skipping")
                statistics.extend(pd.read_csv(config_path.parent / done[key]).to_dict("records"))
                reused += 1
            elif not dem_files_overlap(first_path, second_path):
                LOG.info(f"{progress} Skipping comparison for non-overlapping DEMs: {pair_name}")
            else:
                LOG.info(f"{progress} Queued for comparison: {pair_name}")
                todo.append((first_name, second_name))

    workers = max(1, min(int(CFG["workers"]), len(todo) or 1))
    LOG.info(f"{len(todo)} overlapping pair(s) to compare, {workers} at a time")

    def finished(pair, result):
        first_name, second_name = pair
        pair_name = f"{first_name} and {second_name}"
        if result is None:
            return
        rows, stats_file = result
        statistics.extend(rows)
        done[f"{first_name}__{second_name}"] = Path(os.path.relpath(stats_file, config_path.parent)).as_posix()
        write_json(config_path, config)  # only this (parent) process writes the JSON
        LOG.info(f"Recorded {pair_name}: {done[f'{first_name}__{second_name}']}")

    def arguments(pair):
        first_name, second_name = pair
        return (first_name, second_name, dems[first_name], dems[second_name],
                results / f"{first_name}__{second_name}", border_path, config["settings"]["crs"])

    if workers == 1:
        for number, pair in enumerate(todo, 1):
            LOG.info(f"Comparing pair {number}/{len(todo)}: {pair[0]} and {pair[1]}")
            try:
                finished(pair, compare_pair(*arguments(pair)))
            except Exception:  # one failing pair must not stop the others
                LOG.exception(f"Comparison FAILED for {pair[0]} and {pair[1]}; continuing with the next pair")
                failed_pairs.append(f"{pair[0]} and {pair[1]}")
    else:
        # Separate 'spawn' processes: matplotlib and GDAL are not safe to share between threads or forks.
        log_file = next((h.baseFilename for h in logging.getLogger().handlers
                         if isinstance(h, logging.FileHandler)), None)
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(workers, mp_context=context, initializer=_init_worker,
                                 initargs=(dict(CFG), log_file)) as pool:
            futures = {pool.submit(compare_pair, *arguments(pair)): pair for pair in todo}
            for number, future in enumerate(as_completed(futures), 1):
                pair = futures[future]
                try:
                    finished(pair, future.result())
                except Exception:
                    LOG.exception(f"Comparison FAILED for {pair[0]} and {pair[1]}; continuing with the next pair")
                    failed_pairs.append(f"{pair[0]} and {pair[1]}")
                LOG.info(f"{number}/{len(todo)} pairs finished")

    raster_io.RESULTS_DIR = str(results)  # summary of all pairs at the top level
    pd.DataFrame(statistics).to_csv(
        result_path("dem_difference_statistics.csv"),
        index=False,
    )
    LOG.info(f"Attempted {attempted} of {pair_count} combinations; {reused} already done earlier, "
             f"{len(todo)} with overlapping extents run, {len(failed_pairs)} failed")
    if failed_pairs:
        LOG.info(f"{len(failed_pairs)} pair(s) FAILED: {', '.join(failed_pairs)}")
    elapsed_seconds = time.perf_counter() - analysis_start
    hours, remainder = divmod(int(elapsed_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    LOG.info(
        f"Total analysis loop time: {hours:02d}:{minutes:02d}:{seconds:02d} "
        f"({elapsed_seconds:.1f} seconds).")
    return {"dem_paths": {name: paths[0] for name, paths in dems.items()}, "statistics": statistics}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare overlapping region DEMs from a pipeline JSON.")
    parser.add_argument("config", nargs="?", default="pipeline.json")
    config = Path(parser.parse_args().config).resolve()
    settings = json.loads(config.read_text(encoding="utf-8-sig"))["settings"]
    out = config.parent / settings.get("output_dir", "data/pipeline")
    out.mkdir(parents=True, exist_ok=True)
    # Same format as the pipeline; appended to <output_dir>/pipeline.log.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        force=True, handlers=[logging.StreamHandler(), logging.FileHandler(out / "pipeline.log", encoding="utf-8")])
    LOG.info(f"Comparison run: {config}")
    run_all_analyses(config)
