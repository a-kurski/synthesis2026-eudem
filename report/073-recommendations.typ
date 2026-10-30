#import "@preview/drafting:0.2.2"

== Recommendations

=== Recommendations on Standartisation <sec:recommend-standards>

Currently, @INSPIRE specification on elevation is a 260-page document, encompassing everything from the basic definition of a terrain to implementations of the GML schema, with a particular focus on the latter.
We find that the specification is quite limited, focusing on the interoperability only on a very basic level (essentially, that all data follows a schema which can be read in an automated way) without much regard for the interoperability between the datasets themselves.
Currently, the specification is not fully followed: while most elevation datasets appear to be INSPIRE-compliant, France publishes its data as ASCII grid which is expressly disallowed #cite(<inspire2024elevation>, supplement:[p. 166]).
However, this guidance is one line, presented as a note rather than requirement, which makes it easy to ignore.
We would encourage that the specification is reviewed and rewritten in a way that enables easier implementation, e.g. by including a catalogue of all requirements, recommendations, and their scope.

To further ensure better cross-border interoperability, we recommend the following:
- Data providers to adopt a unified way to access and download the data. We particularly recommend a WCS (as adopted by the Netherlands and NRW) as it is an existing standard and allows for automatic server-side querying of a particular geographic extent.
- Data providers to adopt a unified NoData value, and expressly include it in the elevation data.
- Data providers to adopt a unified way to extract a terrain model.
  - Based on the work by #cite(<cai2023>, form: "prose"), we suggest @ICSF will likely perform best for for ground filtering but further research is needed.
  - A standartised interpolation method for filling gaps in the ground points is also needed, as we see artefacts introduced by linear interpolation on a TIN or extracting data from CSF points. We believe that @RBF would produce best results deterministically, but further comparison of the different interpolation methods is needed.
  - We also recommend that the river surface is extracted with a hydro-flattening approach based on the elevation of points classified as water given the errors introduced by interpolation on a TIN or the need for post-processing if the water surface is excluded.
- Supplementary data on dataset quality to be provided. This data can include masks showing the interpolated areas, the water surface, the time of acquisition of each given elevation sample, or the density of (ground) points within each grid cell. This data can support integrating elevation data from different providers.

=== Further Work <sec:recommend-further-work>

There are several areas of the project which warrant improvement.

The evaluation of the results within this report focused on the agreement between national datasets due to absence of robust ground truth.
We recommend that such a ground truth be obtained and results be compared against it.
One such approach, as outlined in @sec:spaceborne-gdem, is evaluating the DTM against the national geodetic control networks.

Although runoff modelling is the key use case of the @DTM produced within the project, the elevation raster is currently not optimised for it, and no runoff modelling was performed.
We suggest that such optimisation and modelling can be performed for the given cross-border @DTM.

The pipeline still struggles with some NoData values as seen with @BW elevation dataset. While a small change, a more robust way to handle NoData even where it is not encoded into the dataset is needed.
The river mask is rather basic in its functionality and currently misses sections of the river; work can continue to develop a more robust water detection algorithm which can better handle the different methods used to extract the water surface.



#drafting.inline-note()[anything else that kinda works but doesn't really?]

Within this project, the differences between the different DTMs are only analysed but not mitigated.
We recommend that ways to detect and automatically fix those differences are investigated, based either on the raster data or a combination of raster and point cloud data.

A more ambitious but worthwhile version of this project would involve a re-extraction of the DTM from the national and regional point cloud data, including re-classification and performing hydro-flattening.
The outcomes of such a project can more specifically inform the recommendations listed in @sec:recommend-standards.

As an alternative to hydro-flattening, the bathymetric data can be introduced into the rivers.
Such data can either be synthetic, as proposed by #cite(<dysarz2018>, form: "prose"), or integrate existing river- and lakebed surveys with aerial lidar data.
