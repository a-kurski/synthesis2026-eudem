#import "@preview/drafting:0.2.2"

== Analysis

Within this section, we evaluate differences on the border between two neighboring regions.
We generate at various automatically generated metrics the DTMs are evaluated on (@sec:border-analysis).
Of those, we find mean, median, RMSE and LE90; the generated raster; RMSE/slope plot and difference histogram to be among the most important as they give information about the general cases. Based this data, a pattern was found regarding the error sources at the borders, described further below.

@tab:stas-overview shows the key statistics for of each pair of the datasets. We note that high @RMSE and high @LE90 correspond to a high systematic error (as is the case for France/Luxembourg border) while high @RMSE but low @LE90 correspond to an outlier (as is the case for @DE-BW/@DE-BY border).

#include "063-table-overview.typ"

The majority of the datasets demonstrate high agreement with each other, with 15 out of 17 pairs meeting the @INSPIRE requirements for @RMSE. The first exception is @FR/@LI border where the errors are caused by the consistent differences between the French --- acquired with radar or photogrammetry --- and Luxembourgish --- acquired with @ALS --- @DTM:pla. In @fig:graphs-compare, we can observe that France displays consistently high RMSE for all slope angles which even exceeds 5m in comparison with a more typical slope/RMSE graph. The second is a fill value which does not match the NoData value of specified in metadata for @DE-BY, described in @sec:postprocessing-errors.

#figure(
  grid(
    columns: (1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/slope_rmse_france_luxembourg.png")
      #text(size: 10pt)[
        Slope/RMSE graph for FR/LU border.
      ]
    ],
    [#image("assets/slope_rmse_germany_rlp_germany_saarland.png")
      #text(size: 10pt)[
        Slope/RMSE graph for DE-RP/DE-SL borders.
      ]
    ]
  ),
  gap: 12pt,
  caption: [Comparison of slope/RMSE graphs.]
) <fig:graphs-compare>
#v(1em)

We also observe that the pairs involving France perform consistently worse. Again, this is due to large sections of the @DTM which are not acquired with @ALS. France also has a median and mean of about 0.5m which matches the offset due to co-registration, suggesting a systematic error. We have not been able to determine whether this error is intrinsic to the dataset or a result of the missing @CRS transform.

=== Error Sources

These error sources can be divided into six categories representing overarching themes: interpolation, ground filtering, temporal, water mask, pre-processing, and post-processing artefacts. To further specify the type of artefact, each category is divided into subcategories which each represent an example of the artefact. The only error source which will not be discussed are the artefacts caused by shortcomings in the river mask, which have been discussed above in @sec:Watermask_artefacts.

@tab:artefact_prevalence gives an overview of these categories and their subcategories. The percentage of border pairs describes in how many of the 17 evaluated border cases an artefact occurs. We exclude the Switzerland/Liechtenstein border from the comparison as the countries share the dataset. We calculate what percentage of all border pairs, at least one of the artefacts within the category occurs --- most borders have more than one type of artefact, and are therefore counted several times. As can be observed, the interpolation is the most frequently occurring artefact. We also evaluate the artefacts by severity, i.e. the magnitude and perceived effect of the error type. The overview can be found in @tab:artefact_prevalence.

The full overview of each border pair and their corresponding artefacts can be found in @tab:artefacts_table. Furthermore, a pairwise analysis of all border pairs can be found in @sec:border_pairs, which contains additional visuals and a case-by-case evaluation of the differences.

#pagebreak()

