#import "@preview/drafting:0.2.2"
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
==== Saarland -- RLP
https://www.welt.de/regionales/rheinland-pfalz-saarland/article205711099/Rheinland-pfaelzische-Landesgrenze-misst-1185-Kilometer.html

The Saarland -- @RLP border is roughly $207$ kilometers long and consists of mostly hilly terrain. The amount of non-compliant pixels for this area appears slightly higher than that for other regions. However, at 0.15% it is still not a significant amount.

Most errors within this region can be attributed to interpolation errors, temporal changes such as windmill construction or quarries, steep slopes, waterbodies missed by the mask, and border artifacts. The only notable difference between the Saarland and @RLP @DTM:pls, appears to be the inclusion of extrapolation artifacts at the borders, as seen in @fig:Saarland-RLP-Extrapolation1 and @fig:Saarland-RLP-Extrapolation2. These are only two out of several occurances. These large areas of similar errors do explain the secondary peaks seen within the difference histogram (@fig:Hessen-BW-BorderArtifact). Upon further inspection, there do also appear to be occurances of overpasses as discussed in @NRW -- @RLP, and cliffs as discussed in Hessen -- @BW.

All in all, despite issues with the source data, the quality of the @DTM is not affected, due to the region cutoff at the border for the catchment @DTM.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/RLP-Saarland-ExtrapolationBoth.png", width: 100%)
      #align(center)[(RLP + Saarland)]
    ],

    [
      #image("assets/RLP-Saarland-ExtrapolationDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Extrapolation example 1",
)
<fig:Saarland-RLP-Extrapolation1>

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
  caption: "Extrapolation example 2",
)
<fig:Saarland-RLP-Extrapolation2>

#figure(
  image("assets/histogram_germany_rlp_germany_saarland.png", width:80%),
  caption:"Saarland-RLP Histogram"
)
<fig:Saarland-RLP-Histogram>

#pagebreak()
==== RLP -- BW

The @RLP -- @BW border is a very flat region, which is entirely bisected by the Rhine river. The border region is home to several ports, which also created the greatest source of discrepancy. These ports prominently contain piles of sand and coal. Because these sources shift during the loading and unloading of ships (@fig:RLP-BW-Coal).

Another source of differences are interpolation errors. These are mostly found around the city of Mannheim. These are the common example of building roofs. Furthermore, the tile offset found in several of the other datasets also occurs at the @RLP -- @BW border, as shown in @fig:RLP-BW-TileOffset. More common differences related to waterbodies, overpasses, and construction sites.

The only notable outlier within the data is the convergence of error similarity at 60%, which is explained by the tile offset. The reason why the percentage is so high is due to the small over all range of elevation differences. Over all, the comparison falls well within the allowed threshold and causes no noticable issues for the full @DTM.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/RLP-BW-CoalESRI.png", width: 100%)
      #align(center)[(ESRI)]
    ],

    [
      #image("assets/RLP-BW-CoalDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Coal storage example",
)
<fig:RLP-BW-Coal>

#figure(
  image("assets/RLP-BW-TileoffsetDH.png"),
  caption:"Tile offset example"
)
<fig:RLP-BW-TileOffset>

#pagebreak()
==== Hessen -- BW

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

#figure(
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/bavaria-hessen-quarry-satellite.png")],
    [#image("assets/bavaria-hessen-quarry-elev.png")],
    [#image("assets/bavaria-hessen-quarry.png")],
  ),
  caption: [Temporal differences between Hessen and Bavaria]
) <fig:hessen-bavaria-forest>

More noteworthy are the small (typically around 0.3--0.5m) differences in rural, especially forested, areas.
These are areas of difference which appear to correspond to linear features in the landscape such as roads, streams, or edges between a forest and an open field.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-bavaria-forest-satellite.png")],
    [#image("assets/hessen-bavaria-forest-osm.png")],
    [#image("assets/hessen-bavaria-forest.png")],
  ),
  caption: [Differences between forested terrain in Hessen and Bavaria]
) <fig:hessen-bavaria-forest>

These are likely consequences of the approaches to ground and vegetation classification employed by the different data providers.
Examining the Bavarian point cloud reveal that all points in the relevant tile are strictly classified into ground (2) and "objects" (20); as well as scan patterns and non-uniform point distribution, largely due to shadowing from trees.
Due to lack of open point cloud data in Hessen, the comparison between two states is impossible.

