#import "@preview/drafting:0.2.2"

= Theory and Context <chap:theory>

This chapter covers the reviewed literature.
In it, we present the definition for the Rhine catchment area; the summary of the relevant aspects of @INSPIRE specification on elevation; existing cross-border digital elevation models; and aspects of processing which affect the agreement between elevation products from different providers.

== Rhine Catchment Area <sec:rhine>

The first step of the project is determining the area on which the project is going to get carried out.
For this, different extents of the Rhine catchment area were considered.
One most commonly agreed upon comes from International Association of Waterworks in the Rhine Basin @iawr_rhine and @ICPR @ICPR2013. It excludes the upstream Meuse but includes the rest of the delta, e.g. Ijssel and Waal.
Another possible definition can be found on Wikimedia (see @fig:rhine-defs), and it includes the Meuse.

#figure(
  grid(
    columns: (auto, auto),
    [#image("assets/8278083_iawr-rheinkarte-2500x3452.jpg", width: 70%)], [#image("assets/960px-Flusssystemkarte_Rhein_04.jpg", width: 70%)]
  ),
  caption: [Maps of the Rhine catchment area from ICPR (left, from #cite(<iawr_home>, form: "prose")) and Wikimedia (right, from #cite(<wiki:rhine>, form: "prose"))]
)<fig:rhine-defs>

For this project, the Rhine river definition comes from HydroBASINS @Lehner2013, derived from a global elevation model. The Meuse and Ijssel are excluded from the main catchment area of the Rhine in this case; their exclusion has been discussed with the client and was deemed appropriate as the automated pipeline supports expanding the geographic extent of the dataset. @fig:rhine-catchment-regions shows the map of the area used in the project, coloured by elevation data provider.

The Rhine catchment area nominally covers (parts of) Switzerland, Liechtenstein, Austria, Italy, Germany, France, Luxembourg, Belgium, and The Netherlands.
The following regions are explicitly defined to be within the scope of the project: Switzerland, Liechtenstein, France, Luxembourg, Germany --- specifically, states of Bavaria, @BW, Hessen, @NRW, @RLP, and Saarland --- and the Netherlands.
Austria, Italy, and Belgium are excluded due to poor availability of data; Germany's Thüringen has been excluded as only a small part of the state falls within the borders of the catchment area.

// #drafting.inline-note()[TODO: update the map?]

#figure(
  image("assets/Catchment_map.png", width: 50%),
  caption: [Rhine cathchment regions and countries (image by authors)]
)<fig:rhine-catchment-regions>

== INSPIRE Specification on Elevation <sec:inspire>

In the @EU, the @INSPIRE Directive @eu_inspire_directive_2007 governs the "sharing, access, and use" of spatial data, specifically within the context of environmental policy.
@INSPIRE defines 34 spatial data themes; elevation data is one of those.
Below is a summary of the data specification on elevation @inspire2024elevation, which can be considered the practical guidance on the theme.
The specification contains necessary contextual information, requirements (as either general implementing rules or elevation-specific technical guidance), and recommendations.
Certain implementation-specific details, such as the @XML schema or data structures and formats, are excluded from the summary below, while the conceptual details are retained.

=== INSPIRE View on Elevation <sec:inspire-elevation>

Within the scope of the specification, the elevation property --- either depth or height --- is understood the three-dimensional shape of the Earth's surface #cite(<inspire2024elevation>, supplement: [pp. 40--43]).
Generally, land-elevation and bathymetry are considered separately; for land-elevation, the elevation property is called height and its positive direction is "upwards", and for bathymetry, it is depth with positive direction pointing downward.
The scope for bathymetry is specifically the sea, inland standing water bodies, and navigable rivers.
The specification also considers an integrated land-sea model, where as measured from a given datum, the height is positive and the depth is _negative_.

The specification considers two possible "shapes" of the terrain #cite(<inspire2024elevation>, supplement: [pp. 43--44]):
- a @DTM, which only represents the bare surface of the Earth;
- a @DSM, which represents the Earth's surface with all static natural and artificial features (e.g. this includes trees and buildings, but not cars).
"Digital elevation model" (@DEM) is used as an umbrella term which encompasses both a @DTM and a @DSM.

Within the scope of the specification, the surface is considered 2.5-dimensional --- for each $x,y$ position, only one elevation value is possible --- and can be represented with gridded coverage (raster data), vector data (contour lines and spot elevations), or a @TIN.
For land-elevation, *grid coverage is required*, and vector representation is recommended #cite(<inspire2024elevation>, supplement: [pp. 44--45]).
For bathymetry, either grid coverage or vector representation are required.

=== Gridded Coverage <sec:inspire-grid>

Following both @INSPIRE specification's requirements and the clients' request, only the gridded coverage is considered within the scope of the project at hand.
The specification requires that the grid is a two-dimensional regular quadrilateral grid and is geo-rectified, i.e. can be transformed to/from a grid of a @CRS via an affine transform #cite(<inspire2024elevation>, supplement: [p. 52]).

Furthermore, the specification includes guidance on providing tiled datasets --- it refers to such coverage as "aggregated coverage", and the process of assembling it is called "aggregation".
While the illsutrations (e.g. on pp. 52 and 53) show that the tiles may be overlapping, the implementation rule (p. 60) requires that:
- the tiles are consistent, i.e. sharing @CRS, encoding, and resolution;
- the grids of the tiles are aligned;
- the footprints of the tiles are either adjacent or disjoint;
- the domain of the aggregated coverage is the union of the tiles' domains.

It is also clarified that the coverage describes the elevation values at the centres of the geographic grid; and the geographic grid cells are the squares rendered when a GeoTIFF is displayed.

#figure(
  image(
    "assets/image26.jpeg",
    width: 70%
  ),
  caption: [INSPIRE definition of gridded coverage. Image from #cite(<inspire2024elevation>)]
)

=== Coordinate Reference Systems <sec:inspire-crs>

Generally, @INSPIRE demands that the @CRS used for datasets of continental Europe is based on @ETRS89, with a matching datum.
These include unmodified @ETRS89, based on the @GRS80 ellipsoid, which uses geodetic coordinates; and different metric @CRS:pla, usually @ETRS89-LAEA or @ETRS89-LCC.
@EVRS is prescribed as the vertical reference system.

Annex D, however, provides specific guidance for gridded elevation data. It deems @ETRS89-LAEA unsuitable for the elevation data for a number of reasons, notably that it does not preserve the geometry of the terrain --- i.e. planar angles.
It instead recommends the use of a zoned geographic grid based on the geodetic coordinates, denoted @ETRS89-GRS80zn.
Under such a grid, the longitudinal resolution of the grid is different for different zones. Below 50°, the grid is "square": the latitude and longitude are in 1:1 ratio; between 50° and 70°, the ratio is 1:2; and it further increases in the higher latitudes.
Annex D is informative only, i.e. it is not expressly required to follow the guidance set out in it.

#include "051-crs.typ"

=== Data Quality <sec:inspire-quality>

The specification defines several criteria to evaluate the data quality against.
These are split into three categories: completeness, logical consistency, and positional accuracy #cite(<inspire2024elevation>, supplement:[pp. 121–138]).

Completeness encompasses omission and commission.
Omission errors are data which is within the dataset's scope but is not present in the dataset; commission errors are data in excess of the dataset's scope, such as duplicates.
In both cases, the target error rate is 0%.

Logical consistency includes conceptual consistency, domain consistency, format consistency, and topological consistency.
Conceptual consistency describes compliance with the conceptual schema; domain consistency describes compliance with the value domain; format consistency is related to the physical structure of the dataset, i.e. the formats and encodings used. Topological consistency is only applicable to the topology vector data and therefore out of scope for this project.
The error rate describes the ratio of non-compliant items and the target is 0%.

Positional accuracy is defined differently for vector and @TIN data and for gridded data.
For a grid, only the planimetric accuracy is considered. The @RMSE --- here, defined as the radius of a circle around the point, such that the true value of a point lies within that circle with a given probability --- is the chosen evaluation metric. The target for the maximum @RMSE is $"GSD"/6$, where @GSD is the ground sample distance, essentially the resolution of the grid.

In the "Data Capture" section #cite(<inspire2024elevation>, supplement:[p. 171]), the resolution is additionally related to the vertical accuracy of the dataset.
For flat terrain, the resolution should be between $3 times "RMSE"$ and $20 times "RMSE"$, while for mountainous terrain it should be between $3 times "RMSE"$ and $10 times "RMSE"$.
This will be the target when evaluating the agreement between overlapping border areas.

== Global Elevation Models <sec:gdem>

A @GDEM covers most of the land surface of the Earth. Currently, there are two main approaches to creating a @GDEM: a conventional approach relies on satellite data, and more recently, there have been efforts to derive a @GDEM from national and regional datasets like suggested by @INSPIRE. Below is a brief overview of both approaches.

=== Satellite Data-Derived Elevation Models <sec:spaceborne-gdem>

Most @GDEM:pla are constructed using data from space-borne @InSAR or optical sensors.
An overview of the most common existing @GDEM:pla has been provided by #cite(<terrain_book>, form: "prose", supplement: "Table 3.2").
The majority of satellite @GDEM:pla are obtained using @InSAR; only two of those presented are derived from optical data.
The common @GSD is 30m or 90m; a few, like WorldDEM or @ALOS are also available at finer resolutions.
The majority of the @GDEM:pla are @DSM:pla; some products offer a "_pseudo_-@DTM" where some ground filtering has been performed.

The European data portal lists two official @DTM datasets: EU-DEM @eurostat_eudem and Copernicus @DEM @eurostat_copernicusdem.
Both are based on Copernicus data and have a 30 and 90 meter cell resolution respectively.
EU-DEM is available in geodetic @ETRS89 and @ETRS89-LAEA and is described to have a vertical @RMSE of 2.9m @dhigras_eudem_validation_2014 while Copernicus @DEM is availabe only in @ETRS89 with a vertical @RMSE of 1.68m @airbus_copernicusdem_validation_2020.
Copernicus further offer a 10m dataset titled EEA-10 which is limited to the @EEA member states and is only available to select users @cdse_copdem.
EEA-10 is the only dataset which is available in INSPIRE format and projected to @ETRS89-LAEA for continental Europe whereas 30m and 90m global datasets are only supplied in WGS84 @airbus_copernicusdem_handbook_2022.

#cite(<krdzalic2024>, form: "prose") evaluate the accuracy of several @GDEM:pla against two sets of reference points in Bosnia and Herzogovina, additionally comparing them with the national @DEM. The authors further compare different interpolation methods in their assessment --- here, only results achieved with bilinear interpolation are referenced as it is the interpolation method recommended by @INSPIRE. For both sets of reference points, national @DEM has the lowest RMSE of 1.64m and 3.02m respectively; Copernicus DEM has the lowest RMSE of the @GDEM:pla with 2.35m and 3.11m respectively.

=== Aggregate Global Elevation Models <sec:mapterhorn>

An aggregate elevation model serves as an alternative to the conventional @GDEM. With this approach, several heterogeneous @DEM:pla are assembled into one finished product --- this is also an approach taken in this project. The only example of this approach known to us is Mapterhorn @wipfli2026mapterhorn. Currently, Mapterhorn combines 70 open-access national, regional, and local elevation products alongside Copernicus DEM GLO-30 into one harmonised @DEM.

There are several shortcomings with current implementation of Mapterhorn. The first one is that it is neither a @DTM nor a @DSM: Copernicus DEM is a _surface_ model, and national products can be both a _terrain_ and a _surface_ model --- therefore, Mapterhorn's elevation data is a mix of both. The second one is the approach to resolving elevation conflicts at the border. Mapterhorn uses a Gaussian blur to blend the elevation data where two datasets overlap, which may introduce elevation points which may not be representative of reality for those point samples. Lastly, Mapterhorn enforces that the @CRS transform is only horizontal, explicitly ruling out vertical transform.

#figure(
  image(
    "assets/mapterhorn-artefact.png",
    width: 50%
  ),
  caption: [Example of smoothing at the border in Mapterhorn]
)

