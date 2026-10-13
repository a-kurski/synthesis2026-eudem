# Continuous AHN raster

The Netherlands configuration fills holes after resampling to the 5 m target
grid. Original valid elevations are preserved, and only missing cells inside
the AOI are filled (polygon exclusions stay excluded).

```json
"hole_filling": {
  "enabled": true,
  "method": "gdal_idw",
  "selection": "all_aoi_nodata",
  "max_distance_m": 100,
  "smoothing_iterations": 0,
  "nearest_fallback": true
}
```

IDW first searches within 100 m. If AOI holes remain, GDAL nearest-neighbour
filling searches across the available input raster. Both passes use only
original valid cells as donors; fallback does not overwrite IDW results.
The fallback requires GDAL 3.9 or newer. It uses disk-backed rasters and
blockwise merging, but the raster-wide search can be slow on large inputs.
The radius is configurable; 100 m is an initial setting, not an accuracy claim.

With at least one valid donor in the input raster, fallback fills every AOI
candidate or raises an error if it cannot. An entirely empty input cannot be
filled; its report records incomplete coverage, and preparation fails if no
valid AOI output exists. No values are synthesized from a constant default.
Set `nearest_fallback` to false to retain distance-limited IDW behaviour.

The hole-filling report records IDW and nearest counts, available donors,
remaining NoData, and `complete_aoi_coverage`. The work-directory
`ahn_fill_mask.tif` uses 0 for cells not filled, 1 for IDW, and 2 for nearest
fallback. The published `ahn_fill_fraction.tif` retains its existing meaning:
0 for original valid cells, 1 for either fill method, and NoData for invalid
or excluded cells. The unfilled baseline is retained.

River gaps are included. Their filled elevations are a continuous estimate
from surrounding terrain, not measured water levels or riverbed elevations.
Existing output rasters are unchanged until preparation is run again.