#figure(
  grid(
    columns: (1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-bavaria-pc-forest-bare.jpeg")],
    [#image("assets/hessen-bavaria-pc-forest-trees.jpeg")],
  ),
  caption: [Bavarian point cloud data]
) <fig:bavaria-forest-slope>

Another detail evident from the comparison is the difference in approach to estimating the elevation of the water surface.
Hessen appears to be relying on the data about the water surface obtained from the point cloud --- the surface does not appear to be perfectly smooth and seems to contain small artefacts.
Bavaria instead uses Delaunay triangulation, seemingly based on the lowest point along the coastline of the water body.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/bavaria-hessen-water-satellite.png")
      satellite view],
    [#image("assets/bavaria-hessen-water.png")
      elevation difference],
    [#image("assets/bavaria-hessen-water-elev-bavaria.png")
      Bavaria],
    [#image("assets/bavaria-hessen-water-elev-hessen.png")
      Hessen]
  ),
  caption: [Differences in water processing between Bavaria and Hessen]
)<fig:bavaria-hessen-water>

==== Hessen -- RLP

The border between Hessen and @RLP largely follows the Rhine.
Compared to the borders between German states, it has the second-highest @RMSE at 1.30m and the highest @LE90 at 0.19m. It also has the second-highest absolute error at -61.59m.
High @RMSE can largely be attributed to errors due to processing in one particular tile; high @LE90 is a symptom of systematic errors.

One of the tiles Hessen includes in its elevation dataset is almost entirely interpolated --- seemingly using two interpolation methods: linear interpolation on a TIN where sample points are available; and another method where data was not available.
Hessen does not publish the point cloud data, yet having observed raster elevation data, we believe that the entire tile was cropped out from the point cloud survey as it only contained partial data.
A small part of Hessen still falls within that tile; and it was re-included by Hessen during the raster processing phase, interpolated based on the ground points from the neighbouring tiles.
It is unclear what the elevation of the southwest extreme point is based on.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-artefact-satellite.png")],
    [#image("assets/hessen-rlp-artefact-hessen.png") Hessen],
    [#image("assets/hessen-rlp-artefact-rlp.png") RLP],
    [#image("assets/hessen-rlp-artefact.png")],
  ),
  caption: [Interpolation artefact by Hessen]
)

Systematic errors can be observed throughout the region where, especially on hilly terrain, there is a relatively consistent 5--20cm difference between the two @DTM:pla.
There are several visible borders between in the difference map where two tiles meet, which likely point at either a different ground filtering algorithm or a misalignment between two different surveys carried out by the same provider.
The hilly terrain makes it impossible to confidently conclude which of the data providers is responsible for this error based on raster data alone.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-tiling-satellite.png")],
    [#image("assets/hessen-rlp-tiling-hessen.png") Hessen],
    [#image("assets/hessen-rlp-tiling-rlp.png") RLP],
    [#image("assets/hessen-rlp-tiling.png")],
  ),
  caption: [Example of systematic error between Hessen and RLP]
)

Smaller errors are also visible in building footprints, where both providers are performing linear interpolation on a TIN but based on somewhat different set of points.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/hessen-rlp-buildings-satellite.png")],
    [#image("assets/hessen-rlp-buildings-hessen.png") Hessen],
    [#image("assets/hessen-rlp-buildings-rlp.png") RLP],
    [#image("assets/hessen-rlp-buildings.png")],
  ),
  caption: [Temporal differences between Switzerland and BW]
)

==== BW -- Bavaria
The @BW -- Bavaria border is similar to the @NRW -- Hessen border, as it is split in two sections due to the catchment area shape. For this region Bavaria provides point cloud data, whereas @BW does not. This means that point cloud comparisons will not be possible for this border region.

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

For this border comparison, the @INSPIRE target is not met. The amount of points above the threshold is only $0.14%$. However, the total @RMSE is 5.36m --- a factor $3.2$ greater than what it is allowed to be for the $5$ meter resolution. These results are not acceptable for the final map. However, solving this problem does not fall within the scope or time constraints of this project, and is primarily a challenge created due to available input data and not by the processing pipeline.

#pagebreak()



=== Luxembourg -- Germany -- France
==== Luxembourg -- France

The border area between Luxembourg and france is roughly $50"km"$ long and consists of more even terrain in the east and increasingly hilly terrain in the west with deviations of over 100 meters at relatively short distances. As can be seen in @fig:Lux_Fra_border, most of the western region of the border is flagged as having a deviation greater than the resolution-RMSE ratio.

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
  caption: "Difference overview",
)
<fig:Lux_Fra_border>

As a primary example of this phenomenon the area around Rumelange was more closely evaluated. Unlike most border regions, the differences are not limited to isolated artifacts, but affect most of the border area. A prominent example is the area around Rumelange. Evaluating the elevation map and Google Earth, shows that the area is populated with steep slopes, valley sides, ridges and cliff faces (@fig:Lux_Fra_Rumelange).

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-Lux-Rumelange.png", width: 100%)
      #align(center)[(Flagged Differences)]
    ],

    [
      #image("assets/France-Lux-Rumelange-elevation.png", width: 100%)
      #align(center)[(DTM)]
    ],

    [
      #image("assets/France-Lux-Rumelange-contour.png", width: 100%)
      #align(center)[(DTM)]
    ],
  ),
  caption: "Rumelange difference overview",
)
<fig:Lux_Fra_Rumelange>

