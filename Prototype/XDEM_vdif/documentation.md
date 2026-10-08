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