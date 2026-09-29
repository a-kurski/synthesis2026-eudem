= Literature Review

This chapter goes over the reviewed literature. It discusses both the existing approaches for harmonizing cross-border data, INSPIRE, and point cloud processing methods.


== Cross-border DEM

Whereas most reports focus on semantic data harmonization of cross-border areas, few look at the DTM data. While little more than an educated guess, it is likely due to existing datasets. The European data portal lists two official DTM datasets #ref(<europaDigitalElevation>). These are both based on Copernicus data and have a 30 and 90 meter cell resolution respectively (at the equator). The Copernicus DEM is listed as having a vertical RMSE of $1.68 m$ for the 90 meter dataset #ref(<CopernicusDEM-RP-001_ValidationReport>), and a RMSE of $2.9 m$ for the 30 meter dataset #ref(<europaDigitalElevation>). Meanwhile, most national datasets fall between 0.5 and 2 meter resolution for cells. It is therefore likely, that for most applications on a small scale, the national datasets suffice. While for large scale, cross-border projects, the European DTM dataset suffices.

Nevertheless, one report details a method of cross-border harmonization. The report details harmonization of the coordinate reference system, orthrophoto, semantic information, and the digital terrain model #ref(<Noardo2016>). For this report only the CRS transformation and DTM harmonisation are relevant. They describe the process of transforming the datasets. However, for the pipeline this process will be automated using GDAL. However, it does highlight the INSPIRE, as the recommended quasi-geoid named European Vertical Reference
Frame (EVRF) for the vertical reference. Therefore, EVRF should be considered as the vertical reference.

In an effort to harmonize the DTM, the report describes a gradient approach. In this approach the point proximity of the border is evaluated to determine the weight of the pixel value from either DTM. The following formula is used:

#align(center,
$H_A = "DTM"_"France A" * D/500 + "DTM"_"Italy A" * (500-D)/500$)

Where $H_A$ is the final assigned height, while $D$ represents the distance from the border. While this method does smooth the transition, it does also likely diverge from reality, even if the discrepancy is minimized.