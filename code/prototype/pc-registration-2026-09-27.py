#!/usr/bin/env python3
"""
Pairwise cross-border lidar alignment.

  1. extract_extents  - per-file header bbox, reprojected to ETRS89 -> csv
  2. find_intersections - bbox-intersecting file pairs across the two countries -> csv
  3. register_all     - open3d ICP per pair -> one row per pair in a csv:
                         full 4x4 transform + bbox-centre-based pure translation

ponytail notes:
  - Extent bbox is reprojected using its 4 corners only, not edge-densified.
    Fine at country-tile scale; upgrade if a tile straddles a projection
    singularity.
  - "Intersection" is bbox-vs-bbox (shapely), not the true point-cloud footprint.
    Cheap and sufficient as a candidate-pair filter before ICP.
  - register_pair loads full point clouds (no COPC-aware partial read) and
    ICP is seeded with identity, assuming the common-CRS reprojection already
    puts clouds close. Swap in RANSAC global registration first if a pair's
    initial offset can exceed max_corr.
  - "memory allocation of N bytes failed" with no Python traceback is a
    native allocator abort (lazrs/Rust or laszip/C), not a catchable
    exception - it means one file's header/chunk-table is corrupt enough
    that the decoder tries to allocate a garbage-sized buffer. That's why
    point loading runs in a subprocess: the parent survives the abort,
    names the offending file, and skips just that pair.
"""
import argparse
import csv
import itertools
import multiprocessing as mp
import tempfile
from pathlib import Path

import laspy
import numpy as np
from pyproj import CRS, Transformer
from shapely.geometry import box

LAZ_BACKENDS = {
    "auto": None,
    "lazrs": laspy.LazBackend.Lazrs,
    "lazrs-parallel": laspy.LazBackend.LazrsParallel,
    "laszip": laspy.LazBackend.Laszip,
}

ETRS89 = "EPSG:4258"        # geographic lon/lat, for reporting extents
ETRS89_LAEA = "EPSG:3035"   # projected metres, for ICP


def sanity_check_point_count(path, header):
    """Guard against a corrupted header point_count sending the LAZ decoder
    into a multi-hundred-GB allocation, which aborts the whole process at the
    C-runtime level (no Python exception to catch, no traceback). Real LAZ
    essentially never compresses below ~0.05 bytes/point; anything past that
    is treated as a corrupt/unsupported file and skipped instead of decoded."""
    size = Path(path).stat().st_size
    if size > 0 and header.point_count > 0 and header.point_count / size > 20:
        raise ValueError(
            f"{path}: header claims {header.point_count:,} points for only "
            f"{size:,} bytes - looks corrupted, refusing to decompress"
        )


def file_extent_etrs89(path):
    """(minx, miny, maxx, maxy, src_crs_wkt) in EPSG:4258 from a laz/copc.laz header."""
    with laspy.open(path, laz_backend=laspy.LazBackend.Lazrs) as f:
        h = f.header
        sanity_check_point_count(path, h)
        src_crs = h.parse_crs()
        if src_crs is None:
            raise ValueError(f"{path}: no CRS found in header")
        xs = [h.mins[0], h.maxs[0], h.mins[0], h.maxs[0]]
        ys = [h.mins[1], h.mins[1], h.maxs[1], h.maxs[1]]
    tr = Transformer.from_crs(src_crs, CRS(ETRS89), always_xy=True)
    ex, ey = tr.transform(xs, ys)
    return min(ex), min(ey), max(ex), max(ey), src_crs.to_wkt()


def extract_extents(directory, country, out_csv, append=False):
    """Step 2: write one extent row per laz/copc.laz file under `directory`."""
    files = sorted(Path(directory).rglob("*.laz"))
    write_header = not (append and Path(out_csv).exists())
    with open(out_csv, "a" if append else "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["country", "file", "minx", "miny", "maxx", "maxy", "src_crs_wkt"])
        for p in files:
            print(f"  header: {p}", flush=True)
            minx, miny, maxx, maxy, wkt = file_extent_etrs89(p)
            w.writerow([country, str(p), minx, miny, maxx, maxy, wkt])
    return out_csv


def find_intersections(extents_csv, out_csv):
    """Step 3: every bbox-intersecting (file_a, file_b) pair across the two countries."""
    import pandas as pd
    df = pd.read_csv(extents_csv, encoding="utf-8")
    countries = df["country"].unique()
    if len(countries) != 2:
        raise ValueError(f"expected exactly 2 countries in {extents_csv}, got {list(countries)}")
    a, b = df[df.country == countries[0]], df[df.country == countries[1]]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_a", "file_b", "country_a", "country_b",
                    "ix_minx", "ix_miny", "ix_maxx", "ix_maxy"])
        for ra, rb in itertools.product(a.itertuples(), b.itertuples()):
            box_a, box_b = box(ra.minx, ra.miny, ra.maxx, ra.maxy), box(rb.minx, rb.miny, rb.maxx, rb.maxy)
            if box_a.intersects(box_b):
                w.writerow([ra.file, rb.file, ra.country, rb.country, *box_a.intersection(box_b).bounds])
    return out_csv


