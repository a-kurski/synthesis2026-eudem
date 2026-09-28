# Country preparation: Netherlands first

`main.py` is the new entry point for preparing national terrain data for a later
Rhine-catchment comparison. The Netherlands implementation is functional; the
country registry provides a small extension point for later implementations.
The original AHN–NRW comparison is preserved in `version_1/`; run its entry point
from that folder. See [the archive guide](../version_1/ARCHIVE.md).

## Organisation

```text
main.py                            entry point
config.netherlands.json            polygon, source, target and output settings
dtm/
  runtime.py                       shared QGIS/Python startup
  coordinator.py                   select country; plan, execute, log results
  target_grid.py                   common comparison-grid definition
  countries/
    netherlands/
      __init__.py                  native AHN rules and tile planning
      acquisition.py               AHN downloads, cache, receipts and probe
      processing.py                clean → mosaic → warp → clean/mask → verify
      hole_filling.py              optional native-grid gap filling and provenance
      stitching.py                 publish target-grid tiles and stitch exact pixels
  acquire.py                       existing WCS/cache/checksum helpers
  geo.py                           existing geometry, validity and grid checks
  process.py                       existing raster/GDAL operations
version_1/                         original comparison, source snapshot and data
```

The current workflow reuses its shared helper modules. Version 1 holds separate
snapshots of those helpers so its code stays independent. Netherlands-specific decisions
(AHN acquisition, native EPSG:28992/0.5 m, averaging to the German grid, unchanged
NAP heights) reside in the country package. The existing `align()` helper is
specifically the AHN-to-EPSG:25832 operation; future countries must supply their
own transformation rather than blindly call this AHN-specific helper.

## Commands

Run from this workspace using the ordinary Python launcher:

```powershell
python main.py config.netherlands.json --plan
python main.py config.netherlands.json --self-test
python main.py config.netherlands.json --probe
python main.py config.netherlands.json
python main.py config.netherlands.json --yes
```

`--plan` performs no network requests but writes a plan and logs. `--self-test`
runs offline synthetic tests. `--probe` downloads one tiny AHN tile, not the full
area. The ordinary run prints a plan and requests `DOWNLOAD`; `--yes` explicitly
starts unattended acquisition and preparation. No full acquisition is triggered
by creating this skeleton.

## Input and target grid

Change `aoi` to your polygon GeoPackage; paths are relative to the config file.
The current config explicitly uses `netherlands.gpkg`. The border shapefiles
are not implicitly substituted or used as clipping masks.
Supply `layer` when the GeoPackage has multiple layers.

By default, `target.reference_raster` is null. The polygon is transformed to
EPSG:25832 (ETRS89 / UTM zone 32N). Its bounding box is expanded outward to
whole-metre coordinates, defining a north-up 1 × 1 m grid covering the entire
polygon. The origin is on the whole-metre lattice. This includes NoData cells
outside the polygon's actual boundary and inside its holes.

The saved `target_grid.json` and tiny `target_grid.vrt` define the exact grid.
The VRT contains only grid geometry, **not German terrain elevations**. A later
country run can use this VRT as its `target.reference_raster` to use precisely
the same extent, dimensions and cell positions. Using only the same CRS is not
enough; separately planned AOIs can have different extents and array dimensions.

Alternatively supply a real German raster in `target.reference_raster` to match
its grid. It must be north-up, EPSG:25832, 1 m, and cover the entire supplied AOI.
An undersized reference fails before downloading instead of silently clipping
the requested area. This option copies the grid, not the reference's validity
mask or elevations.

## Netherlands operations

1. Validate config and polygon, preserving polygon holes.
2. Plan AHN-native WCS chunks intersecting the polygon.
3. Save the AOI hash, plan, settings and environment versions.
4. Fetch AHN service metadata; verify or download source tiles with the existing
   retry, checksum, full-read and native-grid validation.
5. Save the exact source manifest. The existing `version_1/data/ahn_tiles` cache is reused
   when settings and tile bounds match; NRW downloads are not performed.
6. Clean copies of tiles, converting masks, NoData, NaN/Inf and extreme sentinel
   values to `-9999` before aggregation. Preserve original downloads.
7. Build the cleaned AHN VRT and native 0.5 m mosaic.
   If filling is enabled, interpolate a separate native copy before its warp;
   also keep the unfilled branch. See the hole-filling section below.
8. Reproject/average AHN directly onto the planned 1 m target grid in one warp,
   using the existing exact-transform and no-vertical-shift settings.
9. Combine the final cleaning pass with polygon masking, producing Float32
   elevations in metres with `-9999` NoData. Keep the full target grid extent.
