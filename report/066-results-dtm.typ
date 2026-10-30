#import "@preview/drafting:0.2.2"

The pipeline successfully produces a DTM of the Rhine catchment area. This is shown in @fig:final_dtm.

#figure(
    image("assets/whole_dtm_with_legend.png", width: 70%),
    caption: [Finalized Rhine Catchment DTM]
)<fig:final_dtm>

The final DTM is stored as a Virtual Raster (VRT) referencing 11 regional GeoTIFFs. It uses the ETRS89 / UTM zone 32N coordinate reference system (EPSG:25832), with a spatial resolution of 5 m and Float32 elevation values. The raster contains 109,091 columns and 133,579 rows. The minimum elevation is -324.90 m, occurring in a quarry in North Rhine-Westphalia, while the maximum of 4,272.68 m occurs in the Swiss Alps. The mean elevation is 452.32 m, with a standard deviation of 448.49 m. The elevation range is 4,597.58 m.

The DTM covers 97.33% (159284.05 km#super[2] or 6371361919 cells out of 163645.59 km#super[2] or 6545823685 cells) of the catchment area, for an omission rate of 2.67 %.
The omission rate can be attributed exclusively to the missing regions (Austria, Italy, and Belgium) and NoData values within the Dutch dataset.

The commission rate within the final DTM is zero.
However, the overlaps at the border add up to 4140.09 km#super[2], resulting in a commission rate of the underlying data of 2.60%.

The seamlessness of the DTM is dependent on the quality of the underlying datasets.
Where the agreement is high, the DTM is seamless.
Where it is low, such as due to temporal or processing differences, a "step" can be observed.

// #drafting.inline-note()[zoomed-in hillshade]
