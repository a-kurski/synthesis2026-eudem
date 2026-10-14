# Raster Variance and River-Region Growth

The program processes DEM GeoTIFFs in `data/`. For each DEM, it loads the
matching `{country}_classes_2018.tif` class raster, calculates a local
Gaussian variance map, and grows regions from minimum-variance cells within
the water mask. The class mask identifies seed locations only: grown regions
can extend outside it across valid DEM cells. It also retains the pairwise
DTM-comparison analyses for overlapping country DEMs. River-mask generation
does not polygonize results or run a sigma sweep.

## Inputs

- Each DEM must have a matching country class raster in `data/`, for example
  `NRW.tif` uses `Germany_classes_2018.tif`.
- Class-raster value `3` identifies seed locations; values `1` and `2` are
  ignored when choosing minima. The class raster is reprojected to the DEM grid
  with nearest-neighbor resampling; only its overlapping area is read and
  processed.
- The aligned class-3 mask is expanded by one DEM pixel in all directions.
  NoData DEM cells are excluded from variance calculation and region growth.
- DEM files whose basename ends in `_dep` are treated as deprecated and
  excluded from both mask generation and pairwise comparisons.
- DEM filenames must contain a recognized country name. German aliases include
  `NRW`, `RhPf`, `NiSa`, `Bayern`, and `Baden`.

## Processing and outputs

Local Gaussian variance is calculated on demand during seed selection and
region growth, using `GAUSSIAN_SIGMA` in `main.py`. The program evaluates
variance for class-3 seed candidates to find each component minimum, then
calculates a neighboring cell's variance only when region growth reaches it.
This avoids filtering the full DEM in advance. The saved variance raster
contains values calculated for seed candidates and the growth frontier;
unvisited cells are NoData.

Every 8-connected component of the buffered class mask is treated as a seed
area. Its lowest-variance cell becomes a seed. Region growth can proceed
through any valid DEM cell, inside or outside the class mask, and includes an
8-connected neighbor when its variance differs from the current grown cell by
no more than `REGION_GROWING_VARIANCE_TOLERANCE`. Since comparisons are
incremental, a region may extend along a gradual variance change even if its
endpoint differs from its seed by more than the tolerance.

Seeds with a minimum variance greater than `SEED_VARIANCE_THRESHOLD` are
discarded. The default threshold is `1e-3`; a seed exactly at the threshold is
kept. If every seed is discarded, the program writes an empty grown-region
mask rather than stopping the rest of the analysis.

The default tolerance is `0.005` in the variance map's squared elevation units.
It is a starting value for fine-tuning, not a validated threshold. Adjust it
in `main.py`.

For each input DEM, the program saves:

- `{dem}_variance.tif`: local variance across valid DEM cells; NaN NoData
  outside valid DEM cells.
- `{dem}_river_mask.tif`: value `1` for grown regions, `0` for other valid DEM
  cells, and `255` NoData elsewhere.

All outputs are written to `results/`. Run the workflow with:

```bash
python main.py
```

## Pairwise DTM comparison

After processing the raster masks, the program checks each pair of comparison
DEMs for spatial overlap. Non-overlapping pairs are skipped. For each
overlapping pair, it reprojects the second DEM to the first DEM's grid,
estimates and saves elevation uncertainty and spatial correlation, performs
Nuth-Kaab plus second-order deramp coregistration, and saves the aligned
elevation-difference raster. It also records mean, median, standard deviation,
RMSE, MAE, minimum, maximum, and the INSPIRE target percentage in
`dem_difference_statistics.csv`. These comparisons are independent of the
river-mask region-growing results.

The original comparison helpers remain available for local INSPIRE RMSE,
standard deviation, histogram, CDF, aspect, slope-error, border-strip, and
problem-region analyses. Pairwise comparisons use all non-class DEMs in
`data/`, excluding deprecated `_dep` rasters.