#let cat(name, n, pct, rank_occ, rank_sev) = (
  table.cell(fill: rgb("e9eef3"))[*#name*],
  table.cell(fill: rgb("e9eef3"))[*#n*],
  table.cell(fill: rgb("e9eef3"))[*#pct*],
  table.cell(fill: rgb("e9eef3"))[*#rank_occ*],
  table.cell(fill: rgb("e9eef3"))[*#rank_sev*],
)

#let sub(name, n, pct) = (
  pad(left: 1em)[#name],
  [#n],
  [#pct],
  [],
  [],
)

#figure(
  table(
    columns: (auto, auto, auto, 60pt, 60pt),
    inset: 3pt,
    align: (x, y) => if x == 0 { left + horizon } else { center + horizon },
    stroke: 0.5pt + rgb("aab2bb"),

    table.header(
      [*Category / subcategory*],
      [*Border pairs*],
      [*Percentage of border pairs*],
      [*Rank occurrence*],
      [*Rank severity*],
    ),

    ..cat("Interpolation", 17, "100%", 1, 5),
    ..sub("Interpolation differences", 17, "100%"),

    ..cat("Ground filtering", 15, "88%", 2, 2),
    ..sub("Slopes", 13, "76%"),
    ..sub("Overpass", 5, "29%"),

    ..cat("Temporal", 14, "82%", 3, 3),
    ..sub("Construction", 11, "65%"),
    ..sub("Quarry", 10, "59%"),
    ..sub("Storage", 5, "29%"),
    ..sub("Snow", 1, "6%"),

    ..cat("Water mask", 13, "76%", 4, 4),
    ..sub("River mask failure", 13, "76%"),
    ..sub("Water handling", 5, "29%"),

    ..cat("Post-processing", 7, "41%", 5, 1),
    ..sub("Border artefacts", 5, "29%"),
    ..sub("Extrapolation", 5, "29%"),

    ..cat("Pre-processing", 7, "41%", 5, 6),
    ..sub("Tile differences", 4, "24%"),
    ..sub("Acquisition striping", 4, "24%"),
  ),
  caption: [
    Identified artefact categories and their prevalences.
  ],
) <tab:artefact_prevalence>

#include "061-artefact_table.typ"

=== Interpolation artefacts

Interpolation disagreements occur at all borders. This is because a @DTM does not include buildings or vegetation within the data, it only includes terrain which means that some data has to be excluded from the source data. There are various methods to filter out these features.This results in gaps in the dataset which need to be filled, typically via interpolation. The exact point within the pipeline, source data, and interpolation algorithm all affect the elevation values of the resulting @DTM.

Most data providers do not describe the method through which this filtering and/or interpolation is performed. Therefore, it is hard to definitively say whether differences occur as a result of differences in interpolation strategy, or due to another reasons such as temporal changes without evaluating the underlying point cloud.

The magnitude of the errors differs between region pairs. Some regions show little disagreement, while others can show elevation differences of 1–2 meters, with isolated cases going beyond that. We suggest that the errors can be better assessed if an accurate interpolation mask can be obtained. We can also use point cloud data to harmonise the interpolation --- this has not been performed within the project.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Building Interpolation-maps.png", width:80%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, Maxar Technologies (2026).
      ]
    ],

    [
      #image("assets/Building Interpolation.png",width:80%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],


  ),
  caption: "Example of elevation differences caused by interpolation disagreements. Dark red values represent large positive difference while dark blue shows negative difference",
) <fig:Building-interpolation>

One important note is that interpolation is not always at fault for differences observed for buildings. Especially for large area buildings, ground filtering can also cause disagreements. @DE-NW uses synthetic ground points from the CSF instead of interpolation to extract the @DTM --- this causes artefacts seen in @fig:ground-building.

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-buildings-satellite.png")],
    [#image("assets/nrw-hessen-buildings.png")],
    [#image("assets/nrw-hessen-warehouse.jpeg")]
  ),
  caption: [Ground and building filtering differences between NRW and Hessen.]
)<fig:ground-building>

=== Ground filtering artefacts

Ground filtering is the second most common artefact encountered for the border pairs. For this category we consider steep slopes (cliffs, valleys), and disagreements caused by overpass handling. Out of these subcategories, errors due to steep slopes are both the most common and most severe, while overpasses are rare and only create small, local disagreements.

Errors in overpasses can only be found in roughly a quarter of all border pairs --- they may also be present in other @DTM:pla but are processed similarly there. The severity of the difference largely depends on the height of the overpass and generally exceed the 1.67m threshold. @fig:NRW-RLP-overpass-example shows an example of different overpass processing.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-overpass.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From AeroWest,
        Airbus, Maxar Technologies \
        (2026).
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassNRW.png", width: 100%)
      #text(size: 10pt)[
        DTM provided by NRW.
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassRLP.png", width: 100%)
      #text(size: 10pt)[
        DTM provided by RLP.
      ]

    ],
  ),
  caption: "Example of an overpass being treated differently between NRW and RLP due to differences in ground filtering.",
)
<fig:NRW-RLP-overpass-example>
#v(1em)

