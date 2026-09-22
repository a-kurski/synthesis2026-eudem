from pathlib import Path

import cv2
import numpy as np
from osgeo import gdal
from pyproj import CRS

crs = CRS.from_epsg(4326)

#===========================================
#Load DEM
#===========================================

BASE_DIR = Path(__file__).resolve().parent
FILE1 = BASE_DIR / "data" / "AHN5_M_193000_417000.TIF"
FILE2 = BASE_DIR / "data" / "dgm1_32_289_5736_1_nw_2024.tif"
TARGET_CRS = "EPSG:25832"


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
    output_path = file.with_name(f"{file.stem}_reprojected{file.suffix}")
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


def fill_nodata(file):
    #gdal exceptions
    gdal.UseExceptions()

    #output path for filled file
    filled_path = file.with_name(f"{file.stem.removesuffix('_reprojected')}_filled{file.suffix}")
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
    hillshade_path = file.with_name(f"{file.stem.removesuffix('_filled')}_hillshade{file.suffix}")
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


def ensure_resolution(file, target_resolution=5.0):
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

    output_path = file.with_name(f"{file.stem}_{target_resolution:g}m{file.suffix}")
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
        resampleAlg="average",
        outputType=gdal.GDT_Float32,
        creationOptions=["COMPRESS=LZW"],
    )
    dataset = None
    if result is None:
        raise RuntimeError(f"Could not resample raster: {file}")

    result = None
    print(f"Resampled {file.name}: {current_width:g} m -> {target_resolution:g} m")
    return output_path


def align_to_common_grid(files, target_resolution=5.0):
    """Put rasters on one shared grid while retaining their full union extent."""
    datasets = [gdal.Open(str(file)) for file in files]
    if any(dataset is None for dataset in datasets):
        raise FileNotFoundError("Could not open all rasters for common-grid alignment.")

    extents = []
    for dataset in datasets:
        transform = dataset.GetGeoTransform()
        width = dataset.RasterXSize
        height = dataset.RasterYSize
        x0 = transform[0]
        x1 = x0 + width * transform[1]
        y0 = transform[3]
        y1 = y0 + height * transform[5]
        extents.append((min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)))

    x_min = np.floor(min(extent[0] for extent in extents) / target_resolution) * target_resolution
    x_max = np.ceil(max(extent[1] for extent in extents) / target_resolution) * target_resolution
    y_min = np.floor(min(extent[2] for extent in extents) / target_resolution) * target_resolution
    y_max = np.ceil(max(extent[3] for extent in extents) / target_resolution) * target_resolution
    bounds = (x_min, y_min, x_max, y_max)

    aligned_files = []
    for file, dataset in zip(files, datasets):
        output_path = file.with_name(f"{file.stem}_common_grid{file.suffix}")
        if output_path.exists():
            output_path.unlink()
        aux_path = Path(f"{output_path}.aux.xml")
        if aux_path.exists():
            aux_path.unlink()

        result = gdal.Warp(
            str(output_path),
            dataset,
            format="GTiff",
            outputBounds=bounds,
            xRes=target_resolution,
            yRes=target_resolution,
            targetAlignedPixels=True,
            srcSRS=TARGET_CRS,
            dstSRS=TARGET_CRS,
            resampleAlg="bilinear",
            outputType=gdal.GDT_Float32,
            srcNodata=-9999,
            dstNodata=-9999,
            creationOptions=["COMPRESS=LZW"],
        )
        dataset = None
        if result is None:
            raise RuntimeError(f"Could not align raster: {file}")
        result = None
        aligned_files.append(output_path)

    print(f"Aligned {len(aligned_files)} rasters to one {target_resolution:g} m grid")
    return aligned_files


