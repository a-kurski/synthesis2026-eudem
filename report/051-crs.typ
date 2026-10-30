#import "@preview/drafting:0.2.2"

==== Input CRS

Most national data providers supply elevation coverage in the local @CRS, such as Amersfoort/RD New (@EPSG code 28992) for the Netherlands. The only exception to this rule is Germany as it uses @UTM zones #drafting.margin-note[TODO: cite]. We found that every dataset uses a national vertical reference system, such as @NAP for the Netherlands or @DHHN2016 for Germany. The full overview of the horizontal and vertical reference systems for each dataset can be found in #drafting.margin-note()[TODO: ref appx].

==== Target CRS

Following a discussion with the clients, we determined that @ETRS89-LAEA is best suited for the current project for the following reasons:
- *Cell area.* The primary use of the @DEM is hydrological modelling. The cells of @ETRS89-LAEA each have the same area, removing the need to recompute it for each cell.
- *Cell shape.* The area of the project is close to the origin of the @CRS which minimises the shape distortion, as seen in @fig:tissot: the Tissot's indicatrices are near-circular, with the semi-major and semi-minor axes being within 0.2% of 1. In practice, this means that the equal spacing of the grid in the X and Y directions will also be near-equal in reality (intuitively, a square cell on a map represents square parcel of the land).
- *Cell orientation.* The angles are distorted somewhat more: the westernmost point is at 4#sym.degree E, which results in a cell being rotated 6° relative to true North at that point; however the centroid of the dataset is at 8#sym.degree E, which means a rotation of only 2#sym.degree.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 6pt,
    [#image("assets/tissot-etrs89.pdf", width: 100%) Geodetic ETRS89], [#image("assets/tissot-equi7.pdf", width: 100%) Equi7 Europe],
    [#image("assets/tissot-lcc.pdf", width: 100%) ETRS89-LCC], [#image("assets/tissot-laea.pdf", width: 100%) ETRS89-LAEA],
  ),
  caption: [Comparison of Tissot indicatrices for different projections]
) <fig:tissot>

The preservation of the angles --- which is named among the key reasons to use geodetic coordinates in the @INSPIRE specification --- has been determined to be of lowest priority considering the theme of the project, while the preservation of area is of highest priority.
A qualitative analysis of Tissot indicatrices (@fig:tissot) shows that the distortions in the Rhine catchment area are relatively minimal with @ETRS89-LAEA, whereas @ETRS89-GRS80 noticeably distorts shape and @ETRS89-LCC distorts area.

Additionally, the use of Equi7Grid was considered.
Equi7Grid has been developed by Vienna University of Technology specifically to support high-resolution raster data by minimising data loss and data inflation @tuwgeo_equi7.
// #drafting.inline-note("got an issue with the source that prevented compiling")
@fig:tissot shows the distortion caused by using the Europe subgrid.
The use of a @CRS other than one derived from @ETRS89 is explicitly disallowed by the @INSPIRE specification, which excludes Equi7Grid from the candidate @CRS:pla for this project.
However, we recognise that in other cases, a different @CRS may be advantageous.
Therefore, the pipeline is designed to support selection of a user-specified target @CRS by its @EPSG code.
