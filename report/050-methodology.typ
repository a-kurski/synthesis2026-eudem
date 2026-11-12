#import "@preview/unify:0.8.1": qty
#import "@preview/lovelace:0.3.0": *
#import "@preview/drafting:0.2.2"
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

= Methodology <chap:method>

This chapter describes the methodology used in the DTM harmonisation pipeline. It provides both a general overview and specifics of our approach to processing heterogeneous elevation data and subsequent analysis of the results.
It additionally covers water mask generation alongside the visualisation and comparison methods employed.

== Pipeline Overview

Within this project, we create a fully automated pipeline for processing and harmonising heterogeneous gridded elevation data.
Raster processing has been chosen as the focus of the project as re-extracting a @DTM from scratch is computationally expensive and is deemed unnecessary: as shown in @chap:results, most national @DTM:pla are sufficiently accurate to allow near-seamless integration.
The pipeline can currently handle data from 6 countries within the Rhine catchment area and is expected to support similar data from other providers.
Point cloud processing has been excluded from the pipeline due to the limited time of the project and limited availability of the data; where available, point clouds are used for additional evaluation of the gridded @DTM.


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
  caption: [Flowchart of the processing steps of the pipeline.]
)

The pipeline is split into two stages: processing and comparison~--- the above flowchart only shows the processing stage; comparison is described in @sec:border-analysis.
Both stages take a `.json` file as input and write the intermediate and final results to it.
The comparison stage reads and evaluates data completed during processing.
The user is not expected to interact or pass arguments directly to the pipeline~--- instead, they fill in the `.json` with input data.

The global settings influence both the final product and the performance of the pipeline.
The key raster settings include the target @CRS and resolution, region extent, interpolation settings, and path where the output raster should be written to.
The performance settings govern the maximum number of threads which can be used for processing or the number of regions which can be processed at once.

The region settings include the path to vector and raw raster data, information about regions @CRS and @VCRS in case they are not specified within metadata, and whether interpolation is needed~--- currently, only Dutch @DTM needs interpolation.
Additionally, a water mask is passed for the river detection part of the algorithm.

For the comparison stage, the settings include the threshold for flagging errors and the path to region's river or interpolation masks.

Full breakdown of all settings can be found in @sec:PipelineREADME.

=== Data Acquisition <sec:acquisition>

Data acquisition is a crucial step which enables the rest of the workflow despite technically being outside of the fully automated part of the pipeline.
Data discovery was performed primarily based on @vanderheide2026pointcloud supported by additional online searches.

We find that national and regional data providers offer different download options: the Netherlands and @DE-NW offer a @WCS server for access/download; @DE-BY and France offer tiled raster data in a binary (`.xyz` and `.asc` respectively) format; Luxembourg offers a single untiled @COG; the remaining datasets are available as GeoTIFF (`.tif`) tiles from a catalogue or a download portal.
Some providers (@DE-HE, France) bundle the tiles into zip archives by administrative subdivision.

The downloads are handled automatically but each region essentially requires a bespoke solution due to the differences in the data portals and the catalogues.