#===========================================
#SIFT
#===========================================
def sift(file):
    img = gdal.Open(file)
    if img is None:
            raise RuntimeError(f"Could not build hillshade for {img}")

    #convert hillshade to matrix
    hillshade = img.GetRasterBand(1).ReadAsArray().astype(np.float32)
    hillshade = np.nan_to_num(hillshade, nan=0.0)

    #get hillshade extremes
    hill_min = float(np.min(hillshade))
    hill_max = float(np.max(hillshade))

    #normalizing
    normalized = (hillshade - hill_min) / (hill_max - hill_min)
    normalized = np.clip(normalized, 0.0, 1.0)
    normalized = (normalized * 255).astype(np.uint8)

    sift = cv2.SIFT_create(
            nOctaveLayers=5,
            contrastThreshold=0.005,
            edgeThreshold=16,
            sigma=1.6,
    )
    keypoints, descriptors = sift.detectAndCompute(normalized, None)

    if keypoints is None or descriptors is None:
        return [], None
    return keypoints, descriptors

def load_normalized_hillshade(file):
    """Load and normalize a hillshade using the same steps as sift()."""
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


def descriptors_from_keypoints(keypoints, hillshade_file):
    """Calculate SIFT descriptors for existing keypoints."""
    image = load_normalized_hillshade(hillshade_file)
    detector = cv2.SIFT_create(
        nOctaveLayers=3,
        contrastThreshold=0.04,
        edgeThreshold=2,
        sigma=1.6,
    )
    _, descriptors = detector.compute(image, keypoints)
    return descriptors


def match_descriptors(desc1, desc2, ratio=0.75):
    """Match descriptor arrays, or recover them when keypoints are supplied."""
    if isinstance(desc1, (list, tuple)) and isinstance(desc2, (list, tuple)):
        hillshade1 = FILE1.with_name(
            f"{FILE1.stem}_hillshade{FILE1.suffix}"
        )
        hillshade2 = FILE2.with_name(
            f"{FILE2.stem}_hillshade{FILE2.suffix}"
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
    """Keep only matches that agree with one robust affine transformation."""
    if len(matches) < 3:
        return []

    points1 = np.float32([keypoints1[match.queryIdx].pt for match in matches])
    points2 = np.float32([keypoints2[match.trainIdx].pt for match in matches])
    _, inlier_mask = cv2.estimateAffinePartial2D(
        points1,
        points2,
        method=cv2.RANSAC,
        ransacReprojThreshold=threshold,
        maxIters=5000,
        confidence=0.99,
        refineIters=10,
    )

    if inlier_mask is None:
        return []

    return [
        match
        for match, is_inlier in zip(matches, inlier_mask.ravel())
        if is_inlier
    ]


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
    image1 = load_normalized_hillshade(file1)
    image2 = load_normalized_hillshade(file2)

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
    output_path = BASE_DIR / "sift_matches_v2.png"
    cv2.imwrite(str(output_path), output)
    print(f"Saved match visualization to {output_path.name}")



if __name__ == "__main__":
    gdal.UseExceptions()
    hillshades = []
    dem_files = []
    keypoints = []
    descriptors = []
    for input_file in (FILE1, FILE2):
        reprojected_file = reproject(input_file,TARGET_CRS)
        resolution_file = ensure_resolution(reprojected_file)
        dem_files.append(resolution_file)

    dem_files = align_to_common_grid(dem_files)
    hillshades = []
    keypoints = []
    descriptors = []
    aligned_dem_files = []
    for resolution_file in dem_files:
        filled_path = fill_nodata(resolution_file)
        hillshade_path = hillshade(filled_path)
        sift_out,desc_out = sift(hillshade_path)
        aligned_dem_files.append(filled_path)
        hillshades.append(hillshade_path)
        keypoints.append(sift_out)
        descriptors.append(desc_out)

    matches = match_descriptors(descriptors[0], descriptors[1])
    print(f"Descriptor matches: {len(matches)}")

    matches = filter_geometric_matches(
        keypoints[0],
        keypoints[1],
        matches,
    )
    print(f"Geometrically consistent matches: {len(matches)}")

    height_records = extract_match_heights(
        aligned_dem_files[0],
        aligned_dem_files[1],
        keypoints[0],
        keypoints[1],
        matches,
    )
    statistics = summarize_height_differences(height_records)
    save_match_height_data(
        height_records,
        BASE_DIR / "matched_heights.csv",
    )
    print(f"Height records: {len(height_records)}")
    for name, value in statistics.items():
        print(f"{name}: {value}")

    save_match_visualization(
        hillshades[0],
        keypoints[0],
        hillshades[1],
        keypoints[1],
        matches,
    )