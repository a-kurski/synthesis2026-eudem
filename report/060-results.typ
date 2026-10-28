#import "@preview/drafting:0.2.2"
= Results <chap:results>

This chapter discusses the results of the data acquisition, the pipeline, analysis of the border-pairs and general findings about the @DTM:pls. The first section describes the challenges encountered while aquiring the data. Section 2 describes the results of the reprojection, resampling, regridding and interpolation. After, the analysis of the process is discussed, specifically analyzing the effect of various factors on the observed border errors. Lastly, any additional observations that do not fall within these categories will be discussed.
#drafting.inline-note(
"At current stage, only some intermediate results are available.")



== Data Acquisition <sec:results-acquisition>
The data scraping is not considered a part of the processing pipeline due to the variations in scraping methods, accessing differences, and computation time. However, due to its relevance to the challenges of creating a @DEM of the Rhine catchment area, it has been included in this chapter. The pipeline assumes all data is available in their raw formats that is, individual @DTM tiles in most of the cases. In case the requested data is not available, the pipeline proceeds to download it from the specified source. Currently, all acquisition of data labeled as a must in @Moscow_Prioritization is implemented within the scraping software.

The pipeline acquires elevation data from 11 regions within 6 countries. The data comes in different formats, availability, @CRS, nodata specification, and resolution. The table below summarizes the characteristics of the data.

#include "elevation_data_characteristics.typ"
#drafting.inline-note("TODO: arda write about this section here")

== Pipeline <chap:Pipeline>


#drafting.inline-note("Go over the pipeline shortcomings in accordance with the subquestion")
harmonizing nodata -> reprojection -> regridding -> resampling -> interpolation (Netherlands)


...
The last step of the scraping process is interpolation. This step only applies to the Netherlands due to the absence of interpolated @DTM data. This applies to any cell where the ground was not found, including waterbodies, buildings, trees and any other ground obscuring features. Due to the resampling of the data, isolated nodata cells often already get removed. However, for larger areas such as rivers and buildings interpolation is still necessary.

For this process nearest inverse distance weighing is used. This does not catch all nodata values. In case it does not, nearest neighbor interpolation is used to supplement to fill the remaining holes. However, due to the range set for nearest neighbor, not all nodata cells are interpolated. Increasing the radius would likely solve this issue, but would also significantly increase processing time. Therefore, the interpolation limitations of the Netherlands have had to be excepted as a shortcoming of the pipeline, caused by the available data.

...

The river mask is limited by the quality of the course resolution of the SDG mask @SDG. It has trouble with small rivers as these are generally marked as values of 1 within the river mask, which are currently skipped in the interest of avoiding outliers.


=== Watermask artifacts
Watermask artifacts are related to the watermask extraction as described in @sec:Water_mask_processing. These are the second to most common artifact encountered in border analysis. The purpose of the watermask of course, is to filter out all waterbodies, as large deviations in elevation are known to occur here and are therefore, not interesting for the analysis. However, the mask is limited in effectiveness. 

The region growing algorithm relies on the assumption that the watersurface is smooth. However, this is not always the case. The first example of this fact is found in @fig:River_mask_manmade. Here a hydro electric power plant causes a deviation in the elevation. The rough watermask from @FEE marks this as an area which is not considered water. Therefore, there is a break in the watermask, and the area surrounding the plant such the left secondary channel, is not modeled.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Lux-Saarland-HydroGoogle.png", width: 80%)
      #align(center)[(Google maps)]
    ],

    [
      #image("assets/Lux-Saarland-HydroDH.png", width: 80%)
      #align(center)[(DH)]
    ],
  ),
  caption:[Rivermask failure due to man-made objects]
)<fig:River_mask_manmade>

Another common shortcoming which is similar to the previous, is that the @FEE mask is incomplete. Not all lakes have valid seed points contained within. Furthermore, the reprojection of @FEE cell centers onto the empty mask, due to invalid row and/or column values as a result of division by 0 errors. These are known limitations of the river mask which could be solved by extracting the mask from the national point clouds of the respective regions.

#drafting.inline-note("Issue with seed point projection.")

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-missing-lakes-Maps.png", width: 80%)
      #align(center)[(Google maps)]
    ],

    [
      #image("assets/France-missing-lakes.png",width:80%)
      #align(center)[(Mask refined)]
    ],

    [
      #image("assets/France-missing-lakes-FEE.png",width:80%)
      #align(center)[(Mask FEE)]
    ],
  ),
  caption:[Rivermask failure due missing input raster for region growing]
)<fig:River_mask_missinglakes>

Other issues include areas that are marked as neither lake or river by @FEE. Examples include swampy areas on the Netherlands – @NRW border. This difference is illustrated in @fig:getoutofmyswamp.

#figure(grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-StoneSwampGoogle.png", width: 80%)
      #align(center)[(Google Maps)]
    ],

    [
      #image("assets/Netherlands-NRW-StoneSwampDH.png", width: 80%)
      #align(center)[(DH)]
    ],
  ),
  caption: [Omission of swamp-like areas from the watermask prevents ommision from difference comparison])
<fig:getoutofmyswamp>

The last artifact appears most frequently within the French region of the mask. This does not affect the border area as the masks of both regions overlap here. However, this appears to be caused by the @TIN approximation of the water surface. This causes shard-like sections of discoloration in the @DTM. Unlike other artifacts this does not strongly affect the border areas. However, it does mean it cannot be used as a true harmonisation step for the Rhine @DTM.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-ommision-riverfail-Maps.png", width: 100%)
      #align(center)[(Google maps)]
    ],

    [
      #image("assets/France-ommision-riverfail.png",width:100%)
      #align(center)[(Mask failure)]
    ],

    [
      #image("assets/France-ommision-riverfail-TIN.png",width:100%)
      #align(center)[(TIN artifacts on DTM)]
    ],
  ),
  caption:[Rivermask failure due missing input raster for region growing]
)<fig:River_mask_TIN>
#pagebreak()

#include "062-analysis.typ"