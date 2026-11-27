import os
import tempfile

import numpy as np
import rasterio
import xdem
from pyproj import CRS
from rasterio.shutil import copy as rio_copy

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

TARGET_CRS = CRS.from_epsg(3035)   # ETRS89-extended / LAEA Europe
TARGET_VCRS = CRS.from_epsg(9389)  # EVRF2019 height (EVRF2007 = 5621)

source_vcrs = {
    **dict.fromkeys(
        ("NRW", "NiSa", "RhPf", "Saar", "BaWu", "Hessen", "Bay"), CRS.from_epsg(7837)
    ),
    "France": CRS.from_epsg(5720),
    "Luxembourg": CRS.from_epsg(5774),
    "Netherlands": CRS.from_epsg(5709),
    "Switzerland": CRS.from_epsg(5728),
}
target_vcrs = dict.fromkeys(source_vcrs, TARGET_VCRS)


def result_path(filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, filename)


def load_xdem():
    return xdem


def infer_vcrs_country(file_name_or_path):
    text = os.path.basename(str(file_name_or_path)).upper()
    return next(
        (country for country in source_vcrs if country.upper() in text),
        None,
    )


def name_from_path(path):
    return os.path.splitext(os.path.basename(path))[0].removesuffix("_vcrs")


def safe_name(obj, fallback="dem"):
    return name_from_path(getattr(obj, "name", None) or fallback)


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
    transformed_path = result_path(
        f"{file_name}_{TARGET_CRS.to_epsg()}_{TARGET_VCRS.to_epsg()}_vcrs.tif"
    )
    if (
        os.path.isfile(transformed_path)
        and os.path.getmtime(transformed_path) >= os.path.getmtime(dem_path)
    ):
        return load_xdem().DEM(transformed_path)

    dem, _ = load_file(dem_path)
    dem = transform_dem_to_target_vcrs(dem, country_name, source_vcrs, target_vcrs)
    if CRS.from_user_input(dem.crs) != TARGET_CRS:
        dem = dem.reproject(crs=TARGET_CRS)
    save_raster(dem, transformed_path)
    return dem


def load_file(filename):
    dem = xdem.DEM(filename)
    return dem, os.path.splitext(os.path.basename(filename))[0]


def save_raster(array, filename, transform=None, crs=None, nodata=None, dtype=None,
                resampling="AVERAGE", tags=None):
    if transform is None:
        array.to_file(filename, driver="COG")
        return

    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

    if dtype is None:
        dtype = array.dtype

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
                predictor=3 if np.issubdtype(np.dtype(dtype), np.floating) else 2,
                blocksize=512,
                overviews="AUTO",
                resampling=resampling,
                num_threads="ALL_CPUS",
                bigtiff="IF_SAFER",
            )
