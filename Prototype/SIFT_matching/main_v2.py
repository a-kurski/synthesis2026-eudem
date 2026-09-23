from pathlib import Path

import cv2
import numpy as np
import random as rd
rd.seed(17)
from osgeo import gdal
from pyproj import CRS
from pyproj.transformer import TransformerGroup
from itertools import combinations

crs = CRS.from_epsg(4326)

#===========================================
#Load DEM
#===========================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
REPROJECTED_DIR = DATA_DIR / "reprojected"
RESAMPLED_DIR = DATA_DIR / "resampled"
VERTICAL_DIR = DATA_DIR / "vertical_adjusted"
FILLED_DIR = DATA_DIR / "filled"
HILLSHADE_DIR = DATA_DIR / "hillshade"
RESULTS_DIR = BASE_DIR / "results"

FILE1 = INPUT_DIR / "AHN5_M_193000_417000.TIF"
FILE2 = INPUT_DIR / "AHN5_M_192000_417000.TIF"
FILE3 = INPUT_DIR / "dgm1_32_288_5737_1_nw_2024.tif"
FILE4 = INPUT_DIR / "dgm1_32_288_5736_1_nw_2024.tif"
FILE5 = INPUT_DIR / "dgm1_32_289_5736_1_nw_2024.tif"
FILE6 = INPUT_DIR / "607_5270.tif"
FILE7 = INPUT_DIR / "dgm_50cm_1628-71_2019.tif"
FILE8 = INPUT_DIR / "607_5269.tif"
FILE9 = INPUT_DIR / "dgm_50cm_1628-78_2019.tif"
TARGET_CRS = "EPSG:25832"
TARGET_VERTICAL_CRS = "EPSG:5621"  # EVRF2007 height
MIN_OVERLAP_FRACTION = 0.10
REUSE_EXISTING_OUTPUTS = True
APPLY_GERMAN_VERTICAL_TRANSFORM = True
APPLY_DUTCH_VERTICAL_TRANSFORM = True
APPLY_AUSTRIAN_HEIGHT_COMPENSATION = True
AHN_INPUT_INDICES = {0, 1}
GERMAN_INPUT_INDICES = {2, 3, 4, 5, 7}
AUSTRIAN_INPUT_INDICES = {6, 8}

COUNTRY_BY_EPSG = {
    28992: "Netherlands",
    25832: "Germany",
    31254: "Austria",
    2056: "Switzerland",
}


def stage_output(file, directory, suffix, *, extension=None):
    """Return a generated output path inside its processing-stage directory."""
    directory.mkdir(parents=True, exist_ok=True)
    if extension is None:
        extension = file.suffix
    return directory / f"{file.stem}{suffix}{extension}"


def reuse_existing_output(file, directory, suffix, *, extension=None):
    """Return a previously generated output instead of regenerating it."""
    output_path = stage_output(file, directory, suffix, extension=extension)
    if REUSE_EXISTING_OUTPUTS and output_path.exists():
        print(f"Reusing existing output: {output_path.name}")
        return output_path
    return None


#===========================================
#Process DEM
#===========================================
def reproject(file,crs):
    # Open the source file.
    source = gdal.Open(str(file))

    #error handling no source
    if source is None:
        raise FileNotFoundError(f"Could not open raster: {file}")

    source_crs = CRS.from_wkt(source.GetProjection()).to_2d()
    target_crs = CRS.from_user_input(TARGET_CRS).to_2d()
    output_path = stage_output(file, REPROJECTED_DIR, "_reprojected")
    existing_path = reuse_existing_output(file, REPROJECTED_DIR, "_reprojected")
    if existing_path is not None:
        return existing_path
    if output_path.exists():
        output_path.unlink()
    aux_path = Path(f"{output_path}.aux.xml")
    if aux_path.exists():
        aux_path.unlink()

    result = gdal.Warp(
        str(output_path),
        source,
        srcSRS=source_crs.to_wkt(),
        dstSRS=target_crs.to_wkt(),
        resampleAlg="bilinear",
        outputType=gdal.GDT_Float32,
        srcNodata=-9999,
        dstNodata=-9999,
        format="GTiff",
    )
    if result is None:
        raise RuntimeError(f"Could not reproject raster: {file}")

    result = None
    source = None
    return output_path


