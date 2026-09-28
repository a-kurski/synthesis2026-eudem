= Literature Review

This chapter will go over the reviewed literature. It discusses both the existing approaches for harmonizing cross-border data, INSPIRE, and point cloud processing methods.

== INSPIRE Specification on Elevation

In the European Union, the INSPIRE Directive  @eu_inspire_directive_2007 governs the "sharing, access, and use" of spatial data, specifically within the context of environmental policy.
INSPIRE defines 34 spatial data themes; elevation data is one of those.
Below is a summary of the data specification on elevation @inspire2024elevation, which can be considered the practical guidance on the theme.
The specification contains necessary contextual information, requirements (as either general implementing rules (IR) or elevation-specific technical guidance (TG)), and recommendations.

=== INSPIRE View on Elevation

Within the scope of the specification, the elevation property --- either depth or height --- is understood the three-dimensional shape of the Earth's surface #cite(<inspire2024elevation>, supplement: [p. 40--43]).
Generally, land-elevation and bathymetry are considered separately; for land-elevation, the elevation property is called height and its positive direction is "upwards", and for bathymetry, it is depth with positive direction pointing downward.
The scope for bathymetry is specifically the sea, inland standing water bodies, and navigable rivers.
The specification also considers an integrated land-sea model, where as measured from a given datum, the height is positive and the depth is _negative_.

The specification considers two possible "shapes" of the terrain #cite(<inspire2024elevation>, supplement: [p. 43--44]):
- a digital terrain model (DTM), which only represents the bare surface of the Earth;
- a digital surgace model (DSM), which represents the Earth's surface with all static natural and artificial features (e.g. this includes trees and buildings, but not cars).
"Digital elevation model" (DEM) is used as an umbrella term which encompasses both a DTM and a DSM.

=== Elevation Data Models

Within the scope of the specification, the surface is considered 2.5-dimensional --- for each $x,y$ position, only one elevation value is possible --- and can be represented with gridded coverage, vector data (contour lines and spot elevations), or a triangulated irregular network (TIN).
For land-elevation, *grid coverage is required*, and vector representation is recommended.
For bathymetry, either grid coverage or vector representation are required.