Further examining the uncertainty pattern of the border region further supports these observations (@fig:Lux_Fra_Rumelange_uncertainty). Areas with high uncertainty (shown in red), represent elevation differences due to random errors of $1.6$ meters, while low uncertainty regions (in blue), correspond with the regions of small differences in the elevation difference map. Due to the respective national @DTM:pls being generated from @LiDAR data, small differences in sample point locations can create large differences in the elevation of a point. This effect becomes more pronounced due to the 5 meter resolution of the French @DTM and the 0.5 meter resolution of the Luxembourg @DTM.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/France-Lux-Rumelange-DH.png", width: 100%)
      #align(center)[(DH)]
    ],

    [
      #image("assets/France-Lux-Rumelange-uncertainty.png", width: 100%)
      #align(center)[(Uncertainty)]
    ],
  ),
  caption: "Random error effects due to sloped terrain",
)
<fig:Lux_Fra_Rumelange_uncertainty>

Influence of the slope on the can also be observed directly from the @RMSE analysis (@fig:Lux_Fra_Rumelange_slope). Areas with a slope above 5 degrees have a @RMSE surpassing 4 meters. This behavior deviates from most other border regions where the RMSE gradually increases with slope. The result suggests that the steep terrain is one of the dominant causes of disagreement between the two @DTM:pls.

#figure(
  image("assets/slope_rmse_france_luxembourg.png",width:60%),
  caption:[RMSE grows strongly due to the effects of terrain slope, up to 5.5 meters at 40 degrees]
)
<fig:Lux_Fra_Rumelange_slope>

Further artifacts within the region do more closely correspond with the rest of Luxembourg and the border regions in general. These include building interpolation differences, narrow streams not captured by the river mask, and isolated quarry or construction areas. This region does not comply with the thresholds set within @chap:method, with 23% of all points surpassing the threshold. Furthermore, the resolution would need to be increased by over 80% to nearly 10 meters for compliance with the @INSPIRE target. As eluded to earlier, this difference may be a byproduct of the low resolution @DTM compared to the fine resolution of the Luxembourg @DTM, which has introduced resampling differences. While outside of the time constraint of the project, evaluating the results of the comparison against the higher resolution French @DTM could result in better alignment. Alternatively, reextraction from the national point clouds could also be a way to rectify these differences.

==== Luxembourg -- RLP
The Luxembourg -- @RLP border is roughly 80 kilometers long, and with that is the longest border that is evaluated for the catchment area. On the east side of the overlapping area there is the Our river. Observing the overlap map shows that the rivermask was not succesful at filtering out the waterbodies entirely for the region. This is a known artifact known to be caused by narrow waterbodies. Furthermore, these river areas have been flagged as noticable differences and due count towards the difference at the border.

Other differences in this region are in line with the other borders surrounding Luxembourg, such as river ports with piled resources, steep cliffs, construction areas and building interpolation differences. The only real artifact that shows up on the histogram, is a singular secondary peak. Observing the difference @DTM, shows that this is caused by a lake, which was missed by the river mask. This is illustrated in @fig:Lux-rlp-peak as a peak starting at 700 meters. The border effect graph also clearly illustrates the difference at the border river.

#figure(
  image("assets/border_effect_germany_rlp_luxembourg.png"),
  caption:"River differences (0m), lake river mask failure (700 – 1200m)"
)
<fig:Lux-rlp-peak>

