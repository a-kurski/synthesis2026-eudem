#import "@preview/unify:0.8.1": qty
#import "@preview/drafting:0.2.2"
== Regions of Germany

=== North Rhine-Westphalia / Rhineland-Palatinate

@DE-NW:l, and @DE-RP both fall within the extent of Germany. The overlapping border area is hilly with few water bodies spread throughout the landscape. As with all Germany @DTM data, the tiles are aligned to the same tile grid, and overlap by one or two tiles.

Loading in the `dh_germany_nrw_germany_rlp.tif` raster shows several interesting features. @fig:NRW-RLP-striping shows North-South or South-North scanning tracks created by aerial @lidar scanning. The elevation jump in the order of $3 "cm"$, which while minimal, shows that some differences are caused by the misalignment of the scan passes within tiles.

#figure(
  image("assets/NRW-RLP-striping.png", width:40%),
  caption:[Lidar flight path artefact on the elevation difference raster, magnitude of differences up to #qty("3", "cm").]
)
<fig:NRW-RLP-striping>

Secondly, there appears to be misalignment between tiles within the @DTM. This is illustrated in @fig:NRW-RLP-nonalignment as the sharp transition between the four tiles. This transition is however more drastic at a difference of #qty("30", "cm") in the difference @DTM. On close inspection of the @DE-NW and @DE-RP @DTM:pls, it appears that cells on the edge between tiles, the jump between neighbouring cell values increased with #qty("40", "cm") more on the @DE-NW @DTM, compared to the @DE-RP @DTM. However, it is possible this effect occurs on both the @DE-NW and @DE-RP @DTM:pls.

`statistics_germany_nrw_germany_rlp.csv` corroborates these findings. It lists the similarity of errors within one kilometre to be $99.9%$. High correlation which is consistent throughout the correlation graph either points towards a tiling or vertical transform artefact. The median difference between the two DTMs is $-2"cm"$, which also corresponds with the z-shift for the coregistration.

#figure(
  image("assets/NRW-RLP-nonalignment.png",width:40%),
  caption: "Tiling artefacts on the elevation difference map over the DE-NW/DE-RP border.",
)
<fig:NRW-RLP-nonalignment>

Lastly, as described in @sec:Water_mask_processing, small water bodies such as narrow rivers or small lakes are not filtered out and are therefore counted towards the differences in the comparison. This however, a small contribution and does not appear disproportionately represented in the calculated problem areas.

There do appear to be several differences which are likely related to @lidar sensing limitations or subsequent processing steps. Examples include interpolation errors for buildings (@fig:NRW-RLP-roofinter), ground filtering discrepancies (@fig:NRW-RLP-overpass), temporal changes (@fig:NRW-RLP-quarry)(verified using Google Earth), and steep slopes (@fig:NRW-RLP-slope).

Nevertheless, the overall alignment of the @DE-NW and @DE-RP @DTM:pls does comply with the @INSPIRE target described in @sec:inspire-quality. Furthermore, only $0.05%$ of points within the overlap fall outside of the @INSPIRE derived threshold described in @sec:border-analysis. Therefore, the quality of the resulting @DTM does comply with the guidelines we have followed for the full Rhine @DTM.

#figure(
  grid(
    columns: 4,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-roofinterESRI.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-BW.
      ]
    ],

    [
      #image("assets/NRW-RLP-roofinterNRW.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-NW.
      ]
    ],

    [
      #image("assets/NRW-RLP-roofinterRLP.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],

    [
      #image("assets/NRW-RLP-roofinter.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ]
  ),
  caption: [Example of elevation differences caused by roof interpolations. Red polygons in the leftmost figure indicate areas where the elevation difference exceeds #qty("1.6", "m").],
)
<fig:NRW-RLP-roofinter>

#figure(
  grid(
    columns: 4,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-overpass.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, Maxar Technologies. \
        (2026).
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassNRW.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-NW.
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassRLP.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],

    [
      #image("assets/NRW-RLP-overpassDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Example of a highway overpass, where DE-NW prioritizes the highway as ground, while DE-RP prioritizes the road underneath. The DE-NW and DE-RP rasters were set to 195–215 metres. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:NRW-RLP-overpass>

#figure(
  grid(
    columns: 4,
    gutter: 5pt,

    [
      #image("assets/NRW-RLP-quarry.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, Maxar Technologies. \
        (2026).
      ]
    ],

    [
      #image("assets/NRW-RLP-quarryNRW.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-NW.
      ]
    ],

    [
      #image("assets/NRW-RLP-quarryRLP.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],

    [
      #image("assets/NRW-RLP-quarryDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ]
  ),
  caption: [Example of differences between the DE-NW and DE-RP DTMs, as result of temporal quarry changes. The DE-NW and DE-RP rasters were set to 115–235 metres. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:NRW-RLP-quarry>

#figure(
  image("assets/slope_rmse_germany_nrw_germany_rlp.png",width:60%),
  caption: "RMSE of the elevation difference plotted against terrain slope.",
)
<fig:NRW-RLP-slope>

=== Hessen / Baden-Württemberg

The border between @DE-HE and @DE-BW is one of the shorter borders, coming in at roughly #qty("33", "km"). It does however contain some interesting elements such as an exclave of @DE-HE inside of @DE-BW. This exclave does however not appear to contain any notable differences. Furthermore, the elevations in this region range from $90$ metres in the large and relatively flat valley, to nearly $550$ metres in the hills (@fig:Hessen-BW-overview).

#figure(
  image("assets/Hessen-BW-overview.png",width:40%),
  caption:"DE-HE/DE-BW border. The red polygon shows the overlapping area of the two DTMs."
)
<fig:Hessen-BW-overview>

The first obvious difference is a bright highlight at the border of the @DTM (@fig:Hessen-BW-Borderartefact). This artefact is a byproduct of the @DE-BW dataset being cut differently compared to the @DE-HE dataset. Therefore, this difference is an artefact caused by the clipped dataset and not a real physical difference. This effect occurs on all difference analysis @DTM:pls, though it is not always as pronounced as within this comparison.

#figure(
  image("assets/Hessen-BW-Borderartifact.png",width:40%),
  caption:[DE-HE/DE-BW border artefact. The color scale was set to −1 to #qty("1", "m") to highlight the differences. The red polygon shows the area exceeding the #qty("1.6", "m") threshold.]
)
<fig:Hessen-BW-Borderartefact>

A secondary source of differences appears to be the narrow clearings within wooded areas (@fig:Hessen-BW-clearing). This occurs in several locations. It is unclear exactly why this happens. The uncertainty @DTM representing random error shows a very constant, yet small error of around #qty("3", "cm"). This implies that the observed error is not simply consisting of noise. Observing the @DE-BW @DTM, we see a steep drop in elevation. Streetview furthermore confirms that it is indeed a cliff face. The elevation difference is likely caused by ground filtering or different flight paths during @lidar scanning.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Hessen-BW-clearingESRI.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From AeroWest, Airbus\ Geobasis-DE/BKG.\ (2026)
      ]
    ],

    [
      #image("assets/Hessen-BW-clearingDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Cliff face example, the red polygons show a difference above #qty("1.6", "m") on the ESRI aerial image. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:Hessen-BW-clearing>

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Hessen-BW-clearingUC.png", width: 100%)
      #text(size: 10pt)[
        Uncertainty map.
      ]
    ],

    [
      #image("assets/Hessen-BW-clearingSV.png", width: 100%)
      #text(size: 10pt)[
        Google Street View\ (49.4762° N, 8.4208° E).
      ]
    ],
  ),
  caption: [Cliff face example, random error inspection shows random errors in #qty("3", "cm") range which imply this is not the main cause, Google Street View confirms cliff hypothesis.],
)
<fig:Hessen-BW-clearingEx>

