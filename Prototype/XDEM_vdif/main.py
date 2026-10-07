import os
import glob
import xdem
import numpy as np
import matplotlib.pyplot as plt
import geoutils as gu
import geopandas as gpd
import pandas as pd
from affine import Affine
from pyproj import CRS, Transformer
from shapely.geometry import box

#change to json files
# Source vertical CRS (fill these in later)
source_vcrs = {
    "NRW": CRS.from_epsg(7837), #https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/hoehenmodelle/digitale-gelaendemodelle/digitales-gelaendemodell
    "NiSa": CRS.from_epsg(7837), #https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-gel-ndemodell-dgm1
    "RhPf": CRS.from_epsg(7837),#https://geoshop.rlp.de/digitale_gelaendemodelle/digitale_gelaendemodelle_dgm.html
    "Saar": CRS.from_epsg(7837), #https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1060&Itemid=475
    "BaWu": CRS.from_epsg(7837), #
    "Hessen": CRS.from_epsg(7837), #
    "Bay": CRS.from_epsg(7837), #
    "France": CRS.from_epsg(5720),
    "Luxembourg": CRS.from_epsg(5774),
    "Netherlands": CRS.from_epsg(5709),
    "Switzerland": CRS.from_epsg(5728),
}

# IMPORTANT: the target values must be vertical CRS objects, not projected horizontal CRS
# like EPSG:5129. For the pilot workflow we keep the target vertical datum aligned with
# each country's source vertical datum to avoid invalid transforms and SSL/grid download issues.
target_vcrs = {country: source_vcrs[country] for country in source_vcrs}

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def result_path(filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, filename)


def load_file(file_path):
    dtm = xdem.DEM(file_path)
    name = os.path.splitext(os.path.basename(file_path))[0]
    return dtm, name


def infer_country_name(file_name_or_path):
    text = os.path.basename(str(file_name_or_path)).upper()
    for country in source_vcrs:
        if country.upper() in text:
            return country
    for country in target_vcrs:
        if country.upper() in text:
            return country
    return None


def safe_name(obj, fallback="dem"):
    raw_name = getattr(obj, "name", None)
    if raw_name is None:
        return fallback
    base_name = os.path.basename(str(raw_name))
    if not base_name:
        return fallback
    return os.path.splitext(base_name)[0]


def transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs):
    if country_name not in target_vcrs:
        raise ValueError(f"Target vertical CRS for {country_name} not found.")

    source_vcr = source_vcrs[country_name]
    target_vcr = target_vcrs[country_name]

    if source_vcr == target_vcr:
        return dem

    transformed = dem.to_vcrs(
        target_vcr,
        force_source_vcrs=source_vcr
    )
    return transformed if transformed is not None else dem


def save_dem(dem, country_name):
    save_raster(dem, result_path(f"{country_name}_vcrs.tif"))


def save_raster(raster, filename):
    if hasattr(raster, "to_file"):
        raster.to_file(filename)
    else:
        raster.save(filename)


def save_vector(vector, filename):
    if hasattr(vector, "to_file"):
        vector.to_file(filename)
    else:
        vector.save(filename)


def safe_nanmean(values):
    values = np.asarray(values)
    if values.size == 0 or not np.isfinite(values).any():
        return np.nan
    return np.nanmean(values)


def safe_nanrmse(values):
    values = np.asarray(values)
    if values.size == 0 or not np.isfinite(values).any():
        return np.nan
    return np.sqrt(np.nanmean(values**2))


def analyze_dem(dem_1, dem_2):
    # Ensure both rasters share the same grid before coregistration or arithmetic.
    # This is especially important for partially overlapping pilot datasets.
    if dem_1.shape != dem_2.shape or dem_1.transform != dem_2.transform:
        dem_2 = dem_2.reproject(dem_1)

    # Coregistration
    coreg = (
        xdem.coreg.NuthKaab()
        + xdem.coreg.Deramp(poly_order=2)
    )

    coreg.fit(dem_1, dem_2)
    dem_2_aligned = coreg.apply(dem_2)

    # Elevation differences
    dh = dem_1 - dem_2_aligned

    # Convert to NumPy array and remove nodata
    dh_array = dh.data.filled(np.nan)
    valid = np.isfinite(dh_array)

    values = dh_array[valid]

    # Statistics
    if values.size == 0:
        mean = median = std = rmse = mae = np.nan
    else:
        mean = np.mean(values)
        median = np.median(values)
        std = np.std(values)
        rmse = np.sqrt(np.mean(values**2))
        mae = np.mean(np.abs(values))
        min = np.min(values)
        max = np.max(values)

    # INSPIRE target
    INSPIRE_target = 5/3

    # [0-100] = good, [100-...] = bad
    if np.isnan(rmse):
        INSPIRE_perc = np.nan
    else:
        INSPIRE_perc = (rmse)/INSPIRE_target * 100

    pd.DataFrame({
        "reference_dem": [safe_name(dem_1)],
        "comparison_dem": [safe_name(dem_2)],
        "mean": [mean],
        "median": [median],
        "std": [std],
        "rmse": [rmse],
        "mae": [mae],
        "min": [min],
        "max": [max],
        "INSPIRE_target%": [INSPIRE_perc]
        }).to_csv(result_path("dem_difference_statistics.csv"), index=False)

    # Save difference raster
    save_raster(
        dh,
        result_path(f"dh_{safe_name(dem_1)}_{safe_name(dem_2)}.tif"),
    )
    
    return {
        "coreg": coreg,
        "aligned_dem": dem_2_aligned,
        "dh": dh,
        "mean": mean,
        "median": median,
        "std": std,
        "rmse": rmse,
        "mae": mae,
    }

