# Bavaria DGM5 preparation

`config.germany.bavaria.json` uses the existing `country_masks/Germany_Bayern.gpkg`
study-area mask. Set `aoi` to another polygon dataset to prepare a smaller area;
it is intersected with that regional mask. Only positive-area intersections with
catalogue-backed 1 km cells are acquired. Holes and multipart AOIs are respected.

```powershell
python main.py config.germany.bavaria.json --plan
python main.py config.germany.bavaria.json --probe
python main.py config.germany.bavaria.json --yes
```

Planning is offline; acquisition resolves availability from the official catalogue.
`download_workers` defaults to **4 in the supplied Bavaria config**. Workers use
private HTTP sessions and process separate tiles concurrently, including XYZ
conversion. Set it to `1` for serial acquisition. The existing
`request_pause_seconds` (default 0.25 seconds) spaces request starts across all
workers, including retries and mirror fallback. Cached tiles need no HTTP pacing.
Results remain in catalogue-selection order. On failure or Ctrl+C, pending work
is cancelled and active workers drain; completed validated cache files remain
reusable. Restart an already running command to use a changed worker count.

Probe downloads and converts at most one selected tile. Bavaria has no statewide
prefetch operation. An unavailable catalogue cell is recorded in the run's
`bavaria_selection.json` and remains NoData; a failed download of an advertised
tile stops the run instead of silently dropping terrain.

## Processing steps

1. Transform the polygon AOI to EPSG:25832 and intersect the regional mask.
2. Read/cache the official Metalink 4 catalogue; resolve intersecting 1 km cells
   by their complete `{easting_km}_{northing_km}.zip` names.
3. Validate cached ZIP byte count and SHA-256 against that catalogue, or download
   using its URLs in order with bounded retries and mirror fallback. Downloads
   are validated in adjacent `.part` files before atomic replacement.
4. Inspect ZIP paths and contents, safely read the matching TXT, and validate its
   complete ordered rectangular 5 m grid. Ordinary tiles have 200 × 200 cells;
   cropped boundary tiles can have fewer. All centres must lie within the nominal
   filename footprint. Duplicates, missing points within the native rectangle,
   irregular spacing and reordered records fail validation.
5. Write/reuse native Float32 GeoTIFFs in EPSG:25832, with 5 m cells. Conversion
   assigns the declared horizontal CRS; it does not interpolate or reduce resolution.
6. Build native VRT mosaics grouped by their actual grid origins, without shifting
   source values. Copy/window when the source and target grids match; otherwise
   use one shared average warp of the native mosaics onto the exact target reference.
   Valid target-lattice coverage has priority where boundary footprints overlap.
7. Apply the regional polygon AOI mask and publish through the shared COG module,
   preserving the usual compression, tiling, overviews and value verification.
8. Retain source provenance, licence, attribution and DHHN2016/NHN height reference.
   No vertical transformation or hole filling is applied.

## Cache and output layout

```text
data/germany/bavaria/
  source_archive/<i>_<j>.zip     persistent original sources and support documents
  raw_tiles/<i>_<j>.tif          persistent validated native 5 m conversions
  <run_id>/processed/           target tiles, provenance, intermediate work
  <run_id>/stitched/bavaria.tif  final 5 m COG
logs/preparation/germany/bavaria/
  09.meta4                     persistent official catalogue
  archive_receipts/
  raw_receipts/                source digest, conversion policy and raster digest
  <run_id>/                    config, selection, source manifest and results
```

Repeated/overlapping AOIs reuse matching archives and converted tiles. Each
selected ZIP is checked against the current catalogue before a derivative is
accepted. A changed source SHA-256 requires reacquisition and reconversion;
an unsuccessful update never permits the old derivative to be returned.
Existing bytes are preserved until their validated replacement succeeds.

`catalogue_max_age_days` defaults to 30; use `null` to disable expiry.
`catalogue_refresh: true` explicitly refreshes the catalogue each invocation.
An existing valid catalogue remains usable if refresh fails, with a logged warning.
`--fresh-download` refreshes the catalogue and selected ZIPs/conversions. No
network access is needed for an unexpired catalogue and valid matching cache.

The default target snaps to the pipeline's 5 m grid. When
`target.reference_raster` is supplied, its exact origin, extent and dimensions
are authoritative. Bavaria supports shifted 5 m reference origins through one
alignment operation. Other regional reference-grid restrictions are unchanged.

## NoData and provenance