Further artefacts include common elements throughout the catchment @DTM. These include building interpolation differences, quarries/construction sites, and lakes/rivers not caught by the river mask. These errors are expected and can likely only be fixed through the re-extraction of the @DTM, by using both the @DE-HE and @DE-BW point clouds. Nevertheless, the @DE-HE/@DE-BW border falls well within the @INSPIRE threshold, with only 0.06% of points being non-compliant. The alignment of the two @DTM:pls also appears to be accurate, with the coregistration recommending a vertical transform of only $1" cm"$ for the best possible alignment.

=== Saarland / Rhineland-Palatinate
// https://www.welt.de/regionales/rheinland-pfalz-saarland/article205711099/Rheinland-pfaelzische-Landesgrenze-misst-1185-Kilometer.html

The @DE-SL/@DE-RP border is roughly #qty("207", "km") long and consists of mostly hilly terrain. The amount of non-compliant pixels for this area appears slightly higher than that for other regions. However, at 0.15% it is still not a significant amount.

Most errors within this region can be attributed to interpolation errors, temporal changes such as wind turbine construction or quarries, steep slopes, water bodies missed by the mask, and border artefacts. The only notable difference between the @DE-SL and @DE-RP @DTM:pls, appears to be the inclusion of extrapolation artefacts at the borders, as seen in @fig:Saarland-RLP-Extrapolation1 and @fig:Saarland-RLP-Extrapolation2. These are only two out of several occurrences. These large areas of similar errors do explain the secondary peaks seen within the difference histogram (@fig:Saarland-RLP-Histogram). Upon further inspection, there do also appear to be occurrences of overpasses as discussed in @DE-NW/@DE-RP, and cliffs as discussed in @DE-HE/@DE-BW.

All in all, despite issues with the source data, the quality of the @DTM is not affected, due to the region cutoff at the border for the catchment @DTM.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/RLP-Saarland-ExtrapolationBoth.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-RP and DE-SL.
      ]
    ],

    [
      #image("assets/RLP-Saarland-ExtrapolationDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Extrapolation example 1, large negative difference accompanied by feathering of elevation values due to extrapolation. The DE-RP and DE-SL rasters were set to 400–700 metres. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:Saarland-RLP-Extrapolation1>

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/RLP-Saarland-Extrapolation2RLP.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],

    [
      #image("assets/RLP-Saarland-Extrapolation2Saar.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-SL.
      ]
    ],

    [
      #image("assets/RLP-Saarland-Extrapolation2DH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Extrapolation example 2, large positive and negative differences accompanied by feathering of elevation values due to extrapolation. The DE-RP and DE-SL rasters were set to 400–575 metres. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:Saarland-RLP-Extrapolation2>

#figure(
  image("assets/histogram_germany_rlp_germany_saarland.png", width:80%),
  caption: "DE-SL/DE-RP histogram of elevation differences. Secondary peaks around the -30, -20, and 20 metre marks mostly represent extrapolation artefacts.",
)
<fig:Saarland-RLP-Histogram>

#pagebreak()
=== Rhineland-Palatinate / Baden-Württemberg

The @DE-RP/@DE-BW border is a very flat region, which is entirely bisected by the Rhine river. The border region is home to several ports, which also created the greatest source of discrepancy. These ports prominently contain piles of sand and coal which are moved around during the loading and unloading of ships (@fig:RLP-BW-Coal).

Another source of differences are interpolation errors. These are mostly found around the city of Mannheim. These correspond to building roofs. Furthermore, the tile offset found in several of the other datasets also occurs at the @DE-RP/@DE-BW border, as shown in @fig:RLP-BW-TileOffset. More common differences are related to water bodies, overpasses, and construction sites.

