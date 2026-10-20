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

==== NRW - RLP

@NRW:l, and @RLP both fall within the extent of Germany. The overlapping border area is hilly with few waterbodies spread throughout the landscape. As with all Germany @DTM data, the tiles are aligned to the same tile grid, and overlap by one or two tiles.

Loading in the $italic("dh_germany_nrw_germany_rlp.tif")$ @DTM, representing the elevation differences, there are several interesting observations. @fig:NRW-RLP-striping shows North-South or South-North scanning tracks created by aerial @LiDAR scanning. The elevation jump in the order of $3 "cm"$, which while minimal, shows that some differences are caused by the misalignment of the scan passes within tiles. 

#figure(
  image("/report/assets/NRW-RLP-striping.png", width:40%),
  caption:"Striping artifact on the border difference DTM"
)
<fig:NRW-RLP-striping>

Secondly, there appears to be misalignment between tiles within the @DTM. This is illustrated in @fig:NRW-RLP-nonalignment as the sharp transition between the four tiles. This transition is is however more drastic at a difference of $30"cm"$ in the difference @DTM. On close inspection of the @NRW and @RLP @DTM:pls, it appears that cells on the edge between tiles, the jump between neighboring cell values increased with $40"cm"$ more on the @NRW @DTM, compared to the @RLP @DTM. However, it is possible this effect occurs on both the @NRW and @RLP @DTM:pls. To evaluate this we would require the uncut tiles within the @DTM of a region and perform coregistration to determine the vertical tile shift. Unfortunately, we do not have access to this data.
#drafting.inline-note("maybe pt cloud data would solve this.")

$italic("statistics_germany_nrw_germany_rlp.csv")$ confirms these findings. It lists the similarity of errors within one kilometer to be $99.9%$. High correlation which is consistent throughout the correlation graph either points towards a tiling or vertical transform artifact. Since the median difference between the two tiles is $-2"cm"$, which also corresponds with the z-shift for the coregistration. Therefore, it can be concluded most errors within the border comparison are caused by this tiling artifact.

#figure(
  image("/report/assets/NRW-RLP-nonalignment.png",width:40%),
  caption:"Tile vertical misalignment artifact on the border difference DTM"
)
<fig:NRW-RLP-nonalignment>

Lastly, as described in @chap:Pipeline, small waterbodies such as narrow rivers, or small lakes are not filtered out and are therefore counted towards the differences in the comparison. This is however, a small contribution and does not appear disproportianally represented in the calculated problem areas.

There do appear to be several differences which are likely related to @LiDAR sensing limitations or subsequent processing steps. Examples include interpolation errors for buildings (@fig:NRW-RLP-roofinter), ground filtering discrepancies (@fig:NRW-RLP-overpass), temporal changes (@fig:NRW-RLP-quarry)(verified using Google Earth), and steep slopes (@fig:NRW-RLP-slope).

Nevertheless, the overall alignment of the @NRW and @RLP @DTM:pls does comply with the @INSPIRE target described in @sec:inspire-quality. Furthermore, only $0.05%$ of points within the overlap fall outside of the @INSPIRE derived threshold described in @sec:border-analysis. Therefore, the quality of the resulting @DTM does comply with the guidelines we have followed for the full Rhine @DTM.

#figure(
  grid(
    columns: 4,
    gutter: 5pt,

    [
      #image("/report/assets/NRW-RLP-roofinterESRI.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("/report/assets/NRW-RLP-roofinterNRW.png", width: 100%)
      #align(center)[(NRW)]
    ],

    [
      #image("/report/assets/NRW-RLP-roofinterRLP.png", width: 100%)
      #align(center)[(RLP)]
    ],

    [
      #image("/report/assets/NRW-RLP-roofinter.png", width: 100%)
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
      #image("/report/assets/NRW-RLP-overpass.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("/report/assets/NRW-RLP-overpassNRW.png", width: 100%)
      #align(center)[(NRW)]
    ],

    [
      #image("/report/assets/NRW-RLP-overpassRLP.png", width: 100%)
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
      #image("/report/assets/NRW-RLP-quarry.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("/report/assets/NRW-RLP-quarryNRW.png", width: 100%)
      #align(center)[(NRW)]
    ],

    [
      #image("/report/assets/NRW-RLP-quarryRLP.png", width: 100%)
      #align(center)[(RLP)]
    ],

    [
      #image("/report/assets/NRW-RLP-quarryDH.png", width: 100%)
      #align(center)[(DH)]
    ]
  ),
  caption: "Quarry example",
)
<fig:NRW-RLP-quarry>

#figure(
  image("/report/assets/slope_rmse_germany_nrw_germany_rlp.png",width:60%),
  caption:"Slope effect on the RMSE of the difference"
)
<fig:NRW-RLP-slope>

==== 

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
