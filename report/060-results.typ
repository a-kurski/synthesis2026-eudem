#import "@preview/drafting:0.2.2"
= Results <chap:results>

This chapter discusses the results of the data acquisition, the pipeline, analysis of the border-pairs and general findings about the @DTM:pls. The first section describes the challenges encountered while aquiring the data. Section 2 describes the results of the reprojection, resampling, regridding and interpolation. After, the analysis of the process is discussed, specifically analyzing the effect of various factors on the observed border errors. Lastly, any additional observations that do not fall within these categories will be discussed.

== Data Acquisition <sec:results-acquisition>
The data scraping is not considered a part of the processing pipeline due to the variations in scraping methods, accessing differences, and computation time. However, due to its relevance to the challenges of creating a @DEM of the Rhine catchment area, it has been included in this chapter. The pipeline assumes all data is available in their raw formats that is, individual @DTM tiles in most of the cases. In case the requested data is not available, the pipeline proceeds to download it from the specified source. Currently, all acquisition of data labeled as a must in @Moscow_Prioritization is implemented within the scraping software.

#include "elevation_data_characteristics.typ"

The pipeline acquires elevation data from 11 regions within 6 countries. The data comes in different formats, availability, @CRS, and resolution. @tab:elevation-data summarizes the characteristics of data from their sources. Some regions offer multiple DTM products that differ in resolution, format, and download accessibility. Selecting a suitable product therefore involved trade-offs between data quality and computational efficiency. For France, two products were considered: RGE ALTI and MNT LiDAR HD. Although MNT LiDAR HD provides newer, higher-resolution elevation data, its publicly available GeoTIFF tiles have a resolution of 0.5 m. Processing these data at the scale of the French study area would require considerably more storage and computational resources, particularly since the target grid has a resolution of 5 m. In contrast, RGE ALTI is available at 5 m resolution, although its ASCII Grid format requires conversion to GeoTIFF. RGE ALTI was therefore selected, prioritising storage and computational efficiency over the potentially higher accuracy and more recent acquisition of MNT LiDAR HD.

The selection of RGE ALTI in France represented the clearest trade-off between data quality and computational efficiency. For some regions, however, data acquisition and processing had already been implemented before the target grid resolution of 5 m was established. This was the case for the Netherlands, where the existing implementation using the 0.5 m AHN product was retained despite the availability of a 5 m product. For most German regions, the standard 1 m DTM products were used, with Bavaria being an exception where a 5 m product was available for download. In Baden-Württemberg, a 5 m product was also available, but required payment, so the openly available 1 m product was selected. For Switzerland and Liechtenstein, the nationwide 2 m product was resampled to the target grid. In Luxembourg, the more recent 0.5 m nationwide product was preferred over an older 5 m product, as the relatively small study area made processing the higher-resolution data feasible. Once the source data is acquired, it is then processed in the pipeline to match the specifications of the target grid.

== Pipeline <sec:pipeline>

#include "065-results-pipeline.typ"

== DTM of the Rhine Catchment Area

#include "066-results-dtm.typ"

=== Water Mask <sec:Watermask_artefacts>

The watermask was not an initially intended addition for the project. However, during analysis it was shown that including waterbodies showed large deviations in elevation between regions. Due to a lack of an existing high quality water mask, an existing mask was refined as detailed in @sec:Water_mask_processing. However, due to shortcomings of the mask and the applied algorithm, artefacts still occur, even if their impact on the analysis is minimized. The final result of the river mask can be observed in @fig:River_mask_final.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,
    [
      #image("assets/rhinecatchment-full.png", width: 100%)
    ],
    [
      #image("assets/rivermask-local.png", width: 100%)
    ],
  ),
  caption:[River mask visualized on the entire Rhine Cathcment (left), and around the Cologne area in Germany (right).]
)<fig:River_mask_final>
#v(1em)


