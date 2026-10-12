import glob
import os
import sys
import time
from typing import Optional

if __name__ == "__main__":
    print("Starting up; loading geospatial and scientific libraries...", flush=True)

# print("load geopandas", flush=True)
import geopandas as gpd
# print("load geoutils", flush=True)
import geoutils as gu
# print("load numpy", flush=True)
import numpy as np
# print("load pandas", flush=True)
import pandas as pd
# print("load rasterio", flush=True)
import rasterio
# print("load shapely", flush=True)
import shapely
# print("load affine", flush=True)
from affine import Affine
# print("load pyproj", flush=True)
from pyproj import CRS, Transformer
# print("load rasterio.features", flush=True)
from rasterio.features import shapes
# print("load shapely.geometry", flush=True)
from shapely.geometry import box, shape

SHOW_ALL_RIVER_FEATURES = False
RUN_SIGMA_SWEEP = True
SIGMA_SWEEP_MAX = 7
GAUSSIAN_SIGMA = 1


def update_progress(label, completed, total):
    if total == 0:
        return
    update_interval = max(1, total // 100)
    if completed != total and completed % update_interval:
        return

    width = 24
    filled = width * completed // total
    bar = "#" * filled + "-" * (width - filled)
    percentage = 100 * completed // total
    sys.stdout.write(
        f"\r{label:<18} [{bar}] {completed:>7}/{total:<7} "
        f"{percentage:3d}%"
    )
    if completed == total:
        sys.stdout.write("\n")
    sys.stdout.flush()


def load_xdem():
    # print("Loading xdem (DEM support)...", flush=True)
    import xdem

    # print("xdem loaded.", flush=True)
    return xdem


def load_pyplot():
    # print("Loading Matplotlib for plotting...", flush=True)
    import matplotlib.pyplot as pyplot

    # print("Matplotlib ready.", flush=True)
    return pyplot


source_vcrs = {
    "NRW": CRS.from_epsg(7837),
    "NiSa": CRS.from_epsg(7837),
    "RhPf": CRS.from_epsg(7837),
    "Saar": CRS.from_epsg(7837),
    "BaWu": CRS.from_epsg(7837),
    "Hessen": CRS.from_epsg(7837),
    "Bay": CRS.from_epsg(7837),
    "France": CRS.from_epsg(5720),
    "Luxembourg": CRS.from_epsg(5774),
    "Netherlands": CRS.from_epsg(5709),
    "Switzerland": CRS.from_epsg(5728),
}

target_vcrs = {country: source_vcrs[country] for country in source_vcrs}

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def result_path(filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, filename)


def load_file(file_path):
    return load_xdem().DEM(file_path), os.path.splitext(os.path.basename(file_path))[0]


def infer_country_name(file_name_or_path):
    text = os.path.basename(str(file_name_or_path)).upper()
    return next((country for country in source_vcrs if country.upper() in text), None)


def safe_name(obj, fallback="dem"):
    name = os.path.splitext(os.path.basename(str(getattr(obj, "name", None) or fallback)))[0]
    return name.removesuffix("_vcrs")


def transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs):
    if source_vcrs[country_name] == target_vcrs[country_name]:
        return dem
    return dem.to_vcrs(target_vcrs[country_name], force_source_vcrs=source_vcrs[country_name])


def save_dem(dem, filename):
    save_raster(dem, filename)


def load_or_transform_dem(dem_path, country_name):
    if country_name is None:
        return load_file(dem_path)[0]

    file_name = os.path.splitext(os.path.basename(dem_path))[0]
    transformed_path = result_path(f"{file_name}_vcrs.tif")
    if os.path.isfile(transformed_path):
        # print(f"Using existing transformed DEM: {transformed_path}", flush=True)
        return load_xdem().DEM(transformed_path)

    # print(f"Transforming DEM: {os.path.basename(dem_path)}", flush=True)
    dem, _ = load_file(dem_path)
    dem = transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs)
    save_dem(dem, transformed_path)
    return dem


