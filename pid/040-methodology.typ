= Methodology <Methodology>

This chapter describes the expected approach to research and development that will be performed over the course of the project. In addition, methods for quality assurance are discussed.

== Research Approach

== Pipeline Design

Based on the requirements outlined in @Moscow_Prioritization, it is anticipated that the technical pipeline will consist of the following steps:

// + Literature Reivew
+ Data acquisition
+ Data preprocessing
+ Point cloud processing
+ Raster DEM processing
+ Data postprocessing
+ Documentation

Below is the detailed description of each of the steps above.

// === Literature Review

// Prior to starting implementation of the pipeline, a review of existing approaches to processing and harmonisation of raster and point cloud data is going to be conducted, with a particular emphasis on cross-border or more broadly heterogeneous data. This is essential to

=== Data Discovery and Acquisition

Data acquisition chiefly refers to getting access to the necessary datasets — global, national, and regional — and downloading them. For each country, the data should include at minimum a point cloud, a DEM (ideally, separate DSM and DTM); and if possible, also a topographic dataset describing bodies of water. Most of this data is covered under INSPIRE and therefore should be available from national geoportals. The full list of datasets is found in @appx-data-sources.

=== Data Preprocessing

At this step, the spatial extent and other characteristics of input data and the resolution of rasters is determined — this resolution in particular informs the resolution of the output. The raster files are cropped to the spatial extent of the Rhine catchment area; and the point clouds are reduced only to the border areas where there is intersection and potential conflict in height data. It is expected that this step is carried out using Python libraries such as `PDAL`, `GDAL`, `rasterio`, and `laspy`.

=== Point Cloud Processing

This stage of the pipeline includes:
- converting the point clouds to the same CRS;
- aligning them if the CRS conversion is determined to be insufficiently accurate;
- performing the ground filtering to extract the DTM;
- rasterising the output.
While the majority of these operations are supported by `PDAL` and `rasterio`, we anticipate that aligning heterogeneous point clouds is going to require additional research into tools and subsequent development and testing.

=== Raster Processing

This stage of the pipeline includes:
- converting raster files to the same CRS;
- if necessary, further aligning them using the same transformation as the respective point cloud;
- raster resampling to align their resolution;
- interpolating if a raster image has gaps (such as in the case of the Netherlands' DTM);
- stitching the individual tiles into one file.
At the end of this stage, the raster DEM is complete.

=== Data Postprocessing

To make the raster usable and for broader visualisation purposes, some further postprocessing may be required. In @Moscow_Prioritization, this is referred to under a blanket term of "auxiliary masks and rasters", which may include the following:
- a land/sea mask;
- a land/inland water mask;
- a "NoData" mask (i.e. regions of NoData in the original raster file);
- a point density map;
- "Border" mask (i.e. regions where heterogeneous datasets had to be harmonised).

=== Documentation

Per the clients' request, the software is also going to be documented. The documentation will cover how to run the software (essentially a `README`) but also the challenges, issues, and limitations that the team will have encountered over the course of the project. This documentation will be separate from, but partly overlapping with, the report.

== Quality Assurance

We anticipate several aspects to quality assurance:

- *Evaluating input data.* This includes examining the existing DEMs for resolution, coverage, interpolation approaches, and whether both DSM and DTM are provided; and PCs for density, coverage, and classification.
- *Test runs to evaluate pipeline.* Using both synthetic and smaller samples of real-world data, evaluate the harmonisation of the point cloud and subsequently, the DEM.
- *INSPIRE compliance.* The output should be compliant with the INSPIRE Data Specification on Elevation. This is to be ensured both at the development stage and by evaluating samples of the output.
- *Comparison to existing DEMs.* The best candidate for this step is Copernicus DEM published by the European Space Agency. While we anticipate both spatial (mainly resolution — Copernicus DEM is freely available at 30m resolution while expected resolution of Rhine DEM is 5m or finer) and temporal (dates of acquisition) discrepancies, this should still provide some overview of the pipeline's performance across different areas of the catchment area.

Furthermore, clients will provide their input on our progress so further quality assurance steps will be implemented if necessary.
