# Switzerland and Liechtenstein: swissALTI3D

Both country entries use `dtm/countries/switzerland/`. The combined configuration
uses the existing `country_masks/Swiss_liech.gpkg`; the Liechtenstein configuration
uses `country_masks/Liechtenstein.gpkg`. No new national boundaries are acquired.
Use the combined configuration to prepare both study areas in one run.

## Commands

From the workspace, using the existing Python/QGIS bootstrap:

```powershell
python main.py config.switzerland.json --plan
python main.py config.liechtenstein.json --plan
python scripts/switzerland_pilot.py config.switzerland.json --plan
python scripts/switzerland_pilot.py config.switzerland.json
python main.py config.switzerland.json --self-test
```

`--plan` is offline: it saves the common grid, WGS84 discovery geometry and
resampling halo. Tile counts and editions are unknown until acquisition.
The pilot always uses a roughly 150 x 220 m rectangle near Vaduz, independent
of the production mask/reference. Its products and reports are saved beneath
`logs/preparation/<country>/pilots/<run_id>/`; native assets/receipts use the
shared cache. Pilots do not change production latest-run pointers.

For production, after inspecting the plan and allowing enough working disk:

```powershell
python main.py config.switzerland.json --yes
```

`python main.py config.liechtenstein.json --yes` prepares only Liechtenstein's
mask. `--probe` discovers tiles for the configured mask and downloads one native
tile without processing. Use the pilot for a geographically small live test.

Every fresh acquisition queries all STAC pages and re-evaluates current editions.
To retry an interrupted run with exactly the saved selection, supply that run's
manifest (replace `<run_id>` with the real directory name):

```powershell
python main.py config.switzerland.json --yes --source-manifest "logs/preparation/switzerland/<run_id>/swissalti3d_manifest.json"
```

The same option is supported by the pilot, using its saved manifest path.
Alternatively set `source_manifest` in the config; relative paths resolve beside
the config. Resume refuses a different study area or catalogue. It creates a new
processing run and reuses validated downloads; it does not continue a partial warp.

## Source and processing

- Public [swisstopo STAC API](https://docs.geo.admin.ch/download-data/stac-api/overview.html),
  collection `ch.swisstopo.swissalti3d`. All returned next-page links are followed.
- Discovery transforms the densified study geometry to WGS84 with longitude-first
  axes, with the shared half-cell-diagonal processing halo. Actual footprints
  filter the envelope query. Publication uses the original study-area mask.
- Selection uses validated item IDs and product dates, independently per spatial
  tile. Maintenance timestamps do not rank editions. Missing newest-edition 2 m
  COGs, conflicting assets/editions and unsupported checksum formats fail clearly.
- Source files are native 2 m EPSG:2056 GeoTIFFs. Published SHA-256 multihashes are
  verified before atomic publication and on cache reuse. Actual raster CRS,
  spacing, tile extent and NoData metadata are inspected. Originals stay unchanged.
- Both countries share `data/switzerland/raw_tiles/` and Swiss receipts/lock.
  The default is two download workers, configured by `download_workers`, with
  existing request pacing, explicit timeouts, bounded attempts and Retry-After.
- Selected files form a VRT only. One `average` warp performs horizontal
  reprojection, 2 m to 5 m resampling and alignment to `target_grid` bounds.
  `-ovr NONE` forces full-resolution sources; `-s_srs EPSG:2056 -novshift`
  prevents automatic vertical correction. This follows the existing average policy.
- Final outputs are masked Float32, EPSG:25832, 5 m, NoData -9999, with lossless
  DEFLATE COGs and internal average overviews where dimensions warrant them.
  Shared publication creates processed tiles and `stitched/swissalti3d.tif`.
  Zero and negative elevations remain valid. `processed/coverage.json` reports
  missing AOI cells, which remain NoData; an all-missing output fails.
- Heights remain LN02 (EPSG:5728); metadata and manifests retain this reference
  and `©swisstopo`. No height correction or vertical grid acquisition is performed.

The acquisition log contains `swissalti3d_manifest.json` with the query and frozen
items/assets; `source_manifest.json` adds local paths and download receipts with
checksums, retrieval times and inspected raster metadata. Generated data stays in
the existing ignored `data/` and `logs/` trees.

## Implementation and validation

New files: the three `dtm/countries/switzerland/` modules, both country configs,
`scripts/switzerland_pilot.py`, `tests/test_switzerland.py` and this guide.
Integration changes are limited to country registration/resume handling in
`dtm/coordinator.py`, the shared provider cache namespace in `dtm/paths.py`, and
the README/data-layout documentation. Other country processing is unchanged.

Offline checks cover edition ordering, pagination, footprint/asset filtering,
manifest resume versus refreshed discovery, checksum rejection, atomic replacement,
cross-country cache/lock sharing, retry handling, grid alignment, source NoData,
zero/negative heights, ignoring deliberately incorrect source overviews and COG
structure. The complete suite also checks internal output overviews and existing
country processors. The live pilot checks the actual checksum and GDAL COG layout.

Verified on 2026-10-04 with QGIS GDAL 3.11.3: all 70 offline tests passed. Both
production configurations passed offline planning. The Vaduz pilot selected the
2026 edition of spatial tile `2757-1223`, verified its published checksum and
produced a 31 x 46 grid with all 1,343 AOI cells valid. Full COG validation returned
no warnings or errors. A Liechtenstein pilot reused that asset after fresh
discovery; frozen-manifest resume also passed without network access. No
countrywide acquisition or processing run was launched. GDAL emitted its
`STRIP_VERT_CS` option warning during warp; the explicitly horizontal source and
target CRS remain enforced, and constant-height tests verified no height shift.
