== Limitations

The project has resulted in our successfully producing a harmonised @DTM of the Rhine catchment area. Furthermore, the automated pipeline for processing and analysis has been completed and tested, resulting in the evaluation of data quality between bordering regions to determine the quality of the product.

However despite this success, there are limitations to the project.
The first limitation is the scope of the project itself.
Originally designed for a group of 4--6, it was completed by only three people over the course of 10 weeks.
Within this time frame, they performed acquisition, harmonisation, and evaluation; carried out project management; and presented their results in this report and in talks.
The small number of people essentially prevented multitasking~--- for instance, data acquisition and processing were paused at one point to allow the team to focus on presenting the results.
As a result, several aspects of the project were excluded from its scope: these include re-extracting the @DTM from raw point cloud data, automated artefact correction, and more extensive validation of the final product.

Several issues were anticipated within the risk analysis carried out at the start of the project (@sec:risk).
During week 6 of the project, the processing server was unavailable due to planned but unannounced maintenance. While coding and documentation continued, no testing or processing was possible. Furthermore, personal circumstances affected the availability of the team members during weeks 8 and 9. These events occurred during the final stages of analysis and reporting, leaving little opportunity to mitigate them.
However, the impact of these events was not significant enough to completely stop the project.

As described above, the scope of the project was reduced to focus primarily on @DTM:pls instead of point clouds. While it significantly reduced the total workload, it did prevent evaluating raw data instead of processed elevation data. The raw data should in theory contain fewer processing differences such as ground filtering or water handling. Furthermore, using a unified processing method would enable a better extraction of the water surface.

Another limitation is the reliance on external raster datasets. The quality of the end product is determined by the sum of its parts. Throughout the analysis it became clear that most artefacts are the result of temporal, spatial and processing differences between datasets, and not necessarily the processing pipeline. In several cases, large artefacts such as extrapolation data or misaligned tiles caused large differences between the elevation data. In other cases, the exact cause could not be established due to the lack of data about processing methodology, or raw point cloud data to evaluate the raw data for clues.

The water mask itself also introduces limitations. While not an originally intended element of the pipeline, the analysis proved that water was a consistent source of large disagreements and would need to be filtered out for any meaningful analysis to be carried out. However, it makes assumptions about water such as having small elevation changes, and requires a coarse, incomplete existing mask to function. So while the analysis benefits from the feature, it still needs refinement. It is currently also not used to correct the water surface in the final product.

Several limitations related to the border analysis itself also exist. The comparisons evaluate agreement based on the quality of the overlap between datasets instead of their absolute accuracy. Accounting for the dataset accuracy and combining it with the border differences would give a better idea of the accuracy of the @DTM, however due to the lack of such metadata, it is not possible to determine this accuracy.

Finally, a number of artefact categories are based on qualitative rather than quantitative evidence. While in many cases, interpretation allows the cause of a difference to be determined based on facts and data, we haven't always been able to determine it exactly. Verifying whether the interpretations are correct would require processing of metadata, and classified point cloud data for all regions. Such data was not widely available, or within the scope and temporal constraints of the project.

// Despite all these limitations and setbacks, the project does demonstrate that a harmonised cross-border @DTM can be constructed in an automated manner from heterogeneous datasets. Furthermore, the analysis shows that many of the inconsistencies can be traced back to source data inconsistencies, rather than the pipeline, which can in most cases be solved through reprocessing of the data using point clouds. The identified limitations therefore represent both challenges for future works, and opportunities for improving cross-border interoperability for elevation datasets in Europe.