==== Luxembourg -- Saarland
The border area between Luxembourg and Saarland is roughly 11 kilometers and like @RLP -- @BW, is entirely bisected by a river, that being the Mosel in this particular case. The borde area consists of flat areas around the river and consists of hills and cliffs on the west side.

This region contains several of the more common differences encountered in other regions can also be found here. This includes harbor loading areas for sand, steep cliffs, construction sites, waterbodies not entirely caught by the river mask, and roof interpolation differences.

The only unique error found around this area is the inclusion of hydro electric powerplants. While this difference can really be attributed to the limits of the river mask, it is an interesting feature within the water which could pose a challenge to solve, were improving the river mask to be attempted, as the water here does not follow the the smooth water hypothesis. Furthermore, the decision would need to be made if the plant should be removed entirely. This depends on wether all countries model this feature in their @DTM, or simply classify it as part of the river, removing it from the @DTM entirely.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Lux-Saarland-HydroGoogle.png", width: 100%)
      #align(center)[(Google maps)]
    ],

    [
      #image("assets/Lux-Saarland-HydroDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Hydro electric powerplant example",
)
<fig:Lux-Saarland-Hydro>

For this region, the percentage of points above the @INSPIRE threshold, is around $1%$. While above average, this is caused by the fact that it is a small region, where the spatial dimensions of the differences remain consistent with differences found in other regions. Nevertheless, the difference @DTM falls well within the @INSPIRE target threshold, and contains no significant errors such as border extrapolation, misaligned tiles or inexplicable differences.

=== Germany -- France
==== Saarland -- France <sec:saarland-france>

The approximately 157 km border between Saarland and France crosses rolling hills, forested slopes and river valleys, with sections following the Saar and Blies rivers. Across the compared overlap, the two DTMs generally agree closely: the mean elevation difference is +0.035 m and the median is −0.020 m, where positive differences indicate higher elevations in Saarland. Half of the absolute differences are below 0.163 m, and 90% are below 0.981 m. Nevertheless, the RMSE reaches 1.213 m, reflecting substantial discrepancies at particular locations.

These discrepancies are concentrated rather than evenly distributed. Only 5.81% of the compared area exceeds the 1.667 m comparison threshold, yet this portion contributes approximately 90% of the total squared elevation difference. Differences greater than 5 m occupy just 1.27% of the area but contribute about 63% of that total. The distribution therefore has a narrow centre and long tails, with extremes from approximately −22 m to +33 m. Neighbouring positive and negative differences partly cancel, so the small mean understates the local disagreement.

The Google Earth inspections and corresponding difference maps place these results in their terrain context. In @fig:saarland-france-region1, the long dark blue difference pattern in panel (b) corresponds to a cliff identified in the Google Earth terrain view in panel (a). The pronounced discrepancies follow this abrupt terrain edge, with additional patches within the surrounding woodland. In @fig:saarland-france-region2, the largest differences in panel (b) coincide with an apparent valley-like terrain feature visible in panel (a). These selected examples illustrate recurring settings of disagreement rather than representing every location along the border.

// Equal panel frames preserve the complete images without stretching or cropping.
#let saarland-france-panel(path, panel-caption) = block(
  width: 100%,
  breakable: false,
)[
  #image(path, width: 100%, height: 43mm, fit: "contain")
  #v(3pt)
  #align(center)[#text(size: 9pt)[#panel-caption]]
]

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      saarland-france-panel("assets/region1_bare.png", [(a) Google Earth terrain view]),
      saarland-france-panel("assets/region1_dtm.png", [(b) Elevation-difference overlay]),
    ),
    caption: [*Forested escarpment beside water bodies.*],
  ) <fig:saarland-france-region1>
]

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      saarland-france-panel("assets/region2_bare.png", [(a) Google Earth terrain view]),
      saarland-france-panel("assets/region2_dtm.png", [(b) Elevation-difference overlay]),
    ),
    caption: [*Wooded slopes and abrupt terrain changes.*],
  ) <fig:saarland-france-region2>
]

Terrain steepness is the strongest quantified association. RMSE rises from approximately 0.8 m on slopes of 0–5° to 2.7 m at 20–25° and 5.6 m at 45–50°. This supports the visual observation that steep slopes and rapidly changing relief are particularly problematic. Forest cover is a recurring characteristic of the inspected hotspots, although its contribution has not been quantified separately from slope. Differences in ground filtering beneath canopy and restricted ground observations in narrow valleys are possible contributors. In @fig:saarland-france-region3, the largest differences, shown as dark blue patches, coincide with forested areas identified during the visual inspection. Nearby patches of contrasting differences further illustrate how substantial local mismatches can cancel in the regional mean.