A similar approach was described by #cite(<Noardo2016>, form: "prose") who report on harmonisation of the @CRS, orthrophoto, semantic information, and the @DEM and #cite(<biagi_interpolation>, form: "prose") who focus on @DEM harmonisation specifically.
The papers try and harmonise Italian elevation data with France and Switzerland respectively, focusing on the mountainous regions.
Both demonstrate presence of errors of high magnitude, exceeding 100m.
To resolve those errors, both sets of authors suggest an approach conceptually similar to that of Mapterhorn --- #cite(<Noardo2016>, form: "author") obtain the elevation of the border regions by performing a linear interpolation on the overlapping region while #cite(<biagi_interpolation>, form: "author") perform bicubic interpolation --- which also introduce issues similar to using a Gaussian blur in that the data around the border may not match reality.
#cite(<Noardo2016>, form: "author") comment on the potential discrepancy; #cite(<biagi_interpolation>, form: "author") leave it unaddressed.

== Point Cloud Processing <sec:pc-processing>

A potential source of disagreement between gridded elevation data from different providers is the approach used to derive it from point clouds.

Ground filtering is one of key steps to extracting a @DTM from a point cloud. #cite(<Silva2018GroundFiltering>, form: "prose") compare @PMF, @MCC, @PTIN, and @WLS.
One notable finding from this study is that @PMF outputs a set of ground points with constant density whereas the other three algorithms produce a set of ground points with uneven density depending on the type of surface.
@PMF's set is also approximately 10–15 times smaller than the other algorithms.
However the resulting @DTM:pla are still very close to each other, with highest @RMSE of 0.37m (for shrubland; when comparing @MCC to @PMF).
#cite(<Silva2018GroundFiltering>, form: "author") note that @PMF assumes constant slope and therefore struggles in steeper parts of the terrain.
#cite(<cai2023>, form: "prose") carry out further assessment of @MSF, @PMF, @CSF, and @ICSF.
The study provides both a quantitative and a qualitative assessment of the different methods.
Quantitatively, omission and commission errors are evaluated: @MSF has the highest error rate of up to 20% for complex scene; @PMF and @CSF have generally comparable and slightly lower error rates (ca 14% for the same scene); @ICSF performs best, with an error rate of ca 7% for the same scene.
Qualitative analysis can be illustrated with @fig:ground-filter.
Compared to the reference (column a), @MSF (b) can introduce noise, @PMF (c) and @CSF (d) tend to smooth out steep slopes — this is especially apparent in row 2c — while @ICSF is mostly artefact-free.

