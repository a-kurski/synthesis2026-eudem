# Regional DTM merge pipeline

Merges digital terrain models from several regions (countries, states, provinces, ...) into one seamless DTM in a common horizontal and vertical reference system, and compares the regions where they overlap.

Each region can come with its own tile format, CRS, height system, nodata convention and gaps. All of these differences are described in one JSON file; none of them is hardcoded. To process a different set of regions you write a new JSON, not new code.

Downloading data and point-cloud processing are out of scope: the pipeline starts from raster tiles that are already on disk.

## Contents

- [How it works](#how-it-works)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Outputs](#outputs)
- [Comparison](#comparison)
- [Running large jobs](#running-large-jobs)
- [Tests](#tests)
- [Code layout](#code-layout)
- [Limitations](#limitations)

## How it works

`main.py` runs five stages in order. Each stage reads the JSON, does its work and writes what it produced (file paths) back into the same JSON. A rerun skips everything that's already recorded and exists on disk, so an interrupted run resumes where it stopped.

1. **`vectors`**: buffers every region outline by `buffer_m` and records which regions intersect.
2. **`rasters`**: for each region, builds a virtual mosaic of its tiles and warps it in one step to the target CRS, height system and resolution. Each region's DEM keeps a `buffer_m` margin beyond its outline, so neighbouring DEMs overlap. Optional extras per region: subtracting a geoid for ellipsoidal heights, gap filling (with a mask of the filled cells) and cropping to the outline.
3. **`rivers`**: for each region, grows a water mask over the DEM, starting from seed cells taken from a water raster. The comparison uses these masks to leave water surfaces out of the statistics.
4. **`overlaps`**: where two regions overlap and one region's cell was interpolated (gap-filled) while the other has a measured value, the measured value replaces it. Nothing else is changed: no averaging, no feathering.
5. **`assemble`**: writes each region's DEM inside its own outline, applies the overrides from the previous stage, masks everything outside the overall extent and writes the result as a Cloud Optimized GeoTIFF. It also stitches the regions' river masks the same way, each inside its own outline, into one binary river mask on the same grid (1 = water, 0 = land, 255 = NoData).

The comparison (`python -m dtm.comparison`) is a separate step that runs on the region DEMs after the pipeline.

## Installation

You need Python 3.10 or newer and GDAL 3.8 or newer with its Python bindings. Install GDAL from conda-forge or your system packages; `pip install gdal` usually fails or gives a GDAL without the drivers you need. If your tiles use LERC compression, the GDAL build must support LERC; conda-forge's does.

With micromamba or conda:

```bash
micromamba create -n dtm -c conda-forge python gdal numpy scipy tqdm \
    xdem geoutils rasterio numba geopandas pandas matplotlib
micromamba activate dtm
pip install scikit-gstat        # used by xdem's uncertainty estimate; not on conda-forge
```

The `vectors`, `rasters`, `overlaps` and `assemble` stages only need GDAL, numpy, scipy and tqdm. The `rivers` stage and the comparison also need the xdem stack (see `requirements.txt`).

Check your install by running the tests (see [Tests](#tests)).

### Height transformations and PROJ grids

Height system changes are done by PROJ, and many of them need grid files. Either install the grids you need (`projsync --source-id <agency>`) or let PROJ download them on demand:

```bash
export PROJ_NETWORK=ON
```

If PROJ only knows a "ballpark" transformation between two height systems, it leaves heights unchanged. The pipeline then logs a warning for that region (`PROJ has no EPSG:a -> EPSG:b transformation here; heights are NOT shifted`). You can see which transformations PROJ would use with:

```bash
projinfo -s EPSG:<source> -t EPSG:<target> --spatial-test intersects
```

## Quick start

1. Put each region's outline (a polygon in any vector format GDAL reads) and its DEM tiles somewhere on disk.
2. Write a JSON file. A minimal example with two regions:

   ```json
   {
     "settings": {
       "crs": 3035,
       "vertical_crs": 5621,
       "resolution": 5,
       "extent": null,
       "output_dir": "output"
     },
     "regions": {
       "region_a": {
         "vector": "outlines/region_a.gpkg",
         "raster": "data/region_a/**/*.tif",
         "crs": 25832,
         "vertical_crs": 7837,
         "interpolate": false
       },
       "region_b": {
         "vector": "outlines/region_b.gpkg",
         "raster": "data/region_b/*.asc",
         "crs": 2154,
         "vertical_crs": 5720,
         "interpolate": true
       }
     }
   }
   ```

3. Run it:

   ```bash
   python main.py my_config.json
   ```

The merged DTM is written to `output/merged_dtm.tif`. Paths in the JSON are relative to the JSON file itself, not to the folder you run from.

Other ways to run it:

```bash
python main.py my_config.json --stages rasters overlaps assemble   # only some stages
python -m dtm.river_mask my_config.json                            # river masks only
python -m dtm.comparison my_config.json                            # comparison, after the pipeline
python main.py my_config.json && python -m dtm.comparison my_config.json
```

## Configuration

The JSON has two parts you write, `settings` and `regions`. The pipeline adds more entries as it runs (see [State written by the pipeline](#state-written-by-the-pipeline)).

### `settings`

| Key | Meaning | Default |
|---|---|---|
| `crs` | EPSG code of the output horizontal CRS. | required |
| `vertical_crs` | EPSG code of the output height system. `null` turns off all height transformations. | `null` |
| `resolution` | Output cell size, in units of `crs`. | required |
| `extent` | Polygon of the area to cover; the final DTM is masked to it. `null` uses the union of all region outlines. | `null` |
| `output_dir` | Folder for all outputs. | `data/pipeline` |
| `product_name` | File name of the merged DTM. | `merged_dtm.tif` |
| `buffer_m` | Buffer around each outline: used for the intersection test and as the margin of each region's DEM. | `1000` |
| `nodata` | NoData value of all outputs. | `-9999` |
| `max_vertical_shift_m` | The pipeline logs the height shift PROJ applies at each region's centre, and warns if it is larger than this. A shift of tens of metres usually means ellipsoidal and physical heights are being mixed. | `10` |
| `interpolation_mask` | Optional polygon; gap filling is limited to the part of each region inside it. | `null` |
| `borders` | Optional border lines, used for the distance-to-border analyses in the comparison. | none |
| `skip_missing` | `true`: regions with a missing outline, missing tiles or a missing geoid are skipped with a warning. `false`: the run stops. | `false` |
| `threads` | Total number of threads, or `"ALL_CPUS"`. | `"ALL_CPUS"` |
| `region_workers` | Number of regions warped at the same time; `threads` is split evenly between them. | `1` |
| `warp_memory_mb` | Memory per warp, in MB. | `2048` |
| `hole_filling` | Gap-filling settings, see below. | see below |
| `river_growing` | River-mask settings, see below. Each region can override these. | see below |
| `comparison` | Comparison settings, see [Comparison](#comparison). | see there |
| `qgis_root` | Windows only: path to a QGIS/OSGeo4W installation whose Python and GDAL should be used. Leave `null` otherwise. | `null` |

`hole_filling` (used for regions with `"interpolate": true`):

| Key | Meaning | Default |
|---|---|---|
| `method` | `"gdal_idw"`, inverse-distance weighting with GDAL's FillNodata. The only method available. | `"gdal_idw"` |
| `selection` | `"all_aoi_nodata"`: every NoData cell inside the region outline is a candidate. The only option available. | `"all_aoi_nodata"` |
| `max_distance_m` | How far to search for valid cells. Gaps wider than about twice this distance stay NoData. | `100` |
| `nearest_fallback` | Fill whatever is left with the nearest valid value. Very slow on large regions with big empty areas. | `true` |
| `smoothing_iterations` | Must be `0`. | `0` |

`river_growing`:

| Key | Meaning | Default |
|---|---|---|
| `seed_values` | Values in the region's water raster (`river_seeds`) that mark water. | `[2, 3]` |
| `tolerance_m` | Largest height step between neighbouring cells of the same water body. Growth stops at larger steps. | `0.02` |
| `seed_buffer_cells` | Dilate the seed cells by this many DEM cells before growing. | `0` |

### `regions`

One entry per region; the key is the region's name, used in file names and logs.

| Key | Meaning | Default |
|---|---|---|
| `vector` | Region outline (polygon). The region's data is used inside it. | required |
| `raster` | Path or glob pattern for the source tiles (`**` searches subfolders). Any format GDAL reads, e.g. GeoTIFF or ASCII grid. | required |
| `crs` | EPSG code of the tiles' horizontal CRS. It's set explicitly because tiles often lack a CRS, or spell the same one differently. | required |
| `vertical_crs` | EPSG code of the tiles' height system. If `settings.vertical_crs` is set as well, heights are transformed by PROJ. | none |
| `geoid` | Geoid raster: geoid heights N in metres, any CRS. When set, the source heights are taken as ellipsoidal and converted as H = h − N after the warp; `vertical_crs` is then informational only (e.g. `4937` for ETRS89). | none |
| `interpolate` | Fill gaps in this region's DEM and record which cells were filled. | `false` |
| `crop` | Cut the DEM to the outline. If `false`, the DEM keeps its buffer and neighbours overlap; the merge still uses each region only inside its outline. | `false` |
| `resampling` | GDAL resampling method used by the warp. | `"average"` |
| `source_nodata` | A value the tiles use for missing data without declaring it as NoData (e.g. `0`). These cells are then ignored by the warp, including its averaging. Overrides any NoData value the tiles declare. | none |
| `river_seeds` | Water raster for this region (any CRS). Cells with one of the `seed_values` are seeds. Without it, the region gets no river mask. | none |
| `river_growing` | Overrides for `settings.river_growing`, for this region only. | none |
| `point_clouds` | Ignored (point clouds are out of scope). | — |

How the source data is handled:

- **Tiles without a NoData value**: gaps between tiles are given `settings.nodata`, so they're treated as gaps rather than read as 0 m. If the tiles themselves fill missing areas with a value such as 0, set `source_nodata`. Otherwise those cells come out as near-0 heights, shifted by the height transformation, and are averaged into neighbouring cells.
- **Tiles in different but equivalent CRS definitions** are mosaicked together. The region's `crs` is used for all of them.
- **Height systems with a ballpark transformation only** are left unchanged, with a warning (see [PROJ grids](#height-transformations-and-proj-grids)).
- **Ellipsoidal heights**: give a `geoid`. Any geoid model works, for example the global EGM2008 (`curl -fL -o geoids/egm08.tif https://cdn.proj.org/us_nga_egm08_25.tif`). A regional geoid that matches your target height system is more accurate.

### State written by the pipeline

| Entry | Written by | Content |
|---|---|---|
| `regions.<name>.intersections` | `vectors` | Names of the intersecting regions. |
| `overlaps.<a>__<b>` | `vectors`, `overlaps` | Overlap polygon and override raster. |
| `regions.<name>.dem` | `rasters` | Processed DEM of the region. |
| `regions.<name>.fill_mask` | `rasters` | Mask of the gap-filled cells, or `null`. |
| `regions.<name>.river_mask` | `rivers` | River mask of the region. |
| `product` | `assemble` | Merged DTM. |
| `river_product` | `assemble` | Merged binary river mask. |
| `comparisons.<a>__<b>` | comparison | Statistics CSV of a finished pair. |

Don't edit these by hand. To redo a region, delete its folder in `output_dir` (or its `dem` entry) and rerun. To redo a comparison pair, delete its `comparisons` entry or its statistics CSV.

## Outputs

Everything is written under `settings.output_dir`:

```
<output_dir>/
├── <product_name>                     merged DTM (Cloud Optimized GeoTIFF)
├── <product name>_river_mask.tif      merged river mask, Byte COG: 1 = water, 0 = land, 255 = NoData
├── extent.gpkg                        area covered by the merged DTM
├── pipeline.log                       log of all runs, appended
├── intersections/<a>__<b>.gpkg        buffered overlap of two regions
├── <region>/
│   ├── tiles.vrt                      virtual mosaic of the source tiles
│   ├── dem.tif                        region DEM in the target CRS/height system, with buffer
│   ├── hole_filling/                  filled DEM and fill mask (regions with interpolate: true)
│   └── *_river_mask.tif               0 = no water, 1..n = water body id
├── overlaps/<a>__<b>/merged.tif       measured-over-interpolated overrides (NaN elsewhere)
└── comparison/                        see Comparison
```

## Comparison

`python -m dtm.comparison my_config.json` compares every pair of region DEMs whose extents overlap. Finished pairs are recorded in the JSON (`comparisons`) and skipped on the next run, as long as their statistics file exists and is newer than both DEMs, so an interrupted comparison resumes and a reprocessed region is compared again. A pair is recognised in either order (`a__b` or `b__a`). The summary table always lists all finished pairs. With `comparison.workers` above 1, several pairs run at once, each in its own process. Their log lines are prefixed with the pair name, e.g. `[a__b]`. It uses the region DEMs with their buffers, not the merged DTM, so it sees both datasets on either side of a border. For each pair it:

- excludes water cells (both regions' river masks, dilated by `river_buffer_cells`);
- computes the raw difference `dh = first − second`, and the difference after Nuth & Kaab coregistration (a horizontal and vertical shift only);
- computes statistics (mean, median, standard deviation, RMSE, MAE, NMAD, LE90, min, max, cells above the threshold), with and without the gap-filled cells;
- flags cells where |dh| exceeds `resolution × threshold_fraction` and groups them into problem regions. Gap-filled cells are left out of both, since measured data replaces them where the neighbour has it;
- if `settings.borders` is set, plots the error against distance to the border;
- estimates the random error with xdem's [uncertainty workflow](https://xdem.readthedocs.io/en/stable/uncertainty.html) (Hugonnet et al., 2022), on stable terrain (no water, no gap-filled cells) after coregistration:
  1. **Heteroscedasticity:** the spread (NMAD) of the differences is binned by terrain attributes (slope and maximum curvature by default), which gives an error map for every cell.
  2. **Spatial correlation:** a variogram of the standardized differences, fitted with a sum of models; each model gives one correlation range.
  3. **Propagation:** the error of the mean difference is the mean error divided by √(number of effective samples). It's reported in each statistics row as `mean_dh_sigma_m`, together with `n_effective`, `mean_sigma_dh_m` and `error_correlation_1km`. The overlap area is treated as a disk, which is conservative for thin border strips (fewer effective samples, so a larger error).

`settings.comparison`:

| Key | Meaning | Default |
|---|---|---|
| `threshold_fraction` | Threshold for problem cells, as a fraction of the resolution. The default, resolution / 3, follows the INSPIRE recommendation. | `0.333…` |
| `river_buffer_cells` | Dilation of the river masks before excluding them. | `1` |
| `max_distance_m` | Range of the distance plots (error correlation, distance to border). | `2000` |
| `border_strip_m` | Width of the distance-to-border strips. | `50` |
| `local_rmse_tile_m` | Tile size of the local RMSE raster. | `50` |
| `problem_min_area_m2` | Smallest problem region kept. | `200` |
| `problem_merge_distance_m` | Problem cells closer together than this are merged into one region. | `60` |
| `uncertainty` | Run the uncertainty analysis. It's the slowest part, so `false` skips it. | `true` |
| `precision_of_other` | `"same"`: both DEMs are equally precise, so each DEM's error is the difference's error / √2. `"finer"`: the first DEM is much more precise, so all of the error is assigned to the second. | `"same"` |
| `uncertainty_variables` | Terrain attributes used to explain how the error varies (any xdem terrain attribute). | `["slope", "max_curvature"]` |
| `variogram_models` | Variogram models summed to model the spatial correlation. | `["Gaussian", "Spherical"]` |
| `workers` | Number of pairs compared at the same time, each in its own process. Memory is the limit, see [Running large jobs](#running-large-jobs). | `1` |

Outputs, in `<output_dir>/comparison/`:

```
comparison/
├── dem_difference_statistics.csv           all pairs in one table
└── <a>__<b>/
    ├── statistics_<a>_<b>.csv              before/after coregistration, with/without filled cells
    ├── dh_<a>_<b>.tif                      raw difference
    ├── exceeds_threshold_<a>_<b>.tif       1 = above threshold, 0 = within, 255 = no data, water or gap-filled
    ├── problem_regions_<a>_<b>.gpkg
    ├── border_strips_<a>_<b>.csv, border_effect_<a>_<b>.png
    ├── histogram_*.png, cdf_*.png, slope_rmse_*.png
    ├── uncertainty_<a>_<b>.tif/.png         error map (1σ per DEM)
    ├── heteroscedasticity_<var>_<a>_<b>.png  error vs terrain attribute
    ├── variogram_<a>_<b>.png, Correlation_<a>_<b>.png   spatial correlation of the error
    └── local_inspire_rmse_*.tif, dh_std_*.tif, aspect_difference_*.tif
```

The Nuth & Kaab shift in the log is a quick diagnostic. A few centimetres is normal. A large vertical shift points to a wrong height system, for example ellipsoidal heights declared as orthometric. A consistent horizontal shift points to a georeferencing problem in one of the datasets.

## Running large jobs

- **Memory:** each warp uses up to `warp_memory_mb`, and there are `region_workers` warps at a time. River masks are built one region at a time but hold the whole region DEM in memory: roughly 25–30 bytes per cell at peak, so 75–90 GB for a 3-billion-cell region.
- **Comparison:** each pair loads the overlap of the two DEMs' bounding boxes and holds several copies of it in memory (several GB to a few tens of GB for large regions). Raise `comparison.workers` only as far as memory allows. Each pair uses about one core, so more workers mostly cost memory, not CPU.
- **Threads:** `threads` is the total budget. For many medium-sized regions, several `region_workers` with fewer threads each usually finish sooner than one worker with all threads.
- **Long runs:** use `screen` or `tmux`. Keep a copy of the output with `2>&1 | tee run.log`. With `set -o pipefail`, the exit code still reflects failures.
- **Missing data:** with `"skip_missing": true`, incomplete regions are skipped and retried on the next run, so you can start before all data is in.

## Tests

```bash
python -m unittest discover tests
```

The tests run offline on small synthetic rasters. They cover the merge rules, a two-region run end to end, skipping and retrying missing regions, geoid conversion, river masks, the merged river mask and the comparison statistics. The river-mask and comparison tests are skipped if xdem isn't installed.

## Code layout

```
main.py                   entry point (python main.py config.json)
dtm/
├── pipeline.py           the five stages and the JSON handling
├── river_mask.py         river masks (runnable on its own)
├── comparison.py         pairwise comparison (runnable on its own)
├── hole_filling.py       gap filling
├── process.py            raster helpers, COG writer
├── geo.py                vector/raster helpers
├── raster_io.py          xdem/rasterio I/O for comparison and river masks
├── progress.py           progress logging
└── runtime.py            optional QGIS environment on Windows
tests/test_pipeline.py
```

## Limitations

- Downloads and point clouds aren't handled.
- Height transformations are only as good as what PROJ provides. For a missing grid, PROJ either fails or makes no change at all (with a warning in the log). Check the warnings in `pipeline.log`.
- Overlaps are resolved only where one side is interpolated. Disagreements between two measured datasets are reported by the comparison, but not corrected.
- River growing follows flat water surfaces using `tolerance_m`. Steep or stepped water bodies, such as weirs and rapids, may be captured only in part.
- See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for findings and open issues from the Rhine-basin runs.
