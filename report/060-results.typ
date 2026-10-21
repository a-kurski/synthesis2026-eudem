#import "@preview/drafting:0.2.2"
= Results <chap:results>

This chapter discusses the results of the data scraping, the pipeline, analysis and our findings. The first section describes the challenges encountered while aquiring the data. Section 2 describes the results of the reprojection, resampling, regridding and interpolation. After, the analysis of the process is discussed, specifically analyzing the effect of various factors on the observed border errors. Lastly, any additional observations that do not fall within these categories will be discussed.
#drafting.inline-note(
"At current stage, only some intermediate results are available.")



== Data scraping
The data scraping is not considered a part of the processing pipeline. However, due to its relevance to the challenges of creating a @DEM of the Rhine catchment area, it has been included in this chapter. Currently, all data labeled as a must in @Moscow_Prioritization is implemented within the scraping software.

#drafting.inline-note("TODO: arda write about this section here")

== Pipeline <chap:Pipeline>
#drafting.inline-note("Go over the pipeline shortcomings in accordance with the subquestion")
harmonizing nodata -> reprojection -> regridding -> resampling -> interpolation (Netherlands)


...
The last step of the scraping process is interpolation. This step only applies to the Netherlands due to the absence of interpolated @DTM data. This applies to any cell where the ground was not found, including waterbodies, buildings, trees and any other ground obscuring features. Due to the resampling of the data, isolated nodata cells often already get removed. However, for larger areas such as rivers and buildings interpolation is still necessary.

For this process nearest inverse distance weighing is used. This does not catch all nodata values. In case it does not, nearest neighbor interpolation is used to supplement to fill the remaining holes. However, due to the range set for nearest neighbor, not all nodata cells are interpolated. Increasing the radius would likely solve this issue, but would also significantly increase processing time. Therefore, the interpolation limitations of the Netherlands have had to be excepted as a shortcoming of the pipeline, caused by the available data.

...

The river mask is limited by the quality of the course resolution of the SDG mask @SDG. It has trouble with small rivers as these are generally marked as values of 1 within the river mask, which are currently skipped in the interest of avoiding outliers.
== Analysis
#drafting.inline-note("Explain what we see in the comparisons")

#pagebreak()
=== Regions of Germany

==== NRW -- RLP

@NRW:l, and @RLP both fall within the extent of Germany. The overlapping border area is hilly with few waterbodies spread throughout the landscape. As with all Germany @DTM data, the tiles are aligned to the same tile grid, and overlap by one or two tiles.

Loading in the $italic("dh_germany_nrw_germany_rlp.tif")$ @DTM, representing the elevation differences, there are several interesting observations. @fig:NRW-RLP-striping shows North-South or South-North scanning tracks created by aerial @LiDAR scanning. The elevation jump in the order of $3 "cm"$, which while minimal, shows that some differences are caused by the misalignment of the scan passes within tiles.

#figure(
  image("assets/NRW-RLP-striping.png", width:40%),
  caption:"Striping artifact on the border difference DTM"
)
<fig:NRW-RLP-striping>

Secondly, there appears to be misalignment between tiles within the @DTM. This is illustrated in @fig:NRW-RLP-nonalignment as the sharp transition between the four tiles. This transition is is however more drastic at a difference of $30"cm"$ in the difference @DTM. On close inspection of the @NRW and @RLP @DTM:pls, it appears that cells on the edge between tiles, the jump between neighboring cell values increased with $40"cm"$ more on the @NRW @DTM, compared to the @RLP @DTM. However, it is possible this effect occurs on both the @NRW and @RLP @DTM:pls. To verify this hypothesis, we compared the point clouds to determine where this effect is introduced.
#drafting.inline-note("maybe pt would data would solve this.")

$italic("statistics_germany_nrw_germany_rlp.csv")$ confirms these findings. It lists the similarity of errors within one kilometer to be $99.9%$. High correlation which is consistent throughout the correlation graph either points towards a tiling or vertical transform artifact. Since the median difference between the two tiles is $-2"cm"$, which also corresponds with the z-shift for the coregistration. Therefore, it can be concluded most errors within the border comparison are caused by this tiling artifact.

