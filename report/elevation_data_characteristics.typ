// Source-data characteristics: one header row and eleven named region rows.
// Acquisition years refer to surveying, not download dates.
// Report vertical accuracy with its metric (e.g. RMSE) and units.
// Coverage refers to the study area; distinguish source gaps from later filling.
#set text(size: 8pt)

  #let fields = (
    [Region], [Dataset / provider], [Source format], [Survey method],
    [Native grid (m)], [CRS (EPSG)],
    [Vertical datum],
  )
  #let rows = (
    ([Netherlands], [AHN / Rijkswaterstaat], [GeoTIFF], [ALS], [0.5], [28992], [NAP]),
    ([Bavaria (DE)], [DGM5 / LDBV], [XYZ Tiles], [ALS], [5], [25832], [DHHN2016 / NHN]),
    ([Baden-#linebreak()Württemberg (DE)], [DGM1 / LGL], [XYZ Tiles], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([Hessen (DE)], [ATKIS DGM1 / HVBG], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([North Rhine-#linebreak()Westphalia (DE)], [DGM1 / Geobasis NRW], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([Rhineland-#linebreak()Palatinate (DE)], [DGM1 / LVermGeo], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([Saarland (DE)], [DGM1 / LVGL], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([France], [RGE ALTI 5 m / IGN], [ASCII Grid], [Mixed#super[1]], [5], [2154], [IGN69]),
    ([Luxembourg], [LiDAR 2024 MNT / ACT], [GeoTIFF], [ALS], [0.5], [2169], [n/a]),
    ([Liechtenstein], [swissALTI3D / swisstopo], [GeoTIFF], [Mixed#super[2]], [2], [2056], [LN02]),
    ([Switzerland], [swissALTI3D / swisstopo], [GeoTIFF], [Mixed#super[2]], [2], [2056], [LN02]),
  )


  #show figure.where(kind: table): set figure.caption(position: top)
  #show figure.caption.where(position: top): set text(size: 9pt)

  #figure(
    placement: auto,
    table(
      columns: (2.6fr, 2.1fr, 1.5fr, 1fr, 0.85fr, 1fr, 1.65fr),
      inset: (x: 2pt, y: 5pt),
      align: left + horizon,
      stroke: 0.35pt + rgb("bcc3cb"),
      fill: (x, y) => if y == 0 { rgb("edf0f3") },
      table.header(..fields.map(field => strong(field))),
      ..rows.flatten(),
    ),
    gap: 15pt,
    caption: [Characteristics of the source elevation datasets used in the study.],
    supplement: [Table],
  ) <tab:elevation-data>

  #v(5pt)
  #set text(size: 7.5pt)
