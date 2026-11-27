# Country preparation: Netherlands first

`main.py` is the new entry point for preparing national terrain data for a later
Rhine-catchment comparison. The Netherlands and Germany/NRW implementations are functional; the
country registry provides an extension point for later implementations. See
[Germany / NRW preparation](GERMANY_NRW_PREPARATION.md).
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
  publication.py                   shared masking and exact tile publication
  paths.py                         country/region output and log namespaces
  countries/
    netherlands/
      __init__.py                  native AHN rules and tile planning
      acquisition.py               AHN downloads, cache, receipts and probe
      processing.py                clean → mosaic → warp → clean/mask → verify
      hole_filling.py              optional target-grid gap filling and provenance
      stitching.py                 compatibility import for shared publication
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
The current config explicitly uses `small_study_area.gpkg`. The border shapefiles
are not implicitly substituted or used as clipping masks.
Supply `layer` when the GeoPackage has multiple layers.

By default, `target.reference_raster` is null. The polygon is transformed to
EPSG:25832 (ETRS89 / UTM zone 32N). Its bounding box is expanded outward to
multiples of 5 m, defining a north-up 5 × 5 m grid covering the entire
polygon. Cell edges are on the zero-origin 5 m lattice; centres are 2.5 m from
those edges. EPSG:25832 specifies the CRS; this workflow additionally fixes the
grid resolution and origin. This includes NoData cells
outside the polygon's actual boundary and inside its holes.

The saved `target_grid.json` and tiny `target_grid.vrt` define the exact grid.
The VRT contains only grid geometry, **not German terrain elevations**. A later
country run can use this VRT as its `target.reference_raster` to use precisely
the same extent, dimensions and cell positions. Using only the same CRS is not
enough; separately planned AOIs can have different extents and array dimensions.

Alternatively supply a real German raster in `target.reference_raster` to match
its grid. It must be north-up, EPSG:25832, 5 m, have an origin on multiples of
5 m, and cover the entire supplied AOI. A previous 1 m reference is rejected
when the requested resolution is 5 m.
An undersized reference fails before downloading instead of silently clipping
the requested area. This option copies the grid, not the reference's validity
mask or elevations.

`target.resolution` is 5 in the current configuration and defaults to 5 when
omitted. An explicit different positive resolution is supported for controlled
comparisons, using the same zero-origin lattice convention. Existing run outputs
are never resampled or modified by this change.

## Netherlands operations

1. Validate config and polygon, preserving polygon holes.
2. Define the 5 m target grid, then plan AHN-native WCS chunks with context for
   boundary-cell footprints and resampled hole-filling donors.
3. Save the AOI hash, plan, settings and environment versions.
4. Fetch AHN service metadata; verify or download source tiles with the existing
   retry, checksum, full-read and native-grid validation.
5. Save the exact source manifest. Existing raw cache tiles are reused
   when settings and tile bounds match; NRW downloads are not performed.
6. Clean copies of tiles, converting masks, NoData, NaN/Inf and extreme sentinel
   values to `-9999` before aggregation. Preserve original downloads.
7. Build the cleaned AHN VRT and native 0.5 m mosaic.
8. Reproject/average the unfilled native mosaic once onto the target lattice,
   using exact-transform and no-vertical-shift settings. When filling is enabled,
   include a donor margin of ceil(search distance / target resolution) + 1 cells.
   Fill remaining NoData on this resampled grid using unchanged GDAL IDW and
   zero smoothing. Preserve originally valid target values. Crop the baseline,
   filled raster and fill status to the exact reference extent without resampling.
9. Combine the final cleaning pass with polygon masking, producing Float32
   elevations in metres with `-9999` NoData. Keep the full target grid extent;
   polygon membership is determined at each 5 m cell centre.
10. Verify final alignment and count valid AHN cells. With zero valid cells,
    leave the all-NoData output for inspection and fail without replacing the
    latest successful result.
11. Write finished target-grid tiles under `processed_tiles`, then stitch their
    explicit file list into `stitched/ahn.tif` without further resampling.
    Verify grid alignment and pixel-for-pixel equality with the prepared surface.
12. Record the successful result and its paths.

The AOI mask marks polygon membership, not AHN/NRW common coverage. AHN's missing
cells remain NoData in the baseline; filling can estimate some of them in a
separate output. No minimum fractional source coverage is imposed during
averaging. Heights remain in NAP: there is no vertical datum harmonisation.

## Outputs