The only notable outlier within the data is the convergence of error similarity at 60%, which is explained by the tile offset. The reason why the percentage is so high is due to the small overall range of elevation differences. Overall, the comparison falls well within the allowed threshold and causes no noticeable issues for the full @DTM.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/RLP-BW-CoalESRI.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, GeoBasis-DE/BKG,\
        Maxar Technologies\
        (2026)
      ]
    ],
    [
      #image("assets/RLP-BW-CoalDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Example of elevation differences encountered on a coal storage. The temporal changes in the coal mine cause this difference. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:RLP-BW-Coal>

#figure(
  image("assets/RLP-BW-TileoffsetDH.png"),
  caption: [Elevation differences caused by tiling artefacts. The color scale was set to −0.25 to #qty("0.25", "m") to highlight the differences.],
)
<fig:RLP-BW-TileOffset>

#pagebreak()
// === @DE-HE/@DE-BW
//
// The border between @DE-HE and @DE-BW is one of the shorter borders, coming in at roughly #qty("33", "km"). It does however contain some interesting elements such as an exclave of @DE-HE inside of @DE-BW. This exclave does however not appear to contain any notable differences. Furthermore, the elevations in this region range from $90$ metres in the large and relatively flat valley, to nearly $550$ metres in the hills (@fig:Hessen-BW-overview).
//
// #figure(
//   image("assets/Hessen-BW-overview.png",width:40%),
//   caption: "DE-HE/DE-BW border. The overlapping DTM area is shown by the red polygon.",
// )
// <fig:Hessen-BW-overview>
//
// The first obvious difference is a bright highlight at the border of the @DTM (@fig:Hessen-BW-Borderartefact). The effect. This artefact is a byproduct of the @DE-BW dataset being cut differently compared to the @DE-HE dataset. Therefore, this difference is an artefact caused by the clipped dataset and not a real physical difference. This effect occurs on all difference analysis @DTM:pls, though it is not always as pronounced as within this comparison.
//
// #figure(
//   image("assets/Hessen-BW-Borderartifact.png",width:40%),
//   caption: [Elevation differences caused by DTM border artefacts. The colour scale was set to −1 to #qty("1", "m") to highlight the differences. The red polygon highlights differences with magnitude greater than 1.6 m.],
// )
// <fig:Hessen-BW-Borderartefact>
//
// A secondary source of differences appears to be the narrow clearings within wooded areas (@fig:Hessen-BW-clearing). This occurs in several locations. It is unclear exactly why this happens. The uncertainty @DTM representing random error. It shows a very constant, yet small error of around #qty("3", "cm"). This implies that the observed error is not simply consisting of noise. Observing the @DE-BW @DTM, we see a steep drop in elevation. Streetview furthermore confirms that it is indeed a cliff face. The elevation difference is likely caused by ground filtering or different flight paths during @lidar scanning.
//
// #figure(
//   grid(
//     columns: 2,
//     gutter: 5pt,
//
//     [
//       #image("assets/Hessen-BW-clearingESRI.png", width: 100%)
//       #text(size: 10pt)[
//         Satellite imagery. From AeroWest,
//         Airbus, Geobasis-DE/BKG.
//         (2026)
//       ]
//     ],
//
//     [
//       #image("assets/Hessen-BW-clearingDH.png", width: 100%)
//       #text(size: 10pt)[
//         Elevation difference map.
//       ]
//     ],
//   ),
//   caption: [Elevation differences caused by the presence of a cliff face. The red polygons (left) show a difference greater than 1.6 m. The colour scale was set to −1 to #qty("1", "m") to highlight the differences.],
// )
// <fig:Hessen-BW-clearing>
//
// #figure(
//   grid(
//     columns: 2,
//     gutter: 5pt,
//
//     [
//       #image("assets/Hessen-BW-clearingUC.png", width: 100%)
//       #text(size: 10pt)[
//         Uncertainty map.
//       ]
//     ],
//
//     [
//       #image("assets/Hessen-BW-clearingSV.png", width: 100%)
//       #text(size: 10pt)[
//         Image from Google Street View\
//         (49.4539° N, 8.9474° E)
//       ]
//     ],
//   ),
//   caption: [Cliff face example. Random error inspection shows random errors in #qty("3", "cm") range which imply this is not the main cause. Inspecting Google Street View confirms the presence of the cliff face.],
// )
// <fig:Hessen-BW-clearingEx>
//
// Further artefacts include common elements throughout the catchment @DTM. These include building interpolation differences, quarries/construction sites, and lakes/rivers not caught by the river mask. These errors are expected and can likely only be fixed through the re-extraction of the @DTM, by using both the @DE-HE and @DE-BW point clouds. Nevertheless, the @DE-HE/@DE-BW border falls well within the @INSPIRE threshold, with only 0.06% of points being non-compliant. The alignment of the two @DTM:pls also appears to be accurate, with the coregistration recommending a vertical transform of only $1" cm"$ in vertical direction for the best possible alignment.
//
// #pagebreak()
=== North Rhine-Westphalia / Hessen

Only #qty("59", "km") of @DE-NW/@DE-HE border and 127 1km#sym.times\1km tiles fall into the study area.
Due to the shape of the catchment area, the border is split in two~--- a longer section in the South and a shorter, approximately 3-kilometre section in the North.
Notably, @DE-NW openly publishes point cloud data which enables further analysis, whereas @DE-HE does not.

The errors in this region are relatively low: @RMSE is #qty("18", "cm"), @LE90 is #qty("7.5", "cm"), and only 0.07% of cells exceed the #qty("1.67", "m") difference threshold, suggesting a high agreement between the @DTM:pla.
Still, the biggest differences are #qty("-9", "m") and #qty("22", "m") in the negative and positive direction respectively.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-quarry-satellite.png")],
    [#image("assets/nrw-hessen-quarry.png")],
    [#image("assets/nrw-hessen-roadworks-satellite.png")],
    [#image("assets/nrw-hessen-roadworks.png")]
  ),
  caption: [Elevation difference maps showing areas on the DE-HE/DE-NW border with high elevation differences due to temporal changes. Satellite imagery from Airbus, GeoBasis-DE/BKG, Maxar Technologies.
  ],
)<fig:nrw-hessen-temporal>

Most of the errors which exceed threshold are best explained by the temporal differences in the datasets.
There are two large quarries in the overlapping region, and the earthworks at both sites contribute to the largest errors.
Additionally, there are several places where judging by the historical Google Earth imagery, the error is likely to be due to new or ongoing construction, such as the bridge near the Haiger service station.
Additionally at the time of acquisition, there was snow on the ground in Willingen ski resort which was classified as ground by @DE-NW (@fig:nrw-hessen-snow, snow shown in yellow).

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-snow-satellite.png")],
    [#image("assets/nrw-hessen-snow.png")],
    [#image("assets/nrw-hessen-snow.jpeg", width: 85%)]
  ),
  caption: [Figure 29: Elevation differences caused by the presence of snow in one of the DE-NW surveys. Satellite imagery from Airbus, GeoBasis-DE/BKG, Maxar Technologies.],
)<fig:nrw-hessen-snow>

There are several smaller issues which we believe are best attributed to the differences in processing. The built-up areas display a high number of scattered differences around #qty("0.5", "m") which are likely caused by either the states' approach to ground filtering or interpolation algorithms used to create the original @DTM:pla.
An interesting artefact is a 0.6m-tall "mound" between Wallau and Bad Laasphe.
@DE-NW appears to be using @CSF and extract the heights of synthetic cloth points instead of interpolating authentic ground points~--- we believe the mound is most likely caused by the "sagging" of the simulated cloth (see @fig:nrw-hessen-ground, simulated cloth in yellow), which we verify by examining the point clouds.

#figure(
  grid(
    columns: (1fr, 1fr, 2fr),
    column-gutter: 5pt,
    [#image("assets/nrw-hessen-buildings-satellite.png")],
    [#image("assets/nrw-hessen-buildings.png")],
    [#image("assets/nrw-hessen-warehouse.jpeg")]
  ),
  caption: [Ground and building filtering differences between DE-NW and DE-HE.],
)<fig:nrw-hessen-ground>



=== Hessen / Bavaria

The statistics of the errors along @DE-HE/@DE-BY border are similar to those of @DE-HE/@DE-NW border, but their sources appear to be somewhat different.
Between @DE-HE and @DE-BY, @RMSE is #qty("0.18", "m") and the @LE90 is #qty("0.10", "m"); the minimum and the maximum errors are #qty("-18.35", "m") and #qty("19.07", "m") respectively.

The highest absolute errors can all be traced to temporal changes, specifically the excavation taking place at a single quarry outside Ringheim.
There are additionally some construction works taking place along the border, but there, the magnitude of the errors there is lower.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/bavaria-hessen-quarry-satellite.png")],
    [#image("assets/bavaria-hessen-quarry-elev.png")],
    [#image("assets/bavaria-hessen-quarry.png")],
  ),
  caption: [Elevation differences caused by temporal artefacts between DE-HE and DE-BY.],
) <fig:hessen-bavaria-forest>

More noteworthy are the small (typically around 0.3--#qty("0.5", "m")) differences in rural, especially forested, areas.
These are areas of difference which appear to correspond to linear features in the landscape such as roads, streams, or edges between a forest and an open field. These are likely consequences of the approaches to ground and vegetation classification employed by the different data providers.

Examining the @DE-BY point cloud reveals that all points in the relevant tile are strictly classified into ground (2) and "objects" (20); as well as scan patterns and non-uniform point distribution, largely due to shadowing from trees.
Due to lack of open point cloud data in @DE-HE, the comparison between two states is impossible.

#figure(
  grid(
    columns: (1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-bavaria-pc-forest-bare.jpeg")],
    [#image("assets/hessen-bavaria-pc-forest-trees.jpeg")],
  ),
  caption: [DE-BY point cloud data. Classified ground points in purple.],
) <fig:bavaria-forest-slope>

Another detail evident from the comparison is the difference in approach to estimating the elevation of the water surface.
@DE-HE appears to be relying on the data about the water surface obtained from the point cloud~--- the surface does not appear to be perfectly smooth and seems to contain small artefacts.
@DE-BY instead uses Delaunay triangulation, seemingly based on the lowest point along the shoreline of the water body.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [
      #image("assets/bavaria-hessen-water-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. From AeroWest,
        Airbus, Geobasis-DE/BKG.\
        (2026)
      ]
    ],
    [
      #image("assets/bavaria-hessen-water.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
    [
      #image("assets/bavaria-hessen-water-elev-bavaria.png")
      #text(size: 10pt)[
        DTM of DE-BY.
      ]
    ],
    [
      #image("assets/bavaria-hessen-water-elev-hessen.png")
      #text(size: 10pt)[
        DTM of DE-HE.
      ]
    ]
  ),
  caption: [Differences in water processing between DE-BY and DE-HE.],
)<fig:bavaria-hessen-water>

=== Hessen / Rhineland-Palatinate

The border between @DE-HE and @DE-RP largely follows the Rhine.
Compared to the borders between German states, it has the second-highest @RMSE at #qty("1.30", "m") and the second-highest @LE90 at #qty("0.19", "m"). It also has the second-highest absolute error at #qty("-61.56", "m").
High @RMSE can largely be attributed to errors due to processing in one particular tile; high @LE90 is a symptom of systematic errors.

One of the tiles @DE-HE includes in its elevation dataset is almost entirely interpolated~--- seemingly using two interpolation methods: linear interpolation on a TIN where sample points are available; and another method where data was not available.
@DE-HE does not publish the point cloud data, yet having observed raster elevation data, we believe that the entire tile was cropped out from the point cloud survey as it only contained partial data.
A small part of @DE-HE still falls within that tile; and it was re-included by @DE-HE during the raster processing phase, interpolated based on the ground points from the neighbouring tiles.
It is unclear what the elevation of the southwest extreme point is based on.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-artefact-satellite.png")
    #text(size: 10pt)[
      Satellite imagery. From AeroWest,
      Airbus, Geobasis-DE/BKG.\
      (2026)
      ]
    ],
    [
      #image("assets/hessen-rlp-artefact-hessen.png")
      #text(size: 10pt)[
        DTM of DE-HE.
      ]
    ],
    [
      #image("assets/hessen-rlp-artefact-rlp.png")
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],
    [#image("assets/hessen-rlp-artefact.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Interpolation artefact by DE-HE.],
)

