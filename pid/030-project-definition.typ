#import "@preview/drafting:0.2.2"

= Project Definition <Project_definition>

== Research Questions <questions>

The main research question of this project is:

_How to create a harmonised cross-border DEM of the Rhine catchment area in an automated way?_

As described in the introduction, the project focusses on the issues presented by the cross-border data of the Rhine catchment area. This translates to the creation of an automated pipeline and the report describing the issues that come with attempting the creation of a harmonised DEM. The efficiency refers to creating a pipeline that accounts for the large data quantity and limited computational resources. These two aspects of the main question can be broken down into the following subquestions:

- What is the Rhine catchment area?
- What, if any, existing approaches are there to creating a harmonised DEM from heterogeneous sources?
- What are the existing DEMs at different scales (regional, national, and global)?
- What are the issues with cross-border data?
- What are the INSPIRE requirements for DEMs?
- What are the limitations of an automated harmonisation pipeline?
- How can the accuracy of a reconstructed cross-border DEM be tested?

Answering these subquestions will help to answer the main research question. The first five subquestions will be evaluated in the research phase of the project and relate mostly to existing works and available data. Answering these questions will inform data acquisition and subsequently, software development. The next research questions will be answered during the software development phase as they relate to testing and limitations of the pipeline. These questions will be answered by evaluating the procedures and the output, and discussing the findings with the client.

// == Relevant courses from the MSc Geomatics program

// #drafting.inline-note[Do we care about this?]

// This project applies knowledge gained from several courses from the MSc Geomatics program. Having a basic overview of these courses will highlight the current knowledge possessed by the team. These are the following courses:

// - GEO1000 - Python for Geomatics;
// - GEO1001 - Sensing Technologies;
// - GEO1002 - GIS and Cartography;
// - GEO1004 - 3D modelling for the build environment;
// - GEO1015 - Digital Terrain Modelling.

// GEO1000 is relevant for programming the pipeline in either Python or C++. GEO1001 was the basis for understanding point cloud data collection and processing. GEO1002 is relevant for understanding the data and how to visualise it. GEO1004 is possibly relevant for working with 3D data and point cloud processing. GEO1015 is applicable as it forms the basis for 2D and 2.5D terrain modelling, shortcomings and processing of DEMs.

== Deliverables

By the end of project, the team expects to produce the following output:
- *A working pipeline* for DEM harmonisation. This includes the code and extended documentation which supports its use.
- *A report* justifying the decisions made and describing the process.
