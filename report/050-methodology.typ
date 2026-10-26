#import "@preview/lovelace:0.3.0": *
#import "@preview/drafting:0.2.2"
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

= Methodology <chap:method>

// [X]

This chapter describes the harmonisation pipeline, providing both a general overview and specifics of the approach to processing heterogeneous elevation data and subsequent evaluation of the results.

== Pipeline Overview

// [X]

Within this project, we create a fully automated pipeline for processing and harmonising heterogeneous gridded elevation data.
Raster processing has been chosen as the focus of the project as re-extracting a @DTM from scratch is computationally expensive and is deemed unnecessary, and it is assumed that the national @DTM:pla are sufficiently accurate to allow near-seamless integration --- this assumption is tested in @chap:results.
The pipeline can currently handle data from 6 countries within the Rhine catchment area and is expected to support similar data from other providers.
Point cloud processing has been excluded from the pipeline due to the limited time of the project and limited availability of the data; where available, point clouds are used for additional evaluation of the gridded elevation dataset.


// Boxed "start/end" nodes vs. plain process steps
#let boxed(pos, label, ..args) = node(
  pos, label, stroke: 1pt, inset: 6pt, corner-radius: 2pt, ..args,
)

#figure(
  diagram(
    spacing: (2.5em, 2em),
    edge-stroke: 1pt,
    node-inset: 6pt,

    // ── DEM A branch ──────────────────────────────
    boxed((0, 0), [@DEM A tiles]),
    boxed((0, 1), [Reproject]),
    boxed((0, 2), [Resample]),
    boxed((0, 3), [Aggregate]),
    boxed((0, 4), [Interpolate]),
    boxed((0, 5), [Extract River Mask]),
    // DEM B branch
    boxed((2, 0), [@DEM B tiles]),
    boxed((2, 1), [Reproject]),
    boxed((2, 2), [Resample]),
    boxed((2, 3), [Aggregate]),
    boxed((2, 4), [Interpolate]),
    boxed((2, 5), [Extract River Mask]),


    boxed((1, 7), [Assemble]),

    edge((0, 0), (0, 1), "-|>"),
    edge((0, 1), (0, 2), "-|>"),
    edge((0, 2), (0, 3), "-|>"),
    edge((0, 3), (0, 4), "-|>"),
    edge((0, 4), (0, 5), "-|>"),
    //
    edge((2, 0), (2, 1), "-|>"),
    edge((2, 1), (2, 2), "-|>"),
    edge((2, 2), (2, 3), "-|>"),
    edge((2, 3), (2, 4), "-|>"),
    edge((2, 4), (2, 5), "-|>"),

    // Side branch: DEM -> compare
    boxed((1, 6), [Resolve conflicts]),
    edge((0, 4), (.9, 4), (.9, 6), "-|>"),
    edge((2, 4), (1.1, 4), (1.1, 6), "-|>"),
    edge((1, 6), (1, 7), "-|>"),
  ),
  caption: [Processing flowchart]
)

The pipeline is split into two stages: processing and comparison --- the above flowchart only shows the processing stage; comparison is described below.
Both stages take a `.json` file as input and write the intermediate and final results to it.
The comparison stage reads and evaluates data completed during processing.
The user is not expected to interact or pass arguments directly to the pipeline --- instead, they fill in the `.json` with input data.

The global settings influence both the final product and the performance of the pipeline.
The key raster settings include the target @CRS and resolution, region extent, interpolation settings, and path where the output raster should be written to.
The performance settings govern the maximum number of threads which can be used for processing or the number of regions which can be processed at once.

The region settings include the path to vector and raw raster data, information about regions @CRS and @VCRS in case they are not specified within metadata, and whether interpolation is needed --- currently, only Dutch @DTM needs interpolation.
Additionally, a water mask is passed for the river detection part of the algorithm.

For the comparison stage, the settings include the threshold for error detection as a fraction of the resolution, whether to perform kriging, and the region's river mask.

