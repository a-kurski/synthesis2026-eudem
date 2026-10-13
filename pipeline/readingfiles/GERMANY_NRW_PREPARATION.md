# Germany terrain preparation: NRW

Germany is selected through the same `main.py` entry point as the Netherlands.
`country: "germany"` selects the country dispatcher, and `region: "nrw"` selects
its first regional adapter. Each invocation prepares one country/region and AOI.

## Commands

Run from the workspace:

```powershell
python main.py config.germany.nrw.json --plan
python main.py config.germany.nrw.json --probe
python main.py config.germany.nrw.json --yes
python main.py config.germany.nrw.json --yes --fresh-download
python main.py config.germany.nrw.json --self-test
```

`--plan` is offline and saves a plan. `--probe` retrieves service metadata and a
20 x 20 m native sample. `--yes` performs acquisition and preparation. Omitting
`--yes` retains the existing interactive DOWNLOAD confirmation. The self-test
command runs all country preparation tests, including Netherlands regressions.

The supplied configuration uses `small_study_area.gpkg`, the same AOI as the
Netherlands configuration. Change `aoi` to prepare another polygon. Selecting
NRW identifies the source; it does not automatically request the whole state or
apply an administrative boundary mask. Actual source coverage and the AOI mask
determine which output cells contain data.

## Source and cache

The version 1 source settings are retained: WCS 2.0.1 at
`https://www.wcs.nrw.de/geobasis/wcs_nw_dgm`, coverage `nw_dgm`, native EPSG:25832,
1 m pixels and 2,000 m download chunks. WCS requests retrieve native pixels;
5 m averaging is performed locally.

The downloader saves GetCapabilities and DescribeCoverage responses and validates
TIFF CRS, dimensions, bounds, resolution, readable pixels and checksums. It uses
the existing retry and atomic-download helpers. Service errors are failures,
never silently substituted with missing terrain.

With `reuse_cache: true`, NRW reads only `data/germany/nrw/raw_tiles`.
Receipts live in `logs/preparation/germany/nrw/raw_receipts`. No old runs or
legacy directories are searched. Fresh downloads atomically replace matching
raw TIFFs only after successful validation. The source manifest records the
actual paths and receipt snapshots. Historical caches can be imported once by
`scripts/migrate_data_layout.py`.

## Processing

1. Plan the common 5 m grid in EPSG:25832. Add a 5 m half-cell diagonal
   (approximately 3.536 m) around the AOI for acquisition, ensuring full native
   footprints for retained boundary cells. There is no interpolation buffer.
2. Download/reuse native 1 m terrain and reject unexpected CRS, resolution or
   non-integer pixel origins. Clean working copies of masks, NoData, NaN/Inf and
   extreme sentinel values; preserve original downloads.
3. Mosaic only the explicitly selected source tiles. Build a native-resolution
   VRT window covering the output extent, with NoData padding outside available
   source coverage. VRT pixel positions are unchanged.
4. Aggregate exact 5 x 5 native blocks using Float64 sums and valid-pixel counts,
   writing Float32 5 m elevations. Fully valid blocks contain 25 contributors;
   partial blocks average only valid contributors. Empty blocks remain NoData.
   Processing uses bounded windows rather than a full-area NumPy array.
5. Apply the polygon mask at output cell centres, preserving polygon holes.
   Verify output geometry against the target reference.
6. Publish processed tiles, stitch their explicit file list, and verify exact
   pixel equality. Save a successful result only if there is valid AOI coverage.
   Failure preserves the previous successful `latest_run.json`.

The terrain is never reprojected, shifted or passed through a separate alignment
resampling step. Grid verification checks compatibility without modifying pixels.
The AOI geometry may need projection if supplied in a different CRS.
Hole filling is disabled; requesting `--fill-holes` fails before acquisition.
No unfilled alternative or fill-fraction products are needed.

NRW heights remain in DHHN2016/NHN. Netherlands heights remain in NAP. This stage
does not harmonise vertical datums or compute elevation differences.

## Shared grid and outputs

The NRW adapter requires 5 m EPSG:25832 output with edges on multiples of 5 m.
The native integer-metre lattice nests exactly in that existing target lattice.
Equal AOIs and target settings produce identical country output grids. For an
explicit common extent, set `target.reference_raster` in both configurations to
the same 5 m `target_grid.vrt` or suitable reference TIFF. It must cover the AOI.
A larger reference is allowed; missing NRW coverage stays NoData. A reference's
height values and validity mask are never copied.

```text
data/germany/nrw/
  raw_tiles/                      native TIFFs only
  <run_id>/
    processed/                      target tiles, grid/run/result metadata
      _work/                        intermediate rasters and reports
    stitched/nrw.tif            final 5 m COG (with associated VRT)
data/old_runs/germany/nrw/<run_id>/     preserved outputs from the older pipeline version
logs/preparation/germany/nrw/
  raw_receipts/                    native TIFF provenance and checksum records
  latest_run.json, latest_plan.json
  <run_id>/                       config, plan, manifests, logs and result
```

See [Data layout](DATA_LAYOUT.md) for per-run output, cache, package and migration rules.

Run IDs use Amsterdam local time. `prepared_raster` and
`comparison_ready_raster` both point to `stitched/nrw.tif`. Plans, source
manifests and results include `country` and `region`. Logs, run folders and latest
pointers are scoped by region, keeping later German state workflows independent.

## Adding a German region

Create `dtm/countries/germany/<region>/` implementing the existing five methods:
`validate_config`, `plan`, `download`, `probe` and `prepare`. Register its module
in `REGIONS` in `dtm/countries/germany/__init__.py` and add a configuration with
`country: "germany"` and the new region key. The main coordinator needs no change.
Unknown region keys are rejected rather than falling back to NRW.

Each region owns its source selection, native CRS/resolution, datum, acquisition
and processing rules. Return `vertical_datum_note` in the source plan and result,
and the standard `prepared_raster` / `comparison_ready_raster` result paths.
Use `dtm.paths.scoped_root` for regional acquisition/output paths and
`dtm.publication` for final masking and lossless tile publication. Reuse NRW's
aggregation only if the new region satisfies the same validated native-grid
requirements; it is not a general German-state assumption.

## Validation

On 28 September 2026, all 28 offline tests passed (20 existing tests plus 8 NRW
tests). NRW checks cover 5 x 5 means, source seams crossing target footprints,
invalid source values, polygon holes, larger shared references, source immutability,
pixel-exact stitching, cache receipts, CLI hole-filling rejection, regional output
isolation, and preservation of the latest successful result after empty coverage.

The live NRW WCS probe returned 400 valid native cells in EPSG:25832. An end-to-end
pilot on its complete 5 m footprints produced 9 valid target cells, each exactly
equal to an independent cell-by-cell mean. The pilot preserves original source
checksums and writes a machine-readable report. A second pilot processed a
200 x 200 m sample from the version 1 NRW cache: all 1,600 target cells matched
independent means exactly. Reports are saved in
`data/old_runs/germany/nrw/pilots/2026-09-28_22-44-55/` (live sample) and
`data/old_runs/germany/nrw/pilots/2026-09-28_22-46-33/` (archived sample).

To repeat an offline real-data pilot using any cached native NRW tile:

```powershell
python scripts/nrw_pilot.py config.germany.nrw.json path/to/native_nrw_tile.tif
```

It processes at most 200 x 200 m and writes to
`logs/preparation/germany/nrw/pilots/<run_id>/`. It performs no downloads and does not alter
production latest-run pointers. Full-region throughput and peak disk use have
not been benchmarked; intermediate native mosaics are retained for inspection.