def save_raster(raster, filename, predictor=3):
    raster.to_file(
        filename,
        co_opts={
            "COMPRESS": "ZSTD",
            "ZSTD_LEVEL": "1",
            "PREDICTOR": str(predictor),
            "TILED": "YES",
            "BLOCKXSIZE": "512",
            "BLOCKYSIZE": "512",
            "NUM_THREADS": "ALL_CPUS",
        },
    )


def save_vector(vector, filename):
    vector.to_file(filename)


def nanmean(values):
    return np.nanmean(values)


def nanrmse(values):
    return np.sqrt(np.nanmean(np.asarray(values) ** 2))


def analyze_dem(dem_1, dem_2):
    dem_library = load_xdem()
    # print("Reprojecting comparison DEM...", flush=True)
    dem_2 = dem_2.reproject(dem_1)
    valid_overlap = (
        ~np.ma.getmaskarray(dem_1.data)
        & ~np.ma.getmaskarray(dem_2.data)
        & np.isfinite(dem_1.data.data)
        & np.isfinite(dem_2.data.data)
    )
    if not valid_overlap.any():
        print(
            f"Skipping comparison for {safe_name(dem_1)} and "
            f"{safe_name(dem_2)}: no shared valid elevation pixels.",
            flush=True,
        )
        return None

    coreg = dem_library.coreg.NuthKaab() + dem_library.coreg.Deramp(poly_order=2)

    # print("Estimating DEM uncertainty...", flush=True)
    coreg_2 = dem_2.coregister_3d(
        dem_1, dem_library.coreg.NuthKaab() + dem_library.coreg.VerticalShift(), resample=True
    )
    sig_dem, rho_sig = coreg_2.estimate_uncertainty(dem_1, precision_of_other="same", random_state=42)
    plt = load_pyplot()
    sig_dem.plot(cmap="Purples", cbar_title=r"Error in elevation (1$\sigma$, m)")

    plot_path = result_path(f"uncertainty_{safe_name(dem_1)}_{safe_name(dem_2)}.png")
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close()

    # print("Evaluating and saving spatial correlation...", flush=True)
    x = np.arange(0, 200, 1)
    plt.plot(x, [rho_sig(distance) for distance in x])

    save_raster(sig_dem, result_path(f"uncertainty_{safe_name(dem_1)}_{safe_name(dem_2)}.tif"))

    plot_path = result_path(f"Correlation_{safe_name(dem_1)}_{safe_name(dem_2)}.png")
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close()

    # print("Fitting DEM coregistration...", flush=True)
    coreg.fit(dem_1, dem_2)
    dem_2_aligned = coreg.apply(dem_2)
    # print("Calculating elevation differences and summary statistics...", flush=True)
    dh = dem_1 - dem_2_aligned
    values = dh.data.filled(np.nan)
    valid_values = values[np.isfinite(values)]
    rmse = np.sqrt(np.mean(valid_values**2))
    stats = {
        "reference_dem": safe_name(dem_1),
        "comparison_dem": safe_name(dem_2),
        "mean": np.mean(valid_values),
        "median": np.median(valid_values),
        "std": np.std(valid_values),
        "rmse": rmse,
        "mae": np.mean(np.abs(valid_values)),
        "min": np.min(valid_values),
        "max": np.max(valid_values),
        "INSPIRE_target%": rmse / (5 / 3) * 100,
    }
    pd.DataFrame([stats]).to_csv(result_path("dem_difference_statistics.csv"), index=False)
    save_raster(dh, result_path(f"dh_{safe_name(dem_1)}_{safe_name(dem_2)}.tif"))
    return {"sig_dem":sig_dem,"coreg": coreg, "aligned_dem": dem_2_aligned, "dh": dh, **stats}