Full breakdown of all settings can be found in `README.md` (see #drafting.margin-note()[TODO link to appendix]).

=== Data Acquisition & Pre-processing

Data acquisition is a crucial step which enables the rest of the workflow despite technically being outside of the fully automated part of the pipeline.
National and regional data providers offer different download options: the Netherlands and @NRW offer a @WCS server for access/download; Bavaria and France offer tiled raster data in a binary (`.xyz` and `.asc` respectively) format; Luxembourg offers a single untiled @COG; the remaining datasets are available as GeoTIFF (`.tif`) tiles from a catalogue or a download portal.
Some providers (Hessen, France) bundle the tiles into zip-archives by administrative subdivision.

The downloads are handled automatically but each region essentially requires a bespoke solution due to the differences in the data portals and the catalogues.

For each region, the data is queried within a specified @AOI (here: the intersection of the region's extent and the Rhine catchment area); where possible, the tiles are downloaded in parallel; where necessary, the downloaded are recursively unzipped.
The downloaded data is then validated and checked against a catalogue.

=== Reprojection & Resampling

This is the first step in the raster processing pipeline.

First, all regions without a processed @DEM are listed and a queue is built from largest (processed first) to smallest (processed last) region.
The regions can be processed in parallel and a queue like this helps avoid a situation when one process is performing the reprojection while the remaining processes are sitting idle.

For each region, all tiles are first aggregated into a virtual mosaic (`.vrt`).
Each tile is assigned the region's @CRS as specified in the `.json` file --- this behaviour is necessary as parts of regional datasets (most notably subdivisions of Hessen and @RLP) have their @CRS either missing or incorrectly specified within the tile's metadata; and is placed into the mosaic according to that @CRS.
No region has been found to have a mixed @CRS; we note, however, that this approach may cause issues if that is the case.

Similarly, for certain regions, a NoData value needs to be specified.
Parts of @BW and Hessen, again, record NoData as 0 but do not state this in metadata, which warrants forcing a NoData value.

The output grid is established based on the resolution supplied in the `.json`.
The grid is identical for all regions.
For the product described in this report, the grid is in EPSG:3035 and at 5m resolution; the vertical @CRS is @EVRF\2007 (EPSG:5621) as the PROJ library does not yet natively support transformation to @EVRF\2019.

Then, the rasters are warped (using @GDAL's warp) to the common grid.
At this step, the data is transformed from the source @CRS to target @CRS both horizontally and vertically.
After that, the data is resampled to the target grid.
By default, the chosen resampling method is averaging all the valid (i.e. not NoData) sample points located in the given grid cell, but bilinear interpolation is also possible.
A brief comparison of interpolation methods is included in @chap:results.

The resampled raster is written to file, without cropping, with a NoData value of -9999.

=== Filling Gaps

If specified by a region's setting in the `.json`, gap filling is applied after resampling using @IDW interpolation with a specified maximum search distance and no smoothing.
This order targets gaps remaining in the final-resolution surface and preserves all already valid target elevations.
Valid surrounding terrain may supply interpolation donors outside the @AOI.
Alongside the interpolated surface, a binary interpolation mask are written to file to distinguish unchanged cells from interpolated cells.

=== Resolving Conflicts and Assembling the Output

At this step, we need to decide which data to write to the output @DEM where @DEM:pla of several regions overlap.
Several approaches were considered, such as evaluating for best temporal match or data quality.
The former is not guaranteed by raster metadata --- referring to the GPS time of the corresponding point cloud was considered but ruled out due to storage requirements --- and the latter is difficult to infer from raster elevation data alone.
Instead, we simply write each region's data within its boundaries (as determined by a vector file of that region).

However for regions where interpolation was performed during our processing, we decide to overwrite the interpolated grid cells with non-interpolated data from the neighbouring region if that data is available.
If the agreement between regions is high --- like it is in our case, see @chap:results --- this approach produces fewer and smaller artefacts than accepting interpolation results.

The resulting elevation data is written to an output GeoTIFF, cropped to the specified region extents.

// === Processing algorithm
//
// @alg-dtm-preparation summarises the shared workflow and its source-specific branches. $G$ denotes the final grid and $G_e$ a temporary extension retaining interpolation context. When enabled, @AHN gap filling operates on this extended grid before final cropping and masking.
//
// #[
// #show figure: set align(left)
// #figure(
//   align(left)[
//     #pseudocode-list(
//       booktabs: true,
//       booktabs-stroke: 1pt,
//       line-number-supplement: "line",
//       title: [#smallcaps[*@DTM Acquisition and Harmonisation*]],
//     )[
//       + *Input:* @AOI $A$, source $S$, processing settings $P$
//       + *Output:* @DTM $H$; optional baseline $B$ and fill status $F$
//       + Validate inputs and select supported source rules
//       + Define grid $G$ on the 5 m @EPSG:s code 25832 lattice
//       + Extend acquisition area for cell footprints and filling context
//       + Acquire or reuse native rasters; validate and record sources
//       + Clean invalid elevations and mosaic at native resolution
//       + *if* $S$ is @AHN *then*
//         + $G_e arrow.l G$; extend it if filling is enabled
//         + $B arrow.l$ reproject and average the mosaic directly onto $G_e$
//         + $H arrow.l B$
//         + *if* filling is enabled *then*
//           + $(H, F) arrow.l$ fill remaining gaps in $B$ within $A$ and record fill status
//         + *end*
//         + Crop $H$ and retained $B, F$ to $G$ without resampling
//       + *else if* $S$ is @NRW *then*
//         + Verify that the native 1 m cells nest within $G$
//         + $H arrow.l$ valid-sample mean of each $5 times 5$ block
//         + Retain NoData where no valid contributors exist
//       + *end*
//       + Apply the original @AOI mask to all retained products
//       + Verify grid geometry and nonempty valid @AOI coverage
//       + Create output tiles and stitch them without resampling
//       + Verify stitched geometry and pixel equality with $H$
//       + Save stitched @DTM, setting, and coverage counts
//     ]
//   ],
//   kind: "algorithm",
//   supplement: [Algorithm],
//   caption: [@DTM acquisition and horizontal harmonisation.],
// ) <alg-dtm-preparation>
//  ]

== Water Mask Processing

An expected limitation of the pipeline is retaining the errors introduced by water body interpolation. The solution to this problem is to exclude the subset of points which fall within the river area from the error analysis.

This mask could be identified using the classified point clouds. However, the re-extraction of a DEM from point clouds is out of the scope for this project. Therefore, we can only rely on the DEM data for segmentation. While river/lake masks do exist, they either offer provide global low resolution vector data @HydroATLAS, or low resolution raster data @unep_fee.

In order to create a high quality water mask, the UNEP @FEE mask was used as an input. The @FEE mask contains a value 1, 2, or 3 to describe the certainty of the underlying value being water --- corresponding to "no water", "seasonal water", and "permanent water" --- based on historical remote sensing data. The mask is filtered to only use values of 2 and 3. The mask is then transformed to a binary format.

However, the @FEE mask is not fine enough to be applied to the elevation map. Instead, we can use the @FEE mask as seed points in a region growing algorithm. Since rivers and waterbodies are known to be relatively flat, a low elevation difference threshold is set for the region growing, such that the elevation jump at the shore is registered as the boundary of the water body.

Each mask cell is transformed to the elevation map resolution, @CRS and grid. By applying this mask to the elevation map, it is essentially clipped to contain only heigh values that fall within the @FEE mask. Each cell in this clipped DTM is taken as a seed point for a region growing algorithm. These seed points are added to the region growing queue. Each entry has eight neighbors and for each the height difference with the seed is calculated. When these differences are smaller than the set threshold, the neighboring point is added to the end of the queue. The result is a breadth first search which incrementally classifies cells as a water body. The end result is a mask with region IDs, where cell values above 0 denote the existence of a water body.

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
      + *Input:* @DTM $D$ with valid cells $V$, extent $E$, water probability raster $C$, seed values $S$, vertical tolerance $Delta_z$ \  *Output:* River mask $R$
      + $M <- $ empty boolean grid on the grid of $D$
      + *for each* grid cell $c in C$ within extents of $D$ where $C[c] in S$ *do:*
        + transform grid point of $c$ to target CRS
        + $M[c] <- 1$
      + $M <- M inter P inter V$ #h(1fr) _discard seeds outside the region or without DEM data_
      + $R <- 0$ everywhere; $r <- 0$
      + *for each* seed $s$ in $M$, in row-major order *do*
        + *if* $L[s] != 0$ *do:*
          +  *continue* #h(1fr) _already part of an earlier water body_
        + $r <- r + 1$; $R[s] <- r$
        + $Q <- [s]$ #h(1fr) _FIFO queue: breadth-first growth_
        +       + *while* $Q$ is not empty *do*
          + $c <- $ pop front of $Q$
          + *for each* of the 8 neighbours $n$ of $c$ inside the grid *do*
            + *if* $n in V$ *and* $L[n] = 0$ *and* $|E[n] - E[c]| <= Delta_z$ *then*
              + $L[n] <- r$
              + push $n$ onto $Q$
        + $R[not V] <- -1$
        + *return* $L$
    ]
  ],
  kind: "algorithm",
  supplement: [Algorithm],
  caption: [Binary river-mask generation by seeded region growing from hydrographic classes.],
) <alg-river-mask>
]


