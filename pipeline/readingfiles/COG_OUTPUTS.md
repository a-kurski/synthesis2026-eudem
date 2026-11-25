# Cloud Optimized GeoTIFF outputs

New preparation runs publish AHN and NRW stitched elevation rasters and their
processed tiles as Cloud Optimized GeoTIFFs (COGs). The AHN unfilled baseline
and fill-fraction raster are also COGs. Raw downloads and working rasters keep
their existing formats. Filenames and output locations do not change.

The publication step uses GDAL's COG driver with 512 x 512 internal tiles,
lossless DEFLATE compression, floating-point prediction, and BigTIFF support.
Internal average-resampled overviews are built automatically down to a level
whose dimensions fit within 512 pixels. Small rasters need no overviews.
The main raster's pixel values, grid, NoData, units, and metadata are retained.
Overviews are lower-resolution display representations; averaging the fill
fraction shows the fraction of valid contributing cells that were filled.

Open the stitched `.tif` in QGIS to use its internal overviews. COGs work on
local disks; uploading them is not required. They can substantially reduce
zoomed-out reading, but disk/network/OneDrive latency and rendering settings
still affect performance. Publication takes extra time and temporary disk
space to generate the overviews and rearrange TIFF blocks.

Existing outputs are not automatically converted. To convert one without
rerunning acquisition or interpolation, use an OSGeo4W/QGIS shell on Windows
or the GDAL environment on the server:

```sh
gdal_translate -of COG -co COMPRESS=DEFLATE -co PREDICTOR=FLOATING_POINT -co BIGTIFF=YES -co BLOCKSIZE=512 -co OVERVIEWS=IGNORE_EXISTING -co OVERVIEW_RESAMPLING=AVERAGE input.tif output_cog.tif
```

Use different input and output paths, then open `output_cog.tif` in QGIS.
This command is for continuous elevation or fraction rasters. For categorical
masks use nearest-neighbour overviews instead. Do not modify a finished COG
in place or rebuild its overviews; regenerate it from the source to preserve
the optimized layout.

Reference: https://gdal.org/en/stable/drivers/raster/cog.html