#align(center)[
  #block(breakable: false)[
    #figure(
      image("assets/region3_dtm.png", width: 76%),
      caption: [*Clustered differences in a third inspected area.*],
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
      saarland-france-panel("assets/quary_bare.png", [(a) Quarry imagery]),
      saarland-france-panel("assets/quary_dtm.png", [(b) Elevation-difference overlay]),
    ),
    caption: [*Imagery corresponding to a quarry and its difference raster.*],
  ) <fig:saarland-france-quarry>
]

The regional RMSE is driven primarily by a limited set of pronounced local mismatches. Steep and complex terrain provides the clearest quantitative association, while the inspected images highlight forest cover, exposed escarpments and excavation features as recurring settings. Differences in acquisition timing are an additional possible contributor where the landscape has changed between surveys. Most of the overlap agrees much more closely than the overall RMSE suggests.

==== RLP -- France <sec:rlp-france>

The border between RLP and France is approximately 112 km long and crosses predominantly hilly, forested terrain, particularly through the Pfälzerwald, which continues into France as the Northern Vosges. The Rhine does not form the main boundary, only the easternmost section approaches the Upper Rhine, while much of the border runs over land and partly follows smaller watercourses such as the Lauter. Castle ruins and distinctive rock formations are also characteristic features of this region.

Elevation differences are defined as RLP minus France, so positive values indicate a higher RLP surface. The mean difference is −0.033 m and the median is −0.032 m. Half of the absolute differences are below 0.079 m and 90% are below 0.225 m. The RMSE of 0.260 m, compared with an NMAD of 0.113 m, indicates that a relatively small number of large discrepancies strongly influence the overall result.

@fig:rlp-france-distribution shows the narrow central distribution and the longer tails. Only 0.237% of the compared area, equivalent to 0.670 km², exceeds the 1.667 m comparison threshold, yet these cells contribute 60.4% of the total squared elevation difference. Differences greater than 5 m occupy just 0.044% of the area but contribute 36.3% of that total. Most of the overlap therefore agrees closely, while a small number of locations require separate investigation.

#block(breakable: false)[
  #figure(
    image("assets/rlp_france_distribution.png", width: 100%),
    caption: [*Central distribution and full-distribution exceedance curve.* The left figure shows the distribution of the regional differences around the mean. Values outside ±0.6 m are not shown for visual simplicity. The right figure shows the percentage of all compared cells exceeding the absolute-difference threshold.],
  ) <fig:rlp-france-distribution>
]

The spatial overview in @fig:rlp-france-spatial distinguishes broad patterns of signed difference from concentrated large discrepancies. The ten largest problem regions lie at the western end of the overlap and contain 73.7% of all area above the threshold. The first five of those regions are shown in @fig:rlp-france-spatial and contain 60.0%. However, the strongest individual differences are not in the regions with the biggest concentration of high difference. The locaitons of the largest individual differences are shown in @fig:rlp-france-extremes.

#block(breakable: false)[
  #figure(
    image("assets/rlp_france_spatial.png", width: 100%),
    caption: [*RLP minus France: saved elevation differences.* From top to bottom: mean signed difference, RMSE, and percentage of compared area exceeding 1.667 m. Numbers identify the five largest supplied problem regions. Extreme values go over the displayed limits by the colour scheme.],
  ) <fig:rlp-france-spatial>
]

#block(breakable: false)[
The inspected locations in @fig:rlp-france-extremes place the largest differences in their physical setting. The minimum of −30.37 m occurs at Fleckenstein Castle (7.772331° E, 49.044892° N), where the French DTM is higher. The maximum of +34.54 m occurs at the Klein Arsberg ruins (7.690392° E, 49.038642° N), where the RLP DTM is higher. Another pronounced positive difference was identified at the nearby rock opening (7.693148° E, 49.039210° N). These photographs were taken from public contributions found in Google Maps, and they provide terrain context rather than a direct measurement of DTM error.
]

#let rlp-france-panel(path, panel-caption) = block(width: 100%, breakable: false)[
  #image(path, width: 100%, height: 58mm, fit: "contain")
  #v(3pt)
  #align(center)[#text(size: 9pt)[#panel-caption]]
]