Errors due to slope processing occur at cliffs and in valleys/hills. A cliff typically shows up as a thin and long artefact on the @DEM difference raster, as seen in @fig:Hessen-BW-clearing-example. Due to the steepness of the cliff small horizontal differences between sample points in the @DTM can create large vertical differences if one dataset measures the elevation at the bottom of the cliff and the other at the top. Alternatively, this can be a byproduct of differences in ground filtering methods.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/Hessen-BW-clearingESRI.png", height: 5cm, fit: "contain")
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/Hessen-BW-clearingDH.png", height: 5cm, fit: "contain")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],

    [
      #image("assets/Hessen-BW-clearingSV.png", height: 5cm, fit: "contain")
      #text(size: 10pt)[
        Image from Google Street View \
        (49.4762° N, 8.4208° E)
      ]
    ],
  ),
  caption: "Example of a cliff artefact flagged as a resolution threshold exceeding disagreement",
)
<fig:Hessen-BW-clearing-example>

The second type of slope disagreement can be found primarily in regions which constain deep valleys such as the France – Luxembourg border. The underlying causes are similar: differences in either data acquisition or ground filtering. However unlike cliffs, this type of artefact can cause large sections of disagreement between @DTM:pls (@fig:Lux_Fra_border-example). @fig:Lux_Fra_Rumelange_example shows the region around the city of Rumelange, which is located within a valley. The difference in @DTM elevations here are up to differences of 25 meters in both positive and negative directions. We also observe higher error rates for areas with steep slopes in other datasets, but the magnitude of those is typically under a metre. For France, we expect that a more accurate dataset will mostly resolve these errors; for other regions, standardising the ground filtering algorithm may reduce their magnitude too.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/France-Lux-borderarea.png", width: 100%)
      #align(center)[(DH)]
    ],

    [
      #image("assets/France-Lux-borderarea-issues.png", width: 100%)
      #align(center)[(Flagged Differences)]
    ],
  ),
  caption: "Example of large regions of disagreement, flagged differences in red exceed 1.6 meters of difference at the France – Luxembourg border",
)
<fig:Lux_Fra_border-example>

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-Lux-Rumelange-DH.png", width: 100%)
      #align(center)[(DH)]
    ],

    [
      #image("assets/France-Lux-Rumelange-elevation.png", width: 100%)
      #align(center)[(DTM)]
    ],


    [
        #image("assets/France-Lux-Rumelange-contour.png", width: 100%)
        #align(center)[(Contours)]
    ],
  ),
  caption: "Example of Rumelange where disagreements can increase up to 25 meters.",
)
<fig:Lux_Fra_Rumelange_example>

=== Pre-Processing Artefacts
Pre-processing artefacts are one of the least common types of artefacts. However, these artefacts may have a sizeable effect on the RMSE or LE90 statistics for a given border pair. These differences can be divided into two categories.

The first artefact in this category is striping. One common trend among the datasets within the Rhine catchment area is that most elevation data is derived from the point clouds of the region. These are primarily aerial laser scans, which are performed by flying a plane in parallel straight lines. The width of the bands that this creates are determined by the scanner's field of view.

Small deviations of several centimetres in the elevation of each scanning pass can create a striping effect if not corrected for. The severity of this artefact is minimal, however clearly noticeable when observing differences in @DEM:pls. Its shows up as bands of consistent elevation along-track difference and sharp changes across the tracks, as shown in @fig:Striping_example. This artefact cannot be corrected based on gridded datasets alone.