def transform_vertical_heights(file, source_vertical_epsg, suffix="_EVRF2007"):
    """Convert a raster's source vertical CRS to EVRF2007 in place."""
    output_path = stage_output(file, VERTICAL_DIR, suffix)
    existing_path = reuse_existing_output(file, VERTICAL_DIR, suffix)
    if existing_path is not None:
        return existing_path
    if output_path.exists():
        output_path.unlink()

    source = gdal.Open(str(file))
    if source is None:
        raise FileNotFoundError(f"Could not open raster: {file}")
    source_array = source.GetRasterBand(1).ReadAsArray().astype(np.float32)
    nodata = source.GetRasterBand(1).GetNoDataValue()
    transform = source.GetGeoTransform()
    columns, rows = np.meshgrid(
        np.arange(source.RasterXSize),
        np.arange(source.RasterYSize),
    )
    x = transform[0] + (columns + 0.5) * transform[1]
    y = transform[3] + (rows + 0.5) * transform[5]
    valid = np.isfinite(source_array)
    if nodata is not None:
        valid &= ~np.isclose(source_array, nodata)

    target_array = source_array.copy()
    transformer_group = TransformerGroup(
        CRS.from_user_input(f"{TARGET_CRS}+{source_vertical_epsg}"),
        CRS.from_user_input(f"{TARGET_CRS}+{TARGET_VERTICAL_CRS.split(':')[-1]}"),
        always_xy=True,
    )
    if not transformer_group.transformers:
        raise RuntimeError(
            f"No transformation available from vertical EPSG:{source_vertical_epsg} "
            f"to {TARGET_VERTICAL_CRS}"
        )
    transformer = transformer_group.transformers[0]
    if "ballpark" in transformer.description.lower():
        print(
            f"Warning: PROJ is using a ballpark vertical transformation for "
            f"EPSG:{source_vertical_epsg} -> {TARGET_VERTICAL_CRS}; "
            "install the required PROJ grid for an official correction."
        )
    _, _, transformed_heights = transformer.transform(
        x[valid], y[valid], source_array[valid]
    )
    target_array[valid] = transformed_heights

    result = gdal.Translate(str(output_path), source, format="GTiff")
    source = None
    if result is None:
        raise RuntimeError(f"Could not create vertical-adjustment raster: {file}")
    result = None
    target = gdal.Open(str(output_path), gdal.GA_Update)
    target.GetRasterBand(1).WriteArray(target_array)
    target.FlushCache()
    target = None
    return output_path


def apply_constant_height_offset(file, offset):
    """Write a copy of a DTM with a constant vertical offset applied."""
    output_path = stage_output(file, VERTICAL_DIR, "_austrian_compensated")
    source = gdal.Open(str(file))
    if source is None:
        raise FileNotFoundError(f"Could not open raster: {file}")
    array = source.GetRasterBand(1).ReadAsArray().astype(np.float32)
    nodata = source.GetRasterBand(1).GetNoDataValue()
    valid = np.isfinite(array)
    if nodata is not None:
        valid &= ~np.isclose(array, nodata)
    array[valid] += offset

    if output_path.exists():
        output_path.unlink()
    result = gdal.Translate(str(output_path), source, format="GTiff")
    source = None
    if result is None:
        raise RuntimeError(f"Could not create compensated raster: {file}")
    result = None
    target = gdal.Open(str(output_path), gdal.GA_Update)
    target.GetRasterBand(1).WriteArray(array)
    target.FlushCache()
    target = None
    return output_path