#block(breakable: false)[
  #figure(
    grid(
      columns: (1fr, 1fr, 1fr),
      column-gutter: 7pt,
      rlp-france-panel("assets/rlp_france_fleckenstein.png", [(a) Fleckenstein Castle]),
      rlp-france-panel("assets/rlp_france_klein_arsberg.png", [(b) Klein Arsberg ruins]),
      rlp-france-panel("assets/rlp_france_rock_opening.png", [(c) Nearby rock opening]),
    ),
    caption: [*Terrain settings of selected large differences.* (a) and (b) correspond to the most negative and most positive cells, respectively. (c) illustrates another positive discrepancy. Google Maps photographs supplied with the visual inspection.],
  ) <fig:rlp-france-extremes>
]

Different treatment of ruins and exposed rock during ground classification, followed by interpolation across removed or sparsely sampled features, could produce these local discrepancies. Forest canopy may further limit ground observations around the sites. A raster DTM stores one elevation per horizontal cell and cannot explicitly represent both the top and underside of an overhang. The 5 m grid also smooths narrow rock edges. Consequently, disagreement at these locations may reflect different representations of complex terrain as well as processing errors. Verification requires the original classified point clouds and source-resolution DTMs, cross-sections through the exact cells, and an independent survey or reliable terrain reference. Acquisition dates and processing specifications are needed to distinguish temporal change from classification and interpolation effects.

@fig:rlp-france-patterns shows a different type of discrepancy: broad, approximately parallel bands extending across multiple fields and woodland areas. This pattern suggests an acquisition or processing component rather than terrain features. They resemble artefacts originating from flight line patterns. Survey trajectories and strip identifiers should be compared with the bands, and overlapping point-cloud strips examined separately.

#block(breakable: false)[
  #figure(
    image("assets/rlp_france_patterns.png", width: 100%),
    caption: [*Broad bands in the elevation-difference overlay.* The image shows broad parallel bands extending across the region.],
  ) <fig:rlp-france-patterns>
]

These results quantify agreement between the two DTMs, not their absolute accuracy. Neither surface is independent ground truth, and a small difference can conceal errors shared by both datasets. The selected photographs do not validate all affected cells or establish which provider is more accurate. The principal priorities are therefore the western concentration of large differences, the isolated extremes at complex rock-and-ruin sites, and the flight line patterns.

==== BW -- France <sec:bw-france>

The Baden-Württemberg (BW)–France comparison shows close agreement across much of the Rhine corridor, interrupted by pronounced local discrepancies and coherent spatial patterns. Across 166.52 km² of valid overlap at 5 m resolution, the mean elevation difference is +0.034 m and the median is +0.058 m, where positive values mean that BW is higher than France. The RMSE of 0.730 m is considerably larger than the NMAD of 0.153 m, indicating that large local differences have a strong influence on the overall result. Numerical results refer to differences before alignment, and 1.667 m is the pipeline's screening threshold. These measures describe agreement between the two DTMs; independent ground control would be needed to establish their absolute accuracy.

The difference distribution has a narrow centre and long tails. Half of the absolute differences are below 0.117 m, 90% below 0.508 m, and 95% below 1.059 m. Only 2.744% of compared cells exceed the configured 1.667 m threshold, but these cells occupy 4.57 km² and contribute 82.73% of the total squared difference. Differences larger than 5 m occupy just 0.397% of the area yet contribute 47.62% of squared difference. Positive and negative discrepancies partly cancel in the regional mean, which therefore understates their local importance. The observed extremes range from −25.96 m to +46.72 m.

@fig:bw-france-north-south shows the strongest regional contrast, between the southern overlap and the remainder of the corridor. An exploratory division at EPSG:3035 northing 2,760,000 m, selected after examining the 10 km bands, isolates a southern segment covering 26.89 km², or 16.15% of compared area. This segment contains 89.82% of all threshold-exceeding cells and 85.53% of total squared difference. Its RMSE is 1.680 m, compared with 0.303 m in the remaining northern segment; exceedance rates are 15.26% and 0.333%, respectively. NMAD also rises from 0.132 m in the north to 0.661 m in the south, showing that the southern disagreement affects the broader distribution as well as its most extreme values.

#block(breakable: false)[
  #figure(
    image("assets/bw_france_north_south_profile.png", width: 100%),
    caption: [*Regional variation in the BW–France comparison.* RMSE, threshold exceedances and compared area in 10 km northing bands. The southern bands have substantially larger differences despite containing less compared area than several northern bands. Coverage refers to the available overlap.],
  ) <fig:bw-france-north-south>
]