Systematic errors can be observed throughout the region where, especially on hilly terrain, there is a relatively consistent 5--#qty("20", "cm") difference between the two @DTM:pla.
There are visible seams in the difference map where two tiles meet, which likely point at either a different ground filtering algorithm or a misalignment between two different surveys carried out by the same provider.
The hilly terrain makes it impossible to confidently conclude which of the data providers is responsible for this error based on raster data alone.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-tiling-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. From AeroWest,
        Airbus, Geobasis-DE/BKG.\
        (2026)
        ]
      ],
    [
      #image("assets/hessen-rlp-tiling-hessen.png")
      #text(size: 10pt)[
        DTM of DE-HE.
      ]
    ],
    [
      #image("assets/hessen-rlp-tiling-rlp.png")
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],
    [#image("assets/hessen-rlp-tiling.png")
      #text(size: 10pt)[
        Elevation difference map.
        ]
      ],
  ),
  caption: [Example of systematic difference between DE-HE and DE-RP.],
)

Smaller errors are also visible in building footprints, where both providers are performing linear interpolation on a TIN but based on somewhat different set of points.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-buildings-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. From AeroWest,
        Airbus, Geobasis-DE/BKG.\
        (2026)
        ]
    ],
    [
      #image("assets/hessen-rlp-buildings-hessen.png")
      #text(size: 10pt)[
        DTM of DE-HE.
      ]
    ],
    [
      #image("assets/hessen-rlp-buildings-rlp.png")
      #text(size: 10pt)[
        DTM of DE-RP.
      ]
    ],
    [#image("assets/hessen-rlp-buildings.png")
      #text(size: 10pt)[
        Elevation difference map.
        ]
    ],
  ),
  caption: [Interpolation differences between DE-HE and DE-RP.]
)

=== Baden-Württemberg / Bavaria
The @DE-BW/@DE-BY border is similar to the @DE-NW/@DE-HE border, as it is split in two sections due to the catchment area shape. For this region @DE-BY provides point cloud data, whereas @DE-BW does not. This means that point cloud comparisons will not be possible for this border region.

#figure(
  image("assets/BW-Bavaria-Border.png",width:40%),
  caption: "DE-BW/DE-BY border is divided into a northern and southern section in the catchment area.",
)
<fig:BW-Bavaria-Border>

The border area appears to display two main artefacts. The first of these being a pronounced difference @DTM edge (@fig:BW_Bavaria_Borderartefact). However, this effect only appears at the southern border, and appears absent from the northern border. The cause of this artefact is that the @DE-BW @DTM appears to have two `NoData` values. The metadata states that the `NoData` value is at $-9999$, while the value in the black area is 0 before the vertical transform. The code currently corrects for this artefact. However, the border edge still has traces of this effect due to the rotation applied during the horizontal transform, and the interpolation that occurs at that stage. These errors make up almost 25% of all designated problem areas. @fig:BW-Bavaria-Borderartefact-Histo illustrates the effect this has on the total error distribution for the border comparison. Nearly all values below $-5$ metres can be attributed to this effect.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/BW-Bavaria-BorderartifactBW.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-BW.
      ]
    ],

    [
      #image("assets/BW-Bavaria-BorderArtifactDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Border artefact caused by DE-BW using both a 0 and -9999 `NoData` value, while only declaring the -9999 value as `NoData`. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
)
<fig:BW_Bavaria_Borderartefact>

#figure(
  image("assets/histogram_germany_bw_germany_bavaria.png",width:60%),
  caption: [DE-BW/DE-BY border elevation differences histogram. This region appears to be strongly affected by the edge artefacts caused by the effect of 0 as `NoData` value and bilinear interpolation during CRS transformation, with elevation differences of up to 1000 m of magnitude.],
)
<fig:BW-Bavaria-Borderartefact-Histo>

The second artefact within this border comparison is similar to the one encountered in @DE-NW/@DE-RP section. In this instance, the effect clearly occurs in the @DE-BY @DTM. @fig:BW-Bavaria-Discrete shows this effect. It appears as if these specific tiles are separate from the rest of the @DTM as it contains both positive and negative differences, meaning it cannot be the result of a vertical shift. Zooming in on the border confirms that these different tiles exist in @DE-BY, shown by the faint line at the same line as the elevation difference map. The cause for this can be that the tiles have either been collected at a different time, or that the acquisition was done through another method.

