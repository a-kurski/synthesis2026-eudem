# Germany terrain preparation: Saarland

`config.germany.saarland.json` selects the existing
`country_masks/Germany_Saarland.gpkg` AOI, Mapterhorn's native **1 m DGM1** source,
and the pipeline's current **5 m EPSG:25832** target.

```powershell
python main.py config.germany.saarland.json --plan
python main.py config.germany.saarland.json --probe
python main.py config.germany.saarland.json --yes
python main.py config.germany.saarland.json --self-test
```

`--plan` is offline. With cache reuse enabled, `--probe` and `--yes` first
inspect TIFFs directly in `data/germany/saarland/raw_tiles/`. Manually extracted
TIFFs need no existing receipts: native raster headers are validated, intersecting
tiles are selected, and local SHA-256 receipts are created in regional logs.
No TAR lookup or network request occurs when this local collection is used.

The local TIFF collection is treated as the supplied source dataset; missing
tiles within it are not inferred from the archive. Supply the complete extracted
collection (3,075 TIFFs for the pinned package), or use `--fresh-download` to
reacquire the package. Invalid local rasters or changed receipts stop acquisition
rather than silently accepting changed data.

When no local TIFFs exist, the archive fallback uses
`data/germany/saarland/source_archive/desaarland.tar`. `--fresh-download` bypasses
local reuse and replaces this archive only after successful checksum validation.
`--probe` returns one intersecting tile; `--yes` prepares all intersecting tiles.

## Source and attribution

The [Mapterhorn attribution catalogue](https://download.mapterhorn.com/attribution.json)
identifies `desaarland`, **DGM 1 Saarland**, resolution 1.0 m, access year 2025.
Its [raw archive](https://download.mapterhorn.com/sources/desaarland.tar) contains
the native GeoTIFFs, not the rendered terrain tiles used in the web viewer.

- Producer: **GeoBasis DE/LVGL-SL 2025**.
- Distributor: **Mapterhorn**.
- Licence: Datenlizenz Deutschland – Namensnennung – Version 2.0.
- [Authoritative LVGL source](https://www.shop.lvgl.saarland.de/cloud/index.php/s/wWELJP3D5aRsrqi?path=%2FOD_DGM1_tiff_LK).
- Pinned archive: 3,898,112,000 bytes; published MD5
  `2b5666aeb91ede0cc531331837b1b463`.

Archive fallback verifies the pinned size and MD5, uses bounded retries, and
renames the completed download atomically. No archive is searched for in logs.
Update both the pinned size and checksum when adopting a new upstream archive.

The archive has 3,075 TIFFs plus `metadata.json`, `bounds.csv`, `coverage.gpkg`
and `LICENSE.pdf`. Supporting files are preserved in run logs. Tile discovery
uses actual native raster headers through GDAL's `/vsitar/`; the coordinates in
the package's `bounds.csv` are not native UTM32 coordinates. Some edge TIFFs are
narrower than 1001 pixels. The downloader does not assume a fixed raster size.
Only regular TIFF members are selected; extraction writes basenames under the
shared regional raw-tile directory, without unpacking arbitrary archive paths or links.
Each extracted TIFF gets a SHA-256 receipt in regional logs, linking it to the verified archive.

## Grid and processing

The supplied note describes native 1 m data and suggests a common 1 m output.
The current workspace uses a 5 m target for NRW/RLP. Saarland therefore follows
the current pipeline: **native 1 m directly to the common 5 m grid**, with one
average-resampling operation and no intermediate 1 m alignment raster.

Unlike NRW/RLP, Saarland has half-metre pixel edges. For example,
`DGM1_tif_WND_375-5480.tif` has origin `(374999.5, 5481000.5)` and native NoData
`-10000000000`. The processor checks EPSG:25832, one Float32 band, exact 1 m
pixels, north-up orientation, half-metre edges, and declared finite NoData.
It reads the actual sentinel and masks from each raster; source copies stay intact.

Processing reuses the existing cleaning, mosaic, GDAL average alignment, polygon
masking, grid verification, COG publication and stitching helpers:

1. Select tiles intersecting the AOI buffered by the target half-cell diagonal.
2. Clean working copies, converting source NoData/masks/nonfinite values to -9999.
3. Mosaic selected tiles in sorted name order. Adjacent 1001-pixel tiles
   can overlap by one row/column; the VRT uses its normal last-valid-source
   precedence. It does not count overlapping copies as separate contributors.
4. Resample directly onto the exact reference extent and dimensions using the
   pipeline's **area-weighted average** method. Source and target CRS both remain
   EPSG:25832; there is no horizontal CRS change or vertical transformation.
5. Apply the AOI mask at target cell centres, verify alignment and publish.

NoData output is -9999, elevations are Float32 metres, and hole filling is
disabled. Native shifted pixels contribute according to their overlap area;
NRW's exact integer 5 × 5 block averaging would be incorrect for this source.
Set `target.reference_raster` to a suitable shared 5 m reference to require
identical extents and dimensions across regions. Without one, each AOI gets its
own extent on the same 5 m lattice.

The source TIFF declares only a horizontal CRS. Vertical datum compatibility
remains **unverified** and is recorded as such in output metadata/results. No
vertical EPSG code is invented and no height correction is applied.

## Outputs and validation

```text
data/germany/saarland/
  raw_tiles/                      native TIFFs only
  <run_id>/
    processed/                      target tiles, grid/run/result metadata
      _work/                        intermediate rasters and reports
    stitched/saarland.tif            final 5 m COG (with associated VRT)
data/old_runs/germany/saarland/<run_id>/     preserved outputs from the older pipeline version
logs/preparation/germany/saarland/
  raw_receipts/                    native TIFF provenance and checksum records
  latest_run.json, latest_plan.json
  <run_id>/                       config, plan, manifests, logs and result
```

See [Data layout](DATA_LAYOUT.md) for per-run output, cache, package and migration rules.

The supplied AOI plans a 15,063 × 11,757-cell output at 5 m. The full-region output
has not been prepared. The archive is available locally and the real-data probe
passed. Tests cover archive selection/extraction/integrity, cache reuse, half-pixel
area weights, native NoData, overlapping tile seams, output grids and existing
Netherlands/NRW/RLP behaviour. All **49 regression tests passed** on 3 October 2026;
see `logs/saarland_self_test.log`.

The real-data pilot uses a 200 × 200 m AOI from the inspected WND tile. Its report
is `data/old_runs/germany/saarland/pilots/validation.json`, with processing logs and outputs
under that pilot directory. It compares the 1,600 target cells to independent
source/target pixel-overlap calculations.
All 1,600 cells agreed within one Float32 rounding step: 1,592 matched exactly
and eight differed by at most 0.00003052 m. NoData masks matched exactly.