#figure(
  image("assets/NRW-RLP-nonalignment.png",width:40%),
  caption:"Tile vertical misalignment artifact on the border difference DTM"
)
<fig:NRW-RLP-nonalignment>

Lastly, as described in @chap:Pipeline, small water bodies such as narrow rivers, or small lakes are not filtered out and are therefore counted towards the differences in the comparison. This is however, a small contribution and does not appear disproportionally represented in the calculated problem areas.

There do appear to be several differences which are likely related to @LiDAR sensing limitations or subsequent processing steps. Examples include interpolation errors for buildings (@fig:NRW-RLP-roofinter), ground filtering discrepancies (@fig:NRW-RLP-overpass), temporal changes (@fig:NRW-RLP-quarry)(verified using Google Earth), and steep slopes (@fig:NRW-RLP-slope).

Nevertheless, the overall alignment of the @NRW and @RLP @DTM:pls does comply with the @INSPIRE target described in @sec:inspire-quality. Furthermore, only $0.05%$ of points within the overlap fall outside of the @INSPIRE derived threshold described in @sec:border-analysis. Therefore, the quality of the resulting @DTM does comply with the guidelines we have followed for the full Rhine @DTM.

#figure(
  grid(
    columns: 4,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-roofinterESRI.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/NRW-RLP-roofinterNRW.png", width: 100%)
      #align(center)[(NRW)]
    ],

    [
      #image("assets/NRW-RLP-roofinterRLP.png", width: 100%)
      #align(center)[(RLP)]
    ],

    [
      #image("assets/NRW-RLP-roofinter.png", width: 100%)
      #align(center)[(DH)]
    ]
  ),
  caption: "Roof interpolation example",
)
<fig:NRW-RLP-roofinter>

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-overpass.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/NRW-RLP-overpassNRW.png", width: 100%)
      #align(center)[(NRW)]
    ],

    [
      #image("assets/NRW-RLP-overpassRLP.png", width: 100%)
      #align(center)[(RLP)]
    ],
  ),
  caption: "Overpass example",
)
<fig:NRW-RLP-overpass>

#figure(
  grid(
    columns: 4,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-quarry.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/NRW-RLP-quarryNRW.png", width: 100%)
      #align(center)[(NRW)]
    ],

    [
      #image("assets/NRW-RLP-quarryRLP.png", width: 100%)
      #align(center)[(RLP)]
    ],

    [
      #image("assets/NRW-RLP-quarryDH.png", width: 100%)
      #align(center)[(DH)]
    ]
  ),
  caption: "Quarry example",
)
<fig:NRW-RLP-quarry>

#figure(
  image("assets/slope_rmse_germany_nrw_germany_rlp.png",width:60%),
  caption:"Slope effect on the RMSE of the difference"
)
<fig:NRW-RLP-slope>

#pagebreak()
==== Hessen - BW

The border between Hessen and @BW one of the shorter borders, coming in at roughly $33"km"$. It does however contain some interesting elements such as an exclave of Hessen inside of @BW. This exclave does however not appear to contain any notable differences. Furthermore, the elevations in this region range from $90$ meters in the large and relatively flat valley, to nearly $550$ meters in the hills (@fig:Hessen-BW-overview).

#figure(
  image("assets/Hessen-BW-overview.png",width:40%),
  caption:"Hessen-BW border"
)
<fig:Hessen-BW-overview>

The first obvious difference is a bright highlight at the border of the @DTM (@fig:Hessen-BW-BorderArtifact). The effect. This artifact is a byproduct of the @BW dataset being cut differently compared to the Hessen dataset. Therefore, this difference is an artifact caused by the clipped dataset and not a real physical difference. This effect occurs on all difference analysis @DTM:pls, though it is not always as pronounced as within this comparison.