New run IDs use `YYYY-MM-DD_HH-MM-SS` in Europe/Amsterdam time (including daylight
saving time), for example `2026-09-27_20-49-10`. Logs and output folders use this name; each run keeps its own processed and stitched outputs.
Existing names are preserved; collisions receive `_02`, `_03`, etc.

```text
data/netherlands/
  raw_tiles/                      native TIFFs only
  <run_id>/
    processed/                      target tiles, grid/run/result metadata
      _work/                        intermediate rasters and reports
    stitched/ahn.tif            final 5 m COG (with associated VRT)
data/old_runs/netherlands/<run_id>/     preserved outputs from the older pipeline version
logs/preparation/netherlands/
  raw_receipts/                    native TIFF provenance and checksum records
  latest_run.json, latest_plan.json
  <run_id>/                       config, plan, manifests, logs and result
```

See [Data layout](DATA_LAYOUT.md) for per-run output, cache, package and migration rules.

Processed tiles are non-overlapping windows of up to 1000 × 1000 target pixels
(5 km × 5 km at 5 m resolution), configurable with `processed_tile_size_pixels`. Edge tiles may
be smaller. They are not one-to-one copies of the skewed Dutch source tiles:
shared mosaic warping and target-grid filling use neighbouring terrain before cutting
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

The Netherlands module now implements the post-resampling interpolation stage. The
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

All missing target cells inside the original polygon are candidates, including
water. Only cells valid immediately after resampling supply interpolation values. Estimates
outside the polygon or inside polygon holes are discarded. Original valid
target elevations and downloaded files are preserved. Large unsupported gaps
remain partly or completely NoData. Interpolated water areas are not measured
bathymetry. NAP remains unchanged.

The source acquisition polygon receives a half-cell-diagonal buffer in EPSG:25832
for averaging. When filling is enabled, add the search radius and another
half-cell diagonal for donor footprints (27.071 m total at 5 m / 20 m search).
Then transform to the native CRS and add one 0.5 m source cell. The temporary
resampled grid includes donor context outside the final extent. Only missing
cells inside the AOI are filled; the final reference grid and AOI stay unchanged.
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

Every download writes to `data/netherlands/raw_tiles`; this is the only
runtime cache location. Receipts live under the regional logs, not beside TIFFs.
`--fresh-download` bypasses reuse and replaces a matching TIFF only after
validation. Each run writes its own processed/stitched folders; previous runs and old_runs remain untouched.
Filling and cache reuse remain independent.

Filling adds these products to each run. The unfilled baseline is written
directly as `stitched/ahn_unfilled.tif`, without individual unfilled tiles
or an unfilled VRT. The final fill-fraction raster is
written directly as one full-grid TIFF under `stitched`; individual
fill-fraction tiles and a fill-fraction VRT are not created.

| Product | Meaning |
|---|---|
| `stitched/ahn_unfilled.tif` | Unfilled baseline, still produced. |
| `stitched/ahn.tif` | Filled alternative on the identical target grid. |
| `stitched/ahn_fill_fraction.tif` | 0–1 share of valid source contribution that was interpolated; remaining invalid cells are NoData. |
| `processed/_work/hole_filling/ahn_filled.tif` | Filled target-resolution raster with donor margin. |
| `processed/_work/hole_filling/ahn_fill_mask.tif` | 1 only at accepted interpolated target cells. |
| `processed/_work/hole_filling/original_valid_mask.tif` | Fixed original-donor validity. |
| `processed/_work/hole_filling/aoi_mask.tif` | Target-grid candidate area. |
| `processed/_work/hole_filling/ahn_fill_fraction.tif` | Original valid=0, accepted fill=1, other cells=NoData. |
| `processed/_work/hole_filling/hole_filling_report.json` | Target-grid counts/areas, fill-status statistics, settings and timing. |

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
historical native-grid pilot with `python scripts/hole_filling_pilot.py config.netherlands.json`.
Its integrated preparation check follows the current target-grid filling pipeline;
the standalone native-grid trials remain historical interpolation experiments.
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

Update, 28 September 2026: all 20 automated tests pass after adding 5 m output.
New checks cover a shared 5 m lattice across AOIs, reference resolution/origin
rejection, acquisition context, and direct native-to-5 m GDAL average equivalence
for the unfilled baseline. They verify one warp precedes target-grid filling,
valid target values are preserved, fill status is binary, raw checksums remain unchanged, and baseline/fraction tiles are absent.
Earlier real-data results below and in the pilot report describe historical
1 m runs; they are not new 5 m accuracy measurements.

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
