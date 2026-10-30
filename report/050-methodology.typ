#import "@preview/lovelace:0.3.0": *
#import "@preview/drafting:0.2.2"
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

= Methodology <chap:method>

// [X]

This chapter describes the methodology used in the DTM harmonisation pipeline. It provides both a general overview and specifics of the approach to processing heterogeneous elevation data and subsequent analysis of the results. The additional methodological aspects discussed in this chapter include the water mask generation, and the description of the visualization and comparison methods employed.

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
    boxed((0, 0), [Acquire @DEM A tiles]),
    boxed((0, 1), [Reproject]),
    boxed((0, 2), [Resample]),
    boxed((0, 3), [Aggregate]),
    boxed((0, 4), [Fill Gaps]),
    boxed((0, 5), [Extract River Mask]),
    // DEM B branch
    boxed((2, 0), [Acquire @DEM B tiles]),
    boxed((2, 1), [Reproject]),
    boxed((2, 2), [Resample]),
    boxed((2, 3), [Aggregate]),
    boxed((2, 4), [Fill Gaps]),
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

=== Data Acquisition

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

== Water Mask Processing <sec:Water_mask_processing>

An expected limitation of the pipeline is retaining the errors introduced by water body interpolation. The solution to this problem is to exclude the subset of points which fall within the river area from the error analysis.

This mask could be identified using the classified point clouds. However, the re-extraction of a DEM from point clouds is out of the scope for this project. Therefore, we can only rely on the DEM data for segmentation. While river/lake masks do exist, they either offer provide global low resolution vector data @HydroATLAS, or low resolution raster data @unep_fee.

In order to create a high quality water mask, the UNEP @FEE mask was used as an input. The @FEE mask contains a value 1, 2, or 3 to describe the certainty of the underlying value being water --- corresponding to "no water", "seasonal water", and "permanent water" --- based on historical remote sensing data. The mask is filtered to only use values of 2 and 3. The mask is then transformed to a binary format.

However, the @FEE mask is not fine enough to be applied to the elevation map. Instead, we can use the @FEE mask as seed points in a region growing algorithm. Since rivers and waterbodies are known to be relatively flat, a low elevation difference threshold is set for the region growing, such that the elevation jump at the shore is registered as the boundary of the water body.

Each mask cell is transformed to the elevation map resolution, @CRS and grid. By applying this mask to the elevation map, it is essentially clipped to contain only heigh values that fall within the @FEE mask. Each cell in this clipped DTM is taken as a seed point for a region growing algorithm. These seed points are added to the region growing queue. Each entry has eight neighbors and for each the height difference with the seed is calculated. When these differences are smaller than the set threshold, the neighboring point is added to the end of the queue. The result is a breadth first search which incrementally classifies cells as a water body. The end result is a mask with region IDs, where cell values above 0 denote the existence of a water body. This process can be found as pseudo code in @alg-river-mask, which described the code which performs the operation in plain text.

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

== Cross-Border DTM Analysis <sec:border-analysis>

Once all harmonising steps are complete, the next step is to pairwise compare neighboring datasets and evaluate the results. This is first done by determining which regions share borders and have overlaping elevation products. This is followed by computing the elevation difference rasters, performing coregistration, and analysing statistical aspects of said difference such as correlation between error magnitude and slope, or the rate of @INSPIRE compliance.

To determine which @DTM:pla overlap one another, we first compute the bounding boxes of each @DTM and their overlap is checked in @eq:border-overlap.
#set math.equation(numbering: "(1)")

$
  & max(x_"region_1_min", x_"region_2_min") < min(x_"region_1_max", x_"region_2_max") \
  & quad and max(y_"region_1_min", y_"region_2_min") < min(y_"region_1_max", y_"region_2_max")
$ <eq:border-overlap>

This is not a perfect method as the bounding boxes may overlap even when the datasets do not. Therefore, another check is done by cropping the @DTM of one country with the other and checking if the cropped dataset is not empty. However, this is a computationally expensive operation and is thus only performed if an overlap between the bounding boxes is found.

The next step in the analysis process is to calculate the elevation differences between the @DTM pairs in the overlaping border regions. @GDAL allows for this process to be simplified to a subtraction operation. The resulting elevation difference rasters contain the cellwise elevation difference in the region, and constitute the core of the conducted analysis. They provide a first glance into how much disagreement there is between two regions' elevation products.

