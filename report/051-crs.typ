#import "@preview/drafting:0.2.2"

== CRS Selection

=== Input CRS

Most national data providers supply elevation coverage in the local CRS, such as Amersfoort/RD New (EPSG:28992) for the Netherlands. The only exception to this rule is Germany as it uses Universal Transverse Mercator (UTM) zones #drafting.margin-note[TODO: cite]. We found that every dataset uses a national vertical reference system, such as NAP for the Netherlands or DHHN2016 for Germany. The full overview of the horizontal and vertical reference systems for each dataset can be found in #drafting.margin-note()[TODO: ref appx].

=== Target CRS

As explained in @sec:inspire-crs, INSPIRE requires that the CRS of a dataset is derived from ETRS89, and recommends the use of ETRS89, geodetic coordinates, and latitudinal zones determining the aspect ratio of the cells.
However following a discussion with the clients, we determined that ETRS89-LAEA is best suited for the current project for the following reasons:
- *Cell area.* The primary use of the DEM is hydrological modelling. The cells of ETRS89-LAEA each have the same area, removing the need to recompute it for each cell.
- *Cell shape.* The area of the project is close to the origin of the CRS which minimises the shape distortion, as seen in #drafting.margin-note()[TODO ref figure]: the Tissot's indicatrices are near-circular, with the semi-major and semi-minor axes being within 0.2% of 1. In practice, this means that the equal spacing of the grid in the X and Y directions will also be near-equal in reality (intuitively, a square cell on a map represents square parcel of the land).
- *Cell orientation.* The angles are distorted somewhat more: the westernmost point is at 4#sym.degree E, which results in a cell being rotated 6° relative to true North at that point; however the centroid of the dataset is at 8#sym.degree E, which means a rotation of only 2#sym.degree.

The preservation of the angles --- which is named among the key reasons to use geodetic coordinates in the INSPIRE specification --- has been determined to be of the lowest priority considering the theme of the project, while the preservation of area is of the highest priority.
A qualitative analysis of Tissot indicatrices #drafting.margin-note()[TODO: ref figure] shows that the distortions in the Rhine catchment area are relatively minimal with ETRS89-LAEA, whereas ETRS89-GRS80 noticeably distorts shape and ETRS89-LCC distorts area.

#drafting.inline-note()[TODO: add comparison of tissot for LAEA, LCC, and raw ETRS89]

Additionally, the use of Equi7Grid was considered.
Equi7Grid has been developed by TU Wien specifically to support high-resolution raster data by minimising data loss and data inflation.
#drafting.margin-note()[TODO: ref figure] shows the distortion caused by using the Europe subgrid.
The use of CRS other than derived from ETRS89 is explicitly disallowed by INSPIRE specification, which excludes Equi7Grid from the candidate CRS for this project.
However, we recognise that in other cases, a different CRS may be advantageous.
Therefore, the pipeline is designed to support selection of a user-specified target CRS by its EPSG code.
