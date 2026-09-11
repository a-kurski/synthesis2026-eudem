#import "@preview/drafting:0.2.2"

= Methodology

This chapter describes the requirements for input and output data, the expected approach to answering the individual subquestions and software development that will be performed over the course of the project. In addition, methods for quality assurance are discussed.

== Requirements <sec:reqs>

This section describes the requirements for this project. The requirements are split into 5 categories: "DT" (for "data") describes the datasets that are going to be used as input; "CT"  (meaning "country") describes the expected spatial extent of the output dataset within the Rhine catchment area; "MP" (for "map") describes the contents of the output data; "TC" refers to the technical requirements of the workflow; and "RP" stands for "report". The requirements each have a priority assigned based on the MoSCoW method @enwiki:1373589760. This method divides requirements into four categories: "Must have", "Should have", "Could have", and "Will not have". "Must have" requirements are mandatory; "Should have" requirements are not mandatory but nice-to-have or would add value to the project; "Could have" requirements have been discussed but add limited value or require more work. "Will not have" features have been determined to be strictly outside of the scope of the project as impractical due to high labour, lack of available data, or technical cost. The full assessment is shown in @Moscow_Prioritization.

#let moscow(value) = {
  let color = if value == "Must" {
    rgb("#b3ef88")
  } else if value == "Should" {
    rgb("#f0e876")
  } else if value == "Could" {
    rgb("#f1ac6f")
  } else if value == "Will not have" {
    rgb("#ed7e7e")
  } else {
    none
  }

  box(
    fill: color,
    inset: 4pt,
    width: 100%,
    align(center)[#value]
  )
}

#figure(
  caption: "MoSCoW prioritisation of data requirements for the project",
  table(
    columns: (auto,auto, auto),
    inset: 4pt,
    stroke: (x: none),
    align: horizon,
    table.header([Req ID],[Description], [MoSCoW]),
    [DT-01],[Global/EU DEM], moscow("Must"),
    [DT-02],[Rhine Watershed Mask], moscow("Must"),
    [DT-03],[Rhine Bathymetry], moscow("Will not have"),
    [DT-04], [National/regional PC], moscow("Must"),
    [DT-05], [National/regional DTM], moscow("Must"),
    [DT-06], [National/regional DSM], moscow("Should"),
    [DT-07], [National/regional topographic map], moscow("Could"),
    table.hline(stroke: 2pt),
    [CT-01],[The Netherlands is included], moscow("Must"),
    [CT-02],[Germany is included], moscow("Must"),
    [CT-03],[Belgium is included], moscow("Should"),
    [CT-04],[Switzerland is included], moscow("Must"),
    [CT-05],[France is included], moscow("Must"),
    [CT-06],[Luxembourg is included], moscow("Must"),
    [CT-07],[Austria is included], moscow("Should"),
    [CT-08],[Liechtenstein is included], moscow("Must"),
    [CT-09],[Italy is included], moscow("Will not have"),
    table.hline(stroke: 2pt),
    [MP-01],[DSM raster], moscow("Must"),
    [MP-02],[DTM raster], moscow("Should"),
    [MP-04],[Auxiliary masks and maps], moscow("Should"), //what is a bathymetry mask? is it just water/no water?
    table.hline(stroke: 2pt),
    [TC-01],[Workflow is fully automated], moscow("Must"),
    [TC-02],[Workflow is efficient], moscow("Should"),
    [TC-03],[Workflow is reproducible], moscow("Must"),
    table.hline(stroke: 2pt),
    [RP-01],[Report on findings], moscow("Must"),
    [RP-02],[Report details the workflow], moscow("Must"),
    [RP-03],[Report details the issues with cross-border data], moscow("Must"),
    [RP-04],[Report details the limitations of the workflow], moscow("Must")
  )
) <Moscow_Prioritization>

== Research Approach

=== Theoretical Approach <sec:theoretical-approach>