#figure(
  image("assets/Hessen-BW-BorderArtifact.png",width:40%),
  caption:"Hessen-BW border artifact"
)
<fig:Hessen-BW-BorderArtifact>

A secondary source of differences appears to be the narrow clearings within wooded areas (@fig:Hessen-BW-clearing). This occurs in several locations. It is unclear exactly why this happens. The uncertainty @DTM representing random error. It shows a very constant, yet small error of around $3"cm"$. This implies that the observed error is not simply consisting of noise. Observing the @BW @DTM, we see a steep drop in elevation. Streetview furthermore confirms that it is indeed a cliff face. The elevation difference is likely caused by ground filtering or different flight paths during @LiDAR scanning.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Hessen-BW-clearingESRI.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/Hessen-BW-clearingDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Forest clearing",
)
<fig:Hessen-BW-clearing>

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Hessen-BW-clearingUC.png", width: 100%)
      #align(center)[(Uncertainty)]
    ],

    [
      #image("assets/Hessen-BW-clearingSV.png", width: 100%)
      #align(center)[(Google Street View (49.4762, 8.4208))]
    ],
  ),
  caption: "Forest clearing cause",
)
<fig:Hessen-BW-clearingEx>

Further artifacts include common elements throughout the catchment @DTM. These include building interpolation differences, quarries/construction sites, and lakes/rivers not caught by the river mask. These errors are expected and can likely only be fixed through the reextraction of the @DTM, by using both the Hessen and @BW point clouds. Nevertheless, the Hessen-@BW border falls well within the @INSPIRE threshold, with only 0.06% of points being non-compliant. The alignment of the two @DTM:pls also appears to be accurate, with the coregistration recommending a vertical transform of only $1" cm"$ in vertical direction for the best possible alignment.

#pagebreak()
==== NRW -- Hessen

Only 59 kilometres of @NRW -- Hessen border and 127 1km#sym.times\1km tiles fall into the study area.
Due to the shape of the catchment area, the border is split in two --- a longer section in the South and a shorter, approx. 3-kilometre section in the North.
Notably, @NRW openly publishes point cloud data which enables further analysis, whereas Hessen does not.