def crs_transformation_info(file):
    """Describe the PROJ operation from a source raster CRS to TARGET_CRS."""
    dataset = gdal.Open(str(file))
    if dataset is None:
        raise FileNotFoundError(f"Could not open raster: {file}")

    source_crs = CRS.from_wkt(dataset.GetProjection()).to_2d()
    target_crs = CRS.from_user_input(TARGET_CRS).to_2d()
    source_epsg = source_crs.to_epsg()
    target_epsg = target_crs.to_epsg()
    group = TransformerGroup(source_crs, target_crs, always_xy=True)
    selected = group.transformers[0] if group.transformers else None
    best_unavailable = (
        group.unavailable_operations[0]
        if group.unavailable_operations
        else None
    )

    return {
        "file": file.name,
        "country": COUNTRY_BY_EPSG.get(source_epsg, "Unknown"),
        "source_epsg": source_epsg or "",
        "source_crs": source_crs.name,
        "target_epsg": target_epsg or "",
        "target_crs": target_crs.name,
        "selected_operation": selected.description if selected else "",
        "selected_accuracy_m": selected.accuracy if selected else "",
        "best_unavailable_operation": best_unavailable.name if best_unavailable else "",
        "best_unavailable_grids": "; ".join(
            grid.short_name
            for grid in best_unavailable.grids
        ) if best_unavailable else "",
    }


def save_crs_transformations(records, output_path):
    """Save official CRS transformation metadata for every input raster."""
    import csv

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        output_path.write_text("", encoding="utf-8")
        return

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def fill_nodata(file):
    #gdal exceptions
    gdal.UseExceptions()

    #output path for filled file
    filled_path = stage_output(file, FILLED_DIR, "_filled")
    existing_path = reuse_existing_output(file, FILLED_DIR, "_filled")
    if existing_path is not None:
        return existing_path
    if filled_path.exists():
        filled_path.unlink()
    aux_path = Path(f"{filled_path}.aux.xml")
    if aux_path.exists():
        aux_path.unlink()
    gdal.Translate(str(filled_path), str(file), format="GTiff")

    #fill function
    et = gdal.Open(str(filled_path), gdal.GA_Update)
    et_band = et.GetRasterBand(1)

    result = gdal.FillNodata(
        targetBand=et_band,
        maskBand=None,
        maxSearchDist=5,
        smoothingIterations=0,
    )

    et = None
    return filled_path

def hillshade(file):
    #file open 
    hillshade_path = stage_output(file, HILLSHADE_DIR, "_hillshade")
    existing_path = reuse_existing_output(file, HILLSHADE_DIR, "_hillshade")
    if existing_path is not None:
        return existing_path
    if hillshade_path.exists():
        hillshade_path.unlink()
    aux_path = Path(f"{hillshade_path}.aux.xml")
    if aux_path.exists():
        aux_path.unlink()

    #hillshade
    gdal.alg.raster.hillshade(
        input=file,
        output=hillshade_path
    )
    return hillshade_path


def ensure_resolution(file, target_resolution=2.0):
    """Resample the pixel grid without transforming the raster CRS or heights."""
    dataset = gdal.Open(str(file))
    if dataset is None:
        raise FileNotFoundError(f"Could not open raster: {file}")

    transform = dataset.GetGeoTransform()
    pixel_width, pixel_height = transform[1], transform[5]
    current_width = abs(pixel_width)
    current_height = abs(pixel_height)
    if (
        np.isclose(current_width, target_resolution, atol=1e-6)
        and np.isclose(current_height, target_resolution, atol=1e-6)
    ):
        dataset = None
        print(f"Keeping {file.name}: already {target_resolution:g} m resolution")
        return file

    output_path = stage_output(
        file,
        RESAMPLED_DIR,
        f"_{target_resolution:g}m",
    )
    existing_path = reuse_existing_output(
        file,
        RESAMPLED_DIR,
        f"_{target_resolution:g}m",
    )
    if existing_path is not None:
        return existing_path
    if output_path.exists():
        output_path.unlink()
    aux_path = Path(f"{output_path}.aux.xml")
    if aux_path.exists():
        aux_path.unlink()

    target_width = max(1, round(dataset.RasterXSize * current_width / target_resolution))
    target_height = max(1, round(dataset.RasterYSize * current_height / target_resolution))

    result = gdal.Translate(
        str(output_path),
        dataset,
        format="GTiff",
        width=target_width,
        height=target_height,
        resampleAlg="bilinear",
        outputType=gdal.GDT_Float32,
        creationOptions=["COMPRESS=LZW"],
    )
    dataset = None
    if result is None:
        raise RuntimeError(f"Could not resample raster: {file}")

    result = None
    print(f"Resampled {file.name}: {current_width:g} m -> {target_resolution:g} m")
    return output_path