#figure(
  image("assets/BW-Bavaria-DiscreteDH.png",width:60%),
  caption: "Elevation differences appearing like tiling artefacts. Pronounced red and blue regions show larger differences.",
)
<fig:BW-Bavaria-Discrete>

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/BW-Bavaria-Discrete-zoomDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],

    [
      #image("assets/BW-Bavaria-Discrete-zoomBavaria.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-BY.
      ]
    ],

    [
      #image("assets/BW-Bavaria-Discrete-zoomBW.png", width: 100%)
      #text(size: 10pt)[
        DTM of DE-BW.
      ]
    ],
  ),
  caption: "Discrete tile step zoomed, shows DE-BY mirrors the tile step observed in the difference DEM.",
)
<fig:BW_Bavaria_DiscreteZoom>

Several other errors exist within the border comparison. These are in line with the errors encountered at other borders. These include interpolation errors, differences in ground filtering (differences in overpass handling), temporal changes (mostly due to quarries or construction areas), differences due to watermask shortcomings (including small pools, small lakes, creeks), steep slopes

For this border comparison, the @INSPIRE target is not met. The amount of points above the threshold is only $0.14%$. However, the total @RMSE is #qty("5.36", "m")~--- a factor $3.2$ greater than what it is allowed to be for the $5$ metre resolution. These statistics suggest this border pair is of unacceptable quality; however, the error regions get overwritten and thus do not introduce any conflicts within the final product. Solving this problem does not fall within the scope or time constraints of this project, and is primarily a challenge created due to available input data and not by the processing pipeline.

#pagebreak()



== Luxembourg
=== Luxembourg / France

The border area between Luxembourg and France is roughly #qty("50", "km") long and consists of more even terrain in the east and increasingly hilly terrain in the west with deviations of over #qty("100", "m") at relatively short distances. As can be seen in @fig:Lux_Fra_border, most of the western region of the border is flagged as having a deviation greater than the resolution-RMSE ratio.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/France-Lux-borderarea.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],

    [
      #image("assets/France-Lux-borderarea-issues.png", width: 100%)
      #text(size: 10pt)[
        Flagged Differences.
      ]
    ],
  ),
  caption: "Overlaping border DTM region for LU/FR. The western section of the border almost entirely exceeds the 1.6 metre resolution threshold, shown by the red polygons (right).",
)
<fig:Lux_Fra_border>

As a primary example of this phenomenon the area around Rumelange was more closely evaluated. Unlike most border regions, the differences are not limited to isolated artefacts, but affect most of the border area. A prominent example is the area around Rumelange. Inspecting the DTM shows that the area is populated with steep slopes, valley sides, ridges and cliff faces (@fig:Lux_Fra_Rumelange).

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/France-Lux-Rumelange.png", width: 100%)
      #text(size: 10pt)[
        Flagged Differences.
      ]
    ],

    [
      #image("assets/France-Lux-Rumelange-elevation.png", width: 100%)
      #text(size: 10pt)[
        DTM.
      ]
    ],
  ),
  caption: "Elevation difference in Rumelange, Luxembourg. The DTM shows a hilly terrain, which corresponds to primary areas of disagreement.",
)
<fig:Lux_Fra_Rumelange>

Further examining the uncertainty pattern of the border region further supports these observations (@fig:Lux_Fra_Rumelange_uncertainty). Areas with high uncertainty (shown in red), represent elevation differences due to random errors of $1.6$ metres, while low uncertainty regions (in blue), correspond with the regions of small differences in the elevation difference map. Due to the respective national @DTM:pls being generated from @lidar data, small differences in sample point locations can create large differences in the elevation of a point. This effect becomes more pronounced due to the #qty("5", "m") resolution of the French @DTM and the #qty("0.5", "m") resolution of the Luxembourg @DTM.

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
      #image("assets/France-Lux-Rumelange-uncertainty.png", width: 100%)
      #text(size: 10pt)[
        Uncertainty map.
      ]
    ],
  ),
  caption: [Random elevation differences due to sloped terrain appear (in red) up to values of 5 metres. The uncertainty map shows random errors with a colour scale of −1.5 to #qty("1.5", "m").],
)
<fig:Lux_Fra_Rumelange_uncertainty>

Influence of the slope on the @RMSE can also be observed directly from the @RMSE analysis (@fig:Lux_Fra_Rumelange_slope). Areas with a slope above 5 degrees have an @RMSE surpassing #qty("4", "m"). This behaviour deviates from most other border regions where the RMSE gradually increases with slope. The result suggests that the steep terrain is one of the dominant causes of disagreement between the two @DTM:pls.

#figure(
  image("assets/slope_rmse_france_luxembourg.png",width:60%),
  caption: [RMSE of elevation differences against slope of the terrain. RMSE grows strongly with higher slope, up to #qty("5.5", "m") at 40 degree slopes.],
)
<fig:Lux_Fra_Rumelange_slope>

Further artefacts within the region do more closely correspond with the rest of Luxembourg and the border regions in general. These include building interpolation differences, narrow streams not captured by the river mask, and isolated quarry or construction areas. This region does not comply with the thresholds set within @chap:method, with 23% of all points surpassing the threshold. Furthermore, the resolution would need to be increased by over 80% to nearly #qty("10", "m") for compliance with the @INSPIRE target. As alluded to earlier, this difference may be a byproduct of the low-resolution @DTM compared to the fine resolution of the Luxembourg @DTM, which has introduced resampling differences. While outside of the time constraint of the project, evaluating the results of the comparison against the higher resolution French @DTM could result in better alignment. Alternatively, re-extraction from the national point clouds could also be a way to rectify these differences.

=== Luxembourg / Rhineland-Palatinate
The @LU/@DE-RP border is roughly #qty("80", "km") long. On the east side of the overlapping area there is the Our river. Observing the overlap map shows that the rivermask was not successful at filtering out the water bodies entirely for the region. This is a known artefact caused by narrow water bodies. Furthermore, these river areas have been flagged as noticeable differences and count towards the difference at the border.

Other differences in this region are in line with the other borders surrounding Luxembourg, such as river ports with piled resources, steep cliffs, construction areas and building interpolation differences. The only real artefact that shows up on the histogram, is a singular secondary peak. Observing the difference @DTM, shows that this is caused by a lake, which was missed by the river mask. This is illustrated in @fig:Lux-rlp-peak as a peak starting at #qty("700", "m"). The border effect graph also clearly illustrates the difference at the border river.