Visual inspection identifies earthworks and quarries along the Rhine as the setting of many problematic regions. Excavation faces, embankments, terraces and material deposits can change substantially between surveys, producing adjacent positive and negative elevation differences. Consequently, some discrepancies may represent genuine terrain change between acquisition dates, alongside differences in how steep faces and sharp terrain edges are represented. Matching acquisition dates and historical imagery is necessary to separate these contributions. The ten largest supplied problem regions contain 58.38% of all flagged area and contribute 61.96% of total squared difference, making them useful priorities for targeted inspection.

Region 2 is particularly important because it contains both global extremes, only 148 m apart, near 7.530° E, 47.663° N. Its footprint RMSE is 4.30 m. Region 1, the largest by flagged area, contains 0.682 km² of exceedances and is predominantly negative, with a footprint mean of −2.42 m. These coherent, metre-scale discrepancies require local investigation of terrain history and surface representation before any correction is selected.

Slope is also relevant. The saved slope–RMSE curve rises from approximately 0.60 m at 0–5° to 1.47 m at 20–25°, 3.41 m at 35–40°, and 6.90 m at 45–50°. This association is consistent with larger differences around excavation faces, embankments and other abrupt changes in relief. However, these values are visual readings from the saved plot; bin counts are unavailable, and slope has not been separated statistically from the southern concentration or land-use setting. Steepness therefore helps identify sensitive locations but does not establish the cause of each discrepancy.

Alongside these large local differences, @fig:bw-france-patterns shows flight-line-like bands similar to those in the RLP–France comparison (@fig:rlp-france-patterns). The comparative visual inspection identifies bands running in the same direction and matching exactly with the RLP–France patterns. Because the French DTM is common to both comparisons, this correspondence strongly suggests an origin in the French acquisition and the relative alignment or adjustment of its flight paths. The spatially varying bands are consistent with residual differences between flight strips that persist across the two regional comparisons. Flight-line footprints and adjustment records would allow this interpretation to be tested directly and help distinguish acquisition effects from later processing.

#align(center)[
  #block(breakable: false)[
    #figure(
      image("assets/bw_france_patterns.png", width: 68%),
      caption: [*Flight-line-like patterns in the BW–France difference overlay.* Coherent bands and sharper local features along the Rhine. The bands match the direction and continuity of those in @fig:rlp-france-patterns. The embedded legend describes the selected display, not the full regional range of differences.],
    ) <fig:bw-france-patterns>
  ]
]

// below: this ChatGPT?

The most useful follow-up actions are:

- Investigate the southern hotspots first, particularly regions 2 and 1, using matching source DTMs, acquisition dates and historical imagery to distinguish earthworks and quarry development from processing differences.
- Check French flight-strip alignment, comparing strip footprints and adjustment records with the bands shared by BW–France and RLP–France. Test any correction on stable terrain and verify it across both comparisons.
- Analyse slope and border distance within geographic subsets, with sample counts and land-use context, before attributing the pooled patterns to one mechanism.
- Recalculate inconsistent polygon areas and refit the uncertainty model, preserving the empirical variogram, fitted parameters, masks and processing provenance needed to validate the results.

=== Switzerland -- Germany & France

==== Switzerland -- France

Overall, the border between France and Switzerland contains errors similar to those found on the French--German border.
These include one instance of striping, most visible in the suburbs of Basel.
The stripe appears to follow the edge of the French @DTM, which further points towards it being caused by poorly aligned flight-paths.

#figure(
  image("assets/fr-ch-flightpath.png", width: 40%),
  caption: [Flight-path artefacts between France and Switzerland]
)

There is also a large artefact in the forested region near Pfetterhouse.
In the French @DTM, the elevation of peaks appears to be underestimated while the elevation of valleys is overestimated --- essentially, the @DTM is over-smoothed.
We speculate that regions like this come from a different survey with different approach to ground filtering (perhaps ground is estimated with a global interpolation function) but we have not been able to verify or falsify this hypothesis.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/fr-ch-forest-ch.png") Switzerland],
    [#image("assets/fr-ch-forest-fr.png") France],
    [#image("assets/fr-ch-forest.png")],
  ),
  caption: [Ground filtering differences between Switzerland and France]
)

==== Switzerland -- BW