10. Verify final alignment and count valid AHN cells. With zero valid cells,
    leave the all-NoData output for inspection and fail without replacing the
    latest successful result.
11. Write finished target-grid tiles under `processed_tiles`, then stitch their
    explicit file list into `ahn_stitched/ahn.tif` without further resampling.
    Verify grid alignment and pixel-for-pixel equality with the prepared surface.
12. Record the successful result and its paths.

The AOI mask marks polygon membership, not AHN/NRW common coverage. AHN's missing
cells remain NoData in the baseline; filling can estimate some of them in a
separate output. No minimum fractional source coverage is imposed during
averaging. Heights remain in NAP: there is no vertical datum harmonisation.

## Outputs

New run IDs use `YYYY-MM-DD_HH-MM-SS` in Europe/Amsterdam time (including daylight
saving time), for example `2026-09-27_20-49-10`. Logs and outputs share this name.
Existing names are preserved; collisions receive `_02`, `_03`, etc.

```text
version_1/data/ahn_tiles/           reusable raw TIFFs and JSON receipts
data/prepared/netherlands/<run_id>/
  target_grid.json                  exact target definition
  target_grid.vrt                   portable geometry-only reference
  raw_ahn_tiles/                    newly downloaded raw TIFFs and JSON receipts
  processed_tiles/                  finished target-grid tiles and tiles.json
    _work/                         native mosaics, warps, masks and fill reports
  ahn_stitched/
    ahn.tif                        FINAL: selected surface, filled by default
    ahn_unfilled.tif                baseline when filling is enabled
    ahn_fill_fraction.tif           contribution fractions when filling is enabled
    *.vrt                          explicit processed-tile mosaics
  result.json                      grid, valid count, datum and output paths
data/prepared/netherlands/latest_run.json
logs/preparation/netherlands/<run_id>/
  config.json, plan.json, processing.log, source_manifest.json,
  ahn_GetCapabilities.xml, ahn_DescribeCoverage.xml, result.json
```

Processed tiles are non-overlapping windows of up to 1000 × 1000 target pixels
(1 km × 1 km), configurable with `processed_tile_size_pixels`. Edge tiles may
be smaller. They are not one-to-one copies of the skewed Dutch source tiles:
shared native-mosaic filling and warping use neighbouring terrain before cutting
the finished German-grid tiles. Intermediate files stay under `_work` for inspection.

The prepared raster is ready for later comparison once another terrain raster
is on the same grid. That later stage must intersect valid coverage and decide
how to handle vertical datums. It will compute differences and statistics; this
preparation stage does not subtract a German raster or generate comparison
statistics. The original comparison entry point remains available.

Advanced defaults are in `dtm/coordinator.py` and can be overridden in JSON:
NoData -9999, block size 512, alignment tolerance 1e-8 m, read timeout 300 s,
four download attempts, pause 0.25 s. This retains the existing QGIS/GDAL,
NumPy and Requests dependencies. Cached full runs still request service metadata;
derived products are rebuilt per run. Use one acquisition at a time per cache.

## Optional hole filling and fresh downloads

The Netherlands module now implements the native-grid interpolation stage. The
default enables it at a **20 m search distance**, with no smoothing.
Configurations without a `hole_filling` section also use these defaults.

```json
"reuse_cache": true,
"hole_filling": {
  "enabled": true,
  "method": "gdal_idw",
  "selection": "all_aoi_nodata",
  "max_distance_m": 20,
  "smoothing_iterations": 0
}
```

All missing native cells inside the original polygon are candidates, including
water. Only original valid AHN cells supply interpolation values. Estimates
outside the polygon or inside polygon holes are discarded. Original valid
native elevations and downloaded files are preserved. Large unsupported gaps
remain partly or completely NoData. Interpolated water areas are not measured
bathymetry. NAP remains unchanged.

The source acquisition polygon is buffered by the search radius plus one native
cell to obtain surrounding terrain. The final target grid and AOI are unchanged.
This may request additional boundary tiles, and the plan displays the buffer.
Changing the fill settings does not change the identity of existing raw tiles.

Command-line overrides take precedence over the JSON settings:

```powershell
# Inspect filling/context and cache settings without downloads
python main.py config.netherlands.json --plan --fill-holes
# Prepare filled AND unfilled outputs using the existing cache
python main.py config.netherlands.json --yes --fill-holes --reuse-cache
# No hole filling, but still reuse the cache
python main.py config.netherlands.json --yes --no-fill-holes
# Download everything fresh and do not fill holes
python main.py config.netherlands.json --yes --fresh-download --no-fill-holes
```

