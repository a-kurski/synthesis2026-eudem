#import "@preview/lovelace:0.3.0": *
#import "@preview/drafting:0.2.2"
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

= Methodology <chap:method>

This chapter describes the current state of the harmonisation pipeline, providing a general overview and specifics of the approach to processing gridded (raster) elevation data and point clouds.

== Pipeline Overview

The aim of the project is to create a fully automated pipeline, which at this stage has not yet been achieved. Instead, separate pipelines for processing raster and point cloud data have been developed, which will be integrated after the midterm.

The raster processing is the main part of the pipeline --- re-extracting a @DTM from scratch is computationally expensive and is deemed unnecessary, and it is assumed #drafting.margin-note[but should be tested!] that the national @DTM:pla are sufficiently accurate. Point cloud processing is secondary and predominantly serves as an additional layer of evaluation and quality assurance.

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
    boxed((0, 0), [@DEM]),
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
    boxed((3.2, 0), [@PC]),
    boxed((3.2, 1), [Register]),
    boxed((3.2, 2), [Analyse registration \ Affine transform]),
    boxed((3.2, 3.4), [Re-extract @DEM \ if necessary]),

    edge((3.2, 0), (3.2, 1), "-|>"),
    edge((3.2, 1), (3.2, 2), "-|>"),
    edge((3.2, 2), (3.2, 3.4), "-|>"),
  )
)

== DTM harmonisation

A Python pipeline using @GDAL prepares national @DTM:pla on a common horizontal grid for subsequent cross-border analysis. Each run processes one country or region within a supplied @AOI. The current implementation supports the Netherlands through @AHN and Germany through @NRW. Shared preparation and verification stages are combined with processing rules specific to each source.

=== Common preparation

The pipeline first validates the inputs and defines a target grid with a cell size of 5 m in @ETRS89 / @UTM zone 32N (@EPSG:s code 25832). Fixing cell placement before processing ensures that cells align where outputs overlap. This is done to ensure cell-by-cell comparison is possible. Output extents follow the @AOI, so separate runs do not necessarily produce rasters with identical dimensions.

The required native-resolution terrain rasters are then acquired or reused from validated downloads. A surrounding margin is included to retain terrain contributing to boundary cells and, where applicable, nearby interpolation donors. Invalid elevations are converted to a common NoData value before averaging, preventing them from affecting the resulting elevations. The cleaned rasters are mosaicked at their native resolution so that subsequent processing can use neighbouring terrain across source-tile boundaries.

=== Transformation and aggregation

For @AHN, the 0.5 m terrain in Amersfoort / RD New (@EPSG:s code 28992) is reprojected and averaged directly onto the 5 m target grid in a single operation. Combining these steps avoids repeated resampling. For @NRW, the 1 m terrain already uses @EPSG:s code 25832. After verifying that its cells nest within the target grid, each 5 m elevation is calculated as the mean of valid elevations in the corresponding $5 times 5$ block. No terrain reprojection is required for @NRW.

The @DTM is also vertically transformed. This is done through the XDEM @API. Not all @DTM:pls have an included @VCRS, there is an included fallback which infers the source @VCRS from the file name. All rasters are transformed to the @EVRF2019.

Both paths exclude invalid values from averaging. Cells without valid contributors remain NoData, while partially observed cells receive the mean of their valid contributors. Averaging reduces data volume but can suppress narrow terrain features and local extremes. Remaining cells with invalid elevation values are set to the common NoData value of -9999

=== Gap filling and final outputs

For @AHN, gap filling is applied after resampling, using inverse-distance interpolation with a maximum search distance of 20 m and no smoothing. This order targets gaps remaining in the final-resolution surface and preserves all already valid target elevations. Valid surrounding terrain may supply interpolation donors outside the @AOI. The interpolation method will be updated to bilinear interpolation in following iterations. The unfilled surface and a binary status raster are retained to distinguish unchanged cells from interpolated cells. @NRW receives no additional gap filling.

After processing, temporary margins are removed and the original @AOI is applied. Applying this mask at this stage retains neighbouring terrain needed during averaging and interpolation. The pipeline then creates output tiles and stitches them into a common grid without resampling. Pixel equality is verified, and processing settings, source records and coverage information are saved for reproducibility.

Harmonisation currently covers horizontal coordinates, cell size and grid placement. @AHN retains @NAP heights and @NRW retains @DHHN2016 / @NHN heights. Vertical-datum differences must therefore be addressed before interpreting cross-source elevation differences. Gap filling estimates missing elevations and does not establish their accuracy.

=== Processing algorithm

@alg-dtm-preparation summarises the shared workflow and its source-specific branches. $G$ denotes the final grid and $G_e$ a temporary extension retaining interpolation context. When enabled, @AHN gap filling operates on this extended grid before final cropping and masking.