#figure(
  image("assets/border_effect_germany_rlp_luxembourg.png"),
  caption: [Elevation differences plotted against distance from border. River differences (#qty("0", "m")), lake river mask failure (700 – #qty("1200", "m")).],
)
<fig:Lux-rlp-peak>

=== Luxembourg / Saarland
The border area between Luxembourg and @DE-SL is roughly #qty("11", "km") and like @DE-RP/@DE-BW, is entirely bisected by a river, that being the Mosel in this particular case. The border area consists of flat areas around the river and consists of hills and cliffs on the west side.

This region contains several of the more common differences encountered in other regions can also be found here. This includes harbour loading areas for sand, steep cliffs, construction sites, water bodies not entirely caught by the river mask, and roof interpolation differences.

The only unique error found around this area is the inclusion of hydroelectric power plants. While this difference can really be attributed to the limits of the river mask, it is an interesting feature within the water which could pose a challenge to solve should improving the river mask be attempted as the water here does not follow the smooth water hypothesis. Furthermore, the decision would need to be made if the plant should be removed entirely. This depends on whether all countries model this feature in their @DTM, or simply classify it as part of the river, removing it from the @DTM entirely.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Lux-Saarland-HydroGoogle.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, Maxar Technologies. \
        (2026).
      ]
    ],

    [
      #image("assets/Lux-Saarland-HydroDH.png", width: 100%)
      #text(size: 10pt)[
        Non-continuous river mask.
      ]
    ],
  ),
  caption: "River mask failure where the mask is not continuous due to a hydroelectric power plant.",
)
<fig:Lux-Saarland-Hydro>

For this region, the percentage of points above the @INSPIRE threshold, is around $1%$. While above average, this is caused by the fact that it is a small region, where the spatial dimensions of the differences remain consistent with differences found in other regions. Nevertheless, the difference @DTM falls well within the @INSPIRE target threshold, and contains no significant errors such as border extrapolation, misaligned tiles or inexplicable differences.

== Germany / France

=== Saarland / France <sec:saarland-france>

The approximately #qty("157", "km") border between @DE-SL and France crosses rolling hills, forested slopes and river valleys, with sections following the Saar and Blies rivers. Across the compared overlap, the two DTMs generally agree closely: the mean elevation difference is +0.035 m and the median is #qty("-0.020", "m"), where positive differences indicate higher elevations in @DE-SL. Half of the absolute differences are below #qty("0.163", "m"), and 90% are below #qty("0.981", "m"). Nevertheless, the RMSE reaches #qty("1.213", "m"), reflecting substantial discrepancies at particular locations.

These discrepancies are concentrated rather than evenly distributed. Only 5.81% of the compared area exceeds the #qty("1.667", "m") comparison threshold, yet this portion contributes approximately 90% of the total squared elevation difference. Differences greater than #qty("5", "m") occupy just 1.27% of the area but contribute about 63% of that total. The distribution therefore has a narrow centre and long tails, with extremes from approximately #qty("-22", "m") to +33 m. Neighbouring positive and negative differences partly cancel, so the small mean understates the local disagreement.

The Google Earth inspections and corresponding difference maps place these results in their terrain context. In @fig:saarland-france-region1, the long dark blue difference pattern on the right corresponds to a cliff visible in the Google Earth imagery on the left. The pronounced discrepancies follow this abrupt terrain edge, with additional patches within the surrounding woodland. In @fig:saarland-france-region2, the largest differences on the right coincide with an apparent valley-like terrain feature visible on the left. These selected examples illustrate recurring settings of disagreement rather than representing every location along the border.

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      [
        #image("assets/region1_bare.png", width: 100%, height: 43mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Google Earth Imagery. From Airbus, Landsat/Copernicus.
        ]
      ],
      [
        #image("assets/region1_dtm.png", width: 100%, height: 43mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Elevation difference map.
        ]
      ],
    ),
    caption: [Elevation differences in forested area with small cliff faces.],
  ) <fig:saarland-france-region1>
]

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      [
        #image("assets/region2_bare.png", width: 100%, height: 43mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Google Earth Imagery. From Airbus, Landsat/Copernicus.
        ]
      ],
      [
        #image("assets/region2_dtm.png", width: 100%, height: 43mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Elevation difference map.
        ]
      ],
    ),
    caption: [Elevation differences on terrain with abrupt elevation changes.],
  ) <fig:saarland-france-region2>
]

Terrain steepness is the strongest quantified association. RMSE rises from approximately #qty("0.8", "m") on slopes of 0–5° to #qty("2.7", "m") at 20–25° and #qty("5.6", "m") at 45–50°. This supports the visual observation that steep slopes and rapidly changing relief are particularly problematic. Forest cover is a recurring characteristic of the inspected hotspots, although its contribution has not been quantified separately from slope. Differences in ground filtering beneath canopy and restricted ground observations in narrow valleys are possible contributors. In @fig:saarland-france-region3, the largest differences, shown as dark blue patches, coincide with forested areas identified during the visual inspection. Nearby patches of contrasting differences further illustrate how substantial local mismatches can cancel in the regional mean.

#align(center)[
  #block(breakable: false)[
    #figure(
      image("assets/region3_dtm.png", width: 76%),
      caption: [Large patches of high elevation differences.],
    ) <fig:saarland-france-region3>
  ]
]

Differences in DTM acquisition dates may also introduce temporal artefacts. The datasets may capture different stages of excavation, earthworks or vegetation clearance, while seasonal differences may affect the vegetation conditions under which the ground surface was estimated. Recently cleared areas identified during the Google Earth inspection suggest a possible influence of acquisition timing, particularly if an older surface retains residual vegetation effects. Some discrepancies may therefore reflect genuine terrain changes between surveys or changes in residual vegetation influence. The individual contributions of these processes have not been established from the selected examples.

The quarry in @fig:saarland-france-quarry provides a clear setting in which acquisition timing may matter. Strong differences trace excavation faces and terraced edges. If the DTMs were acquired at different times, excavation or material deposition between surveys could have changed the height and position of these features. The discrepancies may therefore partly reflect different stages of quarry development, alongside differences in how the DTMs represent steep faces and sharp terrain edges.

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      [
        #image("assets/quary_bare.png", width: 100%, height: 43mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Satellite imagery. From Airbus, CNES. \
          (2026)
        ]
      ],
      [
        #image("assets/quary_dtm.png", width: 100%, height: 43mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Elevation difference map.
        ]
      ],
    ),
    caption: [Elevation differences caused by temporal changes in a quarry.],
  ) <fig:saarland-france-quarry>
]

The regional RMSE is driven primarily by a limited set of pronounced local mismatches. Steep and complex terrain provides the clearest quantitative association, while the inspected images highlight forest cover, exposed escarpments and excavation features as recurring settings. Differences in acquisition timing are an additional possible contributor where the landscape has changed between surveys. Most of the overlap agrees much more closely than the overall RMSE suggests.

=== Rhineland-Palatinate / France <sec:rlp-france>

The border between @DE-RP and France is approximately #qty("112", "km") long and crosses predominantly hilly, forested terrain, particularly through the Pfälzerwald, which continues into France as the Northern Vosges. The Rhine does not form the main boundary, only the easternmost section approaches the Upper Rhine, while much of the border runs over land and partly follows smaller watercourses such as the Lauter. Castle ruins and distinctive rock formations are also characteristic features of this region.

