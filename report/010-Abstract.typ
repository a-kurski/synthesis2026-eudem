#import "@preview/unify:0.8.1": qty
#import "@preview/drafting:0.2.2"
= Abstract <chap:abstract>

High-quality digital elevation models (DEMs) are increasingly available across Europe through regional and local mapping and research programmes.
However, these datasets are created by many different organisations, which results in differences in CRS, resolution, VCRS, processing approaches, and distribution formats between datasets.
These differences pose a challenge to creating one unified elevation dataset spanning across several regions.

This project focuses on creating a harmonised cross-border DEM of the Rhine catchment area in an automated manner.
Within this project, an automated pipeline has been developed which handles data harmonisation, processing, and visualisation.
We acquire the datasets which are then reprojected, vertically transformed, resampled, and aggregated into a single DEM.
Additionally, the pipeline supports interpolation of missing data, generating a high-resolution water mask, and a semi-automated border analysis for neighbouring datasets.

The resulting DTM covers Liechtenstein, Switzerland, France, Luxembourg, the Netherlands, and the German states of Bavaria, Baden-Württemberg, Hessen, Rhineland-Palatinate, Saarland, and Nordrhein-Westfalen.
To evaluate the quality of the harmonised dataset, neighbouring DTMs are compared by performing a difference of elevation rasters, statistical analysis, co-registration, and creating a set of diagnostic plots and raster files which are then evaluated against the requirements set out in the INSPIRE specification on elevation.
The analysis identifies several recurring sources of disagreement, categorised into interpolation, ground filtering, temporal differences, water mask, and pre- and post-processing artefacts.
Of the 17 border pairs within the catchment area, 15 meet the INSPIRE requirements for vertical accuracy (for 15 pairs, a mean RMSE of #qty("0.50", "m") compared to INSPIRE requirement of #qty("1.67", "m") at #qty("5", "m") horizontal resolution) and only two exceed that threshold (RMSE of #qty("3.12", "m") and #qty("5.36", "m")).
The sources of errors are best explained by differences in acquisition processing by data providers; the pipeline does not introduce significant errors.

The project demonstrates that harmonised cross-border DTM data can be generated automatically from heterogeneous elevation data while retaining the original data without applying methods such as cross-border smoothing, unlike existing cross-border elevation products.
We acknowledge that the challenges to harmonising the cross-border DEMs remain, and provide recommendations for improving the interoperability of elevation data.
