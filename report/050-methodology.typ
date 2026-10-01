#import "@preview/lovelace:0.3.0": *
#import "@preview/drafting:0.2.2"
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge

= Harmonisation Pipeline <chap:method>

This chapter describes the current state of the harmonisation pipeline, providing a general overview and specifics of the approach to processing gridded (raster) elevation data and point clouds.

== Pipeline Overview

The aim of the project is to create a fully automated pipeline, which at this stage has not yet been achieved. Instead, separate pipelines for processing raster and point cloud data have been developed, which will be integrated after the midterm.

The raster processing is the main part of the pipeline --- re-extracting a DTM from scratch is computationally expensive and is deemed unnecessary, and it is assumed #drafting.margin-note[but should be tested!] that the national DTMs are sufficiently accurate. Point cloud processing is secondary and predominantly serves as an additional layer of evaluation and quality assurance.

// Boxed "start/end" nodes vs. plain process steps
#let boxed(pos, label, ..args) = node(
  pos, label, stroke: 1pt, inset: 6pt, corner-radius: 2pt, ..args,
)

#figure(
  diagram(
    spacing: (2.2em, 1.5em),
    edge-stroke: 1pt,
    node-inset: 6pt,

    // ── DEM branch ──────────────────────────────
    boxed((0, 0), [DEM]),
    boxed((0, 1), [Reproject]),
    boxed((0, 2), [Resample]),
    boxed((0, 3), [Interpolate]),
    boxed((0, 4), [Stitch]),

    edge((0, 0), (0, 1), "-|>"),
    edge((0, 1), (0, 2), "-|>"),
    edge((0, 2), (0, 3), "-|>"),
    edge((0, 3), (0, 4), "-|>"),

    // Side branch: DEM -> compare
    boxed((1.4, 1), [Compare in overlaps]),
    edge((0, 0), (1.4, 0), (1.4, 1), "-|>"),

    // ── Point cloud branch ──────────────────────
    boxed((3.2, 0), [PC]),
    boxed((3.2, 1), [Register]),
    boxed((3.2, 2), [Analyse registration \ Affine transform]),
    boxed((3.2, 3.4), [Re-extract DEM \ if necessary]),

    edge((3.2, 0), (3.2, 1), "-|>"),
    edge((3.2, 1), (3.2, 2), "-|>"),
    edge((3.2, 2), (3.2, 3.4), "-|>"),
  )
)


== Harmonisation with Point Clouds

In the pipeline, the point clouds are used as an additional step to assess the agreement between two different national datasets. Converting the point clouds to the same CRS and subsequently performing registration allows to obtain better estimates of planimetric and vertical accuracy. The pseudocode describing the general principles is presented below; more elaborate description follows.

#pseudocode-list(booktabs: true, booktabs-stroke: 1pt, line-number-supplement: "line", title: [#smallcaps[*Point Cloud Registration*]])[
  + *Input:* a set of point clouds of country A $scr(a) in scr(A)$; a set of point clouds of country B $scr(b) in scr(B)$ \ *Output:* a set of translation vectors $scr(T)$ obtained from registering $scr(a) in scr(A)$ against $scr(b) in scr(B)$
  + *for* every $scr(a)_i in scr(A) inter scr(b)_j in scr(B) != emptyset$ *do:*
    + perform registration of $scr(a)_i$ against $scr(b)_j$
    + $A_(i j) arrow.l$ affine transform from registration
    + $bold(p)^T = mat(x, y, z) arrow.l$ a point in $scr(a)_i$
    + $bold(p)_t arrow.l A_(i j) bold(p)$ \// _apply affine transform to point_
    + $bold(t)_(i j) arrow.l bold(p)_t - bold(p)$ \// _find pure translation from initial point to transform_
    + append $bold(t)_(i j) "to" scr(T)$
]

Due to computational limitations, the comparison is done between tiles rather than between full national datasets.
The downside of this approach is that the registration is likely to be less accurate overall as it relies on relatively fewer points; the upside is that it may be more informative in regards to small-scale changes at the border.

Another decision made to reduce computational costs is to use the extent of a point cloud as provided in the header when finding pairs of intersections instead of a convex, concave, or an #sym.alpha\-hull.
This may result in false positives among intersection pairs and thus an incorrect assessment of the accuracy.
In these cases, cross-referencing with a raster is advised #highlight(fill: none, stroke: red)[but currently not implemented].

The registration is performed using iterative close point (ICP) algorithm of the `open3D` python library --- equivalent functionality exists in PDAL #highlight(fill: none, stroke: red)[(which we might switch to for the final processing)].
Notably, the registration produces a full affine transform $A = mat(R, bold(t))$ --- as the point clouds can be far from the origin, even a small rotational component has a large influence on the transformation and needs to be compensated with a large translation vector.
To evaluate the accuracy, pure translation is needed. It is obtained by applying the full affine transform $A$ to a point from the dataset $bold(p)$ and subtracting the transformed coordinates from coordinates of the initial point.

#drafting.inline-note()[The intention eventually is that for areas where both the national DEMs and the PCs disagree significantly, we also re-extract a DTM from scratch using the most recent point cloud; we've not done that yet]