def local_inspire_rmse_analysis(dh, tile_size_m=50):
    data = dh.data.filled(np.nan)
    crs = CRS.from_user_input(dh.crs)
    unit_to_meters = crs.axis_info[0].unit_conversion_factor
    pixel_x, pixel_y = abs(dh.transform.a) * unit_to_meters, abs(dh.transform.e) * unit_to_meters
    resolution = np.sqrt(pixel_x * pixel_y)
    tile_rows, tile_cols = (max(1, round(tile_size_m / pixel_y)), max(1, round(tile_size_m / pixel_x)))
    rmse_raster = np.full(data.shape, np.nan, dtype=np.float32)

    for row in range(0, dh.height, tile_rows):
        for col in range(0, dh.width, tile_cols):
            row_end, col_end = min(row + tile_rows, dh.height), min(col + tile_cols, dh.width)
            tile = data[row:row_end, col:col_end]
            valid = np.isfinite(tile)
            values = tile[valid]
            if not values.size:
                continue
            rmse_raster[row:row_end, col:col_end][valid] = np.sqrt(np.mean(values**2))

    name = safe_name(dh)
    output_path = result_path(f"local_inspire_rmse_{name}.tif")
    rmse_dem = dh.copy(new_array=rmse_raster)
    save_raster(rmse_dem, output_path)
    with rasterio.open(output_path, "r+") as output:
        output.update_tags(
            metric="Local RMSE of elevation differences",
            tile_size_m=str(tile_size_m),
            pixel_resolution_m=str(resolution),
            inspire_rmse_threshold_m=str(resolution / 3),
            pass_condition="RMSE <= inspire_rmse_threshold_m",
        )
    return rmse_dem


def std_analysis(dh):
    save_raster(dh - nanmean(dh.data.filled(np.nan)), result_path(f"dh_std_{safe_name(dh)}.tif"))


def histogram_analysis(dh):
    plt = load_pyplot()
    values = dh.data.compressed()
    plt.figure(figsize=(8, 5))
    plt.hist(values, bins=1000)
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Count")
    plt.title("DEM Difference Histogram")
    plt.savefig(result_path(f"histogram_{safe_name(dh)}.png"))
    plt.close()


def cdf_analysis(dh):
    plt = load_pyplot()
    values = np.sort(dh.data.compressed())
    plt.figure(figsize=(8, 5))
    plt.plot(values, np.arange(len(values)) / len(values))
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Cumulative probability")
    plt.title("DEM Difference CDF")
    plt.grid()
    plt.savefig(result_path(f"cdf_{safe_name(dh)}.png"))
    plt.close()

def aspect_difference_analysis(dem_1, dem_2):
    load_pyplot()
    difference = dem_1.aspect() - dem_2.reproject(dem_1).aspect()
    save_raster(difference, result_path(f"aspect_difference_{safe_name(dem_1)}_{safe_name(dem_2)}.tif"))
    difference.plot(cmap="RdBu")


def slope_error_analysis(dem_1, dh):
    plt = load_pyplot()
    slopes, differences = dem_1.slope().data.filled(np.nan), dh.data.filled(np.nan)
    bins = np.arange(0, 55, 5)
    rmses = [nanrmse(differences[(slopes >= lo) & (slopes < hi)]) for lo, hi in zip(bins[:-1], bins[1:])]
    plt.figure(figsize=(8, 5))
    plt.plot(bins[:-1], rmses, marker="o")
    plt.xlabel("Slope (deg)")
    plt.ylabel("RMSE (m)")
    plt.title("RMSE versus Slope")
    plt.savefig(result_path(f"slope_rmse_{safe_name(dh)}.png"))
    plt.close()

def border_strip_analysis(dh, border_vector):
    strips = [0, 50, 100, 250, 500, 1000]
    z = dh.data.filled(np.nan)
    unit_to_meters = border_vector.crs.axis_info[0].unit_conversion_factor
    max_distance = strips[-1] / unit_to_meters
    bounds = Transformer.from_crs(dh.crs, border_vector.crs, always_xy=True).transform_bounds(*dh.bounds, densify_pts=21)
    search_area = box(bounds[0] - max_distance, bounds[1] - max_distance, bounds[2] + max_distance, bounds[3] + max_distance)
    nearby = border_vector.ds.loc[border_vector.ds.geometry.intersects(search_area)].copy()
    nearby.geometry = nearby.geometry.intersection(search_area)
    nearby = nearby.loc[~nearby.geometry.is_empty]
    local_borders = gu.Vector(nearby).reproject(crs=dh.crs)
    pad_columns = int(np.ceil(strips[-1] / abs(dh.transform.a)))
    pad_rows = int(np.ceil(strips[-1] / abs(dh.transform.e)))
    proximity_grid = gu.Raster.from_array(
        np.zeros((dh.height + 2 * pad_rows, dh.width + 2 * pad_columns), dtype=np.uint8),
        transform=dh.transform * Affine.translation(-pad_columns, -pad_rows),
        crs=dh.crs,
    )
    distances = proximity_grid.proximity(local_borders, geometry_type="geometry").crop(dh).data.filled(np.nan)
    rows = [[lo, hi, nanmean(z[(distances >= lo) & (distances < hi) & np.isfinite(z)]),
             nanrmse(z[(distances >= lo) & (distances < hi) & np.isfinite(z)])]
            for lo, hi in zip(strips[:-1], strips[1:])]
    df = pd.DataFrame(rows, columns=["min_dist", "max_dist", "mean", "rmse"])
    df.to_csv(result_path(f"border_strips_{safe_name(dh)}.csv"), index=False)
    return df


