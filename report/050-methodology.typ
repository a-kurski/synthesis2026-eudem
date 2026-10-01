#import "@preview/lovelace:0.3.0": *
#import "@preview/drafting:0.2.2"
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

= Harmonisation Pipeline <chap:method>

This chapter describes the current state of the harmonisation pipeline, providing a general overview and specifics of the approach to processing gridded (raster) elevation data and point clouds.

== Pipeline Overview

The aim of the project is to create a fully automated pipeline, which at this stage has not yet been achieved. Instead, separate pipelines for processing raster and point cloud data have been developed, which will be integrated after the midterm.

The raster processing is the main part of the pipeline --- re-extracting a DTM from scratch is computationally expensive and is deemed unnecessary, and it is assumed #drafting.margin-note[but should be tested!] that the national DTMs are sufficiently accurate. Point cloud processing is secondary and predominantly serves as an additional layer of evaluation and quality assurance.

// Boxed "start/end" nodes vs. plain process steps
#let boxed(pos, label, ..args) = node(
  pos, label, stroke: 1pt, inset: 6pt, corner-radius: 2pt, ..args,
)

#figure(
  diagram(
    spacing: (2.2em, 1.5em),
    edge-stroke: 1pt,
    node-inset: 6pt,

    // ── DEM branch ──────────────────────────────
    boxed((0, 0), [DEM]),
    boxed((0, 1), [Reproject]),
    boxed((0, 2), [Resample]),
    boxed((0, 3), [Interpolate]),
    boxed((0, 4), [Stitch]),

    edge((0, 0), (0, 1), "-|>"),
    edge((0, 1), (0, 2), "-|>"),
    edge((0, 2), (0, 3), "-|>"),
    edge((0, 3), (0, 4), "-|>"),

    // Side branch: DEM -> compare
    boxed((1.4, 1), [Compare in overlaps]),
    edge((0, 0), (1.4, 0), (1.4, 1), "-|>"),

    // ── Point cloud branch ──────────────────────
    boxed((3.2, 0), [PC]),
    boxed((3.2, 1), [Register]),
    boxed((3.2, 2), [Analyse registration \ Affine transform]),
    boxed((3.2, 3.4), [Re-extract DEM \ if necessary]),

    edge((3.2, 0), (3.2, 1), "-|>"),
    edge((3.2, 1), (3.2, 2), "-|>"),
    edge((3.2, 2), (3.2, 3.4), "-|>"),
  )
)

== DTM harmonisation

A Python pipeline using GDAL prepares national digital terrain models (DTMs) on a common horizontal grid for subsequent cross-border analysis. Each run processes one country or region within a supplied area of interest (AOI). The current implementation supports the Netherlands through AHN and Germany through North Rhine-Westphalia (NRW). Shared preparation and verification stages are combined with processing rules specific to each source.

=== Common preparation

The pipeline first validates the inputs and defines a target grid with a cell size of 5 m in ETRS89 / UTM zone 32N (EPSG:25832). Fixing cell placement before processing ensures that cells align where outputs overlap. This is done to ensure cell-by-cell comparison is possible. Output extents follow the AOI, so separate runs do not necessarily produce rasters with identical dimensions.

The required native-resolution terrain rasters are then acquired or reused from validated downloads. A surrounding margin is included to retain terrain contributing to boundary cells and, where applicable, nearby interpolation donors. Invalid elevations are converted to a common NoData value before averaging, preventing them from affecting the resulting elevations. The cleaned rasters are mosaicked at their native resolution so that subsequent processing can use neighbouring terrain across source-tile boundaries.

=== Transformation and aggregation

For AHN, the 0.5 m terrain in Amersfoort / RD New (EPSG:28992) is reprojected and averaged directly onto the 5 m target grid in a single operation. Combining these steps avoids repeated resampling. For NRW, the 1 m terrain already uses EPSG:25832. After verifying that its cells nest within the target grid, each 5 m elevation is calculated as the mean of valid elevations in the corresponding $5 times 5$ block. No terrain reprojection is required for NRW.

Both paths exclude invalid values from averaging. Cells without valid contributors remain NoData, while partially observed cells receive the mean of their valid contributors. Averaging reduces data volume but can suppress narrow terrain features and local extremes. Remaining cells with invalid elevation values are set to the common NoData value of -9999

=== Gap filling and final outputs

For AHN, gap filling is applied after resampling, using inverse-distance interpolation with a maximum search distance of 20 m and no smoothing. This order targets gaps remaining in the final-resolution surface and preserves all already valid target elevations. Valid surrounding terrain may supply interpolation donors outside the AOI. The interpolation method will be updated to bilinear interpolation in following iterations. The unfilled surface and a binary status raster are retained to distinguish unchanged cells from interpolated cells. NRW receives no additional gap filling.

After processing, temporary margins are removed and the original AOI is applied using. Applying this mask at this stage retains neighbouring terrain needed during averaging and interpolation. The pipeline then creates output tiles and stitches them into a common grid without resampling. Pixel equality is verified, and processing settings, source records and coverage information are saved for reproducibility.

Harmonisation currently covers horizontal coordinates, cell size and grid placement. AHN retains NAP heights and NRW retains DHHN2016/NHN heights. Vertical-datum differences must therefore be addressed before interpreting cross-source elevation differences. Gap filling estimates missing elevations and does not establish their accuracy.

