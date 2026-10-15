import os
import glob
import time

import geopandas as gpd
import geoutils as gu
import numpy as np
import pandas as pd
import rasterio
import shapely
import xdem
from affine import Affine
from numba import njit, types
from numba.typed import List
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.features import geometry_window, shapes
from rasterio.warp import reproject, transform_bounds
from scipy import ndimage
from shapely.geometry import box, shape
import tempfile
from rasterio.shutil import copy as rio_copy

rasterio.Env(GDAL_CACHEMAX=512)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
REGION_GROWING_DIF_TOLERANCE = 0.02
SEED_DIF_THRESHOLD = 9999
MASK_BUFFER_PIXELS = 0
MASK_NODATA = 255
CLASS_MASK_SUFFIX = "_classes_2018.tif"

COUNTRY_ALIASES = {
    "germany": ("germany", "nrw", "rhpf", "nisa", "bayern", "baden"),
    "france": ("france",),
    "netherlands": ("netherlands",),
    "switzerland": ("switzerland",),
    "liechtenstein": ("liechtenstein",),
}

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


def result_path(filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, filename)


def load_xdem():
    return xdem


def load_pyplot():
    import matplotlib.pyplot as pyplot

    return pyplot


def infer_vcrs_country(file_name_or_path):
    text = os.path.basename(str(file_name_or_path)).upper()
    return next(
        (country for country in source_vcrs if country.upper() in text),
        None,
    )

def name_from_path(path):
    return os.path.splitext(os.path.basename(path))[0].removesuffix("_vcrs")

def safe_name(obj, fallback="dem"):
    name = os.path.splitext(
        os.path.basename(str(getattr(obj, "name", None) or fallback))
    )[0]
    return name.removesuffix("_vcrs")


def transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs):
    if source_vcrs[country_name] == target_vcrs[country_name]:
        return dem
    return dem.to_vcrs(
        target_vcrs[country_name],
        force_source_vcrs=source_vcrs[country_name],
    )


def load_or_transform_dem(dem_path, country_name):
    if country_name is None:
        return load_file(dem_path)[0]

    file_name = os.path.splitext(os.path.basename(dem_path))[0]
    transformed_path = result_path(f"{file_name}_vcrs.tif")
    if os.path.isfile(transformed_path):
        with rasterio.open(dem_path) as src, rasterio.open(transformed_path) as cached:
            same_grid = (
                src.shape == cached.shape
                and src.transform == cached.transform
                and os.path.getmtime(transformed_path) >= os.path.getmtime(dem_path)
            )
        if same_grid:
            return load_xdem().DEM(transformed_path)

    dem, _ = load_file(dem_path)
    dem = transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs)
    save_raster(dem, transformed_path)
    return dem


def find_dem_files(directory=DATA_DIR):
    return sorted(
        os.path.join(directory, filename)
        for filename in os.listdir(directory)
        if filename.lower().endswith((".tif", ".tiff"))
        and not filename.lower().endswith(CLASS_MASK_SUFFIX)
        and not os.path.splitext(filename)[0].lower().endswith("_dep")
    )


def find_comparison_dem_files(directory=DATA_DIR):
    return find_dem_files(directory)


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


def find_country_class_mask(country, directory=DATA_DIR):
    expected = f"{country}{CLASS_MASK_SUFFIX}".lower()
    for filename in os.listdir(directory):
        if filename.lower() == expected:
            return os.path.join(directory, filename)
    raise FileNotFoundError(
        f"No class mask named {country}{CLASS_MASK_SUFFIX} found in {directory}"
    )


def infer_country_name(dem_path):
    filename = os.path.basename(dem_path).lower()
    for country, aliases in COUNTRY_ALIASES.items():
        if any(alias in filename for alias in aliases):
            return country.title() if country != "netherlands" else "Netherlands"
    raise ValueError(f"Could not determine the country from DEM filename: {dem_path}")


def load_file(filename):
    dem = xdem.DEM(filename)
    return dem, os.path.splitext(os.path.basename(filename))[0]


def save_raster(array, filename, transform=None, crs=None, nodata=None, dtype=None,
                resampling="AVERAGE", tags = None):
    if transform is None:
        array.to_file(filename, driver="COG")
        return

    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

    if dtype is None:
        dtype = array.dtype
    is_float = np.issubdtype(np.dtype(dtype), np.floating)

    profile = {
        "driver": "GTiff",
        "height": array.shape[0],
        "width": array.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }

    with tempfile.TemporaryDirectory(dir=os.path.dirname(filename) or ".") as tmpdir:
        tmp_path = os.path.join(tmpdir, "tmp.tif")
        with rasterio.open(tmp_path, "w", **profile) as tmp:
            tmp.write(array.astype(dtype, copy=False), 1)
            if tags:
                tmp.update_tags(**tags)
        with rasterio.Env(GDAL_CACHEMAX=512):
            rio_copy(
                tmp_path,
                filename,
                driver="COG",
                compress="ZSTD",
                level=1,
                predictor=3 if is_float else 2,
                blocksize=512,
                overviews="AUTO",
                resampling=resampling,
                num_threads="ALL_CPUS",
                bigtiff="IF_SAFER",
            )