def find_border_vector(data_dir):
    preferred_name = "border.gpkg"
    preferred_path = os.path.join(data_dir, preferred_name)
    if os.path.isfile(preferred_path):
        return preferred_path
    candidates = sorted({path for pattern in ("*.gpkg", "*.shp", "*.geojson", "*.json")
                         for path in glob.glob(os.path.join(data_dir, pattern))})
    return candidates[0] if candidates else None


def load_border_vector(vector_path):
    with rasterio.Env(SHAPE_RESTORE_SHX="YES"):
        border_vector = gu.Vector(vector_path)
    border_vector.ds = border_vector.ds.set_crs(border_vector.crs or CRS.from_epsg(3035))
    return border_vector


def border_trend_plot(csv_file):
    plt = load_pyplot()
    df = pd.read_csv(csv_file)
    plt.figure(figsize=(8, 5))
    plt.plot(df["max_dist"], df["rmse"], marker="o")
    plt.xlabel("Distance from border (m)")
    plt.ylabel("RMSE (m)")
    plt.title("Border Effect")

    plt.grid()

    plt.savefig(result_path("border_effect.png"), dpi=300)
    plt.close()


def top_problem_regions(
    dh,
    threshold=0.5,
    min_area=200,
    merge_distance=60,
):
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
        area_m2 = sum(shapely.area(geometries[index]) for index in members) * unit_to_meters**2
        if area_m2 >= min_area:
            merged_records.append({"area_m2": area_m2, "geometry": merged_geometry})

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
    save_vector(regions, result_path("problem_regions.gpkg"))
    print(f"Problem regions: {exceedance_count} cells exceed {threshold} m; {candidate_count} initial regions merged, {len(regions.ds)} retained above {min_area} m².")
    return regions


def find_dem_files(data_dir=None):
    data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
    files = sorted({
        path
        for pattern in ("*.tif", "*.tiff", "*.TIF", "*.TIFF")
        for path in glob.glob(os.path.join(data_dir, pattern))
        if not os.path.splitext(os.path.basename(path))[0].lower().endswith("_dep")
    })
    if not files:
        raise FileNotFoundError(f"No DEM files found in {data_dir}.")
    return files


def dem_files_overlap(path_1, path_2):
    with rasterio.open(path_1) as dem_1, rasterio.open(path_2) as dem_2:
        bounds_1 = dem_1.bounds
        bounds_2 = dem_2.bounds
        if CRS.from_user_input(dem_1.crs) != CRS.from_user_input(dem_2.crs):
            bounds_2 = Transformer.from_crs(
                dem_2.crs, dem_1.crs, always_xy=True
            ).transform_bounds(*bounds_2, densify_pts=21)

    return (
        max(bounds_1[0], bounds_2[0]) < min(bounds_1[2], bounds_2[2])
        and max(bounds_1[1], bounds_2[1]) < min(bounds_1[3], bounds_2[3])
    )