#figure(
  image(
    "assets/cai2023-ground-filters.png",
    width: 60%
  ),
  caption: [Comparison of ground filtering algorithms. From: #cite(<cai2023>, form: "prose")]
) <fig:ground-filter>

// However, the documentation of @PDAL also states it is possible to alternatively use @SMRF. This method is a further developed version of the @PMF. However, #cite(<PINGEL201321>, form: "prose") states that @SMRF uses a slope-dependent elevation, making it more reliable, and possibly solving the issue with @PMF. Therefore, @PDAL using @SMRF ground filtering should allow for a reliable way to generate @DTM:pla from point clouds. Further research into the implementation of other methods will not be discussed or implemented within this project.

Point distribution and interpolation methods can introduce further discrepancies between the raster products from different data providers.
It is expected that these discrepancies are minimal for flatter areas or regions with high point density, and higher for steep slopes or regions with high point density.
It is also expected that the documentation of the interpolation methods is primarily available in the national language of each data provider, if at all, therefore investigating it was deemed to be out of scope of the project.

== Interpolation Methods <sec:theory-interpolate>

Some elevation datasets --- within study area, Dutch @AHN is the only such dataset --- are supplied with "gaps" of NoData, which warrants filling those gaps.
There are several papers @Chen2014, @Gradka2018, @hu2013, @Raza2023, comparing different interpolation methods for terrain modelling.
The methods compared include @IDW, @RBF, @NNI, and kriging.
The first three methods are deterministic as the results are strictly based on the input data and parameters of the function; kriging is stochastic and also requires assumptions about the statistical properties of the dataset.
All authors agree that @IDW produces less accurate results than @IDW produces less accurate results than the alternatives: #cite(<Chen2014>, form: "author") and #cite(<Gradka2018>, form: "author") find that kriging is most accurate; #cite(<hu2013>, form: "author") does not evaluate kriging but recommends that an implementation of @RBF produces best result --- these findings are partly corroborated by #cite(<Gradka2018>, form: "author") who claim that results obtained with @RBF and kriging closely match; and #cite(<Raza2023>, form: "author") finds that @NNI works best for their dataset.
However #cite(<Gradka2018>, form: "author") note that @IDW is less computationally expensive than @RBF and especially kriging.

For this project, we chose @IDW as the interpolation method as it requires minimal tuning compared to the alternatives; it is computationally cheaper; and a ready implementation is available in @GDAL.
Given only a small part of the study region requires interpolation, the compromise is deemed acceptable as interpolation is not the primary focus of the project.

== River Elevation Data <sec:river-elevation>

The way different @DEM:pla treat water body surfaces can further influence the differences between products.

Currently, the Netherlands assigns a `NoData` value to the water bodies without efforts to estimate either the elevation of the water surface or the bathymetry. All other countries in the region either perform hydro-flattening as described by #cite(<zheng2019>, form: "prose") which estimates a flat across-channel surface and a continuous along-channel slope; or interpolate the shoreline. Similar approaches have been trialed for the Dutch elevation model @keurentjes2020ahn3 but are currently not included in the official product. Hydro-flattening may introduce artefacts due to temporal differences between different lidar surveys, which are presented in @chap:results.

A third approach is to estimate the riverbed as proposed by #cite(<dysarz2018>, form: "prose") which would allow for a mixed elevation/bathymetry model. No national product currently uses this approach; and estimating river elevation was deemed to be out of scope for this project.