Based on this difference, we construct polygons to highlight errors greater than a set threshold. Nearby polygons are merged into one which allows to highlight potential areas with high concentration of disagreements rather than just count individual point samples.
We selected the threshold to match the ratio between resolution and vertical @RMSE --- at 5m, that threshold is 1.67m. This threshold is a little lower than Copernicus's 2m @LE90 benchmark. For the analysis, the number of cells where the error rate exceeds the threshold is also presented.

The spatial correlation of the elevation diffeernces is also analyzed. Overall, it is expected that Tobler's #cite(<Tobler1970>, form: "year") first law of geography will hold: the close errors will have a higher correlation than far-away ones.
It is further expected that stochastic errors are uncorrelated, and a high correlation of far away errors likely indicates a systematic error instead. However, the correlation does not account for error magnitude --- a small systematic error will result in a higher correlation rate than a large stochastic one.

Another way to evaluate systematic errors is through coregistration. This is a function in XDEM which performs an affine transform @tc-5-271-2011, which ensures best alignment of the @DTM:pla in $x$, $y$ and $z$ directions. The statistics (@RMSE, @LE90, mean error etc) are calculated for the border region before and after coregistration. A small affine transform with a high @RMSE would indicate stochastic errors.

Diagnostic plots are generated for each border pair: an elevation-difference histogram, an @RMSE versus slope plot using 5-degree slope bins, and a border-effect plot showing @RMSE in 50-meter distance bins. The slope plot examines the relationship between terrain slope and elevation differences, while the border-effect plot can help identify errors caused by extrapolation near dataset edges. The latter can also be sensitive to a single large error.

@INSPIRE suggests different relationships between horizontal resolution and vertical accuracy depending on slope angle. Accordingly, @fig:slope_ex illustrates the expected increase in @RMSE with slope. Deviations from this trend may indicate differences in ground filtering, sample locations on steep terrain, or temporal changes such as quarry excavation.

#figure(
  image("assets/slope_rmse_germany_nrw_germany_rlp.png", width:70%),
  caption:[Typical slope plot example]
)
<fig:slope_ex>

@fig:hist_ex shows an example of a typical elevation difference histogram. The vertical axis follows a logarithmic scale to be more informative. A typical distribution has a sharp peak near zero, with fewer observations at larger difference magnitudes. A mean shifted away from zero may suggest a systematic vertical offset, while secondary peaks may indicate artefacts such as extrapolation errors.

#figure(
  image("assets/histogram_germany_rlp_france.png", width:70%),
  caption:[Typical histogram example]
)
<fig:hist_ex>

Satellite imagery from Google Maps, ESRI World Imagery, Google Earth, or images @OSM can provide additional context for interpreting discrepancies. Historical imagery in Google Earth can also help identify changes over time.

=== Analysis outputs and interpretation

The generated analysis `.csv` file complements the spatial plots with summary statistics for the entire border region. The before and after describe the differences before and after coregistration. Since we will not transform our national @DTM:pls based on the affine transform, the before rows are more interesting. However, the after section does show the effect of vertical transform errors on the total difference. The subset refers to the cells with and without the interpolated values, which may be the same number if no interpolation was applied, both numbers already include the removed river mask. The mean and median describe the systematic errors of the border region, while the @STD, @RMSE, @MAE, and @NMAD describe the magnitude of the outliers (@tab:general_metrics). The minimum and maximum values indicate the greatest disagreements between the nations. Furthermore, the "`above threshold`" statistic describes the amount of cells that do not meet the resolution requirement from @sec:inspire-quality, while the "`percentage above threshold`" describes what the percentage of cells is compared the total amount of cells which do not comply (@tab:accuracy_metrics).

The remaining attributes are mainly used to determine the reliability of the comparison, and the effectiveness of the coregistration (@tab:coreg_metrics). The `mean sigma `$delta$`h` represents the average uncertainty associated with the elevation differences, while `n effective` reflects the number of independent observations after accounting for spatial correlation. The `mean `$sigma$`h/`$sigma$ metric describes the magnitude of the differences, relative to the expected random error. Furthermore, the `error correlation at 1 km` provides an indication of the spatial correlation of the errors, with larger values suggesting that neighbouring cells exhibit similar error behaviour. Finally, the estimated `shift x`, `shift y`, and `shift z` values quantify the horizontal and vertical corrections determined during coregistration and can help identify systematic offsets between neighbouring datasets. Small values of this shift indicate that the vertical and horizontal @CRS transformations already properly align the two @DTM:pls.