#mean offset map for visualization
def std_analysis(dh):
    dh_array = dh.data.filled(np.nan)
    valid = np.isfinite(dh_array)
    values = dh_array[valid]
    mean = safe_nanmean(values)

    dh_std = dh - mean

    save_raster(dh_std, result_path(f"dh_std_{safe_name(dh)}.tif"))

#histogram
def histogram_analysis(dh):
    values = dh.data.filled(np.nan)
    values = values[np.isfinite(values)]

    plt.figure(figsize=(8,5))
    plt.hist(values, bins=100)
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Count")
    plt.title("DEM Difference Histogram")
    plt.savefig(result_path(f"histogram_{safe_name(dh)}.png"))
    plt.close()

#cumulative distribution
def cdf_analysis(dh):
    values = dh.data.filled(np.nan)
    values = np.sort(values[np.isfinite(values)])

    cdf = np.arange(len(values)) / len(values)

    plt.figure(figsize=(8,5))
    plt.plot(values, cdf)
    plt.xlabel("Elevation difference (m)")
    plt.ylabel("Cumulative probability")
    plt.title("DEM Difference CDF")
    plt.grid()
    plt.savefig(result_path(f"cdf_{safe_name(dh)}.png"))
    plt.close()

#aspect difference
def aspect_difference_analysis(dem_1, dem_2):
    dem_2_on_dem_1 = dem_2.reproject(dem_1)

    asp1 = dem_1.aspect()
    asp2 = dem_2_on_dem_1.aspect()

    asp_diff = asp1 - asp2

    save_raster(
        asp_diff,
        result_path(
            f"aspect_difference_{safe_name(dem_1)}_{safe_name(dem_2)}.tif"
        ),
    )

    asp_diff.plot(cmap="RdBu")

#relation slope and error
def slope_error_analysis(dem_1, dh):
    slope = dem_1.slope()

    slopes = slope.data.filled(np.nan)
    diffs = dh.data.filled(np.nan)

    bins = np.arange(0, 55, 5)

    rmses = []

    for i in range(len(bins)-1):
        mask = (
            (slopes >= bins[i]) &
            (slopes < bins[i+1])
        )

        vals = diffs[mask]
        rmses.append(safe_nanrmse(vals))

    plt.figure(figsize=(8,5))
    plt.plot(bins[:-1],rmses, marker="o")
    plt.xlabel("Slope (deg)")
    plt.ylabel("RMSE (m)")
    plt.title("RMSE versus Slope")
    plt.savefig(result_path(f"slope_rmse_{safe_name(dh)}.png"))
    plt.close()

