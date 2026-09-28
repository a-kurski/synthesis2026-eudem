# AHN hole filling: implementation and cached-tile validation

27 September 2026 (pilot ID uses UTC: `20260926T221031Z`).

The optional stage is implemented in
`dtm/countries/netherlands/hole_filling.py` and integrated between the clean
native mosaic and the filled branch's warp. GDAL inverse-distance interpolation
uses original valid AHN donors, a bounded search radius and zero smoothing.
Only accepted NoData estimates inside the AOI are changed. Raw downloads and
the unfilled prepared baseline are retained.

## Offline cached-data pilot

[Detailed report and output paths](../data/pilots/hole_filling/20260926T221031Z/pilot_report.json)
and [compact generated report](../data/pilots/hole_filling/20260926T221031Z/PILOT_REPORT.md).

Three validated cached 1 km AHN tiles intersecting the configured
`netherlands.gpkg` polygon were deliberately selected for varied whole-tile
valid coverage: approximately 40.5%, 69.9% and 95.0%. The actual natural-gap
statistics use the intersection of that polygon with each tile's interior,
leaving 25 m of available context around the tile edge. They are not statistics
for the entire study area or the entire Netherlands.

| Search radius | Natural cells filled | Natural gaps filled | Remaining cells | Filled area |
|---:|---:|---:|---:|---:|
| 5 m | 464,642 | 36.15% | 820,569 | 116,160.50 m² |
| 10 m | 631,694 | 49.15% | 653,517 | 157,923.50 m² |
| 20 m | 873,525 | 67.97% | 411,686 | 218,381.25 m² |

The sample contained 1,285,211 candidate native cells (321,302.75 m²). Large gaps
remain beyond the bounded search distance. No error metric can be computed for
these natural gaps because their true ground elevations are unknown.

## Reconstruction of known AHN values

Artificial square gaps of width 4, 8 and 16 m were placed in valid terrain,
six of each size per tile: 54 holes and 24,192 withheld 0.5 m cells in total.
Each patch and an eight-pixel surrounding ring had originally valid values;
patches were spatially separated. Estimates were compared with the withheld AHN
values. Positive bias means the reconstructed surface was higher.

| Radius | Reconstructed / withheld | Bias | MAE | RMSE | 95th percentile absolute error |
|---:|---:|---:|---:|---:|---:|
| 5 m | 21,600 / 24,192 | −0.0066 m | 0.0531 m | 0.1236 m | 0.2259 m |
| 10 m | 24,192 / 24,192 | −0.0078 m | 0.0528 m | 0.1162 m | 0.2208 m |
| 20 m | 24,192 / 24,192 | −0.0076 m | 0.0522 m | 0.1101 m | 0.2231 m |

The 5 m metrics exclude unreconstructed cells, so their evaluation population
differs. The 10 and 20 m metrics use the same complete withheld set.

The pilot initially used **10 m** for integrated preparation. The workflow now
defaults to **20 m**, as requested on 27 September 2026. This is not an optimised or nationally
validated threshold. The 20 m experiment filled more natural gaps and had slightly
lower holdout RMSE, but it also extends estimates farther into unobserved terrain.

This pilot is exploratory: tiles were not randomly sampled, patches were squares,
there was no independent final test set or slope-stratified accuracy study, and
valid ground patches are not truth for terrain beneath buildings or water. It
does not reproduce or verify NRW's interpolation method. No NRW heights were used.

## Integrated preparation check

The first cached tile also passed the complete Netherlands preparation sequence
at the historical 10 m setting (before the new output-folder layout):
clean, mosaic, native filling, both elevation warps, AOI masking, fill-fraction
warp, and grid verification.

- Unfilled valid target cells: **274,568**.
- Filled valid target cells: **276,837** (2,269 newly valid).
- Target cells containing some interpolated contribution: **7,936**. This exceeds
  newly valid cells because averaging can mix filled and original contributions.
- Fraction and filled-height validity masks matched exactly, and fractions were
  within [0, 1].
- Original cached TIFF checksums matched before and after the pilot.
- Pilot compute time: approximately **47.8 s**, excluding initial selection.
- Saved pilot artifacts: approximately **247 MB**. Peak RAM was not measured.

Raw-source checksums, per-tile counts, per-hole errors, parameters and all output
paths are recorded in the detailed JSON report. The run stayed offline.

## Automated checks

**All 16 current-workflow tests passed on 27 September 2026** (8 preparation
tests and 8 hole-filling/control tests). They used real GDAL operations on small
synthetic rasters. Execution outside the desktop sandbox was required because
it blocks the test suite's temporary raster files. Fresh-download routing was
tested without making live network requests.

The current suite covers original preparation, constant-surface filling, exact
preservation of original valid values, polygon holes, outside-AOI exclusion,
large unsupported gaps, all-NoData inputs, processing-block independence,
cross-tile seam equivalence, buffer planning, fresh-download storage selection,
baseline equivalence, target fractions, configuration validation, and CLI
overrides. The updated suite additionally checks default-on/20 m settings,
legacy-cache reuse, the new download destination, target-tile coverage without
overlap, and exact stitched pixel values. Run `python main.py config.netherlands.json --self-test`.

## User controls

The default and current config enable filling with a 20 m radius and reuse the cache.

```powershell
# Existing cached downloads, with filling
python main.py config.netherlands.json --yes --fill-holes --reuse-cache
# Existing cached downloads, no filling
python main.py config.netherlands.json --yes --no-fill-holes
# Fresh download without filling, preserving old cached inputs
python main.py config.netherlands.json --yes --fresh-download --no-fill-holes
```

New raw data is saved under the new run's `raw_ahn_tiles` folder. Finished tiles
are in `processed_tiles`, and the assembled selected DTM is `ahn_stitched/ahn.tif`. Filling and
cache reuse can also be set independently through `hole_filling.enabled` and
`reuse_cache` in JSON. All gaps inside the AOI are eligible, including water;
the estimates over water are not measured bathymetry. Full-area production
processing was not run as part of this implementation.
