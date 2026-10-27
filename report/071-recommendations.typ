== Recommendations

=== Recommendations on Standartisation

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

=== Further Work