The errors in this region are relatively low: @RMSE is 18cm, @LE90 is 7.5cm, and only 0.07% of cells exceed the 1.67m difference threshold, suggesting a high agreement between the @DTM:pla.
Still, the biggest differences are -9m and 22m in the negative and positive direction respectively.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-quarry-satellite.png")],
    [#image("assets/nrw-hessen-quarry.png")],
    [#image("assets/nrw-hessen-roadworks-satellite.png")],
    [#image("assets/nrw-hessen-roadworks.png")]
  ),
  caption: [Areas on the Hessen--NRW border with high temporal differences]
)<fig:nrw-hessen-temporal>

Most of the errors which exceed threshold are best explained by the temporal differences in the datasets.
There are two large quarries in the overlapping region, and the earthworks at both sites contribute to the largest errors.
Additionally, there are several places where judging by the historical Google Earth imagery, the error is likely to be due to new or ongoing construction, such as the bridge near the Haiger service station.
Additionally at the time of acquisition, there was snow on the ground in Willingen ski resort which was classified as ground by @NRW (@fig:nrw-hessen-snow, snow shown in yellow).

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-snow-satellite.png")],
    [#image("assets/nrw-hessen-snow.png")],
    [#image("assets/nrw-hessen-snow.jpeg", width: 85%)]
  ),
  caption: [Effects of snow on the ground in NRW]
)<fig:nrw-hessen-snow>

There are several smaller issues which we believe are best attributed to the differences in processing. The built-up areas display a high number of scattered differences around 0.5m which are likely caused by either the states' approach to ground filtering or interpolation algorithms used to create the original @DTM:pla.
An interesting artefact is a 0.6m-tall "mound" between Wallau and Bad Laasphe.
@NRW appears to be using @CSF and extract the heights of synthetic cloth points instead of interpolating authentic ground points --- we believe the mound is most likely caused by the "sagging" of the simulated cloth (see @fig:nrw-hessen-ground, simulated cloth in yellow), which we verify by examining the point clouds.

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-buildings-satellite.png")],
    [#image("assets/nrw-hessen-buildings.png")],
    [#image("assets/nrw-hessen-warehouse.jpeg")]
  ),
  caption: [Ground and building filtering differences between NRW and Hessen]
)<fig:nrw-hessen-ground>
==== Hessen -- Bavaria

The statistics of the errors along Hessen--Bavaria border are similar to those of Hessen--NRW border, but their sources appear to be somewhat different.
Between Hessen and Bavaria, @RMSE is 0.18m and the @LE90 is 0.10m; the minimum and the maximum errors are -18.35m and 19.07m respectively.

The highest absolute errors can all be traced to temporal changes, specifically the excavation taking place at a single quarry outside Ringheim.
There are additionally some construction works taking place along the border, but there, the magnitude of the errors there is lower.

#drafting.inline-note()[TODO: Quarry]

More noteworthy are the small (typically around 0.3--0.5m) differences in rural, especially forested, areas.
These are areas of difference which appear to correspond to linear features in the landscape such as roads, streams, or edges between a forest and an open field.
We believe these are likely an effect of ground and/or vegetation filtering used by one of the data providers; without access to point cloud data it is impossible to infer more detailed differences.

#drafting.inline-note()[TODO: Forest]

Another detail evident from the comparison is the difference in approach to estimating the elevation of the water surface.
Hessen appears to be relying on the data about the water surface obtained from the point cloud --- the surface does not appear to be perfectly smooth and seems to contain small artefacts.
Bavaria instead uses Delaunay triangulation, seemingly based on the lowest point along the coastline of the water body.

#drafting.inline-note()[TODO: Water]

==== BW -- Bavaria
The @BW -- Bavaria border to the @NRW -- Hessen border, as it is split in two sections due to the catchment area shape. For this region Bavaria provides point cloud data, whereas @BW does not. This means that point cloud comparisons will not be possible for this border region.

#figure(
  image("assets/BW-Bavaria-Border.png",width:40%),
  caption:"BW – Bavaria border"
)
<fig:BW-Bavaria-Border>

The border area appears to display two main artifacts. The first of these being a pronounced difference @DTM edge (@fig:BW_Bavaria_BorderArtifact). However, this effect only appears at the southern border, and appears abscent from the northern border. The cause of this artifact is that the @BW @DTM appears to have two nodata values. The metadata states that the nodata value is at $-9999$, while the value in the black area is 0 before the vertical transform. The code currently corrects for this artifact. However, the border edge still has traces of this effect due to the rotation applied during the horizontal transform, and the interpolation that occurs at that stage. These errors make up almost 25% of all designated problem areas. @fig:BW-Bavaria-BorderArtifact-Histo illustrates the effect this has on the total error distribution for the border comparison. Nearly all values below $-5$ meters can be attributed to this effect.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/BW-Bavaria-BorderArtifactBW.png", width: 100%)
      #align(center)[(BW)]
    ],

    [
      #image("assets/BW-Bavaria-BorderArtifactDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Border artifact",
)
<fig:BW_Bavaria_BorderArtifact>

#figure(
  image("assets/histogram_germany_bw_germany_bavaria.png",width:60%),
  caption:"BW – Bavaria border"
)
<fig:BW-Bavaria-BorderArtifact-Histo>

The second artifact within this border comparison is similar to the one encountered in @NRW -- @RLP section. In this instance, the effect clearly occurs in the Bavaria @DTM. @fig:BW-Bavaria-Discrete shows this effect. It appears as if these specific tiles are seperate from the the rest of the @DTM as it contains both positive and negative differences, meaning it cannot be the result of a vertical shift. Zooming in on the border confirms that these different tiles exist in the Bavaria, shown by the faint line at the same line as the DH @DTM. The cause for this can be that the tiles have either been collected at a different time, or that the aquisition was done through another method. This can be confirmed using the Bavaria point cloud...