Elevation differences are defined as @DE-RP minus France, so positive values indicate a higher @DE-RP surface. The mean difference is #qty("-0.033", "m") and the median is #qty("-0.032", "m"). Half of the absolute differences are below #qty("0.079", "m") and 90% are below #qty("0.225", "m"). The RMSE of #qty("0.260", "m"), compared with an NMAD of #qty("0.113", "m"), indicates that a relatively small number of large discrepancies strongly influence the overall result.

@fig:rlp-france-distribution shows the narrow central distribution and the longer tails. Only 0.237% of the compared area, equivalent to 0.670 km², exceeds the #qty("1.667", "m") comparison threshold, yet these cells contribute 60.4% of the total squared elevation difference. Differences greater than #qty("5", "m") occupy just 0.044% of the area but contribute 36.3% of that total. Most of the overlap therefore agrees closely, while a small number of locations require separate investigation.

#block(breakable: false)[
  #figure(
    image("assets/rlp_france_distribution.png", width: 100%),
    caption: [Central distribution and full-distribution exceedance curve. The left figure shows the distribution of the regional differences around the mean. Values outside ±0.6 m are not shown for visual simplicity. The right figure shows the percentage of all compared cells exceeding the absolute-difference threshold.],
  ) <fig:rlp-france-distribution>
]

The spatial overview in @fig:rlp-france-spatial distinguishes broad patterns of signed difference from concentrated large discrepancies. The ten largest problem regions lie at the western end of the overlap and contain 73.7% of all area above the threshold. The first five of those regions are shown in @fig:rlp-france-spatial and contain 60.0%. However, the strongest individual differences are not in the regions with the biggest concentration of high difference. The locations of the largest individual differences are shown in @fig:rlp-france-extremes.

#block(breakable: false)[
  #figure(
    image("assets/rlp_france_spatial.png", width: 100%),
    caption: [Elevation differences over the entire border between DE-RP and FR. From top to bottom: mean signed difference, RMSE, and percentage of compared area exceeding #qty("1.667", "m"). Numbers identify the five largest problem regions. Extreme values go over the displayed limits by the colour scheme.],
  ) <fig:rlp-france-spatial>
]

#block(breakable: false)[
The inspected locations in @fig:rlp-france-extremes place the largest differences in their physical setting. The minimum of #qty("-30.37", "m") occurs at Fleckenstein Castle (49.0449° N, 7.7723° E), where the French DTM is higher. The maximum of +34.54 m occurs at the Klein Arsberg ruins (49.0386° N, 7.6904° E), where the @DE-RP DTM is higher. Another pronounced positive difference was identified at the nearby rock opening (49.0392° N, 7.6931° E). These photographs were taken from public contributions found in Google Maps, and they provide terrain context rather than a direct measurement of DTM error.
]

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr, 1fr),
      column-gutter: 7pt,
      [
        #image("assets/rlp_france_fleckenstein.png", width: 100%, height: 58mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Fleckenstein Castle.
        ]
      ],
      [
        #image("assets/rlp_france_klein_arsberg.png", width: 100%, height: 58mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Klein Arsberg ruins.
        ]
      ],
      [
        #image("assets/rlp_france_rock_opening.png", width: 100%, height: 58mm, fit: "contain")
        #v(3pt)
        #text(size: 10pt)[
          Nearby rock opening.
        ]
      ],
    ),
    caption: [Terrain settings of selected large differences. The left and centre photographs show the locations largest negative and positive elevation differences respectively. The photograph on the right shows another location with large positive elevation difference. Photos from Google Maps.],
  ) <fig:rlp-france-extremes>
]

Different treatment of ruins and exposed rock during ground classification, followed by interpolation across removed or sparsely sampled features, could produce these local discrepancies. Forest canopy may further limit ground observations around the sites. A raster DTM stores one elevation per horizontal cell and cannot explicitly represent both the top and underside of an overhang. The #qty("5", "m") grid also smooths narrow rock edges. Consequently, disagreement at these locations may reflect different representations of complex terrain as well as processing errors. Verification requires the original classified point clouds and source-resolution DTMs, cross-sections through the exact cells, and an independent survey or reliable terrain reference. Acquisition dates and processing specifications are needed to distinguish temporal change from classification and interpolation effects.

@fig:rlp-france-patterns shows a different type of discrepancy: broad, approximately parallel bands extending across multiple fields and woodland areas. This pattern suggests an acquisition or processing component rather than terrain features. They resemble artefacts originating from flight line patterns. Survey trajectories and strip identifiers should be compared with the bands, and overlapping point-cloud strips examined separately.

#block(breakable: false)[
  #figure(
    image("assets/rlp_france_patterns.png", width: 100%),
    caption: [Flight-path artefacts over the border region. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
  ) <fig:rlp-france-patterns>
]

=== Baden-Württemberg / France <sec:bw-france>
The @DE-BW (@DE-BW)–France comparison shows close agreement across much of the Rhine corridor, interrupted by pronounced local discrepancies and coherent spatial patterns. Across 166.52 km² of valid overlap at #qty("5", "m") resolution, the mean elevation difference is +0.034 m and the median is +0.058 m, where positive values mean that @DE-BW is higher than France. The RMSE of #qty("0.730", "m") is considerably larger than the NMAD of #qty("0.153", "m"), indicating that large local differences have a strong influence on the overall result.

The difference distribution has a narrow centre and long tails. 95% of the absolute differences are below #qty("1.059", "m"). Only 2.744% of compared cells exceed the configured #qty("1.667", "m") threshold, but these cells occupy 4.57 km² and contribute 82.73% of the total squared difference. Differences larger than #qty("5", "m") occupy just 0.397%. The extremes range from #qty("-25.96", "m") to +46.72 m of elevation difference.

@fig:bw-france-north-south shows the strongest regional contrast, between the southern overlap and the remainder of border. The southern segment of the border region contains 89.82% of all threshold-exceeding cells and 85.53% of total squared difference. Its RMSE is #qty("1.680", "m"), compared with #qty("0.303", "m") in the northern segment. Exceedance rates are 15.26% and 0.333% for the two segments, respectively. NMAD also rises from #qty("0.132", "m") in the north to #qty("0.661", "m") in the south, showing that the southern disagreement affects the broader distribution as well as its most extreme values.

#block(breakable: false)[
  #figure(
    image("assets/bw_france_north_south_profile.png", width: 100%),
    caption: [Regional variation of elevation differences in the DE-BW/FR border. RMSE, threshold exceedances and compared area in #qty("10", "km") northing bands. The southern bands have substantially larger differences despite containing less compared area than several northern bands. Coverage refers to the available overlap.],
  ) <fig:bw-france-north-south>
]

