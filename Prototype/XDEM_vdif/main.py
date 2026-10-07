import glob
import os

import geopandas as gpd
import geoutils as gu
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import shapely
import xdem
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.features import shapes
from shapely.geometry import box, shape

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
    return xdem.DEM(file_path), os.path.splitext(os.path.basename(file_path))[0]


def infer_country_name(file_name_or_path):
    text = os.path.basename(str(file_name_or_path)).upper()
    return next((country for country in source_vcrs if country.upper() in text), None)


def safe_name(obj, fallback="dem"):
    return os.path.splitext(os.path.basename(str(getattr(obj, "name", None) or fallback)))[0]


def transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs):
    if source_vcrs[country_name] == target_vcrs[country_name]:
        return dem
    return dem.to_vcrs(target_vcrs[country_name], force_source_vcrs=source_vcrs[country_name])


def save_dem(dem, country_name):
    save_raster(dem, result_path(f"{country_name}_vcrs.tif"))


def save_raster(raster, filename):
    raster.to_file(filename)


def save_vector(vector, filename):
    vector.to_file(filename)


def nanmean(values):
    return np.nanmean(values)


def nanrmse(values):
    return np.sqrt(np.nanmean(np.asarray(values) ** 2))


def analyze_dem(dem_1, dem_2):
    dem_2 = dem_2.reproject(dem_1)
    coreg = xdem.coreg.NuthKaab() + xdem.coreg.Deramp(poly_order=2)
    coreg.fit(dem_1, dem_2)
    dem_2_aligned = coreg.apply(dem_2)
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
    return {"coreg": coreg, "aligned_dem": dem_2_aligned, "dh": dh, **{key: stats[key] for key in ("mean", "median", "std", "rmse", "mae")}}


def local_inspire_rmse_analysis(dh, tile_size_m=100):
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
    values = dh.data.compressed()
    plt.figure(figsize=(8, 5))
    plt.hist(values, bins=100)
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Count")
    plt.title("DEM Difference Histogram")
    plt.savefig(result_path(f"histogram_{safe_name(dh)}.png"))
    plt.close()


def cdf_analysis(dh):
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
    difference = dem_1.aspect() - dem_2.reproject(dem_1).aspect()
    save_raster(difference, result_path(f"aspect_difference_{safe_name(dem_1)}_{safe_name(dem_2)}.tif"))
    difference.plot(cmap="RdBu")


def slope_error_analysis(dem_1, dh):
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
    preferred_name = "CNTR_BN_01M_2024_3035.shp"
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
    min_area=100,
    merge_distance=20,
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


def find_test_dem_pair(data_dir=None):
    data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
    files = sorted({
        path
        for pattern in ("*.tif", "*.tiff", "*.TIF", "*.TIFF")
        for path in glob.glob(os.path.join(data_dir, pattern))
        if not os.path.splitext(os.path.basename(path))[0].lower().endswith("_dep")
    })
    country_files = [(path, infer_country_name(path)) for path in files]
    pairs = [(a, b) for i, (a, ca) in enumerate(country_files)
             for b, cb in country_files[i + 1:] if ca and cb and ca != cb]
    if not pairs:
        raise FileNotFoundError(f"Need full-region DEMs for two recognized countries in {data_dir}.")
    return min(pairs, key=lambda pair: sum(os.path.getsize(path) for path in pair))


def run_all_analyses(data_dir=None):
    dem_paths = find_test_dem_pair(data_dir)
    dem_1, name_1 = load_file(dem_paths[0])
    dem_2, name_2 = load_file(dem_paths[1])
    country_1, country_2 = infer_country_name(name_1), infer_country_name(name_2)
    dem_1 = transform_dem_to_target_vcrs(dem_1, country_1, source_vcrs, target_vcrs)
    dem_2 = transform_dem_to_target_vcrs(dem_2, country_2, source_vcrs, target_vcrs)
    save_dem(dem_1, country_1)
    save_dem(dem_2, country_2)
    print(f"Running analysis on: {country_1} and {country_2}")
    analysis = analyze_dem(dem_1, dem_2)
    dh = analysis["dh"]
    std_analysis(dh), histogram_analysis(dh), cdf_analysis(dh)
    aspect_difference_analysis(dem_1, dem_2)
    slope_error_analysis(dem_1, dh)
    local_rmse = local_inspire_rmse_analysis(dh)
    regions = top_problem_regions(dh)
    border_vector_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
    border_path = find_border_vector(border_vector_dir)
    print(f"Using border vector: {os.path.basename(border_path)}")
    border_strip_analysis(dh, load_border_vector(border_path))
    border_trend_plot(result_path(f"border_strips_{safe_name(dh)}.csv"))
    return {"dem_1": dem_1, "dem_2": dem_2, "analysis": analysis, "local_rmse": local_rmse, "regions": regions}


if __name__ == "__main__":
    run_all_analyses()