The region growing algorithm relies on the assumption that the water surface is smooth. However, this is not always the case. The first example of this is found in @fig:River_mask_manmade. Here a hydroelectric power plant causes a change in the elevation of the water surface. The rough water mask from @FEE marks this as an area which is not considered water. Therefore, there is a break in the water mask, and the area surrounding the plant such as the left secondary channel, is not modeled.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Lux-Saarland-HydroGoogle.png", width: 80%)
      #align(center)[
        #text(size: 10pt)[
          Google Maps, Imagery © 2026 Airbus, Maxar Technologies.
        ]
      ]
    ],

    [
      #image("assets/Lux-Saarland-HydroDH.png", width: 80%)
      #align(center)[
        #text(size: 10pt)[
          Non-continuous river mask.
        ]
      ]
    ],
  ),
  caption: [
    Rivermask failure where the mask is not continuous due to a hydroelectric power plant.
  ]
)<fig:River_mask_manmade>
#v(1em)

Another similar shortcoming is that the @FEE mask is incomplete. Not all lakes have valid seed points contained within. Furthermore, the reprojection of @FEE cell centers onto the empty mask, due to invalid row and/or column values as a result of division by 0 errors. These are known limitations of the river mask which could be solved by extracting the mask from the national point clouds of the respective regions.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-missing-lakes-Maps.png", width: 100%)
      #align(center)[
        #text(size: 10pt)[
          Google Maps, Imagery © 2026 Airbus, Maxar Technologies.
        ]
      ]
    ],

    [
      #image("assets/France-missing-lakes-FEE.png",width:100%)
      #align(center)[
        #text(size: 10pt)[
          FEE mask.
        ]
      ]
    ],

    [
      #image("assets/France-missing-lakes.png",width:100%)
      #align(center)[
        #text(size: 10pt)[
          Incomplete river mask.
        ]
      ]
    ],

  ),
  caption:[Rivermask failure due missing water cells in the input raster.]
)<fig:River_mask_missinglakes>
#v(1em)

Other issues include areas that are marked as neither lake or river by the @FEE mask. Examples include swampy areas on the Netherlands – @NRW border. This is shown in @fig:getoutofmyswamp.

#figure(grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-StoneSwampGoogle.png", width: 80%)
      #align(center)[
        #text(size: 10pt)[
          Imagery © 2026 Airbus, Landsat / Copernicus,
          Maxar Technologies
        ]
      ]
    ],

    [
      #image("assets/Netherlands-NRW-StoneSwampDH.png", width: 80%)
      #align(center)[
        #text(size: 10pt)[
          Incomplete water mask.
        ]
      ]
    ],
  ),
  caption: [Omission of swamp-like areas from the watermask prevents correct detection of water bodies. The marsh located between the upper lake and smaller patched lakes is not properly accounted for.])
<fig:getoutofmyswamp>

The last artefact appears most frequently within the French region of the mask. This does not affect the border area as the masks of both regions overlap here. However, this appears to be caused by the @TIN approximation of the water surface. This causes shard-like sections of discoloration in the @DTM. Unlike other artefacts this does not strongly affect the border areas. However, it does mean it cannot be used as a true harmonisation step for the Rhine @DTM.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-ommision-riverfail-Maps.png", width: 100%)
      #align(center)[
        #text(size: 10pt)[
          Imagery © 2026 Airbus, Maxar Technologies.
        ]
      ]
    ],

    [
      #image("assets/France-ommision-riverfail.png",width:100%)
      #align(center)[
        #text(size: 10pt)[
          Non-continuous water mask.
        ]
      ]
    ],

    [
      #image("assets/France-ommision-riverfail-TIN.png",width:100%)
      #align(center)[
        #text(size: 10pt)[
          TIN artefacts observed on DTM.
        ]
      ]
    ],
  ),
  caption:[River mask failure due to changes in the water surface elevation caused by TIN interpolation of the surface.]
)<fig:River_mask_TIN>
#pagebreak()

#include "062-analysis.typ"
