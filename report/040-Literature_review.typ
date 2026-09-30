= Literature Review

This chapter will go over the reviewed literature. It discusses both the existing approaches for harmonizing cross-border data, INSPIRE specification on elevation, and point cloud processing methods.



== INSPIRE Specification on Elevation

In the European Union, the INSPIRE Directive  @eu_inspire_directive_2007 governs the "sharing, access, and use" of spatial data, specifically within the context of environmental policy.
INSPIRE defines 34 spatial data themes; elevation data is one of those.
Below is a summary of the data specification on elevation @inspire2024elevation, which can be considered the practical guidance on the theme.
The specification contains necessary contextual information, requirements (as either general implementing rules or elevation-specific technical guidance), and recommendations.
Certain implementation-specific details, such as the XML schema or data structures and formats, are excluded from the summary below, while the conceptual details are retained.

=== INSPIRE View on Elevation

Within the scope of the specification, the elevation property --- either depth or height --- is understood the three-dimensional shape of the Earth's surface #cite(<inspire2024elevation>, supplement: [pp. 40--43]).
Generally, land-elevation and bathymetry are considered separately; for land-elevation, the elevation property is called height and its positive direction is "upwards", and for bathymetry, it is depth with positive direction pointing downward.
The scope for bathymetry is specifically the sea, inland standing water bodies, and navigable rivers.
The specification also considers an integrated land-sea model, where as measured from a given datum, the height is positive and the depth is _negative_.

The specification considers two possible "shapes" of the terrain #cite(<inspire2024elevation>, supplement: [pp. 43--44]):
- a digital terrain model (DTM), which only represents the bare surface of the Earth;
- a digital surface model (DSM), which represents the Earth's surface with all static natural and artificial features (e.g. this includes trees and buildings, but not cars).
"Digital elevation model" (DEM) is used as an umbrella term which encompasses both a DTM and a DSM.

Within the scope of the specification, the surface is considered 2.5-dimensional --- for each $x,y$ position, only one elevation value is possible --- and can be represented with gridded coverage, vector data (contour lines and spot elevations), or a triangulated irregular network (TIN).
For land-elevation, *grid coverage is required*, and vector representation is recommended #cite(<inspire2024elevation>, supplement: [pp. 44--45]).
For bathymetry, either grid coverage or vector representation are required.

=== Gridded Coverage

Following both INSPIRE specification's requirements and the clients' request, only the gridded coverage is considered within the scope of the project at hand.
The specification requires that the grid is a two-dimensional regular quadrilateral grid and is geo-rectified, i.e. can be transformed to/from a grid of a CRS via an affine transform #cite(<inspire2024elevation>, supplement: [p. 52]).

Furthermore, the specification includes guidance on providing tiled datasets --- it refers to such coverage as "aggregated coverage", and the process of assembling it is called "aggregation".
While the illsutrations (e.g. on pp. 52 and 53) show that the tiles may be overlapping, the implementation rule (p. 60) requires that:
- the tiles are consistent, i.e. sharing CRS, encoding, and resolution;
- the grids of the tiles are aligned;
- the footprints of the tiles are either adjacent or disjoint;
- the domain of the aggregated coverage is the union of the tiles' domains.

It is also clarified that the coverage describes the elevation values at the centres of the geographic grid; and the geographic grid cells are the squares rendered when a GeoTIFF is displayed.

=== Coordinate Reference Systems

Generally, INSPIRE demands that the coordinate reference system (CRS) used for datasets of continental Europe is based on ETRS89, with a matching datum.
These include unmodified ETRS89, based on GRS80 ellipsoid, which uses geodetic coordinates; and different metric CRSs, usually ETRS89 Lambert Azimuthal Equal Area (ETRS89-LAEA) or ETRS89 Lambert Conformal Conic (ETRS89-LCC).
European Vertical Reference System (EVRS) is prescribed as the vertical reference system.

Annex D, however, provides specific guidance for gridded elevation data. It deems ETRS89-LAEA unsuitable for the elevation data for a number of reasons, notably that it does not preserve the geometry of the terrain --- i.e. planar angles.
It instead recommends the use of a zoned geographic grid based on the geodetic coordinates, denoted ETRS89-GRS80zn.
Under such a grid, the longitudinal resolution of the grid is different for different zones. Below 50°, the grid is "square": the latitude and longitude are in 1:1 ratio; between 50° and 70°, the ratio is 1:2; and it further increases in the higher latitudes.
Annex D is informative only, i.e. it is not expressly required to follow the guidance set out in it.

=== Data Quality

