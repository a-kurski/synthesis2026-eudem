#import "@preview/drafting:0.2.2"

= Project Definition <chap:Project_definition>

== Terrain Models

#cite(<terrain_book>, form: "prose") provide the following definition of a terrain model: "A terrain is a representation of the Earth’s surface. It gives us the elevation, which is the height above/below a certain reference point (a vertical datum)." In this project, the main representation of terrain is a gridded @DEM, i.e. a raster dataset where the value of each grid cell equals the height of the terrain at its centre~--- within this report, the gridding is implied whenever a @DEM is mentioned. @DEM:pla are further differentiated into @DTM:pla, which only show the elevation of bare earth without human-made structures or vegetation, and @DSM:pla, which show all objects on the surface, such as trees, buildings, and the ground itself.

Each terrain model is associated with a @CRS. A @CRS describes the units of measurement, horizontal and vertical datums, and direction of the axes. Different countries use different reference systems, and conversion between them is needed before different terrain models can be integrated with one another.

== The Need for the European DEM

There are currently several products which offer the EU-wide elevation data as described in @sec:gdem. These products, however, have several shortcomings. Satellite-derived @DEM:pla have coarse resolution and do not fully support extracting the @DTM; aggregate @DEM:pla compromise on accuracy in the border regions.

The aim of this project is to develop an automated pipeline for a higher-quality European @DEM which would support runoff, flood, and other modelling. We specifically consider the @DTM of the Rhine catchment area as the object of the case study.

== Research Questions <questions>

As described in the introduction, the project focuses on the issues presented by the heterogeneous data within the Rhine catchment area, which we translate to the creation of an automated pipeline and a description of the challenges that come with attempting the creation of a harmonised @DEM.

The main research question of this project is thus:

_How to create a harmonised cross-border @DEM of the Rhine catchment area in an automated manner?_

The aspects of the main question can be broken down into the following subquestions:

- What is the Rhine catchment area?
- What, if any, existing approaches are there to creating a harmonised @DEM from heterogeneous sources?
- What are the existing @DEM:pla at different scales (regional, national, and global)?
- What are the @INSPIRE requirements for @DEM:pla?
- What are the issues with cross-border data?
- What are the limitations of an automated harmonisation pipeline?
- How can the accuracy of a reconstructed cross-border @DEM be tested?

Answering these subquestions helps answer the main research question. The first four subquestions are evaluated in the research phase of the project and relate mostly to existing literature and available data. Answering these questions informs data acquisition and subsequent software development. The next questions are answered during the software development phase as they are related to testing of the pipeline by evaluating the procedures and the output, and discussing the findings with the client.
