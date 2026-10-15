import argparse
import glob
import json
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

from .river_mask import river_mask_on_grid
from . import vertical_transform
from .vertical_transform import DATA_DIR, load_file, result_path, save_raster


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
        "nmad": float(xdem.spatialstats.nmad(values)),
        "le90": float(np.percentile(np.abs(values), 90)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "threshold_m": threshold,
        "cells_above_threshold": above,
        "percent_above_threshold": 100 * above / values.size,
        "INSPIRE_target%": rmse / threshold * 100,
    }


def analyze_dem(dem_1, dem_2, name_1, name_2, mask_1=None, mask_2=None, river_buffer=1):
    bounds = transform_bounds(dem_2.crs, dem_1.crs, *dem_2.bounds, densify_pts=21)
    try:
        dem_1 = dem_1.crop(bounds)
    except rasterio.errors.WindowError:
        print(f"No overlap between {name_1} and {name_2} after loading, skipping", flush=True)
        return None
    dem_2 = dem_2.reproject(dem_1)

    river = river_mask_on_grid(mask_1, dem_1, river_buffer) | river_mask_on_grid(mask_2, dem_1, river_buffer)
    print(f"Excluding {np.count_nonzero(river):,} river cells", flush=True)

    if not (
        ~np.ma.getmaskarray(dem_1.data)
        & ~np.ma.getmaskarray(dem_2.data)
        & np.isfinite(dem_1.data.data)
        & np.isfinite(dem_2.data.data)
    ).any():
        print(
            f"Skipping comparison for {name_1} and "
            f"{name_2}: no shared valid elevation pixels.",
            flush=True,
        )
        return None

    coreg = xdem.coreg.NuthKaab() + xdem.coreg.Deramp(poly_order=2)
    coreg.fit(dem_1, dem_2, inlier_mask=~river)
    dem_2_aligned = coreg.apply(dem_2)

    dh = dem_1 - dem_2_aligned
    dh.set_mask(river)

    sig_dem, rho_sig = dem_2_aligned.estimate_uncertainty(
        dem_1,
        precision_of_other="same",
        random_state=42,
    )
    plt = load_pyplot()
    sig_values = sig_dem.data.compressed()          # valid (unmasked) values only
    vmin, vmax = np.nanpercentile(sig_values, [2, 98])
    del sig_values

    sig_dem.plot(
        cmap="Purples",
        vmin=vmin,
        vmax=vmax,
        cbar_title=r"Error in elevation (1$\sigma$, m)",
    )
    plt.savefig(
        result_path(f"uncertainty_{name_1}_{name_2}.png"),
        dpi=300,
        bbox_inches="tight",
    )
    plt.close("all")

    x = np.arange(0, 150, 1)
    plt.plot(x, [rho_sig(distance) for distance in x])
    plt.xlabel("Distance [m]")
    plt.ylabel("Error similarity [%]")

    save_raster(
        sig_dem,
        result_path(f"uncertainty_{name_1}_{name_2}.tif"),
    )

    plt.savefig(
        result_path(f"Correlation_{name_1}_{name_2}.png"),
        dpi=300,
        bbox_inches="tight",
    )
    plt.close()

    # Border consistency on the raw difference (before coregistration), river cells excluded.
    threshold = abs(dh.transform.a) / 3  # resolution / 3
    raw = (dem_1 - dem_2).data.filled(np.nan)
    raw[river] = np.nan
    exceeds = np.where(np.isfinite(raw), np.abs(raw) > threshold, MASK_NODATA_U8).astype("uint8")
    save_raster(
        exceeds,
        result_path(f"exceeds_threshold_{name_1}_{name_2}.tif"),
        dh.transform,
        dh.crs,
        MASK_NODATA_U8,
        dtype="uint8",
        resampling="NEAREST",
        tags={"meaning": f"1 = |{name_1} - {name_2}| > {threshold:g} m (resolution/3), 0 = within, "
                         f"{MASK_NODATA_U8} = no common data or river; before coregistration"},
    )
    rows = [
        {"reference_dem": name_1, "comparison_dem": name_2, "stage": "before_coregistration",
         **difference_statistics(raw, threshold)},
        {"reference_dem": name_1, "comparison_dem": name_2, "stage": "after_coregistration",
         **difference_statistics(dh.data.filled(np.nan), threshold)},
    ]
    pd.DataFrame(rows).to_csv(result_path(f"statistics_{name_1}_{name_2}.csv"), index=False)
    stats = rows[0]
    save_raster(
        dh,
        result_path(f"dh_{name_1}_{name_2}.tif"),
    )
    return {
        "coreg": coreg,
        "aligned_dem": dem_2_aligned,
        "dh": dh,
        "dem_1": dem_1,
        "name_1": name_1,
        "name_2": name_2,
        "statistics": rows,
        **stats,
    }


def local_inspire_rmse_analysis(dh, name, tile_size_m=50):
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
            "inspire_rmse_threshold_m": str(resolution / 3),
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
    strips = range(0, 1001, 50)
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


