#import "@preview/drafting:0.2.2"

= Results <chap:results>

At current stage, only some intermediate results are available.

Raster data for certain regions --- currently, the Netherlands and Germany's Nordrhein-Westfalen --- has been successfully downloaded within a given mask. The data has been processed as described in @chap:method; the resulting raster can be seen below.

#drafting.inline-note()[TODO: add figure]

Point cloud harmonisation has been tested on approximately 20km stretch of the German-Dutch border. Analysing the translation of the resulting 63 intersection shows the following:
- the root median square translation is 277.3 m horizontally and 1.2233 m vertically;
- the highest absolute translation is 1912.6 m horizontally and  5.5389 m vertically;
- the lowest absolute translation is 0 m both horizontally and vertically for one of the intersections.
- the median absolute translation is 0.1825 m horizontally  0.0691 m vertically.

There are several outliers --- pairs where a point cloud is translated several hundred meters horizontally --- which are likely the cases where the footprints the actual data is non-intersecting but the bounding boxes are. Filtering for such outliers is necessary.
