#import "@preview/unify:0.8.1": qty
#import "@preview/drafting:0.2.2"
= Results <chap:results>

This chapter discusses the results of the data acquisition, the pipeline, analysis of the border-pairs and general findings about the @DTM:pls. First, the challenges encountered while acquiring the data are described. Then, the results of the reprojection, resampling, regridding and interpolation are presented, alongside the description of our experience executing the pipeline. After, the analysis of the process is discussed and a summary of the common error types is given.

== Data Acquisition <sec:results-acquisition>

The data scraping is not considered a part of the automated processing pipeline due to the variations in scraping methods, accessing differences, and computation time. For the pipeline to be executed, all data should be made available in their raw formats which in most cases are individual @DTM tiles. In case the requested data is not available, the acquisition script proceeds to download it from the specified source. Currently, all acquisition of data labelled as a "must" in @sec:requirements is implemented within the scraping software.

#include "elevation_data_characteristics.typ"

The pipeline acquires elevation data from 11 regions within 6 countries. The data comes in different formats, availability, @CRS, and resolution. @tab:elevation-data summarises the characteristics of datasets. Some regions offer multiple DTM products that differ in resolution, format, and download accessibility. Selecting a suitable product therefore involved trade-offs between data quality and computational efficiency. For France, two products were reviewed: RGE ALTI and MNT LiDAR HD. Although MNT LiDAR HD provides newer, higher-resolution elevation data, its publicly available GeoTIFF tiles have a resolution of #qty("0.5", "m"), which would require considerably more storage and computational resources. In contrast, RGE ALTI is available at #qty("5", "m") resolution, although its ASCII Grid format requires conversion to GeoTIFF. RGE ALTI was therefore selected, prioritising storage and computational efficiency over the potentially higher accuracy and more recent acquisition of MNT LiDAR HD. RGE ALTI is also more complete, although omissions from MNT LiDAR HD are outside of the study area.

For some regions, however, data acquisition and processing had already been implemented before the target grid resolution of #qty("5", "m") was established. For the Netherlands, the existing implementation using the #qty("0.5", "m") AHN product was retained despite the availability of a #qty("5", "m") product. For most German regions, the standard #qty("1", "m") DTM products were used, with @DE-BY being an exception where a #qty("5", "m") product was available for download. For Switzerland and Liechtenstein, the nationwide #qty("2", "m") product was selected to the target grid. In Luxembourg, the more recent #qty("0.5", "m") nationwide product was preferred over an older #qty("5", "m") product, as the relatively small study area made processing the higher-resolution data feasible.

The total file size of the source data is measured at #qty("804.46", "GB"). Notably, France occupies only #qty("23.04", "GB") or 2.9% of the total compared to the Netherlands' #qty("213.25", "GB") or 26.5%, clearly demonstrating the trade-off between data quality and storage costs.

== Pipeline <sec:pipeline>

#include "065-results-pipeline.typ"

== DTM of the Rhine Catchment Area

#include "066-results-dtm.typ"

=== Water Mask <sec:Watermask_artefacts>

The elevation differences shown above emphasise the need for masking the rivers~--- within the scope of this project, primarily for performing more accurate analysis. Due to a lack of an existing high-quality water mask, an existing mask was refined as detailed in @sec:Water_mask_processing. However, due to the nature of the underlying data ("jumps" in elevation happen even within the same dataset) and the applied algorithm, artefacts still occur, even if their impact on the analysis is minimised. The final result of the river mask can be observed in @fig:River_mask_final.

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
  caption:[River mask visualised on the entire Rhine Catchment (left), and around the Cologne area in DE (right).]
)<fig:River_mask_final>

The region growing algorithm relies on the assumption that the water surface is smooth. However, this is not always the case. The first example of this is found in @fig:River_mask_manmade. Here a hydroelectric power plant causes a change in the elevation of the water surface. The rough water mask from @FEE marks this as an area which is not considered water. Therefore, there is a break in the water mask, and the area surrounding the plant such as the left secondary channel, is not modelled.

#figure(
  grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Lux-Saarland-HydroGoogle.png", width: 80%)
      #align(center)[
        #text(size: 10pt)[
          Satellite imagery. From Airbus, Maxar Technologies (2026).
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
    River mask failure where the mask is not continuous due to a hydroelectric power plant.
  ]
)<fig:River_mask_manmade>

Another similar shortcoming is that the @FEE mask is incomplete. Not all lakes contain valid seed points. Furthermore, the reprojection of @FEE cell centres onto the empty mask sometimes fails due to invalid row and/or column values which results in runtime errors. These are known limitations of the river mask which could be solved by extracting the mask from the national point clouds of the respective regions.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-missing-lakes-Maps.png", width: 100%)
      #align(center)[
        #text(size: 10pt)[
          Satellite imagery. From Airbus, Maxar Technologies (2026).
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
  caption:[River mask failure due missing water cells in the input raster.]
)<fig:River_mask_missinglakes>

Other issues include areas that are not marked as water within the @FEE mask. Examples include swampy areas on @NL/@DE-NW border. This is shown in @fig:getoutofmyswamp.

#figure(grid(
    columns: 2,
    gutter: 5pt,

    [
      #image("assets/Netherlands-NRW-StoneSwampGoogle.png", width: 80%)
      #align(center)[
        #text(size: 10pt)[
          Satellite imagery. From Airbus, Landsat / Copernicus,
          Maxar Technologies (2026).
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
  caption: [Omission of swamp-like areas from the water mask prevents correct detection of water bodies. The marsh located between the upper lake and smaller patched lakes is not properly accounted for.])
<fig:getoutofmyswamp>

The last artefact can be observed along several regions but is most pronounced within France. It is caused by using the @TIN to approximate the water surface. Visually, it appears as shard-like sections of lighter and darker colour in the @DTM where different points along the river bank are chosen as sample points for interpolation on a TIN (see @fig:River_mask_TIN). While it is most severe in areas further from the border and does not significantly affect the quality of the analysis, it does show that further work is needed to fully integrate the water mask.

#figure(
  grid(
    columns: 3,
    gutter: 5pt,

    [
      #image("assets/France-ommision-riverfail-Maps.png", width: 100%)
      #align(center)[
        #text(size: 10pt)[
          Satellite imagery. From Airbus, Maxar Technologies (2026).
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

#include "062-analysis.typ"
