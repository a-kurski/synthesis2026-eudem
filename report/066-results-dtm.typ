#import "@preview/drafting:0.2.2"

The pipeline successfully produces a DTM of the Rhine catchment area. This is shown in @fig:final_dtm.

#figure(
    image("assets/whole_dtm_with_legend.png", width: 70%),
    caption: [Finalized Rhine Catchment DTM]
)<fig:final_dtm>

The DTM covers 97.33% (159284.05 km#super[2] or 6371361919 cells out of 163645.59 km#super[2] or 6545823685 cells) of the catchment area, for an omission rate of 2.67 %.
The omission rate can be attributed exclusively to the missing regions (Austria, Italy, and Belgium) and NoData values within the Dutch dataset.

The commission rate within the final DTM is zero.
However, the overlaps at the border add up to 4140.09 km#super[2], resulting in a commission rate of the underlying data of 2.60%.

The seamlessness of the DTM is dependent on the quality of the underlying datasets.
Where the agreement is high, the DTM is seamless.
Where it is low, such as due to temporal or processing differences, a "step" can be observed.

// #drafting.inline-note()[zoomed-in hillshade]
