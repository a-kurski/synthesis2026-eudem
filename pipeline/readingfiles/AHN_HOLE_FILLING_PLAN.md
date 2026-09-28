# Plan: optional hole filling for Netherlands AHN preparation

Status: initial implementation completed on 27 September 2026. See
[implementation and pilot validation](HOLE_FILLING_VALIDATION.md) and
[current usage](NETHERLANDS_PREPARATION.md). This document retains the original
design; pilot limitations and deferred evaluation are described in the validation report.
Prepared against the current Netherlands module on 26 September 2026.
The active config currently selects `netherlands.gpkg`; retain that user choice.

## Objective and scientific meaning

Estimate terrain elevations in AHN NoData holes inside the study area so later comparisons
can include them. Preserve the original downloads, existing valid AHN elevations,
and an unfilled reference output. Filling estimates unobserved terrain; it does
not recover measured ground, harmonise vertical datums, or reproduce NRW's
production methodology.

AHN documents its 0.5 m DTM as a raster derived from classified ground points,
with NoData where ground was not measured, including water and beneath buildings.
Thus a hole cannot be identified as a building solely from its NoData value.
Source: [AHN products](https://www.ahn.nl/producten).

## Placement in the current pipeline

```text
Polygon and target-grid plan
  → plan AHN acquisition with surrounding context when filling is enabled
  → download/reuse raw tiles
  → clean native tiles
  → mosaic at 0.5 m in EPSG:28992
  → identify NoData cells inside the original study polygon     NEW
  → fill a separate copy from surrounding original valid AHN    NEW
  → reproject/average once per output branch to the target grid
  → final clean and original-AOI mask
  → alignment checks, coverage counts, provenance
```

Interpolate on the native mosaic before warping. This avoids treating download
tile boundaries as terrain boundaries, and avoids defining holes after 1 m
averaging has already changed their shape. Retain the original AOI for the final
mask; the context buffer must not enlarge the target grid or comparison area.

When filling is disabled, preserve the existing acquisition plan and processing
path. When enabled, keep both an unfilled baseline and a filled alternative.
Do not silently replace the meaning of the existing `ahn_prepared.tif` product.

## Hole selection policy

The user prefers targeting all holes inside the study area. Plan the initial
mode as `all_aoi_nodata`: all originally invalid native cells whose centres are
inside the original AOI are candidates. Do not require building footprints,
water masks, enclosed-component classification, or an arbitrary hole-area limit.

1. Derive validity from the cleaned mosaic using the existing validity rules.
2. Rasterise the original AOI on the native grid and select invalid cells inside
   it. AOI polygon holes are deliberately excluded study areas, not elevation
   gaps: preserve those exclusions and all area outside the polygon.
3. Interpolate candidates from original valid AHN within the configured maximum
   donor-search distance. Valid neighbouring terrain outside the AOI can supply
   context; estimates are accepted only inside the AOI.
4. Accept successful finite estimates and leave cells without adequate nearby
   support as NoData. A large hole may be partly filled; report this explicitly.
5. Flag all accepted estimates. Preserve original valid elevations exactly.

This selection includes water gaps and missing coverage inside the polygon.
Estimated water-area elevations are not measured bathymetry or water levels.
Ordinary distance-based interpolation can bridge rivers and embankments; the
unfilled baseline and provenance flags are essential for interpreting these
areas. Optional exclusion masks can be added later if the user changes scope.

Targeting every hole is distinct from guaranteeing a value in every cell. A
bounded local interpolation cannot reconstruct arbitrarily large unsupported
areas. Report the residual NoData rather than silently invoking nearest-neighbour
extrapolation or using NRW elevations. A requirement for 100% completeness would
need a separately agreed fallback estimator and its own validation.

## Initial method

Start with the installed GDAL Python `FillNodata` algorithm using inverse-distance
interpolation and zero smoothing. It uses a four-direction search around missing
pixels and is documented for filling gaps in continuously varying rasters such
as elevation models. No additional raster-processing dependency is needed for
the interpolation itself. This is a baseline to evaluate, not a declaration that
it is the best terrain estimator everywhere.

References: [GDAL Python API](https://gdal.org/en/stable/api/python/utilities.html),
[GDAL filling algorithm](https://gdal.org/en/stable/api/gdal_alg.html#_CPPv414GDALFillNodata15GDALRasterBandH15GDALRasterBandHdiiPPc16GDALProgressFuncPv).

Search distance is in pixels in GDAL; expose metres in the configuration and
convert using the actual native pixel size. For example, 10 m corresponds to
20 pixels at 0.5 m. Search radius is not a maximum hole diameter or area.
The initial all-holes scope imposes no area cutoff; hole size remains a useful
diagnostic when reviewing interpolation quality.

Use only original valid AHN values as donors. Keep a fixed original-validity
mask while generating candidate estimates, then merge only eligible successful
estimates into the final copy. Do not mark protected NoData as valid donors just
to prevent GDAL from filling it. Do not repeatedly expand the donor set with
previously estimated values. Restore/protect every originally valid cell.

Start with no smoothing so the baseline is easier to assess and masks are easier
to reason about. Smoothing, TIN/linear interpolation, or other methods are later
experiments if validation shows unacceptable artifacts, especially on slopes,
embankments or large building footprints.

## Context and scale

When enabled, buffer the source acquisition AOI in EPSG:28992 by at least the
search radius plus a raster-cell margin; reuse the stable native chunk lattice
and unchanged raw tile IDs/receipts. Some additional neighbouring tiles may be
needed even if all existing AOI tiles are cached. Explain this in `--plan`.

Do not load the entire native Netherlands mosaic into memory. Implement mask
creation and final merging by raster blocks. The all-holes scope does not require
connected-component classification, which keeps the initial implementation
smaller. If per-hole size diagnostics are added, component identification must
operate across block edges and be benchmarked for fragmented NoData.

For an initial pilot, GDAL filling can operate on a disk-backed raster copy.
For larger runs, either keep a measured feasible whole-mosaic implementation or
process windows with a read halo covering the search radius and write only their
cores. Keep the original validity and candidate masks fixed. Compare windowed results against the whole-mosaic
method and place holes across both window and tile boundaries in tests.

## Configuration contract

Add an optional `hole_filling` section to the Netherlands config. Keep it disabled
by default so existing configurations retain current behavior. Proposed fields:

| Setting | Purpose |
|---|---|
| `enabled` | Explicitly activate the new stage. |
| `method` | Initially only `gdal_idw`. |
| `max_distance_m` | Maximum original-donor search distance. |
| `selection` | Initially `all_aoi_nodata`, following the user's preference. |
| `smoothing_iterations` | Initially restricted to zero. |

Parameter values must be calibrated. Trial radii of 5, 10 and 20 m are a proposed
experiment, not an established production default. Review large buildings and
water gaps explicitly and increase trial distances only with supporting results.
Validate units, positive finite limits and supported methods before acquisition.
Include resolved parameters and the AOI hash in logs.

## Original proposed configuration shape

```json
"hole_filling": {
  "enabled": true,
  "method": "gdal_idw",
  "selection": "all_aoi_nodata",
  "max_distance_m": 10,
  "smoothing_iterations": 0
}
```

The 10 m value was subsequently pilot-tested and adopted as the initial
configurable setting; it is not nationally validated. No building or water
dataset is required for this mode.

## Files and interfaces to change during implementation

| File | Planned change |
|---|---|
| `dtm/countries/netherlands/hole_filling.py` (new) | AOI candidate mask, interpolation, original-value protection, provenance masks and report. |
| `dtm/countries/netherlands/processing.py` | Call the optional stage between mosaic and warp; prepare filled and unfilled branches on the same target. |
| `dtm/countries/netherlands/__init__.py` | Validate settings and expand the acquisition geometry only when needed. |
| `dtm/coordinator.py` | Report filling/context plan and include output/report paths in result metadata without owning the interpolation method. |
| `config.netherlands.json` | Add explicit settings only when implementation is accepted; preserve the user's current AOI. |
| `tests/test_hole_filling.py` (new) | Numerical, selection, seam, provenance and disabled-mode regression checks. |
| `NETHERLANDS_PREPARATION.md` | Explain options, donor restrictions, artifacts and interpretation. |

Keep raw-cache behavior and `version_1` unchanged. Store all filled surfaces as
new derived run products. Fingerprint fill settings and the AOI separately
from raw tile identity so changing interpolation does not force redownloading.

## Outputs and provenance

- Existing `ahn_prepared.tif`: unfilled baseline, same meaning as today.
- `ahn_prepared_filled.tif`: alternative prepared terrain after accepted filling.
- `ahn_fill_mask_native.tif`: which previously invalid 0.5 m cells were filled.
- `ahn_fill_fraction.tif`: fraction of valid source contribution to each 1 m
  target elevation that came from accepted interpolation.
- `hole_filling_report.json`: candidate, filled and residual cell counts and areas,
  before/after validity counts, parameters, algorithm/software versions, AOI hash,
  and timing/storage measurements. Per-hole diagnostics are optional.

Compute target fill fraction by giving original valid pixels 0, accepted filled
pixels 1, and remaining invalid pixels NoData, then using the same average warp,
extent, dimensions, and AOI mask as the filled elevations. The fraction is relative
to contributing valid source data, not necessarily the complete target footprint.
This is more informative than nearest-neighbour resampling of a binary flag:
one target elevation can mix original and interpolated contributions.

Later comparison should report all-valid results and results grouped by zero
versus nonzero interpolation contribution. A reduced AHN–NRW difference is not
independent evidence of improved accuracy; NRW must not be used as the donor
surface for the AHN being evaluated against it.

## Validation and acceptance

1. Synthetic constant/sloping/curved terrain with artificial holes; preserve all
   original valid native values exactly and verify expected constant-surface fills.
2. Holes across tile/window edges; verify consistent output independent of tile
   subdivision or processing block size.
3. All NoData inside the AOI is eligible, including synthetic water-like and
   large gaps; outside-AOI cells and AOI polygon holes remain excluded. A gap
   touching the AOI boundary may fill using buffered neighbouring terrain.
4. Insufficient support leaves the affected cells unchanged. No infinite/NaN/sentinel
   elevations are introduced as valid data.
5. Original downloads and cache receipts retain their checksums; target CRS,
   transform, extent and dimensions match the existing target exactly.
6. Filling disabled reproduces the existing outputs and acquisition plan.
7. Provenance fractions identify mixed pixels, remain between 0 and 1 where
   valid, and share the final grid and AOI mask.
8. Hide patches of known valid AHN terrain resembling actual building-hole
   shapes; reconstruct them and measure bias, MAE, RMSE and high absolute-error
   percentiles, grouped by size and slope. Use spatially separate tuning and
   evaluation patches. These are proxy checks, not ground truth under buildings.
9. Visually inspect hillshade and profiles for a small urban, rural, sloping and
   riverside sample. Measure runtime/disk/RAM before a large-area run.

Implement in four stages: inventory actual gaps; pilot AOI-only selection/IDW
on small areas; integrate config, outputs and tests; then evaluate and choose
production search distances. Evaluate a small sample before the full study area.
