# Baden-Württemberg DGM1 preparation

Use `config.germany.bw.json` (`country: germany`, `region: bw`). Change `aoi`
to the normal study AOI; retain `country_mask` for the regional intersection.
Set `target.reference_raster` to the shared reference when identical dimensions
and extent are required. Otherwise the existing common EPSG:25832, 5 m lattice
defines the target. Heights retain `DE_DHHN2016_NH`; no vertical transformation.

## Specification and processing steps

1. Discover actual DGM1 archive identifiers from the official LGL 2 km grid.
2. Keep original ZIPs, including XYZ, CSV, metadata and licence documents, in one
   durable cache. Statewide prefetch and AOI processing use this same collection.
3. For an AOI run, intersect the configured regional footprint, buffer by the
   existing German resampling context (5 / sqrt(2) m), and select intersecting
   archive and child-tile geometries. Boundary-only contact does not select a tile.
4. Extract only overlapping 1 km XYZs, using their actual filenames/years.
   Validate each coordinate against the named 1 m pixel-centre grid and matching
   CSV CRS. Border tiles may contain fewer than 1,000,000 records. Place supplied
   points on the nominal 1000 × 1000 grid, leaving absent cells as NoData.
5. Assign EPSG:25832 and cache the converted Float32 TIFF. Validate source grids,
   build a virtual mosaic (VRT), and use the shared exact valid-pixel 5 × 5
   averaging code directly on it. Conversion already normalizes invalid values,
   so BW writes neither separate cleaned TIFFs nor a merged 1 m TIFF.
6. Mask to the AOI intersected with the region and publish through the existing
   COG module. Genuine gaps remain NoData; hole filling is disabled.
7. Save source identifiers, URLs, hashes, verbatim CSV fields, source NoData
   observations and the vertical-reference note in provenance.

## Commands

Run from the workspace in its existing Python/GDAL environment:

```powershell
python main.py config.germany.bw.json --plan
python main.py config.germany.bw.json --prefetch
python main.py config.germany.bw.json --yes
```

`--prefetch` explicitly downloads the entire advertised statewide ZIP collection,
independently of `aoi`, without extracting XYZs or creating rasters. Rerun the
same command after interruption: valid ZIPs are checked and reused. It is not
required before an AOI run; `--yes` fetches only missing AOI archives.

`--probe` downloads/reuses the first selected archive and converts or reuses one
selected tile. `--fresh-download` explicitly refreshes the inventory and selected archives;
combine it with `--prefetch` to refresh the whole collection. Normal runs use the
saved inventory snapshot, so newly published source editions are picked up only
on explicit refresh. Failed downloads leave existing ZIPs and receipts intact.

The live pilot covers 200 × 200 m across two neighbouring archives:

```powershell
python scripts/bw_pilot.py config.germany.bw.json
python main.py config.germany.bw.json --self-test
```

### Acquisition speed and workers

Both `--yes` and `--prefetch` now honour `download_workers`. The default remains
1; start with 2 to overlap archive work. Workers share HTTP request pacing, have
private sessions and geometries, and keep at most the worker count of archive
jobs outstanding. `--probe` remains sequential. More workers increase memory and
disk activity; they do not promise proportional speedup for XYZ text parsing.

The `BW archives + XYZ conversion` progress bar includes ZIP validation,
extraction, text parsing and TIFF creation. It is not a download-only rate.
Per-archive logs separate acquisition/cache-validation time from local preparation.
`--prefetch` avoids conversion; a subsequent `--yes` converts selected XYZs that
are not already cached. Restarts reuse valid source ZIPs and converted TIFFs.
Converted TIFF receipts check the source archive hash, member, conversion version,
bounds, output NoData and TIFF size/hash. Missing, changed or outdated conversions
are rebuilt from the cached ZIP. `--fresh-download` also rebuilds conversions.

Cache reuse hashes each ZIP once and compares its size/hash/URL with its saved
validation receipt, then checks the ZIP directory. Identical previously validated
bytes do not need another full decompression/CRC pass. New downloads and ZIPs
without receipts still receive full CRC validation. The saved archive hash is
reused in child provenance, avoiding repeated reads of the ZIP for every child.

After acquisition, BW validates cached tile grids, builds the VRT, averages to
5 m, masks to the AOI and publishes COGs. The VRT references the persistent TIFFs;
keep `raw_tiles` available while processing. Other regions retain their existing
cleaning and mosaicking behaviour.

## Official discovery and completeness