The border between Switzerland and @BW largely follows the Rhine between Konstanz and Basel and notably includes Büsingen, an exclave of BW within Switzerland.
The regions are overall well-aligned with @LE90 of only 0.12m but a high @RMSE of 0.4m.

The largest errors are best explained by temporal differences --- like in other areas examined above, there are several quarries present near the border. The largest of them is located northeast of Schaffhausen and is responsible for the largest differences in elevation, up to 30m.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-quarry-satellite.png")],
    [#image("assets/ch-bw-quarry-ch.png") Switzerland],
    [#image("assets/ch-bw-quarry-bw.png") BW],
    [#image("assets/ch-bw-quarry.png")],
  ),
  caption: [Temporal differences between Switzerland and BW]
)

A more unique error is due to ground filtering, as can be observed with the industrial complex north of Stein, where differences between the different ground filtering/interpolation methods can exceed 3m. As is evident from the difference mask, both data providers use TIN to interpolate the terrain but a different set of points for constructing said TIN. A likely misclassification of the ground, perhaps due to shadowing or multipath errors, causes the error in the elevation of ground points and therefore the error in the TIN.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-buildings-satellite.png")],
    [#image("assets/ch-bw-buildings-ch.png") Switzerland],
    [#image("assets/ch-bw-buildings-bw.png") BW],
    [#image("assets/ch-bw-buildings.png")],
  ),
  caption: [Differences in building processing between Switzerland and BW]
)

Ground and vegetation filtering also have an effect on forested slopes between Hallau and Eggingen where minor striping can be observed. The stripes appear to be running perpendicular to the slope and, we speculate, can be symptomatic of either differences in ground processing by data providers; or they could be a resampling artefact. We recommend performing point cloud analysis to validate either of these hypotheses, which was skipped due to time constraints of the project.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-forest-satellite.png")],
    [#image("assets/ch-bw-forest-elev.png")],
    [#image("assets/ch-bw-forest.png")]
  ),
  caption: [Differences in ground processing between Switzerland and BW]
)

Similarly to the building interpolation, there is also an observable difference in the water surface. Switzerland appears to be using a hydro-flattening approach whereas @BW is instead using linear interpolation on a TIN.

#figure(
  grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/ch-bw-water-satellite.png")],
    [#image("assets/ch-bw-water-ch.png") Switzerland],
    [#image("assets/ch-bw-water-bw.png") BW],
    [#image("assets/ch-bw-water.png")],
  ),
  caption: [Differences in water processing between Switzerland and BW]
)

=== Germany -- Netherlands

==== Netherlands -- NRW
The border between the Netherlands and @NRW is approximately 50 kilometers long, is mainly flat, but also contains large hills. The main error found within this region is unfortunately a byproduct of our attempt to interpolate the non-interpolated regions of the Netherlands (@fig:Netherlands-NRW-border). These errors are found primarily in the form of extrapolation errors found at various positions along the border. This is a discrepancy caused by differences in the specified borders for the Netherlands within the interpolation algorithm. However, since these areas are trimmed from the final @DTM, it is not a issue which will be fixed during this project.

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
<fig:Netherlands-NRW-border>

Other errors within this region include both small and large scale earth works. Examples include the "Steenfabriek de Bijland", which also includes swampy areas, which are not caught by the river mask (@fig:Netherlands-NRW-Lworks). Another example includes storage of manure and dirt at farms scattered throughout the border area (@fig:Netherlands-NRW-Sworks).

For this border area in particular, there is a strong effect of waterbodies on the difference. The RMSE increases by 10% if the waterbodies are included, compared to the case without. This is likely due to the attempt at interpolating the river areas, which will differ from the approach taken in the german region, which most often involves triangulation of the water surface.

There are no significant differences that have an effect on the creation of the final catchment @DTM, and with more time the existing extrapolation error would also be fixable.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-StoneSwampGoogle.png", width: 100%)
      #align(center)[(Google Maps)]
    ],

    [
      #image("assets/Netherlands-NRW-StoneSwampDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Large earthworks example",
)
<fig:Netherlands-NRW-Lworks>

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-FarmsGoogle.png", width: 100%)
      #align(center)[(Google Maps)]
    ],

    [
      #image("assets/Netherlands-NRW-FarmsDH.png", width: 100%)
      #align(center)[(DH)]
    ],
  ),
  caption: "Small earthworks example",
)
<fig:Netherlands-NRW-Sworks>