#analysis of errors in relation to border distance
def border_strip_analysis(dh, border_vector):
    strips = [0, 50, 100, 250, 500, 1000]
    max_distance = strips[-1]
    z = dh.data.filled(np.nan)

    if not border_vector.crs.is_projected:
        raise ValueError("Border vector must use a projected CRS for meter-based distances.")

    unit_to_meters = border_vector.crs.axis_info[0].unit_conversion_factor
    if not unit_to_meters:
        raise ValueError("Could not determine border-vector CRS units.")

    bounds_transformer = Transformer.from_crs(
        dh.crs,
        border_vector.crs,
        always_xy=True,
    )
    vector_bounds = bounds_transformer.transform_bounds(
        *dh.bounds,
        densify_pts=21,
    )
    margin = max_distance / unit_to_meters
    search_area = box(
        vector_bounds[0] - margin,
        vector_bounds[1] - margin,
        vector_bounds[2] + margin,
        vector_bounds[3] + margin,
    )

    nearby = border_vector.ds.loc[
        border_vector.ds.geometry.intersects(search_area)
    ].copy()
    if nearby.empty:
        distances = np.full(dh.shape, np.nan)
        print(
            f"No border lines within {max_distance} m of the DEM footprint; "
            "border-strip statistics will be empty."
        )
    else:
        nearby.geometry = nearby.geometry.intersection(search_area)
        nearby = nearby.loc[~nearby.geometry.is_empty]
        local_borders = gu.Vector(nearby).reproject(crs=dh.crs)

        pixel_width = abs(dh.transform.a)
        pixel_height = abs(dh.transform.e)
        pad_columns = int(np.ceil(max_distance / pixel_width))
        pad_rows = int(np.ceil(max_distance / pixel_height))
        padded_transform = dh.transform * Affine.translation(
            -pad_columns,
            -pad_rows,
        )
        proximity_grid = gu.Raster.from_array(
            np.zeros(
                (
                    dh.height + 2 * pad_rows,
                    dh.width + 2 * pad_columns,
                ),
                dtype=np.uint8,
            ),
            transform=padded_transform,
            crs=dh.crs,
        )
        dist = proximity_grid.proximity(
            local_borders,
            geometry_type="geometry",
            distance_unit="georeferenced",
        ).crop(dh)
        distances = dist.data.filled(np.nan)

    results = []
    for i in range(len(strips) - 1):
        mask = (
            (distances >= strips[i])
            & (distances < strips[i + 1])
            & np.isfinite(z)
        )
        vals = z[mask]

        results.append(
            [
                strips[i],
                strips[i + 1],
                safe_nanmean(vals),
                safe_nanrmse(vals),
            ]
        )

    df = pd.DataFrame(
        results,
        columns=["min_dist", "max_dist", "mean", "rmse"],
    )
    df.to_csv(
        result_path(f"border_strips_{safe_name(dh)}.csv"),
        index=False,
    )
    return df


def find_border_vector(data_dir):
    preferred_name = "CNTR_BN_01M_2024_3035.shp"
    preferred_path = os.path.join(data_dir, preferred_name)
    if os.path.isfile(preferred_path):
        return preferred_path

    candidates = []
    for pattern in ("*.gpkg", "*.shp", "*.geojson", "*.json"):
        candidates.extend(glob.glob(os.path.join(data_dir, pattern)))
    candidates = sorted(set(candidates))

    if len(candidates) > 1:
        raise ValueError(
            "More than one border vector was found; expected "
            f"{preferred_name} or a single vector file in {data_dir}."
        )
    return candidates[0] if candidates else None


def load_border_vector(vector_path):
    if vector_path.lower().endswith(".shp"):
        previous_restore_setting = os.environ.get("SHAPE_RESTORE_SHX")
        os.environ["SHAPE_RESTORE_SHX"] = "YES"
        try:
            border_vector = gu.Vector(vector_path)
        finally:
            if previous_restore_setting is None:
                os.environ.pop("SHAPE_RESTORE_SHX", None)
            else:
                os.environ["SHAPE_RESTORE_SHX"] = previous_restore_setting
    else:
        border_vector = gu.Vector(vector_path)

    if border_vector.crs is None:
        if "_3035" not in os.path.basename(vector_path):
            raise ValueError(
                f"Border vector has no CRS metadata: {vector_path}"
            )
        border_vector.ds = border_vector.ds.set_crs(CRS.from_epsg(3035))
        print(
            "Border vector has no CRS metadata; using EPSG:3035 "
            "as indicated by its filename."
        )

    geometry_types = set(border_vector.ds.geometry.geom_type.dropna())
    if not geometry_types or not geometry_types.issubset(
        {"LineString", "MultiLineString"}
    ):
        raise ValueError(
            "Border vector must contain line geometries; found "
            f"{sorted(geometry_types)}."
        )
    return border_vector


def border_trend_plot(csv_file):

    df = pd.read_csv(csv_file)

    plt.figure(figsize=(8,5))

    plt.plot(
        df["max_dist"],
        df["rmse"],
        marker="o"
    )

    plt.xlabel("Distance from border (m)")
    plt.ylabel("RMSE (m)")
    plt.title("Border Effect")

    plt.grid()

    plt.savefig(
        result_path("border_effect.png"),
        dpi=300
    )

    plt.close()


