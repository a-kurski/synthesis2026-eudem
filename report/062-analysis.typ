#import "@preview/drafting:0.2.2"
== Analysis
As described in @sec:border-analysis, the analysis step is where we evaluate the border differences between two neighboring regions. There are various metrics to evaluated on. However, the difference raster, RMSE – Slope plot, and difference historgram are among the most important as they give information about the general cases. Based this data, a pattern was found regarding the artifacts at the borders.

These artifacts can be divided into six primary categories representing overarching themes. To further specify the type of artifact, each category is divided into subcategories which each represent an example of the artifact. These main artifacts are interpolation, ground filtering, temporal, watermask, and tile artifacts.


@tab:artifact_prevalence gives an overview of these categories in grey, while the white subsections describe the subcategories. The percentage of border pairs describes in how many of the 18 evaluated border cases an artifact occurs. The bold category percentages detail in what percentage of all border pairs, at least one of the artifacts within the category occurs. As can be observed, the interpolation is the most frequently occuring artifact. However, @tab:artifact_prevalence does not signify the severity of each artifact, which will be further discussed in the remainder of this chapter. The only exception is the artifacts caused by shortcomings in the river mask, which are discussed in #drafting.inline-note("reference the section where the rivermask is discussed"). The full overview of each border pair and their corresponding artifacts can be found in @tab:artifacts_table. Furthermore, a pairwise analysis of all border pairs can be found in @sec:border_pairs, which contains additional visuals and a case-by-case evaluation of the differences.

#let cat(name, n, pct, rank) = (
  table.cell(fill: rgb("e9eef3"))[*#name*],
  table.cell(fill: rgb("e9eef3"))[*#n*],
  table.cell(fill: rgb("e9eef3"))[*#pct*],
  table.cell(fill: rgb("e9eef3"))[*#rank*],
)

#let sub(name, n, pct) = (
  pad(left: 1em)[#name], [#n], [#pct], [],
)

#figure(
  table(
    columns: (auto, auto, auto, auto),
    inset: 3pt,
    align: (x, y) => if x == 0 { left + horizon } else { center + horizon },
    stroke: 0.5pt + rgb("aab2bb"),

    table.header(
      [*Category / subcategory*],
      [*Border pairs*],
      [*Percentage of border pairs*],
      [*Rank*],
    ),

    ..cat("Interpolation", 17, "94%", 1),
    ..sub("Interpolation differences", 17, "94%"),

    ..cat("Ground filtering", 15, "83%", 2),
    ..sub("Slopes", 10, "56%"),
    ..sub("Quarry", 10, "56%"),
    ..sub("Ground filtering", 6, "33%"),
    ..sub("Overpass", 5, "28%"),

    ..cat("Temporal", 14, "78%", 3),
    ..sub("Construction", 11, "61%"),
    ..sub("Storage", 5, "28%"),
    ..sub("Snow", 1, "6%"),

    ..cat("Watermask", 13, "72%", 4),
    ..sub("River mask failure", 13, "72%"),
    ..sub("Water handling", 5, "28%"),

    ..cat("Border", 7, "39%", 5),
    ..sub("Border artifacts", 5, "28%"),
    ..sub("Extrapolation", 4, "22%"),

    ..cat("Tile artifacts", 7, "39%", 5),
    ..sub("Tile differences", 4, "22%"),
    ..sub("Acquisition striping", 4, "22%"),
  ),
  caption: [
    Prevalence of artifact categories and their subcategories.
  ],
) <tab:artifact_prevalence>


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
      #image("assets/BW-Bavaria-DiscreteDH.png", height: 7cm, fit: "contain")
      #align(center)[(Example 1)]
    ],

    [
      #image("assets/NRW-RLP-nonalignment.png", height: 7cm, fit: "contain")
      #align(center)[(Example 2)]
    ],
  ),
  caption: "Example of tile seams due to vertically offset tiles",
) <fig:Tileoffset_example>


#pagebreak()
=== Interpolation artifacts

Interpolation disagreements occur in all border pairs (with the exception of Switzerland – Liechtenstein). This is because a @DTM does not include buildings or vegitation within the data, it only includes terrain. However, the source data for the @DTM:pls is the point cloud, which does include buildings and vegitation. There are various methods to filter out these features. Points in the point cloud classified as buildings can be filtered out before ground filtering, or retained during ground filtering, filtered out of the @DTM based on footprint, etc. 

All these different approaches produce slightly different elevations at the location of a building. The interpolation performed due to reprojection further complicates this. Most data providers do not describe the method through which this filtering and/or interpolation is performed. Therefore, it is hard to say wether differences occur as a result of differences in interpolation strategy, or due to another reasons such as temporal changes (without having the point cloud).