def _load_points_worker(path, target_crs, backend, out_npy):
    """Runs in a child process: any native-allocator abort kills only this
    process, never the parent batch."""
    open_kwargs = {} if backend is None else {"laz_backend": backend}
    with laspy.open(path, **open_kwargs) as f:
        sanity_check_point_count(path, f.header)
        las = f.read()
    tr = Transformer.from_crs(las.header.parse_crs(), CRS(target_crs), always_xy=True)
    x, y = tr.transform(las.x, las.y)
    np.save(out_npy, np.column_stack([x, y, las.z]))


def load_points_common_crs(path, target_crs=ETRS89_LAEA, backend=None, timeout=1800):
    print(f"  points: {path}", flush=True)
    with tempfile.TemporaryDirectory() as td:
        out_npy = Path(td) / "pts.npy"
        ctx = mp.get_context("spawn")
        p = ctx.Process(target=_load_points_worker, args=(str(path), target_crs, backend, str(out_npy)))
        p.start()
        p.join(timeout)
        if p.is_alive():
            p.terminate()
            p.join()
            raise TimeoutError(f"{path}: point loading exceeded {timeout}s, terminated")
        if p.exitcode != 0:
            raise RuntimeError(
                f"{path}: point loading crashed (exit code {p.exitcode}) - "
                "file is likely corrupt or unsupported by the LAZ backend; skipping"
            )
        return np.load(out_npy)


def bbox_center(pts):
    return (pts.min(axis=0) + pts.max(axis=0)) / 2.0


def apply_transform(T, point):
    return (T @ np.append(point, 1.0))[:3]


def register_pair(file_a, file_b, voxel=1.0, max_corr=2.0, backend=None):
    """Step 4: point-to-plane ICP of file_b onto file_a, in a common projected CRS.
    Returns (4x4 T, fitness, rmse, center_of_b, pure_translation) where
    pure_translation = T applied to file_b's bbox centre, minus that centre -
    i.e. the rotation's effect is cancelled out at that one reference point,
    leaving just the local translation there."""
    import open3d as o3d
    pts_a = load_points_common_crs(file_a, backend=backend)
    pts_b = load_points_common_crs(file_b, backend=backend)
    pc_a, pc_b = o3d.geometry.PointCloud(), o3d.geometry.PointCloud()
    pc_a.points, pc_b.points = o3d.utility.Vector3dVector(pts_a), o3d.utility.Vector3dVector(pts_b)
    pc_a, pc_b = pc_a.voxel_down_sample(voxel), pc_b.voxel_down_sample(voxel)
    pc_a.estimate_normals()
    pc_b.estimate_normals()
    result = o3d.pipelines.registration.registration_icp(
        pc_b, pc_a, max_corr, np.eye(4),
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
    )
    T = result.transformation
    center_b = bbox_center(pts_b)
    pure_translation = apply_transform(T, center_b) - center_b
    return T, result.fitness, result.inlier_rmse, center_b, pure_translation


def register_all(intersections_csv, out_csv, backend=None):
    """Run register_pair for every candidate pair; write one row per pair to a csv:
    full 4x4 transform (flattened), fit stats, bbox centre used, and the
    centre-based pure translation. A pair whose point loading crashes or times
    out is logged and skipped rather than aborting the whole run."""
    import pandas as pd
    failures = []
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["file_a", "file_b", "fitness", "rmse"]
            + [f"m{i}{j}" for i in range(4) for j in range(4)]
            + ["center_x", "center_y", "center_z"]
            + ["translation_x", "translation_y", "translation_z"]
        )
        for row in pd.read_csv(intersections_csv, encoding="utf-8").itertuples():
            try:
                T, fitness, rmse, center_b, translation = register_pair(
                    row.file_a, row.file_b, backend=backend
                )
            except (RuntimeError, TimeoutError, ValueError) as e:
                print(f"  SKIPPED {row.file_a} / {row.file_b}: {e}", flush=True)
                failures.append((row.file_a, row.file_b, str(e)))
                continue
            w.writerow([row.file_a, row.file_b, fitness, rmse, *T.flatten(), *center_b, *translation])
    if failures:
        fail_csv = Path(out_csv).with_name(Path(out_csv).stem + "_failures.csv")
        with open(fail_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["file_a", "file_b", "error"])
            w.writerows(failures)
        print(f"{len(failures)} pair(s) skipped, logged to {fail_csv}", flush=True)
    return out_csv


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir_a"); ap.add_argument("country_a")
    ap.add_argument("dir_b"); ap.add_argument("country_b")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--laz-backend", choices=sorted(LAZ_BACKENDS), default="auto",
                     help="LAZ decoder to use for reading points (default: let laspy choose). "
                          "Try 'laszip' if 'lazrs' aborts on a specific file.")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    extents_csv = out / "extents.csv"
    extract_extents(args.dir_a, args.country_a, extents_csv, append=False)
    extract_extents(args.dir_b, args.country_b, extents_csv, append=True)

    intersections_csv = out / "intersections.csv"
    find_intersections(extents_csv, intersections_csv)

    register_all(intersections_csv, out / "transforms.csv", backend=LAZ_BACKENDS[args.laz_backend])


if __name__ == "__main__":
    main()
