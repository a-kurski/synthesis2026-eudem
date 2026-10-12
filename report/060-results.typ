#import "@preview/drafting:0.2.2"
= Results <chap:results>

This chapter discusses the results of the data scraping, the pipeline, analysis and our findings. The first section describes the challenges encountered while aquiring the data. Section 2 describes the results of the reprojection, resampling, regridding and interpolation. After, the analysis of the process is discussed, specifically analyzing the effect of various factors on the observed border errors. Lastly, any additional observations that do not fall within these categories will be discussed.
#drafting.inline-note(
"At current stage, only some intermediate results are available.")



== Data scraping
The data scraping is not considered a part of the processing pipeline. However, due to it's relevance to the challenges of creating a DEM of the Rhine catchment area. Therefore, it has been included in this chapter. Currently, all data labled as a must in @Moscow_Prioritization is implemented within the scraping software. 

#drafting.inline-note("TODO: arda write about this section here")

== Pipeline
#drafting.inline-note("Go over the pipeline shortcomings in accordance with the subquestion")
harmonizing nodata -> reprojection -> regridding -> resampling -> interpolation (Netherlands)


...
The last step of the scraping process is interpolation. This step only applies to the Netherlands due to the absence of interpolated DTM data. This applies to any cell where the ground was not found, including waterbodies, buildings, trees and any other ground obscuring features. Due to the resampling of the data, isolated nodata cells often already get removed. However, for larger areas such as rivers and buildings interpolation is still neccesary.

For this process nearest inverse distance weighing is used. This does not catch all nodata values. In case it does not, nearest neighbor interpolation is used to supplement to fill the remaining holes. However, due to the range set for nearest neighbor, not all nodata cells are interpolated. Increasing the radius would likely solve this issue, but would also significantly increase processing time. Therefore, the interpolation limitations of the Netherlands have had to be excepted as a shortcoming of the pipeline, caused by the available data.

...
== Analysis
#drafting.inline-note("Explain what we see in the comparisons")
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
