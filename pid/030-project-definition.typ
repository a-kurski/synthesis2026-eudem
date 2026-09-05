= Project Definition

== Research and Subquestions
The main research question of this project is:

_How to create a harmonised cross-border DEM (of the Rhine catchment area) in an automated (and efficient) way?_

As described in the introduction, the project focusses on the issues presented by the cross-border data of the Rhine catchment area. This translates to the creation of an automated pipeline and the report describing the issues that come with attempting the creation of a harmonised DEM. The efficiency refers to creating a pipeline that accounts for the large data quantity and limited computational resources. These two aspects of the main question can be broken down into the following subquestions:

- What are the limitions of an automated harmonisation pipeline? 
- What are the unknowns/variables in the data we need to consider? 
- What are the existing DEMs (local/global)? 
- What, if any, are the existing workflows for processing point clouds from heterogeneous sources?

Answering these subquestions will help to answer the main research question. The first two subquestions are more theoretical and will be answered in the report. The last two subquestions are more practical and will be answered in the pipeline.

== Relevant courses from the MSc Geomatics program
This project applies knowledge gained from several courses from the MSc Geomatics program. Having a basic overview of these courses will highlight the current knowledge possessed by the team. These are the following courses:

- GEO1000 - Python for Geomatics;
- GEO1001 - Sensing Technologies;
- GEO1002 - GIS and Cartography;
- GEO1004 - 3D modelling for the build environment;
- GEO1015 - Digital Terrain Modelling.

GEO1000 is relevant for programming the pipeline in either Python or C++. GEO1001 was the basis for understanding point cloud data collection and processing. GEO1002 is relevant for understanding the data and how to visualise it. GEO1004 is possibly relevant for working with 3D data and point cloud processing. GEO1015 is applicable as it forms the basis for 2D and 2.5D terrain modelling, shortcomings and processing of DEMs. 



== Requirements 
This chapter describes the requirements for this project. The requirements are divided into data requirements, country requirements, map requirements, technical content requirements, and report requirements. The requirements each have a priority assigned based on the MoSCoW method. This method divides requirements into four categories: Must have, Should have, Could have, and Won't have. Must have requirements are those which are mandatory. Should have requirements are more akin to nice-to-have features Could have requirements are those which have been discussed but are not mandatory. Won't have requirements are more related to project scope and refer to features which will not be part of the project. The requirements are listed in #ref(<Moscow_Prioritization>).

#let moscow(value) = {
  let color = if value == "Must" {
    rgb("#b3ef88")
  } else if value == "Should" {
    rgb("#f0e876")
  } else if value == "Could" {
    rgb("#f1ac6f")
  } else if value == "Won't have" {
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
  caption: "MoSCoW prioritization of data requirements for the project",
  table(
    columns: (auto,auto, auto),
    inset: 4pt,
    stroke: (x: none),
    align: horizon,
    table.header([Req ID],[Description], [MoSCoW]),
    [DT-01],[Global EU DEM (as ground truth)], moscow("Must"),
    [DT-02],[Rhine Watershed Mask], moscow("Must"),
    [DT-03],[Rhine Bathymetry], moscow("Could"),
    [],[],[],
    [CT-01],[Netherlands is included], moscow("Must"),
    [CT-02],[Germany is included], moscow("Must"),
    [CT-03],[Belgium is included], moscow("Should"),
    [CT-04],[Switzerland is included], moscow("Must"),
    [CT-05],[France is included], moscow("Must"),
    [CT-06],[Luxembourg is included], moscow("Must"),
    [CT-07],[Austria is included], moscow("Must"),
    [CT-08],[Liechtenstein is included (included in Swiss data)], moscow("Must"),
    [CT-09],[Italy is included], moscow("Won't have"),
    [],[],[],
    [MP-01],[DSM map], moscow("Must"),
    [MP-02],[DTM map], moscow("Must"),
    [MP-03],[Land-sea mask], moscow("Must"),
    [MP-04],[Bathymetry mask], moscow("Could"),
    [MP-05],[Nodata mask], moscow("Should"),
    [MP-06],[Point cloud density map], moscow("Should"),
    [],[],[],
    [TC-01],[Workflow is fully automated], moscow("Must"),
    [TC-02],[Workflow is efficient], moscow("Should"),
    [TC-03],[Workflow is reproducible], moscow("Must"),
    [],[],[],
    [RP-01],[Report on findings], moscow("Must"),
    [RP-02],[Report details the workflow], moscow("Must"),
    [RP-03],[Report details the issues with cross-border data], moscow("Must"),
    [RP-04],[Report details the limitations of the workflow], moscow("Must")

  )
) <Moscow_Prioritization>