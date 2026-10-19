# Findings and known issues

Collected during development and the first full runs of the Rhine-basin configuration (`pipeline.json`, October 2026). Data findings are specific to that configuration; pipeline and environment issues apply to any use of the code.

Status: **Open** = needs action or investigation, **Mitigated** = worked around but not fully solved, **Fixed** = solved in the code or config.

## Summary of open items

| # | Item | Section |
|---|---|---|
| D1 | Luxembourg heights: confirm the geoid conversion removes the ~48 m offset | [D1](#d1-luxembourg-heights-are-ellipsoidal-48-m-offset) |
| D2 | RLP is offset ~0.5 m northwards relative to all neighbours | [D2](#d2-rlp-has-a-systematic-05-m-offset-in-y) |
| D3b | BW: reprocess with `source_nodata: 0` and verify | [D3b](#d3b-baden-württemberg-undeclared-zeros-inside-tiles) |
| D5 | Saarland/France: many cells above threshold without a systematic shift | [D5](#d5-saarland--france-many-local-disagreements) |
| D7 | NL and FR heights are not transformed to EVRF2007 | [D7](#d7-height-systems-without-a-real-transform-to-evrf2007) |
| D8 | EVRF2019 not available; output is EVRF2007 | [D8](#d8-evrf2019-not-available) |
| D10 | ~4000 km² of the basin not covered (Austria, Belgium, Thuringia) | [D10](#d10-parts-of-the-basin-not-covered) |
| P7 | Comparison results so far are incomplete (no borders file, missing river masks) | [P7](#p7-comparison-results-so-far-are-incomplete) |

## Data findings

### D1. Luxembourg heights are ellipsoidal (~48 m offset)

**Status: Mitigated (needs verification)**

- Nuth & Kaab gives a vertical shift of −47.9 m for Luxembourg against both RLP and Saarland. RLP/Luxembourg had 5.4 M cells above the threshold.
- The geoid in Luxembourg is about 47–48 m above the GRS80 ellipsoid. So the lidar DEM (`MNT_Lidar2024.tif`) is almost certainly in ETRS89 ellipsoidal heights, not NG95 (EPSG:5774) as first configured.
- **Fix:** Luxembourg now has `vertical_crs: 4937` and `geoid: geoids/us_nga_egm08_25.tif`. The pipeline subtracts the geoid height (H = h − N).
- **Remaining:**
  - Confirm the height reference in the dataset's metadata.
  - After the rerun, the Nuth & Kaab vertical shift against RLP and Saarland should be close to 0. Whatever is left is the mismatch between EGM2008 and EVRF2007, likely cm to dm.
  - A regional geoid (EGG2015, or Luxembourg's official one) would be more accurate than the global EGM2008.

### D2. RLP has a systematic ~0.5 m offset in y

**Status: Open**

Nuth & Kaab shifts with RLP as one side of the pair:

| Pair | Shifted DEM | y shift |
|---|---|---|
| RLP / Saarland | Saarland | +0.530 m |
| RLP / Hessen | Hessen | +0.518 m |
| RLP / BW | BW | +0.509 m |
| RLP / Luxembourg | Luxembourg | +0.524 m |
| RLP / France | France | +0.277 m |
| NRW / RLP | RLP | −0.468 m |

The neighbours agree with each other: Saarland/France gives −0.003 m, and Hessen/BW −0.013 m. So RLP is the outlier.

- **Likely cause:** half a 1 m source cell, i.e. a corner-vs-centre mix-up in the georeferencing. It may only affect the RLP tiles whose CRS was defined differently (see P5).
- **Impact:** a tenth of a 5 m cell, but systematic. It shows up as height differences on slopes along every RLP border.
- **To do:** run `gdalinfo` on a few RLP tiles of each type and check whether their origins are whole metres or end in .5.

### D3. Hessen: tiles without a CRS or NoData value caused a fake surface

**Status: Fixed**

- About half of Hessen came out as a near-zero surface, rising gently from 0.01 to 0.02 m.
- **Cause:**
  - Some Hessen tiles have no CRS, and `gdal.BuildVRT` left them out of the mosaic.
  - The tiles declare no NoData value, so gaps in the mosaic read as 0 m.
  - The DHHN2016 → EVRF2007 transformation then added its cm-level offset to those zeros, which is the gradient.
- **Fix:**
  - The mosaic now accepts tiles regardless of CRS (`allowProjectionDifference=True`); the region's `crs` from the JSON applies to all of them.
  - If the tiles declare no NoData value, the mosaic gets one (`VRTNodata`).
- **Requirement:** tiles without a CRS must still have a valid origin and cell size (e.g. from `.tfw` world files).
- **Result:** after reprocessing, the Hessen comparisons show cm-level shifts and few cells above the threshold.

### D3b. Baden-Württemberg: undeclared zeros inside tiles

**Status: Mitigated (needs reprocessing and verification)**

- Parts of BW came out with near-0 heights instead of NoData, the same symptom as Hessen (D3).
- **Cause:** the BW tiles themselves contain 0 for missing data without declaring it as NoData. The Hessen fix only covers gaps *between* tiles, so these zeros were read as 0 m, got the DHHN2016 → EVRF2007 offset added, and were averaged into neighbouring cells.
- **Fix:** new per-region setting `source_nodata`, set to `0` for `germany_bw`. That value is then treated as NoData in the tiles, so the warp ignores it, including when averaging.
- **To do:**
  - Confirm the fill value: `gdalinfo -stats` on an affected tile should show no `NoData Value` line and `Minimum=0`.
  - Delete `<output_dir>/germany_bw` and rerun. The comparisons with BW then rerun automatically, since its DEM is newer than their statistics.

### D4. RLP tiles dropped because of different CRS definitions

**Status: Fixed**

Some RLP tiles define the same CRS differently, and `BuildVRT` skipped them. They're included now, by the same fix as D3.

### D5. Saarland / France: many local disagreements

**Status: Open**

- 427,598 cells are above the threshold (537 problem regions), far more than any other pair except those with Luxembourg.
- The Nuth & Kaab shift is small (x −0.073, y −0.003, z −0.020 m), so this isn't a global offset.
- **Possible cause:** parts of RGE ALTI come from older or photogrammetric sources.
- **To do:** inspect `problem_regions_germany_saarland_france.gpkg`.

### D6. BW / Bavaria: many cells above threshold

**Status: Open (recheck after the rerun)**

237,395 cells are above the threshold. Neither region had a river mask when the comparison ran (see P1), so rivers (Main, Danube tributaries) were not excluded. Rerun the comparison before drawing conclusions.

### D7. Height systems without a real transform to EVRF2007

**Status: Open (accepted for now)**

| Region | Source height system | PROJ → EVRF2007 (5621) |
|---|---|---|
| Germany (all states) | DHHN2016 (7837) | real transformation (offset) |
| Switzerland, Liechtenstein | LN02 (5728) | real transformation (offset) |
| Netherlands | NAP (5709) | only a no-op ("ballpark"); heights unchanged |
| France | NGF-IGN69 (5720) | only a no-op ("ballpark"); heights unchanged |
| Luxembourg | ETRS89 ellipsoidal | geoid subtracted (D1) |

- For NAP and NGF-IGN69 the true datum offset to EVRF2007 isn't applied. It's small for NAP; for NGF-IGN69 it may be larger.
- The pipeline logs `PROJ has no EPSG:a -> EPSG:b transformation here; heights are NOT shifted` for these regions.

### D8. EVRF2019 not available

**Status: Open (accepted)**

There's no xdem implementation, and the EVRF2019 grids (`nl/de/fr/ch_2019z.asc`) aren't on the PROJ CDN. The output therefore uses EVRF2007 (EPSG:5621) instead of EVRF2019 (9389/9390).

### D9. "Several coordinate operations are going to be used"

**Status: Open (low impact)**

- GDAL logged this during the France warp, which is the most likely source. It means PROJ uses different transformations in different parts of the area, so small seams are possible.
- **Possible fix:** passing `-to ONLY_BEST=YES` to the warp. That's not implemented; it would need a JSON option for the transformation settings.
- Don't use `ALLOW_BALLPARK=NO`: it would make NL, FR and LU fail, since a no-op is their only option.

### D10. Parts of the basin not covered

**Status: Open**

Austria, Belgium and Thuringia (roughly 4000 km² of the basin) aren't in the configuration. Outlines exist in `country_masks/` but no data or region entries.

### D11. Netherlands: large number of gaps

**Status: Open (probably fine)**

- Gap filling filled 1,040,415 of 142,772,063 candidate cells and left 141,731,648.
- Most of these are probably sea and buffer area outside the data, beyond `max_distance_m`. Check the fill mask to confirm.
- The NL warp is slow (about 1h20m for 0.34 billion cells). That's expected with fine (0.5 m) source tiles averaged to 5 m.

### D12. Liechtenstein uses the Swiss tile set

**Status: Accepted**

Liechtenstein's `raster` glob points at all 28,757 Swiss tiles. It works, but building the mosaic takes a few minutes for a small region.

### D13. False pairs in the comparison

**Status: Accepted (harmless)**

- The comparison picks pairs by overlapping DEM bounding boxes. NRW/Bavaria, Saarland/BW and Hessen/France therefore get "compared", then skipped with "no shared valid elevation pixels".
- These regions don't border each other; NRW and Bavaria are about 90 km apart.
- **Possible improvement:** use the intersections from the `vectors` stage instead of bounding boxes.

## Pipeline and runtime issues

### P1. River masks ran out of memory in parallel

**Status: Fixed**

- With 4 regions at once, RLP, BW, Bavaria and France failed with allocation errors (5.7 GiB and 11.2 GiB arrays).
- River masks now run one region at a time.
- A single region still needs roughly 25–30 bytes per cell at peak, so 75–90 GB for Bavaria (3 billion cells).
- **Possible improvement:** processing in chunks, if memory is limited.

### P2. GDAL warp memory units

**Status: Fixed**

- GDAL reads `warpMemoryLimit` values below 10000 as MB and larger values as bytes, so `16384` was taken as 16 KB ("unreasonably small"). The pipeline now converts MB to bytes.
- `GDAL_CACHEMAX` has its own rule: values below 100000 are MB.

### P3. Nearest-value fallback in gap filling is very slow

**Status: Mitigated**

`hole_filling.nearest_fallback: true` ran for hours on NL, because of its large empty areas. It's set to `false` in `pipeline.json`.

### P4. Run stopped after the rivers stage; comparison ran anyway

**Status: Mitigated (usage)**

- The river-mask failures (P1) ended the run with an error, so `overlaps` and `assemble` didn't run.
- The comparison was chained with `;`, so it ran anyway on incomplete inputs.
- Use `&&` to chain the commands, and `set -o pipefail` when piping into `tee`. Otherwise `tee` hides the failure.

### P5. Mosaic dropped tiles with a different CRS

**Status: Fixed.** See D3 and D4.

### P6. Comparison crashed on one pair

**Status: Fixed**

- xdem's uncertainty estimate raised a `QhullError`, which stopped the whole comparison.
- The uncertainty estimate is now optional (skipped with a message), and each pair runs inside its own error handler. Failed pairs are listed at the end.

### P7. Comparison results so far are incomplete

**Status: Open**

- `country_masks/borders.gpkg` was missing on the server, so all distance-to-border analyses were skipped.
- RLP, BW, Bavaria and France had no river masks (P1), so rivers weren't excluded for their pairs.
- Rerun the comparison once both are fixed.

### P8. Forking worker processes after GDAL started threads

**Status: Fixed (no longer relevant)**

- Parallel river masks used forked processes, which crashed because GDAL threads were already running. Switching to "spawn" fixed it.
- River masks are now sequential (P1), so this no longer applies.

### P9. Mosaic of tiles with declared NoData was slow

**Status: Fixed**

- Always forcing a NoData value on the mosaic (the D3 fix) slowed down the France warp.
- The value is now only forced when the tiles declare none.
- Converting the France ASCII tiles to GeoTIFF would speed it up further. That hasn't been done.

## Method notes

### M1. River growing compares elevations, not a variance

**Status: Fixed (renamed)**

- The region growing compared raw elevations: a neighbour joins a water body if its height differs by at most `tolerance_m` (0.02 m by default). That's a flat-water criterion. The code called these values a "local variance", which was misleading.
- The code now uses elevation names throughout (`grow_water_regions`, `current_height`).
- The `*_variance.tif` output is no longer written. It only held a copy of the DEM heights for the cells the growing visited. Dropping it also saves about 4 bytes per cell of memory.
- Datasets with heights stored in coarse steps (e.g. 1 cm) may need a different tolerance. That's possible per region via `river_growing.tolerance_m`.

### M2. Interpolated cells in the threshold mask

**Status: Fixed**

`exceeds_threshold_*.tif` and the problem regions used to include gap-filled cells. Those cells are now left out:

- they're marked 255 in the mask, like missing data and water;
- they're ignored when building the problem regions.

The statistics CSVs still report the results both with and without filled cells.

### M3. Overlaps only resolved where one side is interpolated

**Status: By design**

Where both regions are measured, each region keeps its own data inside its outline: no averaging, and no feathering of rivers. Disagreements between two measured datasets are reported by the comparison but not corrected.

### M4. Harmless warnings in the comparison log

xdem and numpy warnings such as `Covariance of the parameters could not be estimated`, `Mean of empty slice`, `invalid value encountered in sqrt`, `nodata must be set. Setting default nodata to 255` and `Output projection, bounds and grid size are identical` don't affect the results.

## Environment notes

| Issue | Solution |
|---|---|
| The server's system GDAL couldn't read LERC-compressed tiles (several German states) | Use a conda-forge environment (micromamba `eudem`) |
| `scikit-gstat` isn't on conda-forge | Install it with `pip` inside the environment |
| `SyntaxError` on start-up | The environment wasn't active; plain `python` was Python 2 |
| Files on the Windows side have CRLF line endings | Harmless for Python and JSON; watch out when editing with `sed` |
| Server and local copies drifted apart (an older `pipeline.py` was in use) | Copy all of `dtm/` and the JSONs together when updating the server |
| Geoid grid not found | The `geoid` path is relative to the JSON. Download with `curl -fL` so a failed download isn't saved as a small error page |
