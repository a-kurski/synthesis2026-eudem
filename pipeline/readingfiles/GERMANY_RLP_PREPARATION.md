# Germany terrain preparation: Rheinland-Pfalz

`config.germany.rlp.json` selects `country: "germany"`, `region: "rlp"` and the
existing `country_masks/Germany_RheinlandPfalz.gpkg` polygon. Run from the workspace:

```powershell
python main.py config.germany.rlp.json --plan
python main.py config.germany.rlp.json --probe
python main.py config.germany.rlp.json --yes
python main.py config.germany.rlp.json --self-test
```

`--plan` stays offline: its tile count and uncompressed size describe candidate
1 km cells intersecting the AOI plus the shared 5 m aggregation context. Acquisition
resolves these candidates against the current official catalogue. `--probe` downloads
one complete native 1 km tile (not a WCS crop). `--yes` prepares the selected region.
`--fresh-download` bypasses prior runs; default cache reuse validates source settings,
URL, catalogue checksum and size, receipt checksum, and native raster metadata.

## Official source

The [RLP download page](https://geoshop.rlp.de/files/anpassungen/hvd/index.html?config=./products/dgm1.json)
and its [product configuration](https://geoshop.rlp.de/files/anpassungen/hvd/products/dgm1.json)
identify the [statewide TIFF Metalink catalogue](https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4).
The pipeline reads its direct HTTPS URLs, byte sizes and SHA-256 checksums. No
manual export of a selection or additional dependency is required.

Names such as `dgm1_32_423_5632_1_rp_2024.tif` identify the lower-left kilometre
coordinates in UTM32. Only candidate cells available in the catalogue are downloaded;
optional world files are skipped. If multiple years exist for a cell, the newest
is selected. Conflicting entries for the same cell/year fail validation.
The exact catalogue and selected tile list are retained in each run's logs.
Catalogue HTTP failures use `download_attempts` (default 4 total attempts),
waiting 2, 4 and 8 seconds between attempts. Invalid catalogue metadata fails
without retrying. Every acquisition run fetches a new catalogue; it is not cached.
Candidate cells absent from the catalogue are recorded as `unavailable_bounds`;
they are not replaced with invented URLs. A listed tile that fails to download or
validate fails the run. An AOI with no published tiles also fails.

## Processing

Native tiles must have one Float32 band, 1000 × 1000 pixels, 1 m resolution,
NoData -9999, horizontal EPSG:25832 and declared vertical EPSG:7837 (DHHN2016).
Acquisition checks exact filename-derived extents. Processing rejects shifted or
rotated grids. Original downloads remain unchanged.

RLP and NRW reuse `dtm/countries/germany/processing.py`: clean working copies,
mosaic, average exact native 5 × 5 blocks, mask at target cell centres, publish
processed tiles, and stitch the final COG. Valid native contributors are averaged;
all-missing footprints stay NoData. The AOI mask is applied after averaging so
boundary cells retain their full native footprints, consistently with NRW.
No terrain reprojection, grid shift, vertical conversion or hole filling occurs.
The compound source CRS is checked; final output uses horizontal EPSG:25832 and
records the retained height datum in `VERTICAL_DATUM_NOTE`.

The target is the existing 5 m lattice with edges on multiples of 5 m. Set
`target.reference_raster` to the same suitable 5 m reference in multiple region
configs when identical extents and dimensions are required. Separate regional
AOIs otherwise produce different extents on the same lattice.

The supplied preparation note was used as source context. This integration does
not combine regions or harmonise the Netherlands' NAP datum. Before combining
regions, confirm their height references from their source documentation.

## Files and validation

```text
data/germany/rlp/
  raw_tiles/                      native TIFFs only
  <run_id>/
    processed/                      target tiles, grid/run/result metadata
      _work/                        intermediate rasters and reports
    stitched/rlp.tif            final 5 m COG (with associated VRT)
data/old_runs/germany/rlp/<run_id>/     preserved outputs from the older pipeline version
logs/preparation/germany/rlp/
  raw_receipts/                    native TIFF provenance and checksum records
  latest_run.json, latest_plan.json
  <run_id>/                       config, plan, manifests, logs and result
```

See [Data layout](DATA_LAYOUT.md) for per-run output, cache, package and migration rules.

On 3 October 2026 the supplied AOI produced 20,508 offline candidate tiles
(82.03 GB of uncompressed native Float32 pixels; not a download/disk-space estimate).
The full-region raster has not been prepared. Intermediate mosaics are retained,
so total working storage exceeds the native pixel estimate.
The inspected catalogue contained 20,507 of these candidate cells; one was absent.
Acquisition records such cells explicitly and retains NoData outside source coverage.

All 43 offline regression tests passed. They cover catalogue selection and sidecars, download integrity,
cache isolation, CRS/NoData validation, exact averages and regional outputs, alongside
the existing NRW and Netherlands checks. A live one-tile pilot processed a 200 × 200 m
AOI: all 1,600 target cells matched independent native block means exactly.
The live report is `data/old_runs/germany/rlp/pilots/validation.json`; test output is saved
in `logs/rlp_self_test.log`.