For each region, the data is queried within a specified @AOI (here understood as the intersection of the region's extent and the Rhine catchment area); where possible, the tiles are downloaded in parallel; where necessary, the downloaded tiles are recursively unzipped.
The downloaded data is then validated and checked against a catalogue.

=== Reprojection & Resampling

This is the first step in the raster processing pipeline.

First, all regions without a processed @DEM are listed and a queue is built from largest (processed first) to smallest (processed last) region.
The regions can be processed in parallel and this order helps avoid situations when one process is performing the reprojection while the remaining processes are sitting idle.

For each region, all tiles are first aggregated into a virtual mosaic (`.vrt`).
Each tile is assigned the region's @CRS as specified in the `.json` file~--- this behaviour is necessary as parts of regional datasets (most notably subdivisions of @DE-HE and @DE-RP) have their @CRS either missing or incorrectly specified within the tile's metadata; and is placed into the mosaic according to that @CRS.
No region has been found to have a mixed @CRS; we note, however, that this approach may cause issues if that is the case.

Similarly, for certain regions, a `NoData` value needs to be specified.
Parts of @DE-BW and @DE-HE, again, record `NoData` as 0 but do not state this in metadata, which warrants forcing a `NoData` value.

The output grid is established based on the resolution supplied in the `.json`.
The grid is identical for all regions.
For the product described in this report, the grid is in EPSG:3035 and at #qty("5", "m") resolution; the vertical @CRS is EVRF2007 (EPSG:5621) as the PROJ library does not yet natively support transformation to EVRF2019.

Then, the rasters are warped (using `gdalwarp`) to the common grid.
At this step, the data is transformed from the source @CRS to target @CRS both horizontally and vertically.
After that, the data is resampled to the target grid.
By default, the chosen resampling method is averaging all the valid (i.e. not `NoData`) sample points located in the given grid cell, but bilinear interpolation is also possible.
// A brief comparison of interpolation methods is included in @chap:results.

The resampled raster is written to file, without cropping, with a `NoData` value of -9999.

=== Filling Gaps

If specified by a region's setting in the `.json`, gap filling is applied after resampling using @IDW interpolation with a specified maximum search distance and no smoothing.
This order targets gaps remaining in the final-resolution surface and preserves all already valid target elevations.
Valid surrounding terrain may supply interpolation donors outside the @AOI.
Alongside the interpolated surface, a binary interpolation mask are written to file to distinguish unchanged cells from interpolated cells.

=== Resolving Conflicts and Assembling the Output

At this step, we need to decide which data to write to the output @DEM where @DEM:pla of several regions overlap.
Several approaches were considered, such as evaluating for best temporal match or data quality.
The former is not guaranteed by raster metadata~--- referring to the GPS time of the corresponding point cloud was considered but ruled out due to storage requirements~--- and the latter is difficult to infer from raster elevation data alone.
Instead, we simply write each region's data within its boundaries (as determined by a vector file of that region).

However for regions where interpolation was performed during our processing, we decide to overwrite the interpolated grid cells with non-interpolated data from the neighbouring region if that data is available.
If the agreement between regions is high (like it is in our case, see @chap:results) this approach produces fewer and smaller artefacts than accepting interpolation results.

The resulting elevation data is written to an output GeoTIFF, cropped to the specified region extents.

== Water Mask Processing <sec:Water_mask_processing>

An expected behaviour of the pipeline is retaining the errors introduced by water body interpolation by different providers which significantly impacts the error rate when comparing the datasets. The solution to this problem is to exclude the subset of points which fall within the river area from the error analysis.

This mask could be identified using the classified point clouds. However, the re-extraction of a DEM from point clouds is out of the scope for this project. Therefore, we only rely on the DEM data for segmentation. While river/lake masks do exist, they either offer provide global low resolution vector data @HydroATLAS, or low resolution raster data @unep_fee.

In order to create a high quality water mask, the @FEE mask was used as an input. The @FEE mask contains a value 1, 2, or 3 to describe the certainty of the underlying value being water~--- corresponding to "no water", "seasonal water", and "permanent water" respectively~--- based on historical remote sensing data.

However, the @FEE mask is not fine enough to be applied to the elevation map. Instead, we can use the @FEE mask's values of 2 and 3 as seed points in a region growing algorithm. Since rivers and water bodies are known to be relatively flat, we perform region growing detecting neighbourhoods with small changes in elevation.

The mask is transformed to the elevation map resolution, @CRS and grid. Each grid point with value 2 or 3 raster is taken as a seed for a region growing algorithm. These seed points are added to the region growing queue. Each entry has eight neighbours and for each, the height difference with the given cell is calculated. When these differences are smaller than the set threshold~--- empirically, it was found that a #qty("0.02", "m") threshold works best~--- the neighbouring point is added to the end of the queue. The result is a breadth first search which incrementally classifies cells as a water body. The end result is a mask with region IDs, where cell values above 0 denote the existence of a water body. A pseudo-code description of the water masking is found in @alg-river-mask.

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

== DEM Analysis <sec:border-analysis>

Once all harmonisation steps are complete, the next step is to pairwise compare neighbouring datasets and evaluate the results. This is first done by determining which regions share borders and have overlapping elevation products. This is followed by computing the elevation difference rasters, performing co-registration, and analysing statistical aspects of said difference such as correlation between error magnitude and slope, or the rate of @INSPIRE compliance.

To determine which @DTM:pla overlap one another, we first compute the bounding boxes of each @DTM and check if they overlap:\
$max(x_(A min), x_(B min)) < min(x_(A max), x_(B max)) and max(y_(A min), y_(B min)) < min(y_(A max), y_(B max))$, where $A, B$ denote two regions.

However, the bounding boxes may overlap even when the datasets do not. Therefore, another check is done by cropping the @DTM of one country with the other and checking if the cropped dataset is not empty. This is a computationally expensive operation and is thus only performed if an overlap between the bounding boxes is found.

The next step in the analysis process is to calculate the elevation differences between the @DTM pairs in the overlapping border regions by subtracting the @DTM rasters.
The resulting elevation difference rasters contain the cell-wise elevation difference in the region, and constitute the core of the conducted qualitative analysis.
Qualitative analysis is also supported by satellite imagery or @OSM vector maps.

Based on this difference, we construct polygons to highlight errors greater than a set threshold. Nearby polygons are merged into one which allows highlighting potential areas with high concentration of disagreements rather than relying on a count of cells in excess of the threshold.
We selected the threshold to match the minimum ratio between resolution and vertical @RMSE~--- at #qty("5", "m"), that threshold is #qty("1.67", "m"). This threshold is a little lower than Copernicus's #qty("2", "m") @LE90 benchmark. For the analysis, the number of cells where the error rate exceeds the threshold is also presented.

The spatial correlation of the elevation differences is also analysed. Overall, it is expected that Tobler's (#cite(<Tobler1970>, form: "year")) first law of geography will hold: the close-by errors will have a higher correlation than far-away ones.
It is further expected that stochastic errors are uncorrelated, and a high correlation of far away errors likely indicates a systematic error instead. However, the correlation does not account for error magnitude~--- a small systematic error will result in a higher correlation rate than a large stochastic one.

Another way to evaluate systematic errors is through coregistration. This is a function in XDEM which performs an affine transform @tc-5-271-2011, which ensures best alignment of the @DTM:pla in $x$, $y$ and $z$ directions. The statistics (@RMSE, @LE90, mean error etc) are calculated for the border region before and after coregistration. A small affine transform with a high @RMSE would indicate stochastic errors.

Several diagnostic plots are generated for each border pair: an elevation-difference histogram, an @RMSE versus slope plot using 5-degree slope bins, and a border-effect plot showing @RMSE in 50-metre distance bins. The slope plot examines the relationship between terrain slope and elevation differences, while the border-effect plot can help identify errors caused by extrapolation near dataset edges. The latter can also be sensitive to a single large error.

@INSPIRE suggests different target ratios between horizontal resolution and vertical accuracy depending on slope angle: 3–20 for flat terrains and 3–10 for steep terrain. To evaluate the implied increase in error rate, we produce a plot showing the relationship between the slope angle and the error rate.

We also plot a histogram of errors, set to logarithmic scale to better highlight the less prevalent errors too. We expect the errors to largely follow a normal distribution with a mean at 0.
A mean shifted away from zero may suggest a systematic vertical offset, while secondary peaks may indicate artefacts such as extrapolation errors.

=== Analysis outputs and interpretation

The generated `.csv` file with statistics complements the spatial plots with summary statistics for the entire border region. The "before" and "after" describe the differences before and after co-registration. Since we do not apply the affine transform to national @DTM:pls, the "before" rows are more informative. However, the after section does show the effect of vertical transform errors on the total difference. The "subset" refers to the cells with and without the values interpolated by us, which may be the same number if no interpolation was applied; both figures already include the removed river mask. The "mean" and "median" help describe the systematic errors of the border region, while the @STD, @RMSE, @MAE, and @NMAD describe the magnitude of the outliers (@tab:general_metrics). The minimum and maximum values indicate the greatest disagreements between the datasets. Furthermore, the "above threshold" shows the amount of cells that do not meet the error threshold, while the "percentage above threshold" describes what percentage of cells that accounts for (@tab:accuracy_metrics).

The remaining attributes are mainly he to determine the reliability of the comparison, and the effectiveness of the coregistration (@tab:coreg_metrics). The "mean $sigma Delta$ h" represents the average uncertainty associated with the elevation differences, while $N_("eff")$ reflects the number of independent observations after accounting for spatial correlation. The "mean $Delta h$/$sigma$" metric describes the magnitude of the differences, relative to the expected random error. Furthermore, the $rho_(1 "km") $ provides an indication of the spatial correlation of the errors at #qty("1", "km") distance, with larger values suggesting that cells exhibit similar error behaviour. Finally, the estimated $Delta X$, $Delta Y$, and $Delta Z$ values quantify the horizontal and vertical corrections determined during coregistration and can help identify systematic offsets between neighbouring datasets. Small values of this shift indicate that the vertical and horizontal @CRS transformations already properly align the two @DTM:pls.

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
),caption:[Example of general metrics for FR/DE-RP border.])
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
), caption:[Example accuracy and threshold metrics for FR/DE-RP border.])
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
    [*N#sub[eff]*],
    [*Mean Δh/σ*],
    [*$rho_(1 "km")$*],
    [*ΔX (m)*],
    [*ΔY (m)*],
    [*ΔZ (m)*],
  ),

  [Before], [0.1075], [4.567], [0.0503], [0.2353], [-],        [-],        [-],
  [After],  [0.1075], [4.567], [0.0503], [0.2353], [-0.0056], [0.2830], [-0.0286],
),
caption:[Example coregistration metrics for FR/DE-RP border.]
)
<tab:coreg_metrics>

