# Pipeline

## General
The pipeline takes a json config file as an argument, which contains: 
- global settings 
  - CRS
  - resolution
  - spatial extent of the Rhine basin
- region (country/bundesland) settings
  - path to vector data
  - path to raster data
  - path to point clouds
  - intersections with other countries

## Download
Download is handled on a country-by-country basis. The lack of standartisation in geoportals makes this step fundamentally impossible to automate. 

## Vector Processing
find intersecting regions by: 
- buffering each country vector
- finding non-empty intersections between different buffered vectors
and write those to the json

## Country Raster Processing
For each country, the following operations will be performed on the tiled raster: 
1. convert CRS and VRS
2. resample to given resolution (i.e. 5m)
3. interpolate
4. save to file
The path to processed DEM will be stored in JSON

## Processing Intersecting Regions
1. subtract one dtm from the other
2. check if the differences are bigger than threshold (per INSPIRE: resolution / 3), then: 
  1. load point clouds for the area
  2. compare the point clouds (use registration or other metrics?)
  3. re-extract dtm
  4. use point cloud dtm
3. alternatively: 
  just qualitative analysis, simply stick to each country's DEM otherwise

## Assembling the final product
1. write each country's data within its shapefile
2. overwrite with extracted areas

# Currently not considered: 
- differences in water level b/w different datasets
  - integrate w/ a water mask? 
  - just describe? 
  - [this synthesis](https://3d.bk.tudelft.nl/pdfs/synthesis/2020_ahn3_report.pdf) describes hydro-flattening
