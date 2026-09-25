target_crs = "EPSG:3035"  # e.g. ETRS89-extended / LAEA Europe — good for pan-European work
target_res = 5.0  # meters, pick based on your coarsest usable DTM resolution
from osgeo import gdal
from pathlib import Path

input_dir = Path("Prototype/SIFT_matching/data/resampled")
output_dir = Path("Prototype/grid_alignment/output")
output_dir.mkdir(exist_ok=True)

warp_options = gdal.WarpOptions(
    xRes=target_res,
    yRes=target_res,
    targetAlignedPixels=True,
    dstSRS=target_crs,
    resampleAlg="bilinear",
    format="GTiff",
    creationOptions=["COMPRESS=DEFLATE", "TILED=YES", "BIGTIFF=IF_SAFER"],
    multithread=True,
)

failed = []
for src_path in input_dir.glob("*.tif"):
    dst_path = output_dir / src_path.name
    try:
        ds = gdal.Warp(str(dst_path), str(src_path), options=warp_options)
        if ds is None:
            failed.append(src_path.name)
        ds = None  # flush/close
    except Exception as e:
        print(f"Failed: {src_path.name} — {e}")
        failed.append(src_path.name)

print(f"Done. {len(failed)} failures: {failed}")