#figure(
  grid(
    columns: 2,
    gutter: 5pt,
    row-gutter: 10pt,

    [
      #image("assets/Striping example.png", height: 6cm, fit: "contain")
      #text(size: 10pt)[
        NRW/RLP border.
      ]
    ],

    [
      #image("assets/bw_france_patterns.png", height: 6cm, fit: "contain")
      #text(size: 10pt)[
        BW/France border.
      ]
    ],

    grid.cell(
      colspan: 2,
      align(center)[
        #image("assets/rlp_france_patterns.png", height: 4cm, fit: "contain")
        #text(size: 10pt)[
          RLP/France border.
        ]
      ],
    ),
  ),
  caption: "Examples of LiDAR band-like striping artefacts in elevation difference maps. For all examples, the displayed elevation differences were restricted to values between −1 and 1 m to make the striping patterns more visible.",
) <fig:Striping_example>

The second artefact in this category is singular tiles, or sections of tiles that have different vertical offsets compared to the rest of a national @DTM. This appears as visible seam lines on the @DEM difference raster. These differences, however, become less clear when looking at the national @DTM alone. This happens for example at the @NRW – @RLP border, and more prominently at the @BW – Bavaria border (@fig:Tileoffset_example). We speculate that this artefact is caused by (mis-)alignment of data between different surveys. Resolving this artefact is thus challenging without having access to source point clouds. The magnitude of this artefact has been inconsistent: in @fig:Tileoffset_example (a), the maximum difference is 2.6 meters; in @fig:Tileoffset_example (ab the difference between tile elevation steps across the seam is measured at 40 centimeters.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/BW-Bavaria-DiscreteDH.png", height: 7cm, fit: "contain")
      #text(size: 10pt)[
        BW/Bavaria border.
      ]
    ],

    [
      #image("assets/NRW-RLP-nonalignment.png", height: 7cm, fit: "contain")
      #text(size: 10pt)[
        NRW/RLP border.
      ]
    ],
  ),
  caption: "Examples of visible tile seams in elevation difference maps caused by vertical elevation offsets between adjacent DTM tiles.",
) <fig:Tileoffset_example>

<<<<<<< HEAD
=== Ground filtering artefacts

Ground filtering is the second most common artefact encountered for the border pairs. For this category we consider steep slopes (cliffs, valleys), and disagreements caused by overpass handling. Out of these subcategories, steep slopes are both the most common and most severe, while overpasses only create small, local disagreements.

Overpasses can only be found in roughly a quarter of all cases. However, this does not mean they do not exist within other border pairs, but simply do not create elevation differences. The severity of the difference depends on the height of the overpass, though generally exceed the resolution threshold. @fig:NRW-RLP-overpass-example shows and example where the area which exceeds the resolution threshold is highlighted in red, while the NRW and RLP images show the elevation.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-overpass.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From AeroWest,
        Airbus, Maxar Technologies \
        (2026).
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassNRW.png", width: 100%)
      #text(size: 10pt)[
        DTM of NRW.
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassRLP.png", width: 100%)
      #text(size: 10pt)[
        DTM of RLP.
      ]

    ],
  ),
  caption: "Example of an overpass being treated differently between NRW and RLP due to differences in ground filtering.",
)
<fig:NRW-RLP-overpass-example>
#v(1em)

The two main types of slope disagreement are cliffs and valleys/hills. These artefacts can be recognized by a discrete drop in the @DTM or a thin and long artefact on the difference @DEM. An example of this type of artefact can be seen in @fig:Hessen-BW-clearing-example. Due to the steepness of the cliff small horizontal differences between sample points in the @DTM can create large vertical differences as measurements may lie at the top or bottom of the cliff. Alternatively, this can be a byproduct of differnces in ground filtering methods such as cloth simulation, progressive TIN densification, or @SMRF.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/Hessen-BW-clearingESRI.png", height: 5cm, fit: "contain")
      #text(size: 10pt)[
        Satellite imagery. From AeroWest, Airbus, Geobasis-DE/BKG.
        \ (2026)
      ]
    ],

    [
      #image("assets/Hessen-BW-clearingDH.png", height: 5cm, fit: "contain")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],

    [
      #image("assets/Hessen-BW-clearingSV.png", height: 5cm, fit: "contain")
      #text(size: 10pt)[
        Image from Google Street View \
        (49.453946° N, 8.947358° E)
      ]
    ],
  ),
  caption: "Example of a cliff artefact flagged as a resolution threshold exceeding disagreement",
)
<fig:Hessen-BW-clearing-example>