def save_vector(vector, filename):
    vector.to_file(filename)


def nanmean(values):
    return np.nanmean(values)


def nanrmse(values):
    return np.sqrt(np.nanmean(np.asarray(values) ** 2))


def analyze_dem(dem_1, dem_2, path_1=None, path_2=None,river_buffer=1):
    name_1 = name_from_path(path_1) if path_1 else safe_name(dem_1)
    name_2 = name_from_path(path_2) if path_2 else safe_name(dem_2)
    dem_library = load_xdem()
    bounds = transform_bounds(dem_2.crs, dem_1.crs, *dem_2.bounds, densify_pts=21)
    try:
        dem_1 = dem_1.crop(bounds)
    except rasterio.errors.WindowError:
        print(f"No overlap between {name_1} and {name_2} after loading, skipping", flush=True)
        return None
    dem_2 = dem_2.reproject(dem_1)

    river = np.zeros(dem_1.shape, dtype=bool)
    if path_1: river |= river_mask_on_grid(path_1, dem_1, river_buffer)
    if path_2: river |= river_mask_on_grid(path_2, dem_1, river_buffer)
    print(f"Excluding {np.count_nonzero(river):,} river cells", flush=True)

    valid_overlap = (
        ~np.ma.getmaskarray(dem_1.data)
        & ~np.ma.getmaskarray(dem_2.data)
        & np.isfinite(dem_1.data.data)
        & np.isfinite(dem_2.data.data)
    )
    if not valid_overlap.any():
        del valid_overlap
        print(
            f"Skipping comparison for {name_1} and "
            f"{name_2}: no shared valid elevation pixels.",
            flush=True,
        )
        return None

    coreg = dem_library.coreg.NuthKaab() + dem_library.coreg.Deramp(poly_order=2)
    coreg.fit(dem_1, dem_2, inlier_mask=~river)
    dem_2_aligned = coreg.apply(dem_2)


    dh = dem_1 - dem_2_aligned

    save_raster(
            dh,
            result_path(f"dh_{name_1}_{name_2}.tif"),
        )

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

    x = np.arange(0, 500, 1)
    plt.plot(x, [rho_sig(distance) for distance in x])
    plt.xlabel("Distance [m]")
    plt.ylabel("Error similarity [%]")

    save_raster(
        sig_dem,
        result_path(f"uncertainty_{name_1}_{name_2}.tif"),
    )

    plot_path = result_path(
        f"Correlation_{name_1}_{name_2}.png"
    )
    plt.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close()
    
    
    values = dh.data.filled(np.nan)
    valid_values = values[np.isfinite(values)]
    rmse = np.sqrt(np.mean(valid_values**2))
    stats = {
        "reference_dem": name_1,
        "comparison_dem": name_2,
        "mean": np.mean(valid_values),
        "median": np.median(valid_values),
        "std": np.std(valid_values),
        "rmse": rmse,
        "mae": np.mean(np.abs(valid_values)),
        "min": np.min(valid_values),
        "max": np.max(valid_values),
        "INSPIRE_target%": rmse / (5 / 3) * 100,
    }
    pd.DataFrame([stats]).to_csv(
        result_path("dem_difference_statistics.csv"),
        index=False,
    )
    
    return {
        "coreg": coreg,
        "aligned_dem": dem_2_aligned,
        "dh": dh,
        "dem_1": dem_1,
        "name_1": name_1,
        "name_2": name_2,
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

    output_path = result_path(f"local_inspire_rmse_{name}.tif")
    rmse_dem = dh.copy(new_array=rmse_raster)
    save_raster(rmse_dem, output_path)
    output_path = result_path(f"local_inspire_rmse_{name}.tif")
    save_raster(
        rmse_raster,
        output_path,
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


def std_analysis(dh,name):
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


def cdf_analysis(dh,name):
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


def aspect_difference_analysis(dem_1, dem_2,name_1,name_2):
    load_pyplot()
    difference = dem_1.aspect() - dem_2.reproject(dem_1).aspect()
    save_raster(
        difference,
        result_path(f"aspect_difference_{name_1}_{name_2}.tif")
    )
    difference.plot(cmap="RdBu")
    load_pyplot().close("all")


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
    strips = range(0,1001,50)#[0, 50, 100, 250, 500, 1000]
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
    rows = [
        [
            lo,
            hi,
            nanmean(z[(distances >= lo) & (distances < hi) & np.isfinite(z)]),
            nanrmse(z[(distances >= lo) & (distances < hi) & np.isfinite(z)]),
        ]
        for lo, hi in zip(strips[:-1], strips[1:])
    ]
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
            for pattern in ("*.gpkg", "*.shp", "*.geojson", "*.json")
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


def border_trend_plot(csv_file,name):
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


def top_problem_regions(dh, name, threshold=1.0, min_area=200, merge_distance=60):
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


def load_country_water_mask(
    dem,
    country,
    buffer_pixels=MASK_BUFFER_PIXELS,
    directory=DATA_DIR,
):
    class_path = find_country_class_mask(country, directory)
    dem_bounds = dem.bounds
    dem_crs = dem.crs
    dem_transform = dem.transform
    dem_height, dem_width = dem.shape

    with rasterio.open(class_path) as source:
        if source.crs is None:
            raise ValueError(f"Class mask has no CRS: {class_path}")
        source_crs = source.crs
        bounds_in_source_crs = transform_bounds(
            dem_crs,
            source_crs,
            *dem_bounds,
            densify_pts=21,
        )
        class_bounds = (
            source.bounds.left,
            source.bounds.bottom,
            source.bounds.right,
            source.bounds.top,
        )
        if (
            bounds_in_source_crs[2] <= class_bounds[0]
            or bounds_in_source_crs[0] >= class_bounds[2]
            or bounds_in_source_crs[3] <= class_bounds[1]
            or bounds_in_source_crs[1] >= class_bounds[3]
        ):
            raise ValueError(
                f"{country} class mask does not overlap the DEM extent: {class_path}"
            )

        source_window = geometry_window(
            source,
            [
                {
                    "type": "Polygon",
                    "coordinates": [[
                        (bounds_in_source_crs[0], bounds_in_source_crs[1]),
                        (bounds_in_source_crs[0], bounds_in_source_crs[3]),
                        (bounds_in_source_crs[2], bounds_in_source_crs[3]),
                        (bounds_in_source_crs[2], bounds_in_source_crs[1]),
                        (bounds_in_source_crs[0], bounds_in_source_crs[1]),
                    ]],
                }
            ],
            pad_x=1,
            pad_y=1,
        ).round_offsets().round_lengths()
        source_window = source_window.intersection(
            rasterio.windows.Window(0, 0, source.width, source.height)
        )
        source_array = source.read(1, window=source_window)
        source_transform = source.window_transform(source_window)

    target_bounds = transform_bounds(
        source_crs,
        dem_crs,
        *class_bounds,
        densify_pts=21,
    )
    left, bottom, right, top = target_bounds
    col_start = max(
        0, int(np.floor((left - dem_transform.c) / dem_transform.a)) - buffer_pixels
    )
    col_stop = min(
        dem_width, int(np.ceil((right - dem_transform.c) / dem_transform.a)) + buffer_pixels
    )
    row_start = max(
        0, int(np.floor((dem_transform.f - top) / abs(dem_transform.e))) - buffer_pixels
    )
    row_stop = min(
        dem_height,
        int(np.ceil((dem_transform.f - bottom) / abs(dem_transform.e))) + buffer_pixels,
    )
    if col_start >= col_stop or row_start >= row_stop:
        raise ValueError(f"{country} class mask does not overlap the DEM grid")

    window_transform = rasterio.windows.transform(
        rasterio.windows.Window(
            col_start, row_start, col_stop - col_start, row_stop - row_start
        ),
        dem_transform,
    )
    destination = np.zeros((row_stop - row_start, col_stop - col_start), dtype=np.uint8)
    with rasterio.open(class_path) as source:
        reproject(
            source=source_array,
            destination=destination,
            src_transform=source_transform,
            src_crs=source.crs,
            src_nodata=0,
            dst_transform=window_transform,
            dst_crs=dem_crs,
            dst_nodata=0,
            resampling=Resampling.nearest,
        )

    mask = np.zeros((dem_height, dem_width), dtype=bool)
    aligned = (destination == 2) | (destination == 3) 
    if buffer_pixels:
        aligned = ndimage.binary_dilation(
            aligned,
            structure=np.ones((3, 3), dtype=bool),
            iterations=buffer_pixels,
        )
    mask[row_start:row_stop, col_start:col_stop] = aligned
    print(f"Loaded {country} water mask: {np.count_nonzero(mask):,} cells")
    return mask

def river_mask_on_grid(dem_path, reference, buffer_pixels=0):
    """Boolean mask (True = river) of a DEM's river mask, resampled to `reference`'s grid."""
    basename = os.path.splitext(os.path.basename(dem_path))[0]
    mask_path = result_path(f"{basename}_river_mask.tif")
    if not os.path.isfile(mask_path):
        print(f"No river mask found for {basename}, skipping it", flush=True)
        return np.zeros(reference.shape, dtype=bool)

    river = gu.Raster(mask_path).reproject(reference, resampling="nearest")
    mask = river.data.filled(0) == 1       # nodata (255 / outside) counts as not-river
    del river
    if buffer_pixels:
        mask = ndimage.binary_dilation(
            mask, structure=np.ones((3, 3), dtype=bool), iterations=buffer_pixels
        )
    return mask



@njit(cache=True)
def _reflect_index(index, length):
    while index < 0 or index >= length:
        if index < 0:
            index = -index - 1
        else:
            index = 2 * length - index - 1
    return index


@njit(cache=True)
def _fill_seed_cache(elevation, seed_mask, dif_cache):
    height, width = elevation.shape
    for row in range(height):
        for column in range(width):
            if seed_mask[row, column]:
                dif_cache[row, column] = elevation[row,column]

@njit(cache=True)
def _grow_from_seeds(elevation, dif_cache, seeds, tolerance, valid_domain,):
    height, width = elevation.shape
    flat_dif = dif_cache.ravel()
    flat_domain = valid_domain.ravel()
    grown = np.zeros(valid_domain.shape, dtype=np.bool_)
    flat_grown = grown.ravel()

    queue = np.empty(flat_domain.size, dtype=np.int32)  # use int64 if N > 2**31
    tail = 0
    for seed in seeds:
        if not flat_grown[seed]:
            flat_grown[seed] = True
            queue[tail] = seed
            tail += 1

    head = 0
    while head < tail:
        current = queue[head]
        head += 1
        row = current // width
        column = current - row * width
        current_dif = flat_dif[current]

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
                if flat_domain[neighbor] and not flat_grown[neighbor]:
                    if np.isnan(flat_dif[neighbor]):
                        flat_dif[neighbor] = _local_dif_at(
                            elevation, neighbor_row, neighbor_column
                        )
                    if abs(flat_dif[neighbor] - current_dif) <= tolerance:
                        flat_grown[neighbor] = True
                        queue[tail] = neighbor
                        tail += 1
    return grown

@njit(cache=True)
def _local_dif_at(elevation, row, column):
    return elevation[row, column]

def grow_dif_regions(
    elevation,
    seed_mask,
    tolerance=REGION_GROWING_DIF_TOLERANCE,
    valid_domain=None,
):
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Region-growing tolerance must be finite and non-negative")
    if elevation.shape != seed_mask.shape:
        raise ValueError("DEM and seed mask dimensions do not match")

    if valid_domain is None:
        valid_domain = np.isfinite(elevation)
    elif valid_domain.shape != elevation.shape:
        raise ValueError("DEM and valid-domain dimensions do not match")
    valid_domain = valid_domain & np.isfinite(elevation)
    seed_cells = seed_mask & valid_domain

    # --- section to skip seed selection and set all 3 cell centers as a 3
    seed_cells = seed_mask & valid_domain
    seeds = np.flatnonzero(seed_cells)          # flat indices, int64
    if seeds.size == 0:
        raise ValueError("Seed mask contains no valid cells")

    dif_cache = np.full(elevation.shape, np.nan, dtype=np.float32)
    _fill_seed_cache(elevation, seed_cells, dif_cache)

    # optional: keep the per-seed threshold
    keep = dif_cache.ravel()[seeds] <= SEED_DIF_THRESHOLD
    discarded_count = int(np.count_nonzero(~keep))
    seeds = seeds[keep]
    accepted_count = seeds.size
    # ---

    print(
        f"Growing from {accepted_count:,} seeds; discarded {discarded_count:,} "
        f"(8-connected, tolerance {tolerance:g})"
    )
    grown = (
        _grow_from_seeds(
            elevation,
            dif_cache,
            seeds,
            tolerance,
            valid_domain,
        )
        if accepted_count
        else np.zeros(seed_mask.shape, dtype=bool)
    )
    return grown, seeds, accepted_count, dif_cache


def process_dem(dem_path, data_dir=DATA_DIR):
    country = infer_country_name(dem_path)
    print(f"\nProcessing {os.path.basename(dem_path)} ({country})")
    dem, _ = load_file(dem_path)
    water_mask = load_country_water_mask(dem, country, directory=data_dir)
    dem_values = np.asarray(dem.data.filled(np.nan), dtype=np.float32)
    dem_valid = np.isfinite(dem_values)
    elevation = np.where(dem_valid, dem_values, 0.0).astype(np.float32)
    seed_mask = water_mask & dem_valid

    grown, seeds, component_count, dif = grow_dif_regions(
        elevation,
        seed_mask,
        tolerance=REGION_GROWING_DIF_TOLERANCE,
        valid_domain=dem_valid,
    )

    basename = os.path.splitext(os.path.basename(dem_path))[0]
    dif_path = os.path.join(RESULTS_DIR, f"{basename}_dif.tif")
    river_mask_path = os.path.join(RESULTS_DIR, f"{basename}_river_mask.tif")
    save_raster(
        dif,
        dif_path,
        dem.transform,
        dem.crs,
        np.nan,
        dtype="float32",
    )
    river_mask = np.full(dem.shape, MASK_NODATA, dtype=np.uint8)
    river_mask[dem_valid] = 0
    river_mask[grown] = 1
    save_raster(
        river_mask,
        river_mask_path,
        dem.transform,
        dem.crs,
        MASK_NODATA,
        dtype="uint8",
    )
    print(
        f"Saved elevation map and river mask for {component_count:,} accepted seeds "
        f"({seeds.size:,} seeds):\n  {dif_path}\n  {river_mask_path}"
    )


def run_all_analyses(data_dir=DATA_DIR):
    analysis_start = time.perf_counter()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    dem_files = find_dem_files(data_dir)
    if not dem_files:
        raise FileNotFoundError(f"No DEM GeoTIFF files found in {data_dir}")
    for dem_path in dem_files:
        process_dem(dem_path, data_dir)

    comparison_paths = find_comparison_dem_files(data_dir)
    statistics = []
    pair_count = len(comparison_paths) * (len(comparison_paths) - 1) // 2
    last_dem_pair = (None, None)

    border_path = find_border_vector(data_dir)
    border_vector = load_border_vector(border_path) if border_path else None
    if border_vector is None:
        print("No border vector found, skipping border analyses", flush=True)

    print(f"Checking {pair_count} DEM combinations for overlap...", flush=True)
    for first_index, first_path in enumerate(comparison_paths):
        for second_path in comparison_paths[first_index + 1 :]:
            pair_name = (
                f"{os.path.basename(first_path)} and {os.path.basename(second_path)}"
            )
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
            dem_1 = load_or_transform_dem(
                first_path,
                infer_vcrs_country(first_path),
            )
            dem_2 = load_or_transform_dem(
                second_path,
                infer_vcrs_country(second_path),
            )
            analysis = analyze_dem(dem_1, dem_2, first_path, second_path)
            if analysis is None:
                continue

            dh = analysis["dh"]
            dem_1_crop = analysis["dem_1"]     # needs the change in step 3


            name = analysis["name_1"] + "_" + analysis["name_2"]
            name_1 = analysis["name_1"]
            name_2 = analysis["name_2"]

            local_inspire_rmse_analysis(dh,name)
            std_analysis(dh,name)
            histogram_analysis(dh,name)
            cdf_analysis(dh,name)
            slope_error_analysis(dem_1_crop, dh, name)
            aspect_difference_analysis(dem_1_crop, analysis["aligned_dem"], name_1,name_2)
            top_problem_regions(dh,name)

            if border_vector is not None:
                border_strip_analysis(dh, border_vector,name)
                border_trend_plot(result_path(f"border_strips_{name}.csv"),name)

            last_dem_pair = (dem_1, dem_2)
            statistics.append(
                {
                    "reference_dem": name_1,
                    "comparison_dem": name_2,
                    **{
                        key: analysis[key]
                        for key in (
                            "mean",
                            "median",
                            "std",
                            "rmse",
                            "mae",
                            "min",
                            "max",
                            "INSPIRE_target%",
                        )
                    },
                }
            )
            del analysis, dh, dem_1_crop

    statistics_columns = [
        "reference_dem",
        "comparison_dem",
        "mean",
        "median",
        "std",
        "rmse",
        "mae",
        "min",
        "max",
        "INSPIRE_target%",
    ]
    pd.DataFrame(statistics, columns=statistics_columns).to_csv(
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
        "dem_paths": comparison_paths,
        "statistics": statistics,
        "dem_1": last_dem_pair[0],
        "dem_2": last_dem_pair[1],
    }


if __name__ == "__main__":
    print("Starting raster difference and river-region analysis.")
    run_all_analyses()
