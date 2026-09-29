= Literature Review

This chapter will go over the reviewed literature. It discusses both the existing approaches for harmonizing cross-border data, INSPIRE, and point cloud processing methods.

== INSPIRE Specification on Elevation

In the European Union, the INSPIRE Directive  @eu_inspire_directive_2007 governs the "sharing, access, and use" of spatial data, specifically within the context of environmental policy.
INSPIRE defines 34 spatial data themes; elevation data is one of those.
Below is a summary of the data specification on elevation @inspire2024elevation, which can be considered the practical guidance on the theme.
The specification contains necessary contextual information, requirements (as either general implementing rules (IR) or elevation-specific technical guidance (TG)), and recommendations.

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

Generally, INSPIRE demands that the coordinate reference system (CRS) used for datasets of continental Europe is based on ETRS89, with a matching datum. These include unmodified ETRS89, based on GRS80 ellipsoid, which uses geodetic coordinates;