The second type of slope disagreement can be found primarily in regions which constain deep valleys such as the France – Luxembourg border. The cause for this disagreement is the same as for steep cliffs. However, unlike cliffs, this type of artefact can cause large sections of disagreement between @DTM:pls (@fig:Lux_Fra_border-example). @fig:Lux_Fra_Rumelange_example shows the region around the city of Rumelange, which is located within a valley. The difference in @DTM elevations can increase up to differences of 25 meters in both positive and negative directions. The best way to resolve these sorts of discrepancies would be to reextract the @DTM for the border region through the point cloud, as smoothing the terrain such as Mapterhorn does, deviates far from the actual elevation of the region @wipfli2026mapterhorn.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/France-Lux-borderarea.png", width: 100%)
      #text(size: 10pt)[Elevation difference map.]
    ],

    [
      #image("assets/France-Lux-borderarea-issues.png", width: 100%)
      #text(size: 10pt)[Flagged differences in red.]
    ],
  ),
  caption: "Example of large regions of disagreements. Flagged disagreements in red exceed 1.6 meters of difference between the France/Luxembourg datasets.",
)
<fig:Lux_Fra_border-example>

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/France-Lux-Rumelange-DH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],

    [
      #image("assets/France-Lux-Rumelange-elevation.png", width: 100%)
      #text(size: 10pt)[
        DTM
      ]
    ],
  ),
  caption: "Example of Rumelange in Luxembourg, next to the French border. Disagreements of up to 25 meters are observed.",
)
<fig:Lux_Fra_Rumelange_example>

=======
>>>>>>> 6627f71ee4d6db542a8584b1aabbeaa6ce35876a
=== Temporal artefacts

Temporal artefacts rank third as the most common cause of artefacts. This is due to the fact the aquisition time between two regional or national @DTM:pls can differ in the order of years.

There does appear to be a surprising commonality in the specific causes of these differences. The most common cause are construction sites. These include everything from the construction of new buildings, demolishing of buildings, or the construction of windmills.

However, a more interesting type of temporal difference is found in the area surrounding Luxembourg. These are stockpiles of coal and sand at river ports (@fig:Coal). Due to the classification in the point cloud, these are not classified as buildings and are included in the ground filtering. Therefore, as ships are loaded and the distribution changes, the elevation change does appear in the comparison.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/RLP-BW-CoalESRI.png", width: 80%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, GeoBasis-DE/BKG, Maxar Technologies\
        (2026)
      ]
    ],

    [
      #image("assets/RLP-BW-CoalDH.png", width: 80%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: "Large elevation differences observed due to changes of a coal storage between two surveys.",
)
<fig:Coal>
#v(1em)

There is one even more unique difference which only occurs once to our knowledge within the border comparisons. This is the inclusion of snow which has affected the elevation in the @DTM, which was determined through point cloud evaluation (@fig:snow).

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-snow-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. \ From Airbus, \ Maxar Technologies\
        (2026)
      ]
    ],
    [#image("assets/nrw-hessen-snow.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
    [#image("assets/nrw-hessen-snow.jpeg", width: 85%)
      #text(size: 10pt)[
        Point cloud of the area. \ Yellow areas correspond to snow.
      ]
    ]
  ),
  caption: "Elevation differences caused by the presence of snow in one of the surveys..",
)<fig:snow>

These differences can be resolved by comparing the point clouds of the neighboring regions. For the interest of temporal accuracy, it is most favorable to take the data from the latest aquisition time to have the most recent data. However, this does possibly cause a noticable seam at the edge of the overlapping area without any smoothing. Smoothing dilutes the elevation data captured between regions and is undesirable. Furthermore, static features such as hills should not be affected by temporal aspects, and may require a different approach to be rectified. Solving this challenge is not within the boundaries of this project, but could be the focus of a followup project.

=== Border artefacts <sec:postprocessing-errors>