def find_border_vector(data_dir):
    preferred_path = os.path.join(data_dir, "border.gpkg")
    if os.path.isfile(preferred_path):
        return preferred_path
    candidates = sorted(
        {
            path
            for pattern in ("*.gpkg", "*.shp", "*.geojson")
            for path in glob.glob(os.path.join(data_dir, pattern))
        }
    )
    return candidates[0] if candidates else None


def load_border_vector(vector_path):
    with rasterio.Env(SHAPE_RESTORE_SHX="YES"):
        border_vector = gu.Vector(vector_path)
    border_vector.ds = border_vector.ds.set_crs(
        border_vector.crs or CRS.from_epsg(3035)
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


def top_problem_regions(dh, name, threshold=None, min_area=200, merge_distance=60):
    threshold = abs(dh.transform.a) / 3 if threshold is None else threshold  # resolution / 3
    dh_array = dh.data.filled(np.nan)
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
    print(
        f"Problem regions: {exceedance_count} cells exceed {threshold} m; "
        f"{candidate_count} initial regions merged, {len(regions.ds)} retained "
        f"above {min_area} m²."
    )
    return regions


def run_all_analyses(config_path="pipeline.json", data_dir=DATA_DIR):
    """Compare every overlapping pair of region DEMs listed in the pipeline JSON.

    DEM and river mask paths come from each region's `dem` and `river_mask`
    entries (written by the pipeline and river_mask.create_masks).
    """
    analysis_start = time.perf_counter()
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    regions = config["regions"]
    # Results go to <output_dir>/comparison next to the pipeline outputs.
    vertical_transform.RESULTS_DIR = str(config_path.parent / config["settings"].get("output_dir", "data/pipeline") / "comparison")
    resolve = lambda path: str(config_path.parent / path) if path else None  # noqa: E731
    dems = {name: (resolve(r["dem"]), resolve(r.get("river_mask"))) for name, r in regions.items() if r.get("dem")}
    if not dems:
        raise FileNotFoundError(f"No region DEMs recorded in {config_path}; run the pipeline first")
    names = list(dems)

    statistics = []
    pair_count = len(names) * (len(names) - 1) // 2
    last_dem_pair = (None, None)

    border_path = find_border_vector(data_dir)
    border_vector = load_border_vector(border_path) if border_path else None
    if border_vector is None:
        print("No border vector found, skipping border analyses", flush=True)

    print(f"Checking {pair_count} DEM combinations for overlap...", flush=True)
    for first_index, first_name in enumerate(names):
        for second_name in names[first_index + 1 :]:
            (first_path, first_mask), (second_path, second_mask) = dems[first_name], dems[second_name]
            pair_name = f"{first_name} and {second_name}"
            if not dem_files_overlap(first_path, second_path):
                print(
                    f"Skipping comparison for non-overlapping DEMs: {pair_name}",
                    flush=True,
                )
                continue

            print(
                f"Running comparison for overlapping DEMs: {pair_name}",
                flush=True,
            )
            # Pipeline DEMs already share the target CRS/VRS: load as-is.
            dem_1, dem_2 = load_file(first_path)[0], load_file(second_path)[0]
            analysis = analyze_dem(dem_1, dem_2, first_name, second_name, first_mask, second_mask)
            if analysis is None:
                continue

            dh = analysis["dh"]
            dem_1_crop = analysis["dem_1"]
            name_1 = analysis["name_1"]
            name_2 = analysis["name_2"]
            name = f"{name_1}_{name_2}"

            local_inspire_rmse_analysis(dh, name)
            std_analysis(dh, name)
            histogram_analysis(dh, name)
            cdf_analysis(dh, name)
            slope_error_analysis(dem_1_crop, dh, name)
            aspect_difference_analysis(dem_1_crop, analysis["aligned_dem"], name_1, name_2)
            top_problem_regions(dh, name)

            if border_vector is not None:
                border_strip_analysis(dh, border_vector, name)
                border_trend_plot(result_path(f"border_strips_{name}.csv"), name)

            last_dem_pair = (dem_1, dem_2)
            statistics.extend(analysis["statistics"])
            del analysis, dh, dem_1_crop

    pd.DataFrame(statistics).to_csv(
        result_path("dem_difference_statistics.csv"),
        index=False,
    )
    elapsed_seconds = time.perf_counter() - analysis_start
    hours, remainder = divmod(int(elapsed_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    print(
        f"Total analysis loop time: {hours:02d}:{minutes:02d}:{seconds:02d} "
        f"({elapsed_seconds:.1f} seconds).",
        flush=True,
    )
    return {
        "dem_paths": {name: dem for name, (dem, _) in dems.items()},
        "statistics": statistics,
        "dem_1": last_dem_pair[0],
        "dem_2": last_dem_pair[1],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare overlapping region DEMs from a pipeline JSON.")
    parser.add_argument("config", nargs="?", default="pipeline.json")
    run_all_analyses(parser.parse_args().config)
