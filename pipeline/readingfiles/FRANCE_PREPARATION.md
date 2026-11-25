# France: IGN RGE ALTI 5 m

Use the existing France study mask or set `aoi` and `layer` in
`config.france.json`. Paths resolve relative to the config. Departments default
to `25, 54, 55, 57, 67, 68, 70, 88, 90`; these are strings, preserving leading
zeros for other mainland departments. The AOI may extend beyond French source
coverage. Its full target grid is retained, with unavailable areas left as NoData.

```powershell
python main.py config.france.json --plan
python main.py config.france.json --probe
python main.py config.france.json --yes
python main.py config.france.json --self-test
```

`--plan` is offline. `--probe` acquires one overlapping tile; the first probe
may download a whole department archive. `--yes` acquires and processes the AOI.
`download_workers` controls concurrent department archive downloads (default 4
in the supplied config; set 1 for sequential downloads). Downloads run in bounded
batches with separate HTTP sessions and shared request pacing. Metadata discovery
and tile extraction remain sequential. Valid archives are reused; completed
downloads survive a failed batch. A probe uses one department at a time. Because
department footprints overlap, a batch can acquire an extra neighbouring archive
before discovering that coverage is already sufficient.

## Storage and acquisition

```text
data/France/
  raw_tiles/
    25/RGEALTI_FXX_....asc     original 5 m ASCII tiles
    90/RGEALTI_FXX_....asc
  source_archive/90/*.7z      checksum-verified department downloads
  <run_id>/
    processed/               target tiles, grid, result and coverage report
      _work/                 native TIFFs, mosaic VRT, warp and mask
    stitched/rge_alti.tif     final COG

logs/preparation/france/
  raw_receipts/90/*.json      checksums, native grid and source provenance
  catalogue/90.json           pinned IGN archive edition, URL, size and MD5
  departments_2025.json       department boundaries for archive discovery
  <run_id>/                   config, plans, source manifests and logs
```

Existing local tiles are selected by their footprints and validated before use.
Valid supplied ASC files without receipts are adopted as local inputs; their
provenance does not claim a verified IGN download. Altered or truncated cached
tiles are rejected and missing coverage is recovered from the archive. Keep
receipts and catalogue records when moving caches between machines.

When local footprints do not cover the AOI, the adapter selects candidate
departments using cached administrative boundaries. A conservative boundary
buffer includes tiles straddling department borders. It discovers the latest
5 m Lambert-93/IGN69 edition from IGN's paginated Atom catalogue and verifies
the downloaded archive against IGN's byte size and MD5. Archives and their
pinned metadata are reused, including when a larger AOI needs additional tiles.
Only ASC tiles with positive-area intersection with the current AOI are extracted
and passed to processing. Boundary duplicates use a stable department/path order,
recorded in `rge_alti_manifest.json`.

The pipeline processes available overlapping tiles even when the AOI extends
beyond the configured departments' available coverage. Missing footprint area
is recorded in `rge_alti_manifest.json` and `coverage.json`, with a warning.
Source NoData holes and unavailable areas remain NoData; no extrapolation or
automatic AOI clipping is performed. `coverage_status` is `complete`, `partial`
or `empty`. Even an AOI with no available tiles produces an aligned all-NoData
COG with an `empty` status. A probe with no overlapping tile returns no sample.
Download failures, checksum errors and invalid source rasters still raise errors;
they are not treated as unavailable geographic coverage.

`--fresh-download` bypasses raw/archive reuse and refreshes catalogue editions.
Files are replaced only after validation; prior processing runs remain untouched.
First-time archive access requires GDAL >= 3.7 with libarchive `/vsi7z/` support
(available in this workspace's QGIS 3.40.11 environment). No extra Python package
or 7-Zip installation is required. Solid archives can take time to extract.

## Processing

Selected sources must have one band, 1000 x 1000 cells, 5 m spacing, a finite
declared NoData value and EPSG:2154 when a CRS is embedded. Missing ASCII CRS is
assigned from the product declaration; a conflicting CRS fails. IGN filenames
refer to the north-west **cell centre**, so footprint edges are offset by 2.5 m.
The raster header is checked against this footprint. NoData is read from each
source, not assumed to be `-9999` (the live department 90 sample uses `-99999`).

ASC-to-GeoTIFF conversion preserves values, NoData and grid without resampling.
A native Lambert-93 VRT mosaic feeds one bilinear warp directly to the common
EPSG:25832 5 m reference grid, including its exact extent and dimensions.
Set the same `target.reference_raster` in different country configs when their
full extents and dimensions must match. Without a reference, each AOI gets its
own extent on the same 5 m lattice.

The final pixel-centre AOI mask uses `-9999` outside the AOI. Published target
tiles and the stitched output are lossless Float32 COGs, verified against the
prepared surface. Metadata retains IGN provenance and IGN69; `-novshift`
disables automatic vertical correction. Hole filling is not enabled for France.

## Small live pilot

```powershell
python scripts/france_pilot.py --plan
python scripts/france_pilot.py
```

This uses a small Belfort AOI and only department 90, reuses the shared cache,
and writes all pilot products under `logs/preparation/france/pilots/<run_id>/`.
It validates the final COG and repeats acquisition to check tile reuse. It does
not update production latest-run pointers or process the full France study mask.

Verified on 7 October 2026 with QGIS GDAL 3.11.3: all 97 offline regression tests
passed. The Belfort pilot produced 4,004 valid AOI cells, no missing source area,
no remaining AOI NoData cells, and no COG validator errors or warnings. Repeat
acquisition reused the same tile. The report is in
`logs/preparation/france/pilots/2026-10-07_16-52-13/pilot_report.json`.
The full France study-area run was planned but not executed.

## Source references

- [IGN RGE ALTI catalogue](https://data.geopf.fr/telechargement/resource/RGEALTI)
- [Official department boundaries, 2025](https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/departements-100m.geojson)
- [GDAL RGE ALTI tutorial](https://gdal.org/en/stable/tutorials/raster_dtm_tut.html)
- [GDAL archive support](https://gdal.org/en/stable/user/virtual_file_systems.html#vsi7z-7z-archives)