#let headerfill = rgb("e9eef3")
#let gridcolor = rgb("aab2bb")

#figure(
table(
  columns: 7,

  inset: 3pt,
  align: center + horizon,
  stroke: 0.5pt + gridcolor,

  fill: (x, y) => if y == 0 { headerfill },

  table.header(
    [*Stage*],
    [*Subset*],
    [*Valid cells*],
    [*Mean*],
    [*Median*],
    [*Std*],
    [*RMSE*],
  ),

  [Before], [All],      [11,282,135], [-0.0328], [-0.0324], [0.2574], [0.2595],
  [Before], [Measured], [11,282,135], [-0.0328], [-0.0324], [0.2574], [0.2595],

  [After],  [All],      [11,282,135], [-0.0042], [-0.0001], [0.2518], [0.2518],
  [After],  [Measured], [11,282,135], [-0.0042], [-0.0001], [0.2518], [0.2518],
),caption:[General metrics])
<tab:general_metrics>
#figure(
table(
  columns: 9,

  inset: 3pt,
  align: center + horizon,
  stroke: 0.5pt + gridcolor,

  fill: (x, y) => if y == 0 { headerfill },

  table.header(
    [*Stage*],
    [*Subset*],
    [*MAE*],
    [*NMAD*],
    [*LE90*],
    [*Min*],
    [*Max*],
    [*Above thr.*],
    [*% Above*],
  ),

  [Before], [All],      [0.1176], [0.1129], [0.2255], [-30.37], [34.54], [26,792], [0.237],
  [Before], [Measured], [0.1176], [0.1129], [0.2255], [-30.37], [34.54], [26,792], [0.237],

  [After],  [All],      [0.1057], [0.1054], [0.1928], [-30.15], [34.84], [26,976], [0.239],
  [After],  [Measured], [0.1057], [0.1054], [0.1928], [-30.15], [34.84], [26,976], [0.239],
), caption:[Accuracy and threshold metrics])
<tab:accuracy_metrics>
#figure(
  table(
  columns: 8,

  inset: 3pt,
  align: center + horizon,
  stroke: 0.5pt + gridcolor,

  fill: (x, y) => if y == 0 { headerfill },

  table.header(
    [*Stage*],
    [*Mean σΔh*],
    [*Nₑff*],
    [*Mean Δh/σ*],
    [*ρ₁km*],
    [*ΔX (m)*],
    [*ΔY (m)*],
    [*ΔZ (m)*],
  ),

  [Before], [0.1075], [4.567], [0.0503], [0.2353], [-],        [-],        [-],
  [After],  [0.1075], [4.567], [0.0503], [0.2353], [-0.0056], [0.2830], [-0.0286],
),
caption:[Coregistration metrics]
)
<tab:coreg_metrics>

== Visualizing the DTMs

Next to designing the pipeline and implementing analysis methods, an important aspect of this study was to decide on effective visualization methods and color schemes for the catchment-wide and analysis related @DTM:pls.

The catchment-wide @DTM product contains elevation values ranging from -325m to 4272m. The @DTM also contains various terrain types from the Netherlands' low variation in elevation to the Swiss Alps where elevation changes by several thousands of meters. This made visualizing the catchment-wide @DTM challenging, as with most color maps used, the Netherlands appeared completely dark while Switzerland became very bright and saturated, or vice versa. The `pride` color map resulted in a good balance between having an interpretable @DTM, including the extremes, and a visually striking product (@fig:cm_pride)(@cm_pride).

#figure(
  image("assets/cm_pride.png", width:50%),
  caption:[fusion gradient @cm_pride]
)
<fig:cm_pride>

The primary and most informative analysis tools are the elevation difference rasters obtained by subtracting two different @DTM:pls from each other after they have been projected onto the same grid. Various color gradients were tested to best evaluate the difference rasters. However, those provided by default in @QGIS:asf, were not satisfactory for both visualising and analysis purposes. Therefore, `fusion` was used as the primary gradient for elevation difference visuals (@fig:cm_fusion)(@cm_fusion). Using this gradient allows for the clear illustration of difference extremes.

#figure(
  image("assets/cm_fusion.png", width:50%),
  caption:[fusion gradient @cm_fusion]
)
<fig:cm_fusion>

In addition to the color gradients mentioned above, the Viridis and Spectral gradients were used in certain occasions, for example when discovering flight strip patterns or inspecting specific areas.