The magnitude of the errors differs between region pairs. Some regions show little disagreement, while others can show elevation differences of 1–2 meters, with isolated cases going beyond that. While not implemented within this project, a possible approach to solve this challenge could be to generate an interpolation mask. If it holds true that the @DTM is created in the same manner as the @DSM

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Building-Interpolation.png",width:80%)
      #align(center)[(Elevation Difference))]
    ],

    [
      #image("assets/Building Interpolation-maps.png", width:80%)
      #align(center)[(Google Maps)]
    ],
  ),
  caption: "Example of elevation differences caused by interpolation disagreements. Dark red values represent large positive difference while dark blue shows negative difference",
) <fig:Building-interpolation>

One important note is that interpolation is not always at fault for differences observed for buildings. Especially for large area buildings, ground filtering can also cause disagreements. An example of this phenomenon can be found on the @NRW – Hessen border as shown in @fig:ground-building.

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-buildings-satellite.png")],
    [#image("assets/nrw-hessen-buildings.png")],
    [#image("assets/nrw-hessen-warehouse.jpeg")]
  ),
  caption: [Ground and building filtering differences between NRW and Hessen]
)<fig:ground-building>

#pagebreak()
=== Ground filtering artifacts



#pagebreak()
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

=== Border artifacts

Border artifacts refer to wrongly interpolated @DTM edges and extrapolation of data to fill in missing data. The edge artifact is caused by reprojecting of a @DTM to a different @CRS as this uses iterpolation to determine the new elevation value at the new cell center. Since the point is located at the edge, the billinear interpolation can only be performed on a partial kernel. The magnitude of this difference varies between several milimeters to differences that exceed the resolution threshold (1.6 meters)(@fig:BorderArtifact). The solution to this is to clip the offending border pixels from the output @DTM. Because there exists an overlap between the regions, an empty cell should not create gaps within the @DTM, but instead these cells will be overwritten by the neighboring @DTM. However, within the current implementation of the pipeline, border harmonisation is achieved by clipping the @DTM:pls to the national or regional extent. Therefore, these artifacts do not make it into the catchment area @DTM as it is currently.

#figure(
  image("assets/Hessen-BW-BorderArtifact.png",width:40%),
  caption:"Example where a DTM edge difference exceeds the resolution threshold"
)
<fig:BorderArtifact>

The second type of artifact are border regions where some type of interpolation has occured to complete or modify the @DTM. The severity of this artifact is greater as it often covers a larger area, and is harder to filter out due to the diversity of how the artifact presents itself. The first of the ways in which it is presented, occurs at the Hessen – @RLP border. The method through which this artifact has been created is not entirely clear. It appears in the Hessen @DTM and appears to linearly stretch pixel values between two non-neighboring tiles, and also produces sharp geometric shapes. 

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-artefact-satellite.png")],
    [#image("assets/hessen-rlp-artefact-hessen.png") Hessen],
    [#image("assets/hessen-rlp-artefact-rlp.png") RLP],
    [#image("assets/hessen-rlp-artefact.png")],
  ),
  caption: [Interpolation artefact by shown as a combination of smeared and geometrically shaped data for the Hessen DTM]
)

Another example of this occurs at the @RLP – Saarland border (@fig:Extrapolation2). As can be observed in the figure, the valley in blue for the RLP and Saarland images, does not line up between the the two @DTM:pls. Furthermore, the visuals appear smeared in the difference map on the right side (DH), pointing towards values interpolated using a method such as @IDW. In contrast to the previous case, not all of the offending area appears to be interpolated. However, some degree of processing at the border section has caused a disagreement of put to 16 meters in this area.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/RLP-Saarland-Extrapolation2RLP.png", width: 100%)
      #align(center)[(RLP)]
    ],

    [
      #image("assets/RLP-Saarland-Extrapolation2Saar.png", width: 100%)
      #align(center)[(Saarland)]
    ],

    [
      #image("assets/RLP-Saarland-Extrapolation2DH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Example of extrapolation artifact as smeared",
)
<fig:Extrapolation2>

The last example of this type of artifact is one which was introduced due to our own interpolation. In an effort to interpolate the Dutch @DTM nodata values, extrapolation has occured (@fig:Netherlands-border_example). This artifact is created by a disagreement between the border definitions in our Dutch mask and the actual dutch border as it has been clipped. As the mask is slightly expanded, several areas are extrapolated beyond the data available within the Dutch @DTM. Solving this disagreement is a matter up improving the Dutch mask. Furthermore, the availability of @AHN version 6 should eliminate this issue, as it will extend into Germany and beyond the current border mask.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-borderdifferenceAHN.png", width: 100%)
      #align(center)[(Netherlands)]
    ],

    [
      #image("assets/Netherlands-NRW-borderdifferenceDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Border artifact",
)
<fig:Netherlands-border_example>