def river_mask_creation(dem, show_all_features=SHOW_ALL_RIVER_FEATURES):
    print("importing gaussian filter")
    from scipy.ndimage import gaussian_filter

    data = np.asarray(dem.data.filled(0))
    sigmas = (
        range(1, SIGMA_SWEEP_MAX + 1)
        if RUN_SIGMA_SWEEP
        else (GAUSSIAN_SIGMA,)
    )
    sigma_results = []
    variance = None
    score_variance = None
    for sigma in sigmas:
        print(f"Calculating local variance with Gaussian sigma={sigma}...", flush=True)
        filtered = gaussian_filter(data, sigma=sigma)
        mean2 = gaussian_filter(data**2, sigma=sigma)
        variance = mean2 - filtered**2
        if score_variance is None:
            score_variance = variance

        features = river_polygons(
            variance,
            dem,
            show_all_features=show_all_features,
            save_output=not RUN_SIGMA_SWEEP,
        )
        if RUN_SIGMA_SWEEP:
            detected_count = int(
                features.ds["class"].isin(
                    ["large river", "river", "lake"]
                ).sum()
            )
            print(
                f"Sigma {sigma}: {detected_count} classified features.",
                flush=True,
            )
            if detected_count == 0:
                print("No classified features remain; ending sigma sweep.", flush=True)
                break
            iteration_features = features.ds.copy()
            iteration_features["sigma"] = sigma
            sigma_results.append(iteration_features)

    if score_variance is None:
        raise ValueError("Sigma sweep did not run; check SIGMA_SWEEP_MAX.")

    if RUN_SIGMA_SWEEP and len(sigma_results) == SIGMA_SWEEP_MAX:
        print(
            f"Sigma sweep reached its maximum sigma ({SIGMA_SWEEP_MAX}) "
            "while classified features remained.",
            flush=True,
        )

    score = score_variance
    score = gu.Raster.from_array(
        score,
        transform=dem.transform,
        crs=dem.crs,
        nodata=dem.nodata,
        area_or_point=dem.area_or_point,
    )

    score_sigma = 1 if RUN_SIGMA_SWEEP else GAUSSIAN_SIGMA
    print(f"saving sigma={score_sigma} score data --> {dem.name}")

    save_raster(score, result_path(f"{safe_name(dem)}_score.tif"))
    print("data exported")

    if RUN_SIGMA_SWEEP:
        water_features = merge_sigma_features(sigma_results, dem.crs)
        water_features.to_file(
            result_path(f"{safe_name(dem)}_river_mask.gpkg")
        )
        print(
            f"Saved {len(water_features.ds)} merged features from "
            f"{len(sigma_results)} sigma iterations.",
            flush=True,
        )
    else:
        water_features = features

    from rasterio.features import rasterize

    class_values = np.select(
        [
            water_features.ds["class"] == "lake",
            water_features.ds["class"] == "unclassified",
        ],
        [2, 3],
        default=1,
    )
    water_mask = rasterize(
        zip(water_features.ds.geometry, class_values),
        out_shape=data.shape,
        transform=dem.transform,
        fill=0,
        dtype=np.uint8,
    )
    water_mask_raster = gu.Raster.from_array(
        water_mask,
        transform=dem.transform,
        crs=dem.crs,
        nodata=255,
        area_or_point=dem.area_or_point,
    )
    water_mask_path = result_path(f"{safe_name(dem)}_water_mask.tif")
    save_raster(water_mask_raster, water_mask_path, predictor=2)
    raster_contents = (
        "river=1, lake=2, unclassified=3"
        if show_all_features
        else "river=1, lake=2"
    )
    print(f"Saved class raster ({raster_contents}) to {water_mask_path}")
    return


def merge_sigma_features(iteration_features, crs):
    if not iteration_features:
        return gu.Vector(
            gpd.GeoDataFrame(
                columns=[
                    "class",
                    "class_sigma",
                    "sigma_values",
                    "source_feature_count",
                    "area_m2",
                    "geometry",
                ],
                geometry="geometry",
                crs=crs,
            )
        )

    sources = gpd.GeoDataFrame(
        pd.concat(iteration_features, ignore_index=True),
        geometry="geometry",
        crs=crs,
    )
    merged = shapely.ops.unary_union(sources.geometry.tolist())
    geometries = (
        list(merged.geoms)
        if merged.geom_type == "MultiPolygon"
        else [merged]
    )
    spatial_index = sources.sindex
    records = []

    for geometry in geometries:
        if geometry.geom_type != "Polygon":
            continue
        indices = spatial_index.query(geometry, predicate="intersects")
        contributors = sources.iloc[indices]
        latest_contributor = contributors.loc[contributors["sigma"].idxmax()]
        records.append(
            {
                "class": latest_contributor["class"],
                "class_sigma": int(latest_contributor["sigma"]),
                "sigma_values": ", ".join(
                    str(int(sigma)) for sigma in sorted(contributors["sigma"].unique())
                ),
                "source_feature_count": len(contributors),
                "area_m2": geometry.area,
                "geometry": geometry,
            }
        )

    return gu.Vector(
        gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
    )


