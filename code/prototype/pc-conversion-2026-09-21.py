"""
Stitch two overlapping aerial lidar point clouds.

Pipeline:
  1. Read each LAS/LAZ, detect its source CRS (horizontal + vertical) from the file header.
  2. Reproject both to a common target CRS: ETRS89 (horizontal) + EVRF2007 (vertical, EPSG:5730).
     Horizontal UTM zone is auto-picked from the data's location unless you pass one.
  3. Voxel downsample + point-to-plane ICP to fine-align cloud B onto cloud A.
  4. Apply the transform to full-resolution cloud B, concatenate, write out one LAS/LAZ.

Usage:
    python stitch_lidar.py cloud_a.laz cloud_b.laz merged.laz [--utm-zone 32] [--voxel 0.3]

Deps: laspy[lazrs], open3d, pyproj, numpy
"""

import argparse
import numpy as np
import laspy
import open3d as o3d
from pyproj import CRS, Transformer

EVRF2007_EPSG = 5621  # European Vertical Reference Frame 2007 height (EPSG:5730 is EVRF2000 - don't confuse them)


def utm_zone_for(lon: float) -> int:
    return int((lon + 180) // 6) + 1


def target_crs_for(lon: float, utm_zone: int | None) -> CRS:
    zone = utm_zone or utm_zone_for(lon)
    horizontal_epsg = 25800 + zone  # ETRS89 / UTM zone N (25828-25837 etc.)
    return CRS.from_user_input(f"EPSG:{horizontal_epsg}+{EVRF2007_EPSG}")


def load_and_reproject(path: str, target: CRS) -> tuple[np.ndarray, laspy.LasData]:
    las = laspy.read(path, laz_backend=laspy.LazBackend.Laszip)
    src = las.header.parse_crs()
    if src is None:
        raise ValueError(f"{path}: no CRS in header, can't reproject. Pass it manually if known.")

    xyz = np.vstack([las.x, las.y, las.z]).T
    if CRS(src) != CRS(target):
        transformer = Transformer.from_crs(src, target, always_xy=True)
        x, y, z = transformer.transform(xyz[:, 0], xyz[:, 1], xyz[:, 2])
        xyz = np.column_stack([x, y, z])
    return xyz, las


def to_o3d(xyz: np.ndarray, voxel: float) -> o3d.geometry.PointCloud:
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(xyz)
    pc = pc.voxel_down_sample(voxel)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 3, max_nn=30))
    return pc


def register(xyz_a: np.ndarray, xyz_b: np.ndarray, voxel: float) -> np.ndarray:
    """Return 4x4 transform that aligns B onto A (point-to-plane ICP)."""
    pc_a = to_o3d(xyz_a, voxel)
    pc_b = to_o3d(xyz_b, voxel)
    result = o3d.pipelines.registration.registration_icp(
        pc_b, pc_a,
        max_correspondence_distance=voxel * 4,
        init=np.eye(4),
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )
    print(f"ICP fitness={result.fitness:.3f} rmse={result.inlier_rmse:.3f}")
    return result.transformation


def apply_transform(xyz: np.ndarray, T: np.ndarray) -> np.ndarray:
    homo = np.hstack([xyz, np.ones((len(xyz), 1))])
    return (homo @ T.T)[:, :3]


def common_dims(las_a: laspy.LasData, las_b: laspy.LasData, out_format: laspy.PointFormat) -> list[str]:
    """Point dimensions present in both inputs AND supported by the output point format."""
    skip = {"X", "Y", "Z"}  # handled separately as reprojected xyz
    dims_a = {d.name for d in las_a.point_format.dimensions}
    dims_b = {d.name for d in las_b.point_format.dimensions}
    out_dims = {d.name for d in out_format.dimensions}
    return sorted((dims_a & dims_b & out_dims) - skip)


def write_las(path: str, xyz: np.ndarray, las_a: laspy.LasData, las_b: laspy.LasData, target: CRS):
    # Force LAS 1.4 / point format 6: a compound CRS (horizontal+vertical) can only be
    # written as a WKT VLR, which laspy only emits for point format >= 6. Older formats
    # fall back to GeoTIFF keys, which can't represent a compound CRS and raise instead.
    point_format = laspy.PointFormat(6)
    header = laspy.LasHeader(point_format=point_format, version="1.4")
    header.add_crs(target)
    out = laspy.LasData(header)
    out.x, out.y, out.z = xyz[:, 0], xyz[:, 1], xyz[:, 2]

    dims = common_dims(las_a, las_b, point_format)
    print(f"Carrying over dimensions: {dims}")
    for dim in dims:
        values = np.concatenate([np.asarray(getattr(las_a, dim)), np.asarray(getattr(las_b, dim))])
        setattr(out, dim, values)

    # Extra dim marking which input file each point came from (1 = cloud_a, 2 = cloud_b)
    out.add_extra_dim(laspy.ExtraBytesParams(name="source_cloud", type=np.uint8))
    out.source_cloud = np.concatenate([
        np.full(len(las_a.points), 1, dtype=np.uint8),
        np.full(len(las_b.points), 2, dtype=np.uint8),
    ])

    out.write(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cloud_a")
    ap.add_argument("cloud_b")
    ap.add_argument("output")
    ap.add_argument("--utm-zone", type=int, default=None, help="Force ETRS89/UTM zone, e.g. 32")
    ap.add_argument("--voxel", type=float, default=0.3, help="Downsample voxel size (m) for ICP")
    args = ap.parse_args()

    # Peek at cloud A's CRS to pick a sensible UTM zone if not given
    probe = laspy.read(args.cloud_a)
    probe_crs = probe.header.parse_crs()
    lon = float(np.median(probe.x)) if probe_crs and probe_crs.is_geographic else 10.0
    target = target_crs_for(lon, args.utm_zone)
    print(f"Target CRS: {target.name}")

    xyz_a, las_a = load_and_reproject(args.cloud_a, target)
    xyz_b, las_b = load_and_reproject(args.cloud_b, target)

    T = register(xyz_a, xyz_b, args.voxel)
    xyz_b_aligned = apply_transform(xyz_b, T)

    merged = np.vstack([xyz_a, xyz_b_aligned])
    write_las(args.output, merged, las_a, las_b, target)
    print(f"Wrote {len(merged):,} points to {args.output}")


if __name__ == "__main__":
    main()