def raster_extent(file):
    """Return GDAL's projected extent as (xmin, xmax, ymin, ymax)."""
    info = gdal.Info(str(file), format="json")
    if not info or "geoTransform" not in info or "size" not in info:
        raise FileNotFoundError(f"Could not read raster metadata: {file}")

    transform = info["geoTransform"]
    width, height = info["size"]

    x_min = transform[0]
    x_max = transform[0] + width * transform[1]
    y_max = transform[3]
    y_min = transform[3] + height * transform[5]
    return (
        min(x_min, x_max),
        max(x_min, x_max),
        min(y_min, y_max),
        max(y_min, y_max),
    )


def rasters_overlap(file1, file2, minimum_fraction=MIN_OVERLAP_FRACTION):
    """Return whether two rasters have enough projected overlap to match."""
    xmin1, xmax1, ymin1, ymax1 = raster_extent(file1)
    xmin2, xmax2, ymin2, ymax2 = raster_extent(file2)

    overlap_width = min(xmax1, xmax2) - max(xmin1, xmin2)
    overlap_height = min(ymax1, ymax2) - max(ymin1, ymin2)
    if overlap_width <= 0 or overlap_height <= 0:
        return False

    area1 = (xmax1 - xmin1) * (ymax1 - ymin1)
    area2 = (xmax2 - xmin2) * (ymax2 - ymin2)
    overlap_area = overlap_width * overlap_height
    return overlap_area / min(area1, area2) >= minimum_fraction


def save_pair_statistics(statistics_by_pair, output_path):
    """Save height-difference statistics for retained pairs."""
    import csv

    if not statistics_by_pair:
        output_path.write_text("", encoding="utf-8")
        return

    fieldnames = ["image1", "image2"] + list(next(iter(statistics_by_pair.values())).keys())
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for (image1_index, image2_index), statistics in statistics_by_pair.items():
            row = {
                "image1": image1_index + 1,
                "image2": image2_index + 1,
                **statistics,
            }
            writer.writerow(row)