Every new download writes raw tiles under
`data/prepared/netherlands/<run_id>/raw_ahn_tiles`. With cache reuse enabled,
validated files from previous runs and the configured legacy cache are reused
in place; `source_manifest.json` records their actual locations. The raw folder
can therefore be empty for a fully cached run. `--fresh-download`
(`reuse_cache: false`) bypasses those caches without deleting them. Later runs
with reuse enabled automatically find these new raw folders under the same
output root. Filling and cache reuse are independent.

Filling adds these products to each run. The unfilled baseline is written
directly as `ahn_stitched/ahn_unfilled.tif`, without individual unfilled tiles
or an unfilled VRT. The final fill-fraction raster is
written directly as one full-grid TIFF under `ahn_stitched`; individual
fill-fraction tiles and a fill-fraction VRT are not created.

| Product | Meaning |
|---|---|
| `ahn_stitched/ahn_unfilled.tif` | Unfilled baseline, still produced. |
| `ahn_stitched/ahn.tif` | Filled alternative on the identical target grid. |
| `ahn_stitched/ahn_fill_fraction.tif` | 0–1 share of valid source contribution that was interpolated; remaining invalid cells are NoData. |
| `processed_tiles/_work/hole_filling/ahn_filled_native.tif` | Filled 0.5 m native mosaic. |
| `processed_tiles/_work/hole_filling/ahn_fill_mask_native.tif` | 1 only at accepted interpolated native cells. |
| `processed_tiles/_work/hole_filling/original_valid_mask.tif` | Fixed original-donor validity. |
| `processed_tiles/_work/hole_filling/aoi_mask_native.tif` | Native-grid candidate area. |
| `processed_tiles/_work/hole_filling/ahn_fill_fraction_native.tif` | Original valid=0, accepted fill=1, other cells=NoData. |
| `processed_tiles/_work/hole_filling/hole_filling_report.json` | Native counts/areas, target contribution statistics, settings and timing. |

`result.json` keeps `prepared_raster` pointing to the unfilled baseline for
compatibility. Its **`comparison_ready_raster`** points to the filled raster when
filling is enabled, otherwise to the baseline. Downstream code should use that
field when it wants the user's selected variant. Fraction values refer to valid
contributing terrain, not necessarily the entire physical target-cell footprint.

The algorithm uses a disk-backed mosaic copy and blockwise masks/merging. GDAL
temporary work files are directed to the run's hole-filling directory. Peak RAM
has not been benchmarked for a full-country run. The extra baseline, filled
branch and provenance products require additional disk space.

See [the cached-tile validation report](HOLE_FILLING_VALIDATION.md). Reproduce the
offline pilot with `python scripts/hole_filling_pilot.py config.netherlands.json`.
It selects three cached tiles intersecting the current AOI; it never downloads.

## Adding another country later

Create another package under `dtm/countries`, implementing the same five functions:
`validate_config(config)`, `plan(geometry, config)`,
`download(config, source_plan, log_dir)`, `probe(config, source_plan, log_dir)`,
and `prepare(tiles, geometry, reference, run_dir, config)`, plus `VERTICAL_NOTE`.
Register it in `COUNTRIES` in the coordinator. Each invocation selects one country.
Adapt the source-plan/report fields and metadata request count when a new source
does not use the same WCS acquisition pattern. There is no pretended support for
countries whose acquisition and transformation rules have not been implemented.

Keep the common target-grid contract. Each country owns its source CRS,
resolution, download conventions, NoData rules and any future vertical transforms.
Country outputs should report their actual vertical datum and preparation path.

## Validation on 26 September 2026

This initial validation preceded the move of the original workflow into
`version_1/`. The original 13 tests now live there. The current suite now contains
16 tests: 8 preparation checks and 8 hole-filling/control checks. All 16 passed
on 27 September 2026; see the linked hole-filling validation report.

- All 20 offline tests passed: the original 13 comparison tests and 7 preparation
  tests. Actual GDAL programs were used on small synthetic rasters.
- A spatially varying fixture with missing data was prepared and compared
  cell by cell with the existing clean/warp/clean sequence after the same AOI
  mask was applied. Values matched exactly; the polygon hole was excluded and
  the original raster checksum was unchanged.
- Empty AHN coverage failed without replacing the latest successful result.
- Both entry points completed offline planning for the actual study polygon.
  The new plan selects 982 AHN chunks and a 36,923 × 25,471-cell target grid.
- Tests required execution outside the desktop sandbox because its restrictions
  blocked temporary raster-file writes. No production download or full-area
  preparation was executed during implementation; live service behavior was
  not re-tested.