#[
#show figure: set align(left)
#figure(
  align(left)[
    #pseudocode-list(
      booktabs: true,
      booktabs-stroke: 1pt,
      line-number-supplement: "line",
      title: [#smallcaps[*@DTM Acquisition and Harmonisation*]],
    )[
      + *Input:* @AOI $A$, source $S$, processing settings $P$
      + *Output:* @DTM $H$; optional baseline $B$ and fill status $F$
      + Validate inputs and select supported source rules
      + Define grid $G$ on the 5 m @EPSG:s code 25832 lattice
      + Extend acquisition area for cell footprints and filling context
      + Acquire or reuse native rasters; validate and record sources
      + Clean invalid elevations and mosaic at native resolution
      + *if* $S$ is @AHN *then*
        + $G_e arrow.l G$; extend it if filling is enabled
        + $B arrow.l$ reproject and average the mosaic directly onto $G_e$
        + $H arrow.l B$
        + *if* filling is enabled *then*
          + $(H, F) arrow.l$ fill remaining gaps in $B$ within $A$ and record fill status
        + *end*
        + Crop $H$ and retained $B, F$ to $G$ without resampling
      + *else if* $S$ is @NRW *then*
        + Verify that the native 1 m cells nest within $G$
        + $H arrow.l$ valid-sample mean of each $5 times 5$ block
        + Retain NoData where no valid contributors exist
      + *end*
      + Apply the original @AOI mask to all retained products
      + Verify grid geometry and nonempty valid @AOI coverage
      + Create output tiles and stitch them without resampling
      + Verify stitched geometry and pixel equality with $H$
      + Save stitched @DTM, setting, and coverage counts
    ]
  ],
  kind: "algorithm",
  supplement: [Algorithm],
  caption: [@DTM acquisition and horizontal harmonisation.],
) <alg-dtm-preparation>
 ]


== Harmonisation with Point Clouds

In the pipeline, the point clouds are used as an additional step to assess the agreement between two different national datasets. Converting the point clouds to the same @CRS and subsequently performing registration allows to obtain better estimates of planimetric and vertical accuracy. The pseudocode describing the general principles is presented below; more elaborate description follows.

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

The registration is performed using the @ICP algorithm of the `open3D` python library --- equivalent functionality exists in @PDAL #highlight(fill: none, stroke: red)[(which we might switch to for the final processing)].
Notably, the registration produces a full affine transform $A = mat(R, bold(t))$ --- as the point clouds can be far from the origin, even a small rotational component has a large influence on the transformation and needs to be compensated with a large translation vector.
To evaluate the accuracy, pure translation is needed. It is obtained by applying the full affine transform $A$ to a point from the dataset $bold(p)$ and subtracting the transformed coordinates from coordinates of the initial point.

#drafting.inline-note()[The intention eventually is that for areas where both the national @DEM:pla and the @PC:pla disagree significantly, we also re-extract a @DTM from scratch using the most recent point cloud; we've not done that yet]


#drafting.inline-note()[The final version of this chapter will contain more quality ensurance/checking. The pipeline currently is not fully automated and this will be changed for the final version. ]

== River mask processing
One expected limitation of the pipeline is the errors introduced by water body interpolation. The solution to this problem is to exclude the subset of points which fall within the river area from the error analysis.

This mask could be identified from the classified point clouds. However, the reprocessing of the DEM using point clouds is out of the scope for this project. Therefore, we can only rely on the DEM data for segmentation. While river/lake masks do exist, they either provide global low resolution vector data @HydroATLAS, or low resolution raster data @SDG. 

In order to create a high quality water mask, the SDG mask was used as an input. The SDG mask contains a value 1, 2, or 3 to describe the certainty of the underlying value being water. The mask is filtered to only use certainty 2 and 3 values to ensure high confidence. The mask is then transformed to a binary format.

However, the SDG mask is not fine enough to be applied to the elevation map. Instead, we can use the SDG mask as seed points in a region growing algorithm. Since rivers and waterbodies are known to be relatively flat, a low threshold can be set for the region growing, such that the elevation jump at the shore is registered as the boundary of the water body. 

Each mask cell is transformed to the elevation map resolution, @CRS and grid. By applying this mask to the elevation map, it is essentially clipped to contain only heigh values that fall within the SDG mask. Each cell in this clipped DTM is taken as a seed point for a region growing algorithm. These seed points are added to the region growing queue. Each entry has eight neighbors and for each the height difference with the seed is calculated. When these differences are smaller than the set threshold, the neighboring point is added to the end of the queue. The result is a breadth first search which incrementally classifies cells as a water body. The end result is a binary mask, where cell values of one denote the existence of a water body.

