== Conclusion

During this project, an automated pipeline for producing a harmonised DTM of the Rhine catchment area was developed.
The DTM of most of the Rhine catchment area at a 5m resolution was successfully produced by executing the pipeline.

Within the EU, the INSPIRE directive informs the requirements to several themes of geographical information, including elevation.
For land-elevation, INSPIRE Specification on Elevation requires that gridded (i.e. raster) data is available in either GeoTIFF or GML format.
It requires that ETRS89-derived CRS is used, recommending geodetic ETRS89.
The specification further establishes the requirements for data quality: the ones we consider expressly relevant are commission rate, omission rate, and the relationship between GSD and vertical RMSE, where $3 lt.eq "GSD"/"RMSE" lt.eq 20$.

Several definitions of the catchment area were considered.
Within the project, we are using the catchment as defined by HydroSHEDs through performing runoff modelling on a global elevation dataset.
This catchment definition includes the main body of the Rhine but excludes the Maas and parts of the delta such as IJssel.
It covers parts of Italy, Austria, Liechtenstein, Switzerland, Germany, France, Luxembourg, Belgium, and the Netherlands.

Existing approaches to creating cross-border DEMs were also reviewed.
Only Mapterhorn combines heterogeneous --- global, national, and regional --- sources into a single DEM.
However, Mapterhorn currently does not aim to harmonise them or resolve conflicts at the border.
Alternative cross-border products are global elevation models like Copernicus DEM which is only available at low (30m) resolution.

Alongside global elevation models, national and regional datasets were investigated.
Switzerland and Liechtenstein (jointly), France, Luxembourg, and the Netherlands each collect and publish elevation data.
Within Germany, each region collects and publishes their own elevation data.
To our knowledge, there is no elevation product for regions of Italy and Austria falling within the catchment area.
Similarly, we did not succeed at acquiring the elevation data for Belgium.

The datasets are available at a range or resolutions from 0.5m to 5m; several providers publish both a high- and a low-resolution version.
For different products, the data has a different horizontal and vertical CRS; different NoData values; different approaches to terrain filtering and interpolation are used.
Parts of several datasets do not disclose, or incorrectly disclose, their NoData values and CRSs.
Parts of the datasets have also been acquired at different times, resulting in differences in elevation due to changes in terrain, such as earthworks or construction.
Each of these results in extra needs to data discovery and either an additional processing step --- such as CRS transformation or harmonising NoData values --- or may cause a difference in elevation data at the border.

We find that the pipeline is sensitive to the specifics of the input (meta-)data, such as correct CRS or NoData values.
Several of the datasets feature incorrect or incomplete information which warrants additional data discovery and manually specifying this information for each dataset.
The pipeline currently does not correct disagreements between the datasets due the lack of a robust way to evaluate which of the datasets is "correct" in each given case.
It also has been designed assuming all data within a given region has the same CRS and NoData values.
While this assumption holds for the regions we have investigated, the opposite would require further pre-processing of the data.

To test the accuracy of the DEM, we analyse the errors between the overlapping DTM products.
The analysis allows us to evaluate different kinds of errors, such as errors due to processing differences, acquisition time differences, or issues with the CRS transform.
The majority of the datasets demonstrate good agreement as illustrated by low RMSE and LE90, with errors largely caused by changes in elevation over time, often observed in quarries.
Hessen/RLP and Bavaria/BW border pairs have high RMSE due to errors with interpolation and NoData values --- however, these areas fall outside of the extent of their corresponding region and therefore are not present in the product.
French national elevation product appears to be using a global interpolation function on some of the terrain which also results in high error rate and does have an effect on the quality of the product.
Based on border region comparison alone, it is impossible to evaluate the exact magnitude of these errors.
// but I speculate it's around 1m.

// [x] - What is the Rhine catchment area?
// [x] - What, if any, existing approaches are there to creating a harmonised @DEM from heterogeneous sources?
// [x] - What are the existing @DEM:pla at different scales (regional, national, and global)?
// [x] - What are the issues with cross-border data?
// [x] - What are the @INSPIRE requirements for @DEM:pla?
// [x] - What are the limitations of an automated harmonisation pipeline?
// [x] - How can the accuracy of a reconstructed cross-border @DEM be tested?
