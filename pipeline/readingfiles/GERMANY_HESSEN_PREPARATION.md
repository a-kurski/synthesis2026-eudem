# Hessen DGM1: official regional ZIP acquisition

Hessen uses the official [Geodaten online Downloadcenter](https://gds.hessen.de/INTERSHOP/web/WFS/HLBG-Geodaten-Site/de_DE/-/EUR/ViewDownloadcenter-Start).
Mapterhorn is no longer part of Hessen planning, downloads, extraction, cache lookup
or output provenance. Existing legacy archives are left on disk but never read.
The shared German raster processing remains unchanged: native aligned 1 m inputs,
exact valid-cell 5 × 5 averaging, AOI masking, target-grid checks and COG publication.

## Run

```powershell
python main.py config.germany.hessen.json --plan
python scripts/check_hessen_download.py --output logs/hessen_official_transport.json
python main.py config.germany.hessen.json --yes
python main.py config.germany.hessen.json --self-test
```

The offline plan reads `test_masks/hessen_boundaries.gpkg`, layer
`hessen_boundaries`, and intersects its polygons with the supplied AOI plus the
existing 3.536 m resampling context. The current AOI selects 23 districts, matching
`test_masks/hessen_departments.csv`. The CSV is a cross-check, not a fixed selection.
The boundary path resolves relative to the config. A different AOI is supported;
an intersecting district without an explicit verified name mapping fails clearly.
Only positive-area intersections are selected (boundary-only touches are excluded).

`KREIS_NR` identifies each district. `dtm/countries/germany/hessen/regions.py`
contains the explicit Downloadcenter names, including Wiesbaden's different label.
Names are URL-encoded with `urllib.parse.quote`; boundary labels are never used to
guess URLs. The diagnostic reads only four bytes from each selected ZIP and never
fetches a complete regional package.

## Downloadcenter date

`source.download_date` is explicitly configured as `20261013` (YYYYMMDD).
It is a Downloadcenter delivery path, **not an acquisition epoch**. Do not assume
it remains available indefinitely. Inspect the official Downloadcenter and update
this field when the dated links expire. Invalid dates fail config validation;
missing/error responses fail acquisition with the district ID and URL. No region
is silently omitted. Automatic date discovery is not assumed: the inspected
Downloadcenter HTML did not expose the dated ZIP links directly.

The source URL is constructed as:

```text
https://gds.hessen.de/downloadcenter/<date>/3D-Daten/
Digitales Geländemodell (DGM1)/<region>/PKT_<region>.zip
```

## Cache layout

```text
data/germany/hessen/
  source_archive/official/<date>/<KREIS_NR>/
    PKT_<region>.zip
    extracted_<archive_sha256_prefix>/
      <all original ZIP contents, including TIFF, TFW and metadata>
  raw_tiles/
    he_<date>_<KREIS_NR>_<member_hash>_<original_tile_name>.tif
  <run_id>/
    processed/
    stitched/hessen.tif
logs/preparation/germany/hessen/
  regional_packages/official/<date>/<KREIS_NR>/
    archive.json
    extraction.json
  raw_receipts/
  download_work/
  <run_id>/
    config.json, plan.json, source_manifest.json, hessen_selected_tiles.json, ...
```

Complete intersecting district ZIPs are downloaded and retained. Regional source
files retain their original names and directory hierarchy. Only the selected
TIFFs are copied into the normal flat `raw_tiles` cache, with unique names to avoid
collisions in the unchanged shared processor. TFWs and other original files remain
in the extraction, outside this TIFF-only cache. Account for disk space for ZIPs,
full extracted packages, selected raw TIFFs and processing outputs.

Official regional packages can contain another ZIP, for example
`PKT_Kreisfreie Stadt Darmstadt.zip` contains `Darmstadt - DGM1.zip`.
The extractor preserves that inner ZIP and expands it under a unique `_nested/`
directory, preserving its TIFFs, TFWs and other files. Path safety and CRC checks
also apply inside nested ZIPs. Completion is recorded only after nested extraction
has produced TIFFs. An inner-package failure retains the completed outer ZIP for
inspection or a later retry; it does not trigger another network download.

Downloads retain interrupted `.zip.part` files and resume with HTTP Range. An
ignored or invalid Range response never truncates the saved prefix. ZIP structure,
member safety and all member CRCs are checked before replacing a cached archive;
local SHA-256 receipts detect later cache changes. These are local integrity
records, not a claim that Hessen publishes a checksum for each package.
`--fresh-download` explicitly refreshes the selected regional packages; each failed
ZIP download preserves its previous complete archive. Normal reruns reuse complete
extractions without HTTP or repeated ZIP extraction. Interrupted/missing-file
extractions are rebuilt from the cached ZIP; directory existence alone does not
establish completion.

An extraction index is committed only after all files are extracted. It indexes
standard filenames by their 1 km bounds; nonstandard filenames require validated
raster headers. Every selected TIFF is checksum-checked and its actual raster
bounds must match the index before processing. Changing the AOI can select more
TIFFs from an already cached district or acquire additional districts.

Separate district folders prevent source filenames overwriting one another.
Identical boundary tiles from different packages are compared by grid, pixels
and masks and passed to processing once. Differing tiles for the same area fail
with both paths; archive order does not silently decide the terrain version.
Unsafe paths, links, case-colliding paths inside a ZIP and ZIPs without TIFFs fail.

`--probe` acquires/extracts the planned regional packages, validates the selected
TIFFs and returns one TIFF; it is not a lightweight URL check. Use the diagnostic
script above for that purpose. Completed data and old processing runs are retained.

## Processing and provenance

Selected inputs must be single-band EPSG:25832, Float32, exact 1 m
north-up pixels and integer-metre boundaries. Source NoData may be absent or
use another declared value. Cleaning honors each source's NoData and GDAL mask,
excludes NaN/Inf and abs(value) >= 1e20, and normalizes missing output to -9999
before averaging. An absent NoData tag alone does not make a tile invalid;
finite unmasked values (including zero) remain valid. Original files are unchanged.
For official TIFFs without an embedded CRS, the configured EPSG:25832 is assigned
in a temporary processing VRT only after the zone-32 filename, 1000x1000 dimensions
and exact kilometre grid agree. An explicit conflicting CRS is still rejected.
Assignments are logged and listed in `source_crs_assigned_from_config` in the result.
No native grid shift, horizontal
raster reprojection or vertical transformation is introduced. Final output stays
on the existing 5 m common grid; configure a covering `target.reference_raster`
for identical extents and dimensions across regions. The output distributor is
Hessen Geodaten online (HVBG). Vertical datum remains explicitly unverified rather
than inferred from the horizontal EPSG code. Metadata/licence files supplied in
the official regional packages are preserved intact.

## Verification of the replacement

The local metadata audit after the Bergstraße extraction failure checked 1,959
already extracted TIFFs. Of these, 1,225 had no NoData tag; their pixels contained
no masks, NaN/Inf, -9999, zeros or extreme values. Another metadata check found
316 TIFFs without embedded CRS, all matching their zone-32 filenames and exact
kilometre grids. All cached TIFFs pass the revised validator. This audit covers
the extracted cache, not the still-undownloaded districts. Report:
`logs/hessen_cached_nodata_audit.json`.

On 2026-10-13 the offline plan selected exactly the 23 KREIS_NR values in the
provided CSV. All 23 dated official URLs returned HTTP 206 and the ZIP signature
in the lightweight live diagnostic. Report: `logs/hessen_official_transport.json`.
Their advertised sizes total **59,055,914,468 bytes (59.06 GB)**, before extraction;
regional acquisition does not imply a small download for this broad AOI.
All **164 regression tests passed**, including official Hessen ZIP extraction,
cache reuse/recovery, selected-tile validation, duplicate checks and an end-to-end
synthetic COG publication. Full production regional ZIP acquisition has not been
run as part of this implementation.