def top_problem_regions(
    dh,
    threshold=2,
    min_area=400
):

    dh_array = dh.data.filled(np.nan)
    mask = (np.abs(dh_array) > threshold).astype(np.uint8)
    exceedance_count = int(np.count_nonzero(mask))

    if exceedance_count == 0:
        empty_regions = gu.Vector(
            gpd.GeoDataFrame(
                {
                    "area_m2": pd.Series(dtype=float),
                    "severity": pd.Series(dtype=float),
                    "rank": pd.Series(dtype=int),
                },
                geometry=gpd.GeoSeries([], crs=dh.crs),
                crs=dh.crs,
            )
        )
        save_vector(
            empty_regions,
            result_path("problem_regions.gpkg")
        )
        print(
            f"Problem regions: no cells exceed |difference| > {threshold} m; "
            "exported an empty problem_regions.gpkg."
        )
        return empty_regions

    outliers = dh.copy(
        new_array=mask
    )

    regions = outliers.polygonize(
        target_values=1
    )
    candidate_count = len(regions.ds)

    regions.ds["area_m2"] = (
        regions.ds.geometry.area
    )

    regions.ds = regions.ds[
        regions.ds["area_m2"] > min_area
    ]

    regions.ds["severity"] = (
        regions.ds["area_m2"] / 1000
    )

    regions.ds = (
        regions.ds.sort_values(
            "severity",
            ascending=False
        )
        .reset_index(drop=True)
    )

    regions.ds["rank"] = (
        regions.ds.index + 1
    )

    save_vector(
        regions,
        result_path("problem_regions.gpkg")
    )

    retained_count = len(regions.ds)
    print(
        f"Problem regions: {exceedance_count} cells exceed "
        f"|difference| > {threshold} m; {candidate_count} connected "
        f"regions found, {retained_count} larger than {min_area} m². "
        "Exported problem_regions.gpkg."
    )

    return regions


def find_test_dem_pair(data_dir=None):
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(__file__), "data")

    tif_files = []
    for pattern in ("*.tif", "*.tiff", "*.TIF", "*.TIFF"):
        tif_files.extend(glob.glob(os.path.join(data_dir, pattern)))

    tif_files = sorted(set(tif_files))
    full_region_files = [
        path
        for path in tif_files
        if not os.path.splitext(os.path.basename(path))[0]
        .lower()
        .endswith("_dep")
    ]
    country_files = [
        (path, infer_country_name(path))
        for path in full_region_files
    ]
    country_files = [
        (path, country)
        for path, country in country_files
        if country is not None
    ]

    distinct_country_pairs = [
        (path_a, path_b)
        for index, (path_a, country_a) in enumerate(country_files)
        for path_b, country_b in country_files[index + 1:]
        if country_a != country_b
    ]
    if distinct_country_pairs:
        return min(
            distinct_country_pairs,
            key=lambda pair: sum(os.path.getsize(path) for path in pair),
        )

    if len(full_region_files) < 2:
        raise FileNotFoundError(
            "Expected at least two full-region DEM files in "
            f"{data_dir}; files ending in '_dep' are excluded."
        )
    raise ValueError(
        "Could not find full-region DEMs from two different recognized "
        f"countries in {data_dir}; files ending in '_dep' are excluded."
    )


def run_all_analyses(data_dir=None):
    """Run the full DEM analysis workflow on full-region DEMs."""
    dem_paths = find_test_dem_pair(data_dir)

    dem_1, dem_1_name = load_file(dem_paths[0])
    dem_2, dem_2_name = load_file(dem_paths[1])

    country_1 = infer_country_name(dem_1_name)
    country_2 = infer_country_name(dem_2_name)

    if country_1 is None:
        raise ValueError(f"Could not infer country from DEM name: {dem_1_name}")
    if country_2 is None:
        raise ValueError(f"Could not infer country from DEM name: {dem_2_name}")
    if country_1 == country_2:
        raise ValueError(
            f"Pilot DEM pair must cover different countries, but both selected "
            f"files match {country_1}: {dem_1_name} and {dem_2_name}."
        )

    dem_1 = transform_dem_to_target_vcrs(dem_1, country_1, source_vcrs, target_vcrs)
    dem_2 = transform_dem_to_target_vcrs(dem_2, country_2, source_vcrs, target_vcrs)

    save_dem(dem_1, country_1)
    save_dem(dem_2, country_2)

    print(f"Running pilot overlap analysis on: {country_1} and {country_2}")

    analysis = analyze_dem(dem_1, dem_2)
    dh = analysis["dh"]

    std_analysis(dh)
    histogram_analysis(dh)
    cdf_analysis(dh)
    aspect_difference_analysis(dem_1, dem_2)
    slope_error_analysis(dem_1, dh)

    regions = top_problem_regions(dh)

    border_vector_dir = data_dir if data_dir is not None else os.path.join(os.path.dirname(__file__), "data")
    border_vector_path = find_border_vector(border_vector_dir)
    if border_vector_path:
        print(f"Using European border vector: {os.path.basename(border_vector_path)}")
        border_vector = load_border_vector(border_vector_path)
        border_strip_analysis(dh, border_vector)
        border_trend_plot(
            result_path(f"border_strips_{safe_name(dh)}.csv")
        )
    else:
        print("No border vector file found; skipping border strip analysis.")

    print("Pilot analysis finished.")
    return {
        "dem_1": dem_1,
        "dem_2": dem_2,
        "analysis": analysis,
        "regions": regions,
    }


if __name__ == "__main__":
    run_all_analyses()