Alongside these large local differences, @fig:bw-france-patterns shows flight-line-like bands similar to those in the @DE-RP/@FR comparison (@fig:rlp-france-patterns). The comparative visual inspection identifies bands running in the same direction and matching exactly with the @DE-RP/@FR patterns. Because the French DTM is common to both comparisons, this correspondence strongly suggests an origin in the French acquisition and the relative alignment or adjustment of its flight paths. The spatially varying bands are consistent with residual differences between flight strips that persist across the two regional comparisons. Flight-line footprints and adjustment records would allow this interpretation to be tested directly and help distinguish acquisition effects from later processing.

#align(center)[
  #block(breakable: false)[
    #figure(
      image("assets/bw_france_patterns.png", width: 68%),
      caption: [Flight-path artefacts over the border region. The color scale was set to −1 to #qty("1", "m") to highlight the differences.],
    ) <fig:bw-france-patterns>
  ]
]


== Switzerland

=== Switzerland / France

Overall, the border between France and Switzerland contains errors similar to those found on the French--German border.
These include one instance of striping, most visible in the suburbs of Basel.
The stripe appears to follow the edge of the French @DTM, which further points towards it being caused by poorly aligned flight-paths.

#figure(
  image("assets/fr-ch-flightpath.png", width: 40%),
  caption: [Flight-path artefacts between FR and CH.],
)

There is also a large artefact in the forested region near Pfetterhouse.
In the French @DTM, the elevation of peaks appears to be underestimated while the elevation of valleys is overestimated~--- essentially, the @DTM is over-smoothed.
We speculate that regions like this come from a different survey with different approach to ground filtering (perhaps ground is estimated with a global interpolation function) but we have not been able to verify or falsify this hypothesis.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [
      #image("assets/fr-ch-forest-ch.png")
      #text(size: 10pt)[
        DTM of CH.
      ]
    ],
    [
      #image("assets/fr-ch-forest-fr.png")
      #text(size: 10pt)[
        DTM of FR.
      ]
    ],
    [#image("assets/fr-ch-forest.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Ground filtering differences between CH and FR.],
)

=== Switzerland / Baden-Württemberg

The border between Switzerland and @DE-BW largely follows the Rhine between Konstanz and Basel and notably includes Büsingen, an exclave of @DE-BW within Switzerland.
The regions are overall well-aligned with @LE90 of only #qty("0.12", "m") but a high @RMSE of #qty("0.4", "m").

The largest errors are best explained by temporal differences~--- like in other areas examined above, there are several quarries present near the border. The largest of them is located northeast of Schaffhausen and is responsible for the largest differences in elevation, up to #qty("30", "m").

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-quarry-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. From Airbus, CNES\ 2026.
      ]
    ],
    [
      #image("assets/ch-bw-quarry-ch.png")
      #text(size: 10pt)[
        DTM of CH.
      ]
    ],
    [
      #image("assets/ch-bw-quarry-bw.png")
      #text(size: 10pt)[
        DTM of DE-BW.
      ]
    ],
    [#image("assets/ch-bw-quarry.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Temporal differences between CH and DE-BW.],
)

A more unique error is due to ground filtering, as can be observed with the industrial complex north of Stein, where differences between the different ground filtering/interpolation methods can exceed #qty("3", "m"). As is evident from the difference mask, both data providers use TIN to interpolate the terrain but a different set of points for constructing said TIN. A likely misclassification of the ground, perhaps due to shadowing or multipath errors, causes the error in the elevation of ground points and therefore the error in the TIN.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-buildings-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. From Airbus, CNES\ 2026.
      ]
    ],
    [
      #image("assets/ch-bw-buildings-ch.png")
      #text(size: 10pt)[
        DTM of CH.
      ]
    ],
    [
      #image("assets/ch-bw-buildings-bw.png")
      #text(size: 10pt)[
        DTM of DE-BW.
      ]
    ],
    [#image("assets/ch-bw-buildings.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Differences in building processing between CH and DE-BW.],
)

Ground and vegetation filtering also have an effect on forested slopes between Hallau and Eggingen where minor striping can be observed. The stripes appear to be running perpendicular to the slope and, we speculate, can be symptomatic of either differences in ground processing by data providers; or they could be a resampling artefact. We recommend performing point cloud analysis to validate either of these hypotheses, which was skipped due to time constraints of the project.

Similarly to the building interpolation, there is also an observable difference in the water surface. Switzerland appears to be using a hydro-flattening approach whereas @DE-BW is instead using linear interpolation on a TIN.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-water-satellite.png")
      #text(size: 10pt)[
        Satellite imagery. From Airbus, CNES\ 2026.
      ]
    ],
    [
      #image("assets/ch-bw-water-ch.png")
      #text(size: 10pt)[
        DTM of CH.
      ]
    ],
    [
      #image("assets/ch-bw-water-bw.png")
      #text(size: 10pt)[
        DTM of DE-BW.
      ]
    ],
    [#image("assets/ch-bw-water.png")
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: [Differences in water processing between CH and DE-BW.],
)

== Germany / Netherlands

=== Netherlands / North Rhine-Westphalia
The border between the Netherlands and @DE-NW is approximately #qty("50", "km") long, is mainly flat, but also contains large hills. The main error found within this region is unfortunately a byproduct of our attempt to interpolate the non-interpolated regions of the Netherlands (@fig:Netherlands-NRW-border). These errors are found primarily in the form of extrapolation errors found at various positions along the border. This is a discrepancy caused by differences in the specified borders for the Netherlands within the interpolation algorithm, and has been later resolved by changing the border dataset

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-borderdifferenceAHN.png", width: 100%)
      #text(size: 10pt)[
        DTM of NL.
      ]
    ],

    [
      #image("assets/Netherlands-NRW-borderdifferenceDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: "Border artefact caused by interpolation at the border.",
)
<fig:Netherlands-NRW-border>

Other errors within this region include both small and large scale earthworks. Examples include the "Steenfabriek de Bijland", which also includes swampy areas, which are not caught by the river mask (@fig:Netherlands-NRW-Lworks). Another example includes storage of manure and dirt at farms scattered throughout the border area (@fig:Netherlands-NRW-Sworks).

For this border area in particular, there is a strong effect of water bodies on the difference. The RMSE increases by 10% if the water bodies are included, compared to the case without. This is likely due to the attempt at interpolating the river areas, which will differ from the approach taken in the German region, which most often involves triangulation of the water surface.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-StoneSwampGoogle.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, Maxar Technologies. \
        (2026).
      ]
    ],

    [
      #image("assets/Netherlands-NRW-StoneSwampDH.png", width: 100%)
      #text(size: 10pt)[
        Incomplete river mask.
      ]
    ],
  ),
  caption: "Example of a region whre the river mask is incomplete/non-continuous.",
)
<fig:Netherlands-NRW-Lworks>

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-FarmsGoogle.png", width: 100%)
      #text(size: 10pt)[
        Satellite imagery. From Airbus, Maxar Technologies. \
        (2026).
      ]
    ],

    [
      #image("assets/Netherlands-NRW-FarmsDH.png", width: 100%)
      #text(size: 10pt)[
        Elevation difference map.
      ]
    ],
  ),
  caption: "Elevation differences caused by small earthworks.",
)
<fig:Netherlands-NRW-Sworks>