Border artefacts refer to wrongly interpolated @DTM edges and extrapolation of data to fill in missing data. The edge artefact is caused by reprojecting of a @DTM to a different @CRS as this uses iterpolation to determine the new elevation value at the new cell center. Since the point is located at the edge, the billinear interpolation can only be performed on a partial kernel. The magnitude of this difference varies between several milimeters to differences that exceed the resolution threshold (1.6 meters)(@fig:Borderartefact). The solution to this is to clip the offending border pixels from the output @DTM. Because there exists an overlap between the regions, an empty cell should not create gaps within the @DTM, but instead these cells will be overwritten by the neighboring @DTM. However, within the current implementation of the pipeline, border harmonisation is achieved by clipping the @DTM:pls to the national or regional extent. Therefore, these artefacts do not make it into the catchment area @DTM as it is currently.

#figure(
  image("assets/Hessen-BW-Borderartifact.png",width:40%),
  caption:"Example where a DTM edge difference exceeds the resolution threshold."
)
<fig:Borderartefact>
#v(1em)

The second type of artefact are border regions where some type of interpolation has occured to complete or modify the @DTM. The severity of this artefact is greater as it often covers a larger area, and is harder to filter out due to the diversity of how the artefact presents itself. The first of the ways in which it is presented, occurs at the Hessen – @RLP border. The method through which this artefact has been created is not entirely clear. It appears in the Hessen @DTM and appears to linearly stretch pixel values between two non-neighboring tiles, and also produces sharp geometric shapes.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-artefact-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. \ From Airbus, \ Maxar Technologies.\
        (2026)
      ]
    ],
    [#image("assets/hessen-rlp-artefact-hessen.png")
      #text(size: 10pt)[
        DTM of Hessen.
      ]
    ],
    [#image("assets/hessen-rlp-artefact-rlp.png")
      #text(size: 10pt)[
        DTM of RLP.
      ]
    ],
    [#image("assets/hessen-rlp-artefact.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Interpolation artefact found over an entire tile for the Hessen DTM. The RLP DTM in the same location is also shown.]
)
#v(1em)
Another example of this occurs at the @RLP – Saarland border (@fig:Extrapolation2). As can be observed in the figure, the valley in blue for the RLP and Saarland images, does not line up between the the two @DTM:pls. Furthermore, the visuals appear smeared in the difference map on the right side (DH), pointing towards values interpolated using a method such as @IDW. In contrast to the previous case, not all of the offending area appears to be interpolated. However, some degree of processing at the border section has caused a disagreement of put to 16 meters in this area.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/RLP-Saarland-Extrapolation2RLP.png", width: 100%)
      #text(size: 10pt)[
        DTM of RLP.
      ]
    ],

    [
      #image("assets/RLP-Saarland-Extrapolation2Saar.png", width: 100%)
      #text(size: 10pt)[
        DTM of Saarland.
      ]
    ],

    [
      #image("assets/RLP-Saarland-Extrapolation2DH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: "Large elevation differences caused by extrapolation artefacts. The artefacts are visible in the Saarland DTM.",
)
<fig:Extrapolation2>
#v(1em)

The last example of this type of artefact is one which was introduced due to our own interpolation. In an effort to interpolate the Dutch @DTM `NoData` values, extrapolation has occured (@fig:Netherlands-border_example). This artefact is created by a disagreement between the border definitions in our Dutch mask and the actual dutch border as it has been clipped. As the mask is slightly expanded, several areas are extrapolated beyond the data available within the Dutch @DTM. Solving this disagreement is a matter up improving the Dutch mask. Furthermore, the availability of @AHN version 6 should eliminate this issue, as it will extend into Germany and beyond the current border mask.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-borderdifferenceAHN.png", width: 100%)
      #align(center)[
        #text(size: 10pt)[
          DTM of The Netherlands' border with NRW.
        ]
      ]
    ],

    [
      #image("assets/Netherlands-NRW-borderdifferenceDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: "Elevation differences introduced along the Netherlands/NRW border caused by interpolation by the authors.",
)
<fig:Netherlands-border_example>
