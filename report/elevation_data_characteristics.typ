// Evidence and full source links: elevation_data_characteristics_sources.md
// Includes source data, not the common 5 m processed output.
// No page settings: inherits portrait/layout from the containing document.
#block[
  #set text(size: 7pt, hyphenate: false)
  #set par(justify: false, leading: 0.5em)

  #let fields = (
    [Region], [Dataset / provider], [Source format], [Survey method],
    [Native grid (m)], [CRS (EPSG)],
    [Vertical datum],
  )
  #let rows = (
    ([Netherlands], [AHN / Rijkswaterstaat; via PDOK#super[h]], [GeoTIFF], [ALS], [0.5], [28992], [NAP]),
    ([Bavaria (DE)], [DGM5 / LDBV], [XYZ Tiles], [ALS], [5], [25832], [DHHN2016 / NHN]),
    ([Baden-#linebreak()Württemberg (DE)], [DGM1 / LGL], [XYZ Tiles], [ALS#super[b]], [1], [25832], [DHHN2016 / NHN]),
    ([Hessen (DE)], [ATKIS DGM1 / HVBG], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([North Rhine-#linebreak()Westphalia (DE)], [DGM1 / Geobasis NRW], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([Rhineland-#linebreak()Palatinate (DE)], [DGM1 / LVermGeo], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([Saarland (DE)], [DGM1 / LVGL; via Mapterhorn], [GeoTIFF], [ALS], [1], [25832], [ND#super[e]]),
    ([France], [RGE ALTI 5 m / IGN], [ASCII Grid], [Mixed], [5], [2154], [IGN69]),
    ([Luxembourg], [LiDAR 2024 MNT / ACT], [GeoTIFF], [ALS], [0.5], [2169], [ND]),
    ([Liechtenstein], [swissALTI3D / swisstopo], [GeoTIFF], [Mixed#super[f]], [2], [2056], [LN02]),
    ([Switzerland], [swissALTI3D / swisstopo], [GeoTIFF], [Mixed#super[f]], [2], [2056], [LN02]),
  )

  #figure(
    table(
      columns: (2.6fr, 2.1fr, 1.5fr, 1fr, 0.85fr, 1fr, 1.65fr),
      inset: (x: 2pt, y: 5pt),
      align: left + horizon,
      stroke: 0.35pt + rgb("bcc3cb"),
      fill: (x, y) => if y == 0 { rgb("edf0f3") },
      table.header(..fields.map(field => strong(field))),
      ..rows.flatten(),
    ),
    caption: [Characteristics of the source elevation datasets used in the study.],
  ) <tab:elevation-data>

  #v(5pt)
  #set text(size: 7.5pt)
  CHECK survey method for BW Saarland France Liechtenstein Switzerlan
]