Zero is valid terrain. The supplied config explicitly sets `source.nodata: -9999`
with `source.nodata_evidence`. Only this marker is mapped to pipeline NoData.
Malformed, duplicate, out-of-order, irregularly spaced and nonfinite records
still fail conversion, as do missing cells inside a native rectangle. A complete
smaller rectangle is accepted as partial coverage, with no invented elevations
outside it. Unknown large sentinel-like values also require review.

This policy was established by inspecting the failing official source tile
`498_5545.zip` on 2026-10-09, after validating it against the Metalink catalogue.
Archive SHA-256: `f05cba1305f5e70490c54b2bbb327e10a93a2f86d44699591d722a09feb45e16`.
Its TXT contains a complete ordered 200 × 200 grid: 6,567 cells have height -9999;
the remaining 33,433 heights range from 101.68 to 112.13 m. These values indicate
missing-data padding, not actual terrain. This is empirical source evidence,
not a claim that the provider supplied a product-wide NoData declaration.
The earlier pilot tile had no missing values and did not reveal this case.

Another boundary variation was verified in `545_5268.zip`, SHA-256
`682db3810aca79beb55162da67d365f4a3423bbfaf144b88a216550ace5a8818`.
This contains 5,916 records on an 87 × 68 grid, with native upper-left corner
`(545567, 5269000)` and 5 m pixels: a 2 m X offset from the usual grid.
There are 2,681 valid heights and 3,235 explicitly marked NoData cells.
Conversion preserves this native transform and all Float32 values; the source
is aligned only during final preparation. `absent_cells` in receipts counts
records absent relative to a nominal 40,000-cell tile, not target-grid NoData.

The 2026-10-09 cache audit verified all 2,253 available ZIPs against the catalogue
and validated every XYZ grid: 2,252 ordinary grids and this one partial/shifted
grid, with no validation errors. This audits the existing cache, not unacquired
tiles. All 134 regression tests passed, including mixed-grid weighting and
coordinate preservation. The failing real tile was successfully published as
a COG; valid output values exactly matched an independent area-weighted average.
Its repeat reused the conversion offline. Existing full-tile conversions remain
compatible and do not need regeneration for this change.

Audit command and verification records:

```powershell
python scripts/bavaria_audit.py config.germany.bavaria.json
```

- `logs/preparation/germany/bavaria/cache_audit.json`
- `logs/bavaria_partial_regression_tests.txt`
- `logs/preparation/germany/bavaria/2026-10-09_14-43-07/partial_grid_verification.json`

On resuming, existing ZIPs remain reusable. Converted tiles are regenerated when
the source NoData policy in their receipt differs from the current config.

Source product and legal references, checked 2026-10-09:

- [Official DGM5 product](https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dgm5)
- [Official Metalink catalogue](https://geodaten.bayern.de/odd/a/dgm/dgm5xyz/meta/metalink/09.meta4)
- [LDBV terrain documentation](https://www.ldbv.bayern.de/produkte/landschaftsinformationen/gelaende.html)
- [Official licence and attribution terms](https://www.geodaten.bayern.de/odd/m/3/html/nutzungsbedingungen.html)
- [Official pricing/product licence list, section 9.4.2](https://www.ldbv.bayern.de/file/pdf/1269/Geb%C3%BCren_und_Preisliste.pdf)

Licence: CC BY 4.0. Attribution: “Bayerische Vermessungsverwaltung –
www.geodaten.bayern.de”. The config, tile receipts, final COG metadata and
`processed/source_provenance.json` retain the relevant references and modifications.
Catalogue publication time is recorded as catalogue metadata, not elevation epoch.

`tests/test_bavaria.py` covers catalogue parsing, selection, mirror fallback,
cache updates/reuse, XYZ integrity, masking, exact COG values and shifted alignment.

## Verification performed

On 2026-10-09, all 129 offline regression tests passed, including 11 Bavaria tests.
The live pilot selected `619_5514.zip` inside the configured study-area mask,
validated its catalogue size (189,804 bytes) and SHA-256, converted all 40,000
XYZ cells, and published a 9 × 9-cell masked COG. A second run with HTTP requests
blocked reused the catalogue, ZIP and converted TIFF and produced a byte-identical
COG. The full configured regional AOI was not processed during implementation.

```powershell
python scripts/bavaria_pilot.py config.germany.bavaria.json
```

Local verification records:

- `logs/bavaria_regression_tests.txt`
- `logs/bavaria_live_pilot.txt`
- `logs/preparation/germany/bavaria/pilots/2026-10-09_14-10-47/verification.json`

The pilot preserves any configured target reference. With a large explicit
reference raster it will therefore publish that full reference extent, with
NoData outside the small pilot AOI.
