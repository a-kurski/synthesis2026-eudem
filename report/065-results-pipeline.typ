#import "@preview/drafting:0.2.2"

During this project, we have created an automated pipeline which can process, aggregate, and compare national gridded elevation products.
The code has been executed on the server which has a processor with 128 threads and a maximum clock speed of 2900 MHz, and 512GB RAM.
The server was shared with other members of the research group; we cannot guarantee that we had access to its full resources at all times.
The pipeline has been run utilising 64 threads; in 4 parallel processes for individual @DTM rasters, and sequential processing for river mask extraction and border pair comparison.
We have attempted parallel processing for river mask and comparison; however, we found that both tasks have high memory demands which would result in some, especially larger, regions being skipped if sufficient memory could not be allocated.

The time required to produce an aggregate @DEM was measured at 2:29:22; and time to produce the full comparison was measured at 14:44:39.
Note that these times are for a single run of the full pipeline, starting on 2026-10-25 at 00:16:57 and finishing on 2026-10-25 at 20:43:03; they may not be representative of optimal or typical resource availability.

If the associated `.json` file is configured properly, the code can be executed in full and produce the desired outcome.
However, the pipeline and the `.json` needed to be modified several times to account for the unforeseen errors.
The pipeline was first tested on Netherlands and @NRW to ensure individual components are integrated, and it was subsequently run in full.
During the full runs, several issues were discovered and subsequently patched.

The first of these was that Hessen publishes data by administrative unit; for some of these units, NoData is represented with a 0 value but the value is not encoded in the metadata.
Some of Hessen's tiles also had no horizontal CRS.
Stitching these tiles resulted in regions of flat terrain with elevation value around 20cm (non-zero due to CRS transform).
Similar behaviour was observed in RLP, where the coordinates were provided in UTM32N but the CRS was not consistently described in the metadata.
This behaviour has been patched by force-assigning a horizontal and vertical CRS and a NoData value for each region.

Issues with NoData value not declared were also observed in @BW.
These are mostly resolved except for several tiles overlapping with Bavaria, where NoData issue persists.
We acknowledge these issues within the analysis of the border regions, but resolving them was deemed to be of low priority given the time constraints.

During the later runs, we observed that large parts of the Netherlands and France are absent from the final product.
We determined that this issue stems from a missing VCRS transform.
Previously, a warning was issued and the pipeline continued with no VCRS transform applied, but during the later runs, warping some of the tiles was skipped.
We believe this to be a change on the server of the PROJ library, likely following the PHP vulnerability of October 20; however, a definitive diagnostic was not performed.
The fix we adopted was setting the VCRS for affected regions to `null` such that no transform is attempted, which allows the pipeline to be executed.

#figure(
  grid(
    columns: (1fr, 1fr),
    column-gutter: 5pt,
    [#image("assets/dtm-hessen.png")],
    [#image("assets/dtm-missing-france.png")]
  ),
  caption: [Issues diagnosed with earlier runs of the pipeline: incorrect NoData value for Hessen (left) and missing parts of France (right)]
)
