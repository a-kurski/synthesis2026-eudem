#import "@preview/lovelace:0.3.0": *

= Harmonization Pipeline <Harmonization_pipeline>

#pseudocode-list(booktabs: true, booktabs-stroke: 1pt, line-number-supplement: "line", title: [#smallcaps[*Point Cloud Registration*]])[
  + *Input:* a set of point clouds of country A $scr(a) in scr(A)$; a set of point clouds of country B $scr(b) in scr(B)$ \ *Output:* a set of translation vectors $scr(T)$ obtained from registering $scr(a) in scr(A)$ against $scr(b) in scr(B)$
  + *for* every $scr(a)_i in scr(A) inter scr(b)_j in scr(B) != emptyset$ *do:*
    + perform registration of $scr(a)_i$ against $scr(b)_j$
    + $A_(i j) arrow.l$ affine transform from registration
    + $p^T = mat(x, y, z) arrow.l$ a point in $scr(a)_i$
    + $p_t arrow.l A_(i j) p$ \// _apply affine transform to point_
    + $t_(i j) arrow.l p_t - p$ \// _find pure translation from initial point to transform_
    + append $t_(i j) "to" scr(T)$
]
