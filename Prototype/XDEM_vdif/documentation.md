# Documentation

## Functions

### Startup
The program starts by loading all the functions. Due to issues at one point the xdem and pyplot functions are only called when needed. These include load_xdem and load_pyplot.

### result_path()
Creates a results path in case it does not exist yet.

### load_file()
Loads a given raster file based on filepath into xdem

### infer_country_name()
Extracts country name from the file name to be used in determining the source vcrs. 

! Needs to be changed to match the pipeline outputs !

### safe_name()
Extracts country name from vcrs file

### transform_dem_to_target_vcrs()
Transforms country to correct vcrs based on country name, source vcrs and target vcrs. Outputs a converted file.

### save_dem()
Saves DEM file to a raster format.

### load_or_transform_dem()
Checks if there already exists a vcrs transformed DEM of the same name. If so it will not attempt to reconstruct the transformed file and skip to analysis.

### save_raster()
Save raster function from xdem. Added compression and tiling.

### save_vector()
Saves vector data to file.

### nanmean()

### analyze_dem()
Loads two DEMs. Performs coregistration on the two, essentially matching them. Based on this information an estimate_uncertainty analysis is done to determine error correlation and uncertainty. These are saved in plots.

After, the difference of the two aligned rasters is taken. Statistics are calculated for the difference such as std, rmse, mae, min, max, etc. The results are written to a csv.

### local_inspire_rmse_analysis()
Takes the difference dtm and takes RMSE for x*x sized sections to determine if they comply with the inspire threshold. Exports a DEM.

### std_analysis()
Creates a std raster

### histogram_analysis()
Creates a histogram of height differences

### cdf_analysis()
Creates a cummulative plot of the difference values.

### aspect_difference_analysis()
Creates a difference raster between the aspects of the two rasters.

### slope_error_analysis()
Plots the correlation between slope and RMSE of the elevation difference.

### border_strip_analysis()
Analyses the effect of the distance from the border on the RMSE.

### find_border_vector()
Looks up what the border vector file is in the data folder.

### load_border_vector()
Loads the border vector.

### border_trend_plot()
Plots distance from border effect on RMSE.

### top_problem_regions()
Analyses height differences greater than threshold. Based on that it creates buffered polygons which get merged based on merge_distance. If the combined area is smaller than min_area it gets discarded. The polygons get assigned an area, rank, severity (area/1000) and geometry. The output is a vector file.

### find_dem_files()
Finds every full-region DEM in the data folder, excluding derived `_dep` rasters.

### dem_files_overlap()
Checks raster metadata to determine whether two DEM extents overlap, transforming
bounds when their CRSs differ without loading the full raster data.

### river_mask_creation()
Creates a raw local-variance score raster and a class raster from a single DEM. The raw `{dem}_score.tif` remains available for inspection. Set `SHOW_ALL_RIVER_FEATURES` near the top of `main.py` to `True` to include every polygonized low-variance component in the GeoPackage and raster; unclassified components are labeled `unclassified` and use value 3 in the raster. It defaults to `False`, outputting only classified river/lake features. In either mode, raster value 1 marks river candidates (including large rivers), value 2 marks lakes, and value 0 is background. This is a terrain-based classification, not a validated hydrography product or a blended DTM.

Set `RUN_SIGMA_SWEEP` to `True` to run the classifier with integer Gaussian sigma values from 1 through `SIGMA_SWEEP_MAX` (10 by default), stopping early when an iteration returns no classified water candidates. Polygon outputs from the successful iterations are unioned: overlaps are merged, while non-overlapping features remain separate. Each merged feature gets one `class`, taken from its latest contributing sigma, and records that sigma as `class_sigma`; `sigma_values` lists all contributing iterations. The combined result is saved as `{region}_river_mask.gpkg` and rasterized to the class raster. The raw score raster remains the sigma-1 variance when sweep mode is on. When sweep mode is off, `GAUSSIAN_SIGMA` controls the single run.

### river_polygons()
Polygonizes low-variance cells overlapping valid DEM elevations, then writes classified river/lake features to `{region}_river_mask.gpkg`; optionally writes unclassified components too when `show_all_features=True`. Each region's output is saved separately to avoid overwriting another region's polygons. The class field distinguishes `large river`, `river`, `lake`, and `unclassified`, with mutually exclusive candidate flags. River candidates use a 1,000 m² minimum area, 500 m maximum width, 0.04 maximum variance standard deviation, and 0.38 maximum compactness. Large rivers use a 1,000,000 m² minimum area, 500 m maximum width, 0.025 maximum variance standard deviation, and 0.1 maximum compactness. Lakes use a 30,000 m² minimum area, 800 m maximum width, 0.026 maximum variance standard deviation, and 0.15 minimum compactness.

Component and buffer metrics use worker threads and display single-line progress bars in terminal output. Buffer elevations are calculated only for components that pass the initial shape rules, using an exterior ring `buffer_cells` pixels wide (20 by default; 100 m for a 5 m DEM). Buffer cells with NoData elevations are ignored. Lakes must have a buffer height difference of at least `min_buffer_height_difference` (1.2 m by default); river candidates use `min_buffer_height_river` (1 m by default). Set either parameter to `None` to record the metrics without filtering for that class. Components failing the initial rules have NaN buffer metrics.

### run_all_analyses()
Creates a river mask for every DEM in the data folder. It then checks every DEM
combination and runs the pairwise DEM comparison only when their extents overlap.
Non-overlapping pairs are skipped for comparison, but their DEMs still receive
river-mask analysis. The total elapsed time is printed when processing completes.