#[
#show figure: set align(left)
#figure(
  align(left)[
    #pseudocode-list(
      booktabs: true,
      booktabs-stroke: 1pt,
      line-number-supplement: "line",
      title: [#smallcaps[*River Mask Generation*]],
    )[
      + *Input:* @DTM $D$, water probability raster $C$, growth tolerance $T$
      + *Output:* Binary river mask $R$
      + Load @DTM $D$
      + Determine the corresponding country classification raster $C$
      + Reproject $C$ onto the grid of $D$
      + Create initial water mask $W$
      + Assign cells with class value $2$ or $3$ in $C$ to water
      + Restrict $W$ to valid @DTM cells
      + Initialise region-growing seeds $S arrow.l W$
      + For every seed cell in $S$
        + Compute seed elevation value
      + Initialise empty region mask $G$
      + Add all accepted seeds to a processing queue
      + *while* the queue is not empty *do*
        + Remove the next cell $p$ from the queue
        + For each 8-connected neighbour $n$ of $p$
          + *if* $n$ lies within the valid @DTM domain and has not been visited *then*
            + Compute the elevation value of $n$
            + *if* the difference between the elevation values of $p$ and $n$ is less than or equal to $T$ *then*
              + Add $n$ to $G$
              + Add $n$ to the queue
            + *end*
          + *end*
        + *end*
      + *end*
      + Initialise binary river mask $R$ with value $0$
      + Assign river value $1$ to all cells contained in $G$
      + Assign NoData value to invalid @DTM cells
      + Save $R$
    ]
  ],
  kind: "algorithm",
  supplement: [Algorithm],
  caption: [Binary river-mask generation by seeded region growing from hydrographic classes.],
) <alg-river-mask>
]

#drafting.inline-note("Add a nice image that shows the river mask for the entire rhine catchment area and another for a local area")

#image("/assets/image.png")

== Border analysis

The final step of the pipeline is to pairwise compare neighboring datasets, and evaluate the results. The first step in this process is analysing which regions overlap. It is followed by calculating the height difference, coregistration, INSPIRE resolution threshold compliance for fine and course resolutions, height difference @STD:asf, aspect difference, error due to slope, error due to distance from the border, 

The final step of the pipeline is to pairwise compare neighboring datasets, and to evaluate the results. The first step in this process is to identify which @DTM:pls neighbor one another. In order to determine wether overlap exists, the maximum and minimum $x$ and $y$ coordinates of each country's @DTM are stored. The following logic is applied to see if the bounding boxes overlap:

$max(x_("region_1_min"),x_("region_2_min")) < min(x_("region_1_max"),x_("region_2_max")) and max(y_("region_1_min"),y_("region_2_min")) < min(y_("region_1_max"),y_("region_2_max"))$

This is not a perfect method as regions which do not cover the entire bounding box may not overlap. Therefore, another check is done by cropping the @DTM of one country to the other. However, this is a computationally heavier operation and can therefore be avoided if no overlap is known to exist.

The next step in the analysis process is to calculate the elevation differences between the two maps. @GDAL allows for this process to be simplified to a subtraction operation. The raw difference does however not tell the full story. Systematic errors may offset an entire DTM, and are a potential limitation of the vertical transform. Therefore, a @STD raster is also produced to highlight stark deviations in height between the @DTM:pls.

Another way to analyse these systematic errors is through coregistration. This is a function in XDEM which performs an affine transform, through solving of a cosine equation @tc-5-271-2011, which assures best alignment in $x$, $y$ and $z$ directions of the @DTM. Using both the coregistered and raw @DTM:pls, we can calculate statistics such as the @RMSE, @STD, mean, median, min, max, etc. By comparing the results we can determine the effect of misaligned @DTM:pls is, and how it affects true outliers in the difference. Another analysis element we can perform using this coregistration is determining random errors throughout the overlap. These represent likely measurement errors, or errors caused by light bounce during laser scanning.

An important element specified in @sec:inspire-quality, is the compliance with the INSPIRE resolution standard. To analyse this, two seperate raster approaches are used. The first evaluates on a cell by cell size if a cell does, or does not comply with the threshold. The output of this is the $italic("exceeds_threshold")$ mask. This looks at the error per cell and the INSPIRE threshold #drafting.inline-note("explain why INSPIRE was chosen as the treshold"). The second approach uses a course grid which evaluates for a given cell size if sections of the @DTM comply with the standard.

Another metric that is evaluated, is the difference in aspect between the two @DTM:pls. By looking at this metric we can see how the aspect of slopes is maintained between two seperate datasets. Analyzing the aspect is very sensitive to small changes in elevation as this can change the aspect angle drastically.

Aside from random noise and systematic errors, other elements such as slope can affect the error of a @LiDAR derived @DTM:pls. By taking the errors in 5 degree angle bins, we can calculate the RMSE in slope ranges. Due to slope, a small horizontal displacement in sample location, can greatly affect the vertical position of the sample point. Therefore, evaluating this statistic helps us understand when errors are the result of steep slopes.

The last element that is evaluated is the distance from the border. Since there exists overlap between countries, we can evaluate if points further outside of the administrative borders of either region affect the quality of the data and the elevation difference. A similar approach to the slope RMSE is used. By taking the distance of a point from a provided border vector and dividing the distance into bins, we can evaluate at various distances from the border if there is a relation between the distance and the RMSE.