def river_polygons(
    variance,
    dem,
    variance_threshold=0.13,
    min_area=1000,
    river_max_compactness=0.38,
    river_std_threshold=0.04,
    river_max_width=500,
    large_river_min_area=1000000,
    large_river_std_threshold=0.025,
    large_river_max_width_m=500,
    large_river_compactness=0.1,
    lake_min_area=30000,
    lake_std_threshold=0.026,
    lake_max_width_m=800,
    lake_compactness=0.15,
    buffer_cells=20,
    min_buffer_height_difference: Optional[float] = 1.2,
    min_buffer_height_river = 1,
    show_all_features=False,
    save_output=True,
):
    if buffer_cells < 0:
        raise ValueError("buffer_cells must be non-negative.")
    if (
        min_buffer_height_difference is not None
        and not np.isfinite(min_buffer_height_difference)
    ):
        raise ValueError("min_buffer_height_difference must be finite or None.")

    elevations = dem.data.filled(np.nan)
    mask = (
        (variance <= variance_threshold)
        & np.isfinite(elevations)
    ).astype(np.uint8)
    polygons = gu.Raster.from_array(
        mask,
        transform=dem.transform,
        crs=dem.crs,
    ).polygonize(target_values=1)
    polygons.ds["area_m2"] = polygons.ds.geometry.area

    from concurrent.futures import ThreadPoolExecutor
    from scipy.ndimage import distance_transform_edt
    from rasterio.features import geometry_mask
    from rasterio.windows import from_bounds

    dem_crs = CRS.from_user_input(dem.crs)
    if dem_crs.is_geographic:
        raise ValueError("Polygon width in metres requires a projected DEM CRS.")
    meters_per_unit = dem_crs.axis_info[0].unit_conversion_factor
    pixel_size_m = (
        abs(dem.transform.e) * meters_per_unit,
        abs(dem.transform.a) * meters_per_unit,
    )
    buffer_distance = buffer_cells * max(pixel_size_m) / meters_per_unit
    variance_values = np.ma.asarray(variance).filled(np.nan)
    regional_mean = np.nanmean(elevations)
    geometries = list(polygons.ds.geometry)
    raster_height, raster_width = elevations.shape

    print(
        f"Calculating terrain metrics for {len(geometries)} polygon components...",
        flush=True,
    )

    def geometry_window(geom):
        bounds = from_bounds(*geom.bounds, transform=dem.transform)
        col_start = max(0, int(np.floor(bounds.col_off)))
        row_start = max(0, int(np.floor(bounds.row_off)))
        col_stop = min(raster_width, int(np.ceil(bounds.col_off + bounds.width)))
        row_stop = min(raster_height, int(np.ceil(bounds.row_off + bounds.height)))
        rows = slice(row_start, row_stop)
        cols = slice(col_start, col_stop)
        transform = dem.transform * Affine.translation(col_start, row_start)
        return rows, cols, transform

    def calculate_polygon_metrics(geom):
        rows, cols, transform = geometry_window(geom)
        local_elevations = elevations[rows, cols]
        polygon_mask = geometry_mask(
            [geom],
            out_shape=local_elevations.shape,
            transform=transform,
            invert=True,
        )
        local_variance = variance_values[rows, cols]
        inside_elevations = local_elevations[polygon_mask]
        inside_variance = local_variance[polygon_mask]
        valid_inside_elevations = inside_elevations[np.isfinite(inside_elevations)]
        mean_elevation = (
            float(np.mean(valid_inside_elevations))
            if valid_inside_elevations.size
            else np.nan
        )
        variance_std = np.nanstd(inside_variance)
        polygon_width = 2 * distance_transform_edt(
            np.pad(polygon_mask, 1, constant_values=False),
            sampling=pixel_size_m,
        ).max()
        compactness = (
            4 * np.pi * geom.area / geom.length**2
            if geom.length > 0
            else 0
        )
        return variance_std, mean_elevation, polygon_width, compactness

    max_workers = max(1, min(16, os.cpu_count() or 1, len(geometries)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        metrics = []
        for completed, metric in enumerate(
            executor.map(calculate_polygon_metrics, geometries), start=1
        ):
            metrics.append(metric)
            update_progress("Polygon metrics", completed, len(geometries))

    polygons.ds["elev_std"] = [metric[0] for metric in metrics]
    polygons.ds["mean_elevation"] = [metric[1] for metric in metrics]
    polygons.ds["max_width_m"] = [metric[2] for metric in metrics]
    polygons.ds["compactness"] = [metric[3] for metric in metrics]
    area = polygons.ds.area_m2

    below_regional_mean = polygons.ds.mean_elevation < regional_mean
    lake_candidate = (
        (area >= lake_min_area)
        & below_regional_mean
        & (polygons.ds.elev_std <= lake_std_threshold)
        & (polygons.ds.max_width_m <= lake_max_width_m)
        & (polygons.ds.compactness >= lake_compactness)
    )
    large_river_candidate = (
        (area >= large_river_min_area)
        & below_regional_mean
        & (polygons.ds.elev_std <= large_river_std_threshold)
        & (polygons.ds.max_width_m <= large_river_max_width_m)
        & (polygons.ds.compactness < large_river_compactness)
        & ~lake_candidate
    )
    river_candidate = (
        (area >= min_area)
        & (area < large_river_min_area)
        & below_regional_mean
        & (polygons.ds.elev_std < river_std_threshold)
        & (polygons.ds.max_width_m <= river_max_width)
        & (polygons.ds.compactness <= river_max_compactness)
        & ~lake_candidate
        & ~large_river_candidate
    )

    buffer_candidates = lake_candidate | large_river_candidate | river_candidate
    candidate_indices = np.flatnonzero(buffer_candidates.to_numpy())
    buffer_mean_elevations = np.full(len(polygons.ds), np.nan)
    buffer_height_differences = np.full(len(polygons.ds), np.nan)

    def calculate_buffer_metrics(index):
        geom = geometries[index]
        buffered_geom = geom.buffer(buffer_distance)
        rows, cols, transform = geometry_window(buffered_geom)
        local_elevations = elevations[rows, cols]
        polygon_mask = geometry_mask(
            [geom],
            out_shape=local_elevations.shape,
            transform=transform,
            invert=True,
        )
        buffer_mask = geometry_mask(
            [buffered_geom],
            out_shape=local_elevations.shape,
            transform=transform,
            invert=True,
        ) & ~polygon_mask
        inside = local_elevations[polygon_mask]
        surrounding = local_elevations[buffer_mask]
        inside = inside[np.isfinite(inside)]
        surrounding = surrounding[np.isfinite(surrounding)]
        if not inside.size or not surrounding.size:
            return index, np.nan, np.nan
        feature_mean = float(np.mean(inside))
        buffer_mean = float(np.mean(surrounding))
        return index, buffer_mean, buffer_mean - feature_mean

    polygons.ds["buffer_mean_elevation"] = buffer_mean_elevations
    polygons.ds["buffer_height_difference"] = buffer_height_differences
    if candidate_indices.size:
        print(
            f"Calculating {buffer_cells}-cell elevation buffers for "
            f"{candidate_indices.size} preliminary water candidates...",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for completed, (index, buffer_mean, height_difference) in enumerate(
                executor.map(calculate_buffer_metrics, candidate_indices), start=1
            ):
                buffer_mean_elevations[index] = buffer_mean
                buffer_height_differences[index] = height_difference
                update_progress(
                    "Buffer metrics", completed, candidate_indices.size
                )
        polygons.ds["buffer_mean_elevation"] = buffer_mean_elevations
        polygons.ds["buffer_height_difference"] = buffer_height_differences
        print("Finished calculating candidate buffer elevations.", flush=True)

    delta = polygons.ds.buffer_height_difference

    lake_buffer_ok = (
        True
        if min_buffer_height_difference is None
        else delta >= min_buffer_height_difference
    )
    river_buffer_ok = (
        True
        if min_buffer_height_river is None
        else delta >= min_buffer_height_river
    )

    buffer_filter = (
        (lake_candidate & lake_buffer_ok)
        | (large_river_candidate & river_buffer_ok)
        | (river_candidate & river_buffer_ok)
    )

    lake_candidate &= buffer_filter
    large_river_candidate &= buffer_filter
    river_candidate &= buffer_filter

    polygons.ds["is_river_candidate"] = river_candidate
    polygons.ds["is_large_river_candidate"] = large_river_candidate
    polygons.ds["is_lake_candidate"] = lake_candidate
    polygons.ds["class"] = np.select(
        [large_river_candidate, river_candidate, lake_candidate],
        ["large river", "river", "lake"],
        default="unclassified",
    )

    classified_features = polygons.ds["class"].isin(
        ["large river", "river", "lake"]
    )
    removed_count = int((~classified_features).sum())
    if not show_all_features:
        polygons.ds = polygons.ds.loc[classified_features].reset_index(drop=True)
    class_counts = polygons.ds["class"].value_counts().to_dict()
    output_status = "Saved" if save_output else "Prepared"
    if show_all_features:
        print(
            f"{output_status} all {len(polygons.ds)} polygon features "
            f"({removed_count} unclassified); classification counts: {class_counts}"
        )
    else:
        print(
            f"{output_status} {len(polygons.ds)} river/lake features "
            f"({removed_count} unclassified features filtered out); "
            f"classification counts: {class_counts}"
        )

    if save_output:
        polygons.to_file(
            result_path(f"{safe_name(dem)}_river_mask.gpkg")
        )
    return polygons

def run_all_analyses(data_dir=None):
    analysis_start = time.perf_counter()
    print("Loading files...", flush=True)
    dem_paths = find_dem_files(data_dir)

    for dem_path in dem_paths:
        country = infer_country_name(dem_path)
        dem = load_or_transform_dem(dem_path, country)
        print(f"Creating river mask for {os.path.basename(dem_path)}...", flush=True)
        river_mask_creation(dem, show_all_features=SHOW_ALL_RIVER_FEATURES)
        print()

    statistics = []
    pair_count = len(dem_paths) * (len(dem_paths) - 1) // 2
    last_dem_pair = (None, None)
    print(f"Checking {pair_count} DEM combinations for overlap...", flush=True)
    for first_index, first_path in enumerate(dem_paths):
        for second_path in dem_paths[first_index + 1:]:
            pair_name = f"{os.path.basename(first_path)} and {os.path.basename(second_path)}"

            if not dem_files_overlap(first_path, second_path):
                print(f"Skipping comparison for non-overlapping DEMs: {pair_name}", flush=True)
                continue

            print(f"Running comparison for overlapping DEMs: {pair_name}", flush=True)
            dem_1 = load_or_transform_dem(first_path, infer_country_name(first_path))
            dem_2 = load_or_transform_dem(second_path, infer_country_name(second_path))
            analysis = analyze_dem(dem_1, dem_2)
            if analysis is None:
                continue
            last_dem_pair = (dem_1, dem_2)
            statistics.append(
                {
                    "reference_dem": safe_name(dem_1),
                    "comparison_dem": safe_name(dem_2),
                    **{
                        key: analysis[key]
                        for key in (
                            "mean", "median", "std", "rmse", "mae",
                            "min", "max", "INSPIRE_target%",
                        )
                    },
                }
            )

    statistics_columns = [
        "reference_dem", "comparison_dem", "mean", "median", "std",
        "rmse", "mae", "min", "max", "INSPIRE_target%",
    ]
    pd.DataFrame(statistics, columns=statistics_columns).to_csv(
        result_path("dem_difference_statistics.csv"), index=False
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
        "dem_paths": dem_paths,
        "statistics": statistics,
        "dem_1": last_dem_pair[0],
        "dem_2": last_dem_pair[1],
    }


if __name__ == "__main__":
    print("Imports complete; starting analyses.", flush=True)
    run_all_analyses()