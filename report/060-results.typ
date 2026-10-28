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
== Analysis

As described in @sec:border-analysis, the analysis step is where we evaluate the border differences between two neighboring regions. A variety of statistics were evaluated, some of which proved more informative than others. Within this section we will describe which statistics proved most useful for the analysis, primary differences that were encountered, and suggestions on how to rectify, or minimize the border differences between regions.

#drafting.inline-note("fix intro section")
Based on these and other less common metrics, six recurring categories of
artifacts were identified within the border comparisons. Each category is
further divided into several subcategories that describe the specific source
of the observed discrepancies. The identified categories are:

- Tile artifacts;
- Watermask failures;
- Interpolation artifacts;
- Ground filtering artifacts;
- Temporal artifacts;
- Border artifacts.

A complete overview of the identified artifacts for each border pair is
presented in @tab:artifacts_table. To provide a higher-level overview,
@tab:artifact_subcategory_prevalence summarizes the frequency of occurance for the subcategories, while @tab:artifact_prevalence summarizes the frequency with which the different artifact categories occur across all evaluated borders. In the latter table, a category is counted at most once per border pair, irrespective of the number of subcategories that are present. This prevents categories with many subcategories from dominating the statistics and provides a better indication of how widespread a category is throughout the study area.

#figure(
  table(
    columns: 4,

    inset: 3pt,
    align: center + horizon,
    stroke: 0.5pt + rgb("aab2bb"),

    fill: (x, y) => if y == 0 { rgb("e9eef3") },

    table.header(
      [*Subcategory*],
      [*Border pairs*],
      [*Percentage*],
      [*Rank*],
    ),

    [Interpolation differences], [17], [94%], [1],
    [River mask failure], [13], [72%], [2],
    [Construction], [11], [61%], [3],
    [Slopes], [10], [56%], [4],
    [Quarry], [10], [56%], [4],
    [Ground filtering], [6], [33%], [6],
    [Water handling], [5], [28%], [7],
    [Overpass], [5], [28%], [7],
    [Storage], [5], [28%], [7],
    [Border artifacts], [5], [28%], [7],
    [Acquisition striping], [4], [22%], [11],
    [Extrapolation], [4], [22%], [11],
    [Tile differences], [4], [22%], [13],
    [Snow], [1], [6%], [14],
  ),
  caption: [
    Prevalence of identified artifact subcategories.
  ]
)
<tab:artifact_subcategory_prevalence>

#figure(
  table(
    columns: 4,

    inset: 3pt,
    align: center + horizon,
    stroke: 0.5pt + rgb("aab2bb"),

    fill: (x, y) => if y == 0 { rgb("e9eef3") },

    table.header(
      [*Category*],
      [*Border pairs*],
      [*Percentage*],
      [*Rank*],
    ),

    [Interpolation], [17], [94%], [1],
    [Ground filtering], [15], [83%], [2],
    [Temporal], [14], [78%], [3],
    [Watermask], [13], [72%], [4],
    [Border], [7], [39%], [5],
    [Tile artifacts], [7], [39%], [6],
  ),
  caption: [
    Prevalence of artifact categories.
  ]
)
<tab:artifact_prevalence>

The individual categories and their associated subcategories are discussed in
the remainder of this chapter. The complete pairwise analysis for all valid
country pairs can be found in ...


#drafting.inline-note("refer to the appendix with all the pairwise comparisons")
#drafting.inline-note("Explain what we see in the comparisons")
#include "061-artifact_table.typ"

=== Tile artifacts
Tile artifacts are one of the least common types of artifacts. However, these artifacts often have a notable effect on the total difference statistic for a border pair. These differences can be divided into two categories.

The first artifact in this category is aquisition striping. One common trend among the datasets within the Rhine catchment area, is that the elevation data is derived from the @LiDAR point clouds of the region. These are primarily aerial laser scans, which perform a straight line scanning pattern. The width of the bands that this creates are determined by the @FOV of the scanner.