We find that of these metrics, mean, median, RMSE, NMAD, and LE90 best inform the analysis, and the rest are primarily used for context.

== Visualising the DTMs

Next to designing the pipeline and implementing analysis methods, an important aspect of this study was to decide on effective visualisation methods and colour schemes for the catchment-wide and analysis related @DTM:pls.

The catchment-wide @DTM product contains elevation values ranging from #qty("-325", "m") to #qty("4272", "m"). The @DTM also contains various terrain types from the Netherlands' low variation in elevation to the Swiss Alps where elevation changes by several thousands of metres. This made visualising the catchment-wide @DTM challenging, as with most colour maps used, the Netherlands appeared completely dark while Switzerland became very bright and saturated, or vice versa. The Pride @cm_pride colour map resulted in a good balance between having an interpretable @DTM, also at the extremes of the range, and a visually striking product (@fig:cm_pride).

#figure(
  image("assets/cm_pride.png", width:50%),
  caption:[Pride gradient. From #cite(<cm_pride>, form: "prose").]
)
<fig:cm_pride>

The primary and most informative analysis tools are the elevation difference rasters obtained by subtracting two different @DTM:pls from each other after they have been projected onto the same grid. Various colour gradients were tested to best evaluate the difference rasters. However, those provided by default in QGIS were not satisfactory for both visualisation and analysis purposes. Therefore, Fusion @cm_fusion was used as the primary gradient for elevation difference visuals (@fig:cm_fusion) as it is divergent and perceptually uniform. Using this gradient allows for the clear illustration of difference extremes.
For the purposes of analysis, the colour range is set such that it is symmetrical around 0, e.g. [-8, 8]. The exact magnitude differs for different border pairs as some have higher error magnitudes than others.

#figure(
  image("assets/cm_fusion.png", width:50%),
  caption:[Fusion gradient. From #cite(<cm_fusion>, form: "prose").]
)
<fig:cm_fusion>

In addition to the gradients mentioned above, the Viridis and Spectral gradients were used in certain occasions, for example when discovering flight strip patterns or inspecting specific areas.
