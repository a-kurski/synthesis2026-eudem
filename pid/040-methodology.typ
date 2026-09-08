= Methodology

This chapter describes the expected approach to research and development that will be performed over the course of the project. In addition, methods for quality assurance are discussed.

== Research Approach

== Pipeline Design

1. Data acquisition
  - Raster
  - PC
2. Raster pre-processing (CRS conversion, resolution, resampling, interpolation)
3. PC processing (ground filter, harmonisation, rasterisation)
4. Integrating 2 raster files

== Quality Assurance

We anticipate several aspects to quality assurance:

- *Evaluating input data.* This includes examining the existing DEMs for resolution, coverage, interpolation approaches, and whether both DSM and DTM are provided; and PCs for density, coverage, and classification.
- *Test runs to evaluate pipeline.* Using both synthetic and small samples of real-world data, evaluate the harmonisation of the point cloud and subsequently, the DEM.
- *INSPIRE compliance.* The output should be compliant with the INSPIRE Data Specification on Elevation. This is to be ensured both at the development stage and by evaluating samples of the output.
- *Comparison to existing DEMs*. The best candidate for this step is Copernicus DEM published by the European Space Agency. While we anticipate both spatial (mainly resolution — Copernicus DEM is freely available at 30m resolution while expected resolution of Rhine DEM is 5m or finer) and temporal (dates of acquisition) discrepancies, this should still provide some overview of the pipeline's performance across different areas of the catchment area.

Furthermore, clients will provide their input on our progress so further quality assurance steps will be implemented if necessary.