#drafting.inline-note("Look at the bavaria point cloud to see what the difference in aquisition time is between those tiles")

#figure(
  image("assets/BW-Bavaria-DiscreteDH.png",width:60%),
  caption:"Discrete tile step"
)
<fig:BW-Bavaria-Discrete>

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/BW-Bavaria-Discrete-zoomDH.png", width: 100%)
      #align(center)[(DH)]
    ],

    [
      #image("assets/BW-Bavaria-Discrete-zoomBavaria.png", width: 100%)
      #align(center)[(Bavaria)]
    ],

    [
      #image("assets/BW-Bavaria-Discrete-zoomBW.png", width: 100%)
      #align(center)[(BW)]
    ],
  ),
  caption: "Discrete tile step zoomed",
)
<fig:BW_Bavaria_DiscreteZoom>

Several other errors exist within the border comparison. These are in line with the errors encountered at other borders. These include interpolation errors, differences in ground filtering (differences in overpass handling), temporal changes (mostly due to quarries or construction areas), differnces due to watermask shortcomings (including small pools, small lakes, creaks), steep slopes

For this border comparison, the @INSPIRE target is not met. The amount of points above the threshold is only $0.14%$. However, the total @RMSE is a factor $3.2$ greater than what it is allowed to be for the $5$ meter resolution. These results are not acceptable for the final map. However, due to the errors being identified as primarily the edges

#pagebreak()

=== Luxembourg - Germany - France

=== Switzerland - Germany - France

=== Germany - France

=== Germany - Netherlands

== Observations


// Raster data for certain regions --- currently, the Netherlands and Germany's Nordrhein-Westfalen --- has been successfully downloaded within a given mask. The data has been processed as described in @chap:method; the resulting raster can be seen below.

// #figure(
//   image("assets/dtm_border_zoomedout.png", width: 80%),
//   caption: [Visualization of Dutch and German DTMs of the Border Region.]
// )<fig:dtm_border>

// Fig @fig:dtm_border shows the DTMs from the two sources, the AHN and the NRW. The Dutch region can be recognized by the presence of white holes and a non-interpolated river. Although hole filling was done for the AHN, large holes still remain and the river bed remains unfilled. This is due to the finite distance used in the inverse distance-weighing interpolation.

// #figure(
//   image("assets/dtm_border.png", width: 80%),
//   caption: [Zoomed-in Visualization of DTMs.]
// )<fig:dtm_zoomin>

// Fig @fig:dtm_zoomin depicts a closer look at the border region. The background is also left blank to see the unfilled areas clearly. Further implementations will have all holes interpolated so that the elevation product is unified.

// Point cloud harmonisation has been tested on approximately 20km stretch of the German-Dutch border. Analysing the translation of the resulting 63 intersection shows the following:
// - the root median square translation is 277.3 m horizontally and 1.2233 m vertically;
// - the highest absolute translation is 1912.6 m horizontally and  5.5389 m vertically;
// - the lowest absolute translation is 0 m both horizontally and vertically for one of the intersections.
// - the median absolute translation is 0.1825 m horizontally  0.0691 m vertically.

// There are several outliers --- pairs where a point cloud is translated several hundred meters horizontally --- which are likely the cases where the footprints the actual data is non-intersecting but the bounding boxes are. Filtering for such outliers is necessary and #highlight(fill: none, stroke: red)[will be implemented]. A visual analysis of one of the intersecting tiles shows that even without the transformation applied, the two point clouds are closely aligned, further confirming that large translations are likely erroneous.

// #figure(
//   image("assets/pcs-aligned.png", width: 60%),
//   caption: [Default alignment of a Dutch (red) and German (blue) point cloud]
// )

// #drafting.inline-note()[The chapter is not done yet since we do not have the final results of the pipeline or a way to evaluate the quality. The chapter will also contain more results regarding the downloading and processing of the raster and point cloud data. This means there will be more images, tables and other visuals to illustrate both the results and the quality of those results.]