The [LGL product catalogue](https://opengeodata.lgl-bw.de/assets/config/local/odp-products.json)
identifies `DGM`, `DGM1`, and the `zwei_km_gitter` layer. Its
[public layer configuration](https://opengeodata.lgl-bw.de/assets/config/local/core-layerconfig.json)
defines the statewide extent and MVT coverage endpoint:
`https://opengeodata.lgl-bw.de/tiles/vts/2x2Gitter/{z}/{x}/{y}.pbf`.

GDAL reads all four zoom-7 index tiles covering that extent. Each grid feature's
metadata advertises product filenames and download paths; only advertised DGM1
entries are acquired. Names, URLs, duplicate records and the consistent 2 km
origin are validated. The 2026-10-09 inventory contains 9,370 DGM1 archives with
origin residues E=1000 m, N=0 m modulo 2000 m. Discovery does not assume that every
possible rectangular grid cell exists. It also records indexed cells lacking
DGM1 as unavailable.

The `customerGroup=hochschulen-wissenschaft` query is preserved as supplied in
the specification. It is not treated as authentication. Downloads use bounded workers
with a shared configured request pause, 30-second connection timeout, configured read
timeout, bounded exponential retries, ZIP CRC/structure checks and `.part` files
beside their destinations for atomic replacement. No external downloader or new
Python dependency is needed. The portal's UI limits selections to 10 tiles; no
separate published bulk-rate guarantee was established. The downloader therefore
starts conservatively and stops on access errors or persistent throttling.

A listed archive returning 404 is an inventory/server inconsistency and fails
explicitly; it is not silently reclassified as outside coverage. A prefetch stops
on a failed archive, preserves completed files, and writes an incomplete summary.
It reports complete only after every archive in the saved official inventory
has passed validation or matches its previously validated receipt. This is completeness against that dated inventory, not
a claim about future updates or a detailed survey of the elevations inside every
statewide XYZ. Full XYZ validation happens for selected processing tiles.

## Files and cache lifetime

```text
data/germany/bw/
  source_archive/dgm1_32_<E>_<N>_2_bw.zip
  raw_tiles/<XYZ-stem>.tif        persistent converted 1 m tiles
  <run_id>/processed/             common grid, target tiles, _work and provenance
  <run_id>/stitched/bw.tif        final 5 m COG

logs/preparation/germany/bw/
  bw_inventory.json              official availability manifest and snapshot date
  archive_receipts/<ZIP>.json     per-archive cache manifest: URL, hash, bytes, children
  raw_receipts/<XYZ-stem>.json    conversion identity, hash and source provenance
  bw_cache_summary.json           latest statewide prefetch outcome
  download_work/                  cached discovery responses
  <run_id>/bw_selection.json
  <run_id>/source_tiles/          extraction scratch and CSV copies
  <run_id>/source_manifest.json
  <run_id>/bw_prefetch.json        prefetch invocations only
  pilots/<run_id>/pilot_report.json
```

Copy `source_archive`, `raw_tiles`, `bw_inventory.json`, `archive_receipts` and
`raw_receipts` when moving the cache to another machine. Valid ZIPs without receipts can also be adopted after
CRC and structure checks; this is local validation, not a provider checksum.
AOI processing neither deletes nor extracts the whole ZIP collection. Extracted
XYZ text is removed after conversion; the original remains in its ZIP. Other
derivatives are per-run files that may be removed with those run outputs.
Never remove `source_archive` or `raw_tiles` during run cleanup. TIFFs from older
per-run `source_tiles` directories are not automatically adopted; the first run
with persistent conversion caching rebuilds selected tiles from the cached ZIPs.

To explicitly recover completed conversions from an older, stopped run, use:

```bash
python scripts/bw_recover_conversions.py config.germany.bw.json logs/preparation/germany/bw/<run_id>/source_tiles
```

This validates TIFF/ZIP hashes, grids and valid-cell counts before adopting each
tile. It retains original files and uses hard links where possible, copying only
when linking fails. Do not edit linked TIFFs in place. Recovery is resumable and
stops on invalid files or conflicting cache content. A subsequent normal `--yes`
run reuses the recovered cache. If a terminated run left `active.lock`, verify its
recorded process is no longer running before removing that stale lock.

The sample ZIPs advertise no source NoData sentinel. The implementation does not
invent one. It accepts partial coverage, rejects duplicate, off-grid or out-of-tile
coordinates, and writes cells explicitly with GDAL instead of relying on the XYZ
driver's handling of missing cells. Missing cells and nonfinite/extreme elevations
become output NoData; genuine zero elevations are preserved. An undeclared elevation equal
to output NoData (-9999) fails for investigation. CSV accuracy and method codes
are retained without interpreting their statistical meaning. Filename years do
not replace CSV acquisition/update dates. The bundled licence PDF and metadata
TXT remain in each original ZIP and are referenced by provenance.

## Validation performed

On 2026-10-09, the live pilot fetched `557_5434` and `559_5434` through Python,
validated both ZIPs, processed four relevant XYZs, and published an aligned COG.
All 1,600 target cells matched independent 5 × 5 means exactly. A second AOI
acquisition with HTTP disabled succeeded, and original ZIP hashes were unchanged.
The statewide download was not run.

On 2026-10-12, the reported border tile `dgm1_32_388_5279_1_bw_2019.xyz`
was verified from the official `387_5278` archive: all 152,896 supplied points
are valid, and its 847,104 absent cells remain NoData. The partial-tile fix
passed 13 regional tests. All 40,000 cells of the tile's aligned, masked 5 m COG
matched independent coordinate-based means (or NoData) exactly. Statewide
border/survey-year variation has not been exhaustively sampled.

On 2026-10-13, persistent conversion caching passed all 18 regional tests,
including missing/corrupt TIFF repair, conversion-version and source changes,
and preservation of the previous cache after a failed conversion. The two-archive
pilot passed with HTTP and XYZ conversion forbidden on repeat acquisition; all
1,600 final 5 m cells still matched independent means exactly.

The VRT processing change passed 19 BW tests, including exact comparison against
the previous cleaned, physical-mosaic workflow across tile seams and NoData gaps,
and rejection of a shifted source grid.
