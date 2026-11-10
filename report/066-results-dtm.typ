#import "@preview/drafting:0.2.2"

The pipeline successfully produces a DTM of the Rhine catchment area, shown in @fig:final_dtm. For visualization purposes, the elevation colour scheme was adjusted to improve the visual distinction between terrain features across the catchment. The displayed elevation range was limited to −35 m to 1,100 m, with values outside this range assigned the colours of the respective lower and upper limits. This clipping affects only the visualization and does not alter the underlying elevation values.

#figure(
    image("assets/whole_dtm_with_legend.png", width: 70%),
    caption: [Finalized Rhine Catchment DTM]
)<fig:final_dtm>

The final DTM is stored as a Cloud Optimized GeoTIFF file which occupies 17.5 GB of disk space. The final DTM uses ETRS89 / LAEA Europe (EPSG:3035) as its CRS, with a resolution of 5 m and elevation values stored as Float32. The minimum elevation is -324.90 m, occurring in a quarry in North Rhine-Westphalia, while the maximum of 4,272.68 m occurs in the Swiss Alps. The mean elevation is 452.32 m, and the elevation range is 4,597.58 m.

The DTM covers 97.33% (159284.05 km#super[2] or 6371361919 cells out of 163645.59 km#super[2] or 6545823685 cells) of the catchment area, for an omission rate of 2.67 %.
The omission rate can be attributed exclusively to the missing regions (Austria, Belgium, and Thuringen) and `NoData` values within the Dutch dataset.

The commission rate within the final DTM is zero.
However, the overlaps at the border add up to 4140.09 km#super[2], resulting in a commission rate of the underlying data of 2.60%.

The seamlessness of the DTM is dependent on the quality of the underlying datasets.
Where the agreement is high, the DTM is seamless.
This is the case for most of the datasets, illustrated by 3 regions of Germany in @fig:seam-germany.
Where it is low, such as due to temporal or processing differences, a "step" can be observed.
In our case, this happens primarily on the border with France as it is an older and less accurate dataset, as shown in @fig:seam-france.

#figure(
  //placement: auto,
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/de-3-elev-border.png")],
    [#image("assets/de-3-elev.png")],
    [#image("assets/de-3-hillshade.png")]
  ),
  caption: [Example of seamless border between Hessen, NRW, and RLP]
) <fig:seam-germany>

#figure(
  //placement: auto,
  grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/fr-ch-elev-border.png")],
    [#image("assets/fr-ch-elev.png")],
    [#image("assets/fr-ch-hillshade.png")]
  ),
  caption: [Example of border seam between France and Switzerland]
) <fig:seam-france>

// #drafting.inline-note()[zoomed-in hillshade]