The majority of the subquestions will be answered at least in part theoretically. These questions include:
- *What is the Rhine catchment area?* \ To answer this question, the different definitions, descriptions, and spatial extents of the catchment area will be reviewed, and the spatial extent most suited to our project will be chosen in agreement with the supervisors. If no other suitable option is found, the supervisory team has agreed that a watershed vector from HydroSHEDS (see #cite(<Lehner2013>, form: "prose")) is acceptable for the purposes of the project.
- *What, if any, existing approaches are there to creating a harmonised DEM from heterogeneous sources?* \ A literature review will be conducted to answer this question. Existing approaches will be analysed for their advantages, shortcomings, ease of implementation, and whether they have been applied to geospatial data such as 2.5D point clouds and raster DEMs.
- *What are the issues with cross-border data?* \ Existing literature will be reviewed for known issues with interoperability between cross-border datasets.
- *What are the INSPIRE requirements for DEMs?* \ The INSPIRE specification for elevation models will be reviewed and relevant requirements will be noted to follow in the creation of the raster.
- *What are the limitations of an automated harmonisation pipeline?* \ Literature on existing harmonisation approaches will be reviewed and known issues will be noted.
- *How can the accuracy of a reconstructed cross-border DEM be tested?* \ Literature on existing harmonisation and reconstruction pipelines will be reviewed and approaches to testing of the accuracy will be noted and, where relevant, followed.

=== Practical Approach

When a question cannot be answered fully theoretically, practical approaches will be used. These questions include:

- *What are the existing DEMs at different scales (regional, national, and global)?* \ As described in @data-discovery, the regional and national datasets will be findable from national geoportals. Further data discovery is needed for global and international (e.g. pan-European) elevation models; the supervisory team will be consulted as they have experience with them. The resolution, spatial extent and notable individual characteristics of the datasets will be documented.
- *What are the issues with cross-border data?* \ As described in @qa, border regions will be sampled and reviewed; any issues found, if different from those described in the literature, will be documented.
- *What are the limitations of an automated harmonisation pipeline?* \ The pipeline will be tested; known issues in the output raster and limitations of the pipeline will be documented.
- *How can the accuracy of a reconstructed cross-border DEM be tested?* \ If it is found that the literature does not offer satisfactory testing methods, the team will discuss if there are better approaches suitable for the given use case. In this document, the suggested approaches include using synthetic data and cross-referencing with a global elevation dataset.

=== Literature Review

As described in @sec:theoretical-approach, a literature review needs to be conducted to answer most of the subquestions. The literature will be collected on the following themes:
- INSPIRE specification;
- approaches to point cloud harmonisation — keywords will include combining "point cloud" with "harmonisation", "alignment", or "stitching";
- Rhine catchment area;
- cross-border data interoperability.
The list of literature found thus far can be found in @appx-literature.

== Pipeline Design

Based on the requirements outlined in @Moscow_Prioritization, it is anticipated that the technical pipeline will consist of the following steps:

+ Data acquisition
+ Data preprocessing
+ Point cloud processing
+ Raster DEM processing
+ Data postprocessing
+ Documentation

Below is the detailed description of each of the steps above.

=== Data Discovery and Acquisition <data-discovery>

Data acquisition chiefly refers to getting access to the necessary datasets — global, national, and regional — and downloading them. For each country, the data should include at minimum a point cloud, a DEM (ideally, a separate DSM and DTM), and, if possible, also a topographic dataset containing bodies of water. Most of this data is covered under INSPIRE and therefore should be available from national geoportals. European Point Clouds (as described in #cite(<vanderheide2026pointcloud>, form: "prose")) is also used for data discovery. The full list of datasets discovered thus far is found in @appx-data-sources.

=== Data Preprocessing

At this step, the spatial extent and other characteristics of input data and the resolution of rasters are determined — this resolution in particular informs the resolution of the output. The raster files are cropped to the spatial extent of the Rhine catchment area, and the point clouds are reduced only to the border areas where there is intersection and potential conflict in height data. It is expected that this step is carried out using Python libraries such as `PDAL`, `GDAL`, `rasterio`, and `laspy`.

=== Point Cloud Processing

This stage of the pipeline includes:
- converting the point clouds to the same CRS;
- aligning them if the CRS conversion is determined to be insufficiently accurate;
- performing the ground filtering to extract the DTM;
- rasterising the output.
While the majority of these operations are supported by `PDAL` and `rasterio`, it is anticipated that aligning heterogeneous point clouds is going to require additional research into tools and subsequent development and testing.

=== Raster Processing

This stage of the pipeline includes:
- converting raster files to the same CRS;
- if necessary, further aligning them using the same transformation as the respective point cloud;
- raster resampling to align their resolution;
- interpolating if a raster image has gaps (such as in the case of The Netherlands' DTM);
- stitching the individual tiles into one file.
At the end of this stage, the raster DEM is complete.

=== Data Postprocessing

To make the raster usable and for broader visualisation purposes, some further postprocessing may be required. In @Moscow_Prioritization, this is referred to under the blanket term of "auxiliary masks and rasters", which may include the following:
- a land/sea mask;
- a land/inland water mask;
- a "NoData" mask;
- a point density map;
- a "Border" mask (i.e. regions where heterogeneous datasets overlap and need to be harmonised).
This data will be derived from the input datasets — i.e. point clouds, and raster and vector maps. Some of these — such as the NoData mask — will be integrated into the DEM and others — like a point density map or a border mask — will be separate.

=== Documentation

Per the clients' request, the software is also going to be documented. The documentation will cover how to run the software (essentially a `README`) but also the challenges, issues, and limitations that the team will have encountered over the course of the project. This documentation will be separate from, but partly overlapping with, the report.

#pagebreak()

== Quality Assurance <qa>

To ensure the quality of the output data, the following steps will be performed:

- *Evaluating input data.* This includes examining the existing DEMs for resolution, coverage, interpolation approaches, and whether both DSM and DTM are provided; and PCs for density, coverage, and classification.
- *Test runs to evaluate the pipeline.* Using both synthetic and smaller samples of real-world data, evaluate the harmonisation of the point cloud and, subsequently, the DEM.
- *INSPIRE compliance.* The output should be compliant with the INSPIRE Data Specification on Elevation. This is to be ensured both at the development stage and by evaluating samples of the output.
- *Comparison to existing DEMs.* The best candidate for this step is the Copernicus DEM published by the European Space Agency. While the datasets will have spatial (mainly resolution — Copernicus DEM is freely available at 30m resolution while the expected resolution of the Rhine DEM is 5m or finer) and temporal (dates of acquisition) discrepancies, this should still provide some overview of the pipeline's performance across different areas of the catchment area.

Furthermore, clients will provide their input on our progress so further quality assurance steps will be implemented if necessary.