The specification defines several criteria to evaluate the data quality against.
These are split into three categories: completeness, logical consistency, and positional accuracy.

Completeness encompasses omission and commission.
Omission errors are data which should be included in the scope of the dataset but is not; commission errors are data in excess of the dataset's scope, such as duplicates.
In both cases, the target error rate is 0%.

Logical consistency includes conceptual consistency, domain consistency, format consistency, and topological consistency.
Conceptual consistency describes compliance with the conceptual schema; domain consistency describes compliance with the value domain; format consistency is related to the physical structure of the dataset, i.e. the formats and encodings used. Topological consistency is only applicable to the topology vector data and therefore out of scope for this project.
Like with completeness, the target error rate is 0%.

Positional accuracy is defined differently for vector and TIN data and for gridded data.
For a grid, only the planimetric accuracy is considered. The root mean square error --- here, defined as the radius of a circle around the point, such that the true value of a point lies within that circle with a given probability --- is the chosen evaluation metric. The target for the maximum RMSE is $"GSD"/6$, where GSD is the ground sample distance, essentially the resolution of the grid.

In the "Data Capture" section, the resolution is further related to the vertical accuracy of the dataset.
For flat terrain, the resolution should be between $3 "cross" "RMSE"$ and $20 "cross" "RMSE"$, while for mountainous terrain it should be between $3 "cross" "RMSE"$ and $10 "cross" "RMSE"$.

=== Cross-border DEM

Whereas most reports focus on semantic data harmonization of cross-border areas, few look at the DTM data. While little more than an educated guess, it is likely due to existing datasets. The European data portal lists two official DTM datasets #ref(<europaDigitalElevation>). These are both based on Copernicus data and have a 30 and 90 meter cell resolution respectively (at the equator). The Copernicus DEM is listed as having a vertical RMSE of $1.68 m$ for the 90 meter dataset #ref(<CopernicusDEM-RP-001_ValidationReport>), and a RMSE of $2.9 m$ for the 30 meter dataset #ref(<europaDigitalElevation>). Meanwhile, most national datasets fall between 0.5 and 2 meter resolution for cells. It is therefore likely, that for most applications on a small scale, the national datasets suffice. While for large scale, cross-border projects, the European DTM dataset suffices.

Nevertheless, one report details a method of cross-border harmonization. The report details harmonization of the coordinate reference system, orthrophoto, semantic information, and the digital terrain model #ref(<Noardo2016>). For this report only the CRS transformation and DTM harmonisation are relevant. They describe the process of transforming the datasets. However, for the pipeline this process will be automated using GDAL. However, it does highlight the INSPIRE, as the recommended quasi-geoid named European Vertical Reference
Frame (EVRF) for the vertical reference. Therefore, EVRF should be considered as the vertical reference.

In an effort to harmonize the DTM, the report describes a gradient approach. In this approach the point proximity of the border is evaluated to determine the weight of the pixel value from either DTM. The following formula is used:

#align(center,
$H_A = "DTM"_"France A" * D/500 + "DTM"_"Italy A" * (500-D)/500$)

Where $H_A$ is the final assigned height, while $D$ represents the distance from the border. While this method does smooth the transition, it does also likely diverge from reality, even if the discrepancy is minimized. While this method has been considered, further diluting the sampling of reality stands perpendicular to the goal of creating a map which visualizes reality. Therefore, this method will not be used for this project.

=== Ground Filtering
In order to create a new DTM from pointclouds, a method called ground filtering is used. Several different methods exist for this process. However, in the interest of limiting the scope of the project an existing implementation in PDAL will be used. However, other methods were evaluated to compare their performance against the Progressive Morphological Filter used by PDAL.

In @Silva2018GroundFiltering, it is noted that PMF differs from Multi-scale  Curvature  Classification (MCC), Progressive  Triangulated  Irregular  Network (PTIN), and Weighted Linear Least Squares (WLS) by excessively eliminating ground points to generate a DTM from. This causes it to underestimate the DTM elevations, with a particular focus on open-canopy forested areas. The paper theorizes this is likely caused by the fact PMF assumes a constant slope. While this is a serious drawback, it is one that needs to be used in the interest of the scope and time limit of this project.

However, the documentation of PDAL also states it is possible to alternatively use SMRF. This method is a further developed version of the PMF. However, @PINGEL201321 states that SMRF uses a slope dependent elevation, making it more reliable, and possibly solving the issue with PMF. Therefore, PDAL using SMRF ground filtering should allow for a reliable way to generate DTMs from pointclouds. Further research into the implementation of other methods will not be discussed or implemented within this report.