Small deviations in the elevation of each scanning pass can create a striping effect if not corrected for. This is most often observed as bands of similar vertical differences on the difference @DEM, as shown in @fig:Striping_example. To solve this, each band would need to be identified to be offset. Alternatively, the offset would need to be dependent on @LiDAR aquisition time.


#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/Striping example.png", height: 4cm, fit: "contain")
      #align(center)[(Example 1)]
    ],

    [
      #image("assets/bw_france_patterns.png", height: 4cm, fit: "contain")
      #align(center)[(Example 2)]
    ],

    [
      #image("assets/rlp_france_patterns.png", height: 4cm, fit: "contain")
      #align(center)[(Example 3)]
    ],
  ),
  caption: "Example of LiDAR band-like striping",
) <fig:Striping_example>

The second artifact in this category is singular tiles, or sections of tiles that have different vertical offsets compared to the rest of a national @DTM. This appears as visible seamlines on the difference @DEM. These differences however, become less clear when looking at the national @DTM. This happens for example at the @NRW – @RLP border, and more prominently at the @BW – Bavaria border (@fig:Tileoffset_example). While the cause for this artifact is not known for certain, it is possible that this data was captured at a different time, or with a different instrument. This hypothesis can be confirmed by comparing the @LiDAR aquisition time of tiles with such a seam to their neighbors. This is however still a byproduct of inaccurate vertical alignment with a @DTM, in such a manner that it does not correspond with the rest of the @CRF. To solve this difference, the offending tiles would need to be reextracted, and coregistered to the neighboring tiles.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/BW-Bavaria-DiscreteDH.png", height: 5cm, fit: "contain")
      #align(center)[(Example 1)]
    ],

    [
      #image("assets/NRW-RLP-nonalignment.png", height: 5cm, fit: "contain")
      #align(center)[(Example 2)]
    ],
  ),
  caption: "Example of tile seams due to vertically offset tiles",
) <fig:Tileoffset_example>



=== Interpolation artifacts



=== Ground filtering artifacts



=== Temporal artifacts

Temporal artifacts rank third as the most common cause of artifacts. This is due to the fact the aquisition time between two regional or national @DTM:pls can differ in the order of years.

There does appear to be a surprising commonality in the specific causes of these differences. The most common cause are construction sites. These include everything from the construction of new buildings, demolishing of buildings, or the construction of windmills.

However, a more interesting type of temporal difference is found in the area surrounding Luxembourg. These are stockpiles of coal and sand at river ports (@fig:Coal). Due to the classification in the point cloud, these are not classified as buildings and are included in the ground filtering. Therefore, as ships are loaded and the distribution changes, the elevation change does appear in the comparison.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/RLP-BW-CoalESRI.png", width: 80%)
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/RLP-BW-CoalDH.png", width: 80%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Example of coal storage",
)
<fig:Coal>

There is one even more unique difference which only occurs once to our knowledge within the border comparisons. This is the inclusion of snow which has affected the elevation in the @DTM, which was determined through point cloud evaluation (@fig:snow).

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-snow-satellite.png")],
    [#image("assets/nrw-hessen-snow.png")],
    [#image("assets/nrw-hessen-snow.jpeg", width: 85%)]
  ),
  caption: [Example of snow affecting the comparison]
)<fig:snow>

These differences can be resolved by comparing the point clouds of the neighboring regions. For the interest of temporal accuracy, it is most favorable to take the data from the latest aquisition time to have the most recent data. However, this does possibly cause a noticable seam at the edge of the overlapping area without any smoothing. As discussed in ... , smoothing dilutes the elevation data captured between regions and is undesirable. Furthermore, static features such as hills should not be affected by temporal aspects, and may require a different approach to be rectified. Solving this challenge is not within the boundaries of this project, but could be the focus of a followup project. 

#drafting.inline-note("do make sure we compare our product to Mapterhorn")

