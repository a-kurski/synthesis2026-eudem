"""Raster I/O for the comparison and river-mask code (xdem/rasterio)."""
import os
import tempfile

import numpy as np
import rasterio
import xdem
from rasterio.shutil import copy as rio_copy

RESULTS_DIR = "results"  # set by the caller (comparison: one folder per pair)


def result_path(filename):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    return os.path.join(RESULTS_DIR, filename)


def load_file(filename):
    dem = xdem.DEM(filename)
    return dem, os.path.splitext(os.path.basename(filename))[0]


def save_raster(array, filename, transform=None, crs=None, nodata=None, dtype=None,
                resampling="AVERAGE", tags=None):
    if transform is None:  # an xdem/geoutils raster
        if np.dtype(array.dtype) == np.float64:  # float32 is plenty for heights and errors, half the size
            array = array.astype("float32")
        array.to_file(filename, driver="COG")
        return

    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)

    if dtype is None:
        dtype = "float32" if np.dtype(array.dtype) == np.float64 else array.dtype

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