#figure(
  image("assets/rivermask-local.png", width:70%),
  caption:[Rhine catchment area river mask of the area surrounding Cologne]
)

#figure(
  image("assets/rhinecatchment-full.png", width:70%),
  caption:[Rhine catchment area river mask of the full catchment area]
)

== Border Analysis <sec:border-analysis>

The final stage of the project is to pairwise compare neighboring datasets and evaluate the results. The first step in this process is finding out which regions overlap. It is followed by calculating the height difference, performing coregistration, and analysing aspects of said difference such as correlation between error magnitude and slope or the rate of @INSPIRE compliance.

To determine which @DTM:pla overlap one another, we first compute the bounding boxes of each @DTM and their overlap is checked:

$max(x_("region_1_min"),x_("region_2_min")) < min(x_("region_1_max"),x_("region_2_max")) and max(y_("region_1_min"),y_("region_2_min")) < min(y_("region_1_max"),y_("region_2_max"))$

This is not a perfect method as the bounding boxes may overlap even when the datasets do not. Therefore, another check is done by cropping the @DTM of one country with the other and checking if the cropped dataset is not empty. However, this is a computationally expensive operation and is thus only performed if an overlap between the bounding boxes is found.

The next step in the analysis process is to calculate the elevation differences between the two maps.
@GDAL allows for this process to be simplified to a subtraction operation.