=== Processing algorithm

@alg-dtm-preparation summarises the shared workflow and its source-specific branches. $G$ denotes the final grid and $G_e$ a temporary extension retaining interpolation context. When enabled, AHN gap filling operates on this extended grid before final cropping and masking.

#[
#show figure: set align(left)
#figure(
  align(left)[
    #pseudocode-list(
      booktabs: true,
      booktabs-stroke: 1pt,
      line-number-supplement: "line",
      title: [#smallcaps[*DTM Acquisition and Harmonisation*]],
    )[
      + *Input:* AOI $A$, source $S$, processing settings $P$
      + *Output:* DTM $H$; optional baseline $B$ and fill status $F$
      + Validate inputs and select supported source rules
      + Define grid $G$ on the 5 m EPSG:25832 lattice
      + Extend acquisition area for cell footprints and filling context
      + Acquire or reuse native rasters; validate and record sources
      + Clean invalid elevations and mosaic at native resolution
      + *if* $S$ is AHN *then*
        + $G_e arrow.l G$; extend it if filling is enabled
        + $B arrow.l$ reproject and average the mosaic directly onto $G_e$
        + $H arrow.l B$
        + *if* filling is enabled *then*
          + $(H, F) arrow.l$ fill remaining gaps in $B$ within $A$ and record fill status
        + *end*
        + Crop $H$ and retained $B, F$ to $G$ without resampling
      + *else if* $S$ is NRW *then*
        + Verify that the native 1 m cells nest within $G$
        + $H arrow.l$ valid-sample mean of each $5 times 5$ block
        + Retain NoData where no valid contributors exist
      + *end*
      + Apply the original AOI mask to all retained products
      + Verify grid geometry and nonempty valid AOI coverage
      + Create output tiles and stitch them without resampling
      + Verify stitched geometry and pixel equality with $H$
      + Save stitched DTM, setting, and coverage counts
    ]
  ],
  kind: "algorithm",
  supplement: [Algorithm],
  caption: [DTM acquisition and horizontal harmonisation.],
) <alg-dtm-preparation>
 ]


== Harmonisation with Point Clouds

In the pipeline, the point clouds are used as an additional step to assess the agreement between two different national datasets. Converting the point clouds to the same CRS and subsequently performing registration allows to obtain better estimates of planimetric and vertical accuracy. The pseudocode describing the general principles is presented below; more elaborate description follows.

#[
  #show figure: set align(left)

  #figure(
    align(left)[
      #pseudocode-list(
        booktabs: true,
        booktabs-stroke: 1pt,
        line-number-supplement: "line",
        title: [#smallcaps[*Point Cloud Registration*]],
      )[
        + *Input:* a set of point clouds of country A $scr(a) in scr(A)$; a set of point clouds of country B $scr(b) in scr(B)$ \
          *Output:* a set of translation vectors $scr(T)$ obtained from registering $scr(a) in scr(A)$ against $scr(b) in scr(B)$
        + *for* every $scr(a)_i in scr(A) inter scr(b)_j in scr(B) != emptyset$ *do:*
          + perform registration of $scr(a)_i$ against $scr(b)_j$
          + $A_(i j) arrow.l$ affine transform from registration
          + $bold(p)^T = mat(x, y, z) arrow.l$ a point in $scr(a)_i$
          + $bold(p)_t arrow.l A_(i j) bold(p)$ \// _apply affine transform to point_
          + $bold(t)_(i j) arrow.l bold(p)_t - bold(p)$ \// _find pure translation from initial point to transform_
          + append $bold(t)_(i j) "to" scr(T)$
      ]
    ],
    kind: "algorithm",
    supplement: [Algorithm],
    caption: [Point Cloud Registration],
  ) <alg-point-cloud-registration>
]

Due to computational limitations, the comparison is done between tiles rather than between full national datasets.
The downside of this approach is that the registration is likely to be less accurate overall as it relies on relatively fewer points; the upside is that it may be more informative in regards to small-scale changes at the border.

Another decision made to reduce computational costs is to use the extent of a point cloud as provided in the header when finding pairs of intersections instead of a convex, concave, or an #sym.alpha\-hull.
This may result in false positives among intersection pairs and thus an incorrect assessment of the accuracy.
In these cases, cross-referencing with a raster is advised #highlight(fill: none, stroke: red)[but currently not implemented].

The registration is performed using iterative close point (ICP) algorithm of the `open3D` python library --- equivalent functionality exists in PDAL #highlight(fill: none, stroke: red)[(which we might switch to for the final processing)].
Notably, the registration produces a full affine transform $A = mat(R, bold(t))$ --- as the point clouds can be far from the origin, even a small rotational component has a large influence on the transformation and needs to be compensated with a large translation vector.
To evaluate the accuracy, pure translation is needed. It is obtained by applying the full affine transform $A$ to a point from the dataset $bold(p)$ and subtracting the transformed coordinates from coordinates of the initial point.

#drafting.inline-note()[The intention eventually is that for areas where both the national DEMs and the PCs disagree significantly, we also re-extract a DTM from scratch using the most recent point cloud; we've not done that yet]