def save_pair_transforms(transforms_by_pair, output_path):
    """Save retained SIFT image-registration affine matrices as CSV rows."""
    import csv

    fieldnames = [
        "image1",
        "image2",
        "a11",
        "a12",
        "tx",
        "a21",
        "a22",
        "ty",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for (image1_index, image2_index), transform in transforms_by_pair.items():
            writer.writerow({
                "image1": image1_index + 1,
                "image2": image2_index + 1,
                "a11": float(transform[0, 0]),
                "a12": float(transform[0, 1]),
                "tx": float(transform[0, 2]),
                "a21": float(transform[1, 0]),
                "a22": float(transform[1, 1]),
                "ty": float(transform[1, 2]),
            })


#===========================================
#SIFT
#===========================================
def _sift_detector(**kwargs):
    """Build the project's standard SIFT detector configuration."""
    defaults = dict(
        nOctaveLayers=5,
        contrastThreshold=0.005,
        edgeThreshold=16,
        sigma=1.6,
    )
    defaults.update(kwargs)
    return cv2.SIFT_create(**defaults)


def _normalized_hillshade_array(file):
    """Open a hillshade and normalize it to uint8 for SIFT."""
    image = gdal.Open(str(file))
    if image is None:
        raise FileNotFoundError(f"Could not open hillshade: {file}")

    hillshade = image.GetRasterBand(1).ReadAsArray().astype(np.float32)
    hillshade = np.nan_to_num(hillshade, nan=0.0)
    hill_min = float(np.min(hillshade))
    hill_max = float(np.max(hillshade))
    if hill_max == hill_min:
        raise ValueError(f"Hillshade has no variation: {file}")

    normalized = (hillshade - hill_min) / (hill_max - hill_min)
    normalized = np.clip(normalized, 0.0, 1.0)
    return (normalized * 255).astype(np.uint8)


def _compute_sift_features(image, *, keypoints=None, detector_kwargs=None):
    """Compute keypoints and descriptors from a normalized hillshade array."""
    detector = _sift_detector(**(detector_kwargs or {}))
    if keypoints is None:
        return detector.detectAndCompute(image, None)
    return detector.compute(image, keypoints)


def descriptors_from_keypoints(keypoints, hillshade_file):
    """Calculate SIFT descriptors for existing keypoints."""
    image = _normalized_hillshade_array(hillshade_file)
    _, descriptors = _compute_sift_features(
        image,
        keypoints=keypoints,
        detector_kwargs={
            "nOctaveLayers": 3,
            "contrastThreshold": 0.04,
            "edgeThreshold": 2,
        },
    )
    return descriptors


def match_descriptors(desc1, desc2, ratio=0.75):
    """Match descriptor arrays, or recover them when keypoints are supplied."""
    if isinstance(desc1, (list, tuple)) and isinstance(desc2, (list, tuple)):
        hillshade1 = HILLSHADE_DIR / (
            f"{FILE1.stem}_reprojected_2m_filled_hillshade{FILE1.suffix}"
        )
        hillshade2 = HILLSHADE_DIR / (
            f"{FILE2.stem}_reprojected_2m_filled_hillshade{FILE2.suffix}"
        )
        desc1 = descriptors_from_keypoints(desc1, hillshade1)
        desc2 = descriptors_from_keypoints(desc2, hillshade2)

    if desc1 is None or desc2 is None:
        return []

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    raw_matches = matcher.knnMatch(desc1, desc2, k=2)
    reverse_matches = matcher.knnMatch(desc2, desc1, k=2)

    reverse_good = {}
    for pair in reverse_matches:
        if len(pair) == 2:
            match, second_match = pair
            if match.distance < ratio * second_match.distance:
                reverse_good[match.queryIdx] = match.trainIdx

    good_matches = []
    for pair in raw_matches:
        if len(pair) == 2:
            match, second_match = pair
            if (
                match.distance < ratio * second_match.distance
                and reverse_good.get(match.trainIdx) == match.queryIdx
            ):
                good_matches.append(match)

    return good_matches


def filter_geometric_matches(keypoints1, keypoints2, matches, threshold=4.0):
    """Keep matches agreeing with one affine transform and return that transform."""
    if len(matches) < 3:
        return [], None

    points1 = np.float32([keypoints1[match.queryIdx].pt for match in matches])
    points2 = np.float32([keypoints2[match.trainIdx].pt for match in matches])
    transform, inlier_mask = cv2.estimateAffinePartial2D(
        points1,
        points2,
        method=cv2.RANSAC,
        ransacReprojThreshold=threshold,
        maxIters=5000,
        confidence=0.99,
        refineIters=10,
    )

    if transform is None or inlier_mask is None:
        return [], None

    inliers = [
        match
        for match, is_inlier in zip(matches, inlier_mask.ravel())
        if is_inlier
    ]
    return inliers, transform


def pixel_to_map(transform, column, row):
    """Convert a raster pixel coordinate to projected map coordinates."""
    map_x = transform[0] + column * transform[1] + row * transform[2]
    map_y = transform[3] + column * transform[4] + row * transform[5]
    return map_x, map_y


def extract_match_heights(dem_file1, dem_file2, keypoints1, keypoints2, matches):
    """Return matched pixel/map coordinates and elevations from both DEMs."""
    dataset1 = gdal.Open(str(dem_file1))
    dataset2 = gdal.Open(str(dem_file2))
    if dataset1 is None or dataset2 is None:
        raise FileNotFoundError("Could not open one of the DEM files for sampling.")

    array1 = dataset1.GetRasterBand(1).ReadAsArray()
    array2 = dataset2.GetRasterBand(1).ReadAsArray()
    nodata1 = dataset1.GetRasterBand(1).GetNoDataValue()
    nodata2 = dataset2.GetRasterBand(1).GetNoDataValue()
    transform1 = dataset1.GetGeoTransform()
    transform2 = dataset2.GetGeoTransform()

    records = []
    for match in matches:
        x1, y1 = keypoints1[match.queryIdx].pt
        x2, y2 = keypoints2[match.trainIdx].pt
        column1, row1 = int(round(x1)), int(round(y1))
        column2, row2 = int(round(x2)), int(round(y2))

        if not (
            0 <= row1 < array1.shape[0]
            and 0 <= column1 < array1.shape[1]
            and 0 <= row2 < array2.shape[0]
            and 0 <= column2 < array2.shape[1]
        ):
            continue

        height1 = float(array1[row1, column1])
        height2 = float(array2[row2, column2])
        if not np.isfinite(height1) or not np.isfinite(height2):
            continue
        if (nodata1 is not None and np.isclose(height1, nodata1)) or (
            nodata2 is not None and np.isclose(height2, nodata2)
        ):
            continue
        map_x1, map_y1 = pixel_to_map(transform1, column1, row1)
        map_x2, map_y2 = pixel_to_map(transform2, column2, row2)
        difference = height2 - height1
        dx = abs(map_x1-map_x2)
        dy = abs(map_y1-map_y2)
        records.append({
            "image1_column": column1,
            "image1_row": row1,
            "image2_column": column2,
            "image2_row": row2,
            "image1_x": map_x1,
            "image1_y": map_y1,
            "image2_x": map_x2,
            "image2_y": map_y2,
            "d_x": dx,
            "d_y": dy,
            "height1": height1,
            "height2": height2,
            "difference_height2_minus_height1": difference,
            "absolute_difference": abs(difference),
        })

    dataset1 = None
    dataset2 = None
    return records


def estimate_austrian_offset(pair_records):
    """Estimate one shared median vertical offset for all Austrian rasters."""
    offset_samples = []
    for (image1_index, image2_index), records in pair_records.items():
        differences = [
            record["difference_height2_minus_height1"]
            for record in records
        ]
        if image1_index in AUSTRIAN_INPUT_INDICES and image2_index not in AUSTRIAN_INPUT_INDICES:
            offset_samples.extend(differences)
        elif image2_index in AUSTRIAN_INPUT_INDICES and image1_index not in AUSTRIAN_INPUT_INDICES:
            offset_samples.extend(-np.asarray(differences))

    return float(np.median(offset_samples)) if offset_samples else 0.0


def apply_height_offset(records, image1_index, image2_index, offset):
    """Apply one shared Austrian offset and refresh height differences."""
    offset1 = offset if image1_index in AUSTRIAN_INPUT_INDICES else 0.0
    offset2 = offset if image2_index in AUSTRIAN_INPUT_INDICES else 0.0
    for record in records:
        record["height1"] += offset1
        record["height2"] += offset2
        difference = record["height2"] - record["height1"]
        record["difference_height2_minus_height1"] = difference
        record["absolute_difference"] = abs(difference)


def summarize_height_differences(records):
    """Calculate descriptive statistics for matched DEM height differences."""
    differences = np.array(
        [record["difference_height2_minus_height1"] for record in records],
        dtype=np.float64,
    )
    dx = np.array(
        [record["d_x"] for record in records],
        dtype=np.float64
    )

    dy = np.array(
            [record["d_y"] for record in records],
            dtype=np.float64
        )
    
    if differences.size == 0:
        return {"count": 0}

    return {
        "count": int(differences.size),
        "mean_difference": float(np.mean(differences)),
        "median_difference": float(np.median(differences)),
        "std_difference": float(np.std(differences, ddof=1)) if differences.size > 1 else 0.0,
        "mean_absolute_difference": float(np.mean(np.abs(differences))),
        "rmse_difference": float(np.sqrt(np.mean(differences ** 2))),
        "minimum_difference": float(np.min(differences)),
        "maximum_difference": float(np.max(differences)),
        "": "",
        "x_min": float(np.min(dx)),
        "x_max": float(np.max(dx)),
        "x_med": float(np.median(dx)),
        "x_std": float(np.std(dx)),
        "y_min": float(np.min(dy)),
        "y_max": float(np.max(dy)),
        "y_med": float(np.median(dy)),
        "y_std": float(np.std(dy))
    }


def save_match_height_data(records, output_path):
    """Save matched height records as a CSV file."""
    import csv

    if not records:
        output_path.write_text("", encoding="utf-8")
        return

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


#===========================================
#Visualisation
#===========================================

def draw_matches(file1, keypoints1, file2, keypoints2, matches):
    """Draw full hillshade images side by side without cropping them."""
    image1 = _normalized_hillshade_array(file1)
    image2 = _normalized_hillshade_array(file2)

    return cv2.drawMatches(
        image1,
        keypoints1,
        image2,
        keypoints2,
        matches,
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )


def save_match_visualization(file1, keypoints1, file2, keypoints2, matches):
    """Save the full-image match visualization beside this script."""
    output = draw_matches(file1, keypoints1, file2, keypoints2, matches)
    output_path = RESULTS_DIR / "sift_matches_v2.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), output)
    print(f"Saved match visualization to {output_path.name}")


def draw_multi_matches(hillshades, keypoints, pair_matches):
    """Draw each retained image pair in its own grid cell."""
    images = [_normalized_hillshade_array(file) for file in hillshades]
    cells = []
    cell_width = 1200
    cell_height = 620

    for (image1_index, image2_index), matches in pair_matches.items():
        pair_image = cv2.drawMatches(
            images[image1_index],
            keypoints[image1_index],
            images[image2_index],
            keypoints[image2_index],
            rd.sample(matches,20),
            None,
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        )
        available_width = cell_width - 20
        available_height = cell_height - 60
        scale = min(
            available_width / pair_image.shape[1],
            available_height / pair_image.shape[0],
        )
        resized = cv2.resize(
            pair_image,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA,
        )
        cell = np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
        x_offset = (cell_width - resized.shape[1]) // 2
        y_offset = 45 + (available_height - resized.shape[0]) // 2
        cell[y_offset:y_offset + resized.shape[0], x_offset:x_offset + resized.shape[1]] = resized
        cv2.putText(
            cell,
            f"Images {image1_index + 1} and {image2_index + 1}  |  {len(matches)} matches",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cells.append(cell)

    if not cells:
        return np.zeros((cell_height, cell_width, 3), dtype=np.uint8)

    columns = 2
    rows = int(np.ceil(len(cells) / columns))
    canvas = np.zeros((rows * cell_height, columns * cell_width, 3), dtype=np.uint8)
    for cell_index, cell in enumerate(cells):
        row = cell_index // columns
        column = cell_index % columns
        y_start = row * cell_height
        x_start = column * cell_width
        canvas[y_start:y_start + cell_height, x_start:x_start + cell_width] = cell

    return canvas


def save_multi_match_visualization(hillshades, keypoints, pair_matches):
    """Save one visualization containing all input images and pair matches."""
    output = draw_multi_matches(hillshades, keypoints, pair_matches)
    output_path = RESULTS_DIR / "sift_multi_matches.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), output)
    print(f"Saved multi-image visualization to {output_path.name}")



if __name__ == "__main__":
    gdal.UseExceptions()
    #input_files = (FILE1, FILE2, FILE3, FILE4,FILE5)
    #input_files = (FILE6,FILE7,FILE8,FILE9)
    input_files = (FILE1, FILE2, FILE3, FILE4,FILE5, FILE6,FILE7,FILE8,FILE9)
    crs_transformations = [crs_transformation_info(file) for file in input_files]
    save_crs_transformations(
        crs_transformations,
        RESULTS_DIR / "crs_transformations.csv",
    )
    resolution_files = []
    for input_index, input_file in enumerate(input_files):
        reprojected_file = reproject(input_file,TARGET_CRS)
        resolution_file = ensure_resolution(reprojected_file)
        if APPLY_DUTCH_VERTICAL_TRANSFORM and input_index in AHN_INPUT_INDICES:
            resolution_file = transform_vertical_heights(
                resolution_file,
                source_vertical_epsg=5709,
            )
        if APPLY_GERMAN_VERTICAL_TRANSFORM and input_index in GERMAN_INPUT_INDICES:
            resolution_file = transform_vertical_heights(
                resolution_file,
                source_vertical_epsg=7837,
            )
        resolution_files.append(resolution_file)

    overlap_pairs = set()
    for image1_index, image2_index in combinations(range(len(resolution_files)), 2):
        if rasters_overlap(
            resolution_files[image1_index],
            resolution_files[image2_index],
        ):
            overlap_pairs.add((image1_index, image2_index))
        else:
            print(
                f"Skipping images {image1_index + 1}-{image2_index + 1}: "
                "no projected overlap"
            )

    active_indices = sorted({index for pair in overlap_pairs for index in pair})
    if len(active_indices) < 2:
        raise RuntimeError("Fewer than two input rasters overlap; nothing to match.")

    dem_files = [resolution_files[index] for index in active_indices]

    hillshades = []
    keypoints = []
    descriptors = []
    aligned_dem_files = []
    for resolution_file in dem_files:
        filled_path = fill_nodata(resolution_file)
        hillshade_path = hillshade(filled_path)
        normalized = _normalized_hillshade_array(hillshade_path)
        sift_out, desc_out = _compute_sift_features(normalized)
        aligned_dem_files.append(filled_path)
        hillshades.append(hillshade_path)
        keypoints.append(sift_out)
        descriptors.append(desc_out)

    # Match every unique pair and keep the pair indices for later visualization.
    pair_matches = {}
    pair_statistics = {}
    pair_transforms = {}
    pair_records = {}
    for image1_index, image2_index in combinations(range(len(descriptors)), 2):
        original_pair = (
            active_indices[image1_index],
            active_indices[image2_index],
        )
        if original_pair not in overlap_pairs:
            continue

        display_pair = (original_pair[0] + 1, original_pair[1] + 1)

        matches = match_descriptors(
            descriptors[image1_index],
            descriptors[image2_index],
        )
        print(
            f"Images {display_pair[0]}-{display_pair[1]} "
            f"descriptor matches: {len(matches)}"
        )

        matches, transform = filter_geometric_matches(
            keypoints[image1_index],
            keypoints[image2_index],
            matches,
        )
        print(
            f"Images {display_pair[0]}-{display_pair[1]} "
            f"geometric matches: {len(matches)}"
        )

        if len(matches) < 10:
            print(
                f"Skipping images {display_pair[0]}-{display_pair[1]}: "
                "fewer than 10 geometric matches"
            )
            continue

        pair_matches[(image1_index, image2_index)] = matches
        pair_transforms[original_pair] = transform

        height_records = extract_match_heights(
            aligned_dem_files[image1_index],
            aligned_dem_files[image2_index],
            keypoints[image1_index],
            keypoints[image2_index],
            matches,
        )
        pair_records[original_pair] = height_records

    austrian_offset = 0.0
    if APPLY_AUSTRIAN_HEIGHT_COMPENSATION:
        austrian_offset = estimate_austrian_offset(pair_records)
        print(f"Applying shared Austrian height compensation: {austrian_offset:.4f} m")
        for image_index in AUSTRIAN_INPUT_INDICES:
            apply_constant_height_offset(
                resolution_files[image_index],
                austrian_offset,
            )

    for original_pair, height_records in pair_records.items():
        image1_index, image2_index = original_pair
        if APPLY_AUSTRIAN_HEIGHT_COMPENSATION:
            apply_height_offset(
                height_records,
                image1_index,
                image2_index,
                austrian_offset,
            )

        display_pair = (image1_index + 1, image2_index + 1)
        statistics = summarize_height_differences(height_records)
        pair_statistics[original_pair] = statistics
        print(
            f"Images {display_pair[0]}-{display_pair[1]} mean height difference: "
            f"{statistics.get('mean_difference', 0.0):.4f} m"
        )
        print(
            f"Images {display_pair[0]}-{display_pair[1]} height std: "
            f"{statistics.get('std_difference', 0.0):.4f} m"
        )
        save_match_height_data(
            height_records,
            RESULTS_DIR / f"matched_heights_{display_pair[0]}_{display_pair[1]}.csv",
        )

    save_pair_statistics(
        pair_statistics,
        RESULTS_DIR / "pair_height_statistics.csv",
    )
    save_pair_transforms(
        pair_transforms,
        RESULTS_DIR / "pair_transforms.csv",
    )

    save_multi_match_visualization(hillshades, keypoints, pair_matches)