Based on this difference, We construct polygons to highlight errors greater than a set threshold. Nearby polygons are merged into one which allows to essentially detect _areas_ with high error rates rather than just count individual point samples.
We selected the threshold to match the ratio between resolution and vertical @RMSE --- at 5m, that threshold is 1.67m. This threshold is a little lower than Copernicus's 2m @LE90 benchmark.
For the analysis, the number of cells where the error rate exceeds the threshold is also presented.

We can also analyze the spatial correlation of the errors.
Overall, it is expected that Tobler's #cite(<Tobler1970>, form: "year") first law of geography will hold: the close errors will have a higher correlation than far-away ones.
It is further expected that stochastic errors are uncorrelated, and a high correlation of far away errors likely indicates a systematic error instead.
However, the correlation does not account for error magnitude --- a small systematic error will result in a higher correlation rate than a large stochastic one.

Another way to evaluate systematic errors is through coregistration. This is a function in XDEM which performs an affine transform @tc-5-271-2011, which ensures best alignment of the @DTM:pla in $x$, $y$ and $z$ directions. The statistics (@RMSE, @LE90, mean error etc) are calculated for the border region before and after coregistration. A small affine transform with a high @RMSE would indicate stochastic errors.

We also produce several graphs to aid with the analysis.
First one is a histogram of the error magnitudes for a given border pair.
The second is a graph of the error rates relative to the slope angle --- here, expressed as @RMSE for a given 5-degree bin of slope angle.
@INSPIRE suggests different relationships for horizontal resolution and vertical accuracy depending on slope angle; we therefore expect the slope angle to have an effect on the magnitude of the error.
Another graph shows the errors relative to the distance from the border (again, @RMSE for a given 50-meter bin).
This "border effect" graph can, for instance, help detect errors due to extrapolation at the edge of a dataset, but it can also be sensitive to a single large error.
