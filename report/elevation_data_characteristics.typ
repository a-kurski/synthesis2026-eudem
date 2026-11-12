// Source-data characteristics: one header row and eleven named region rows.
// Acquisition years refer to surveying, not download dates.
// Report vertical accuracy with its metric (e.g. RMSE) and units.
// Coverage refers to the study area; distinguish source gaps from later filling.
#set text(size: 9pt)

  #let fields = (
    [Region], [Dataset / provider], [Source format], [Survey method],
    [Native grid (m)], [CRS (EPSG)],
    [Vertical datum],
  )
  #let rows = (
    ([@NL], [AHN / Rijkswaterstaat], [GeoTIFF], [ALS], [0.5], [28992], [NAP]),
    ([@DE-BY], [DGM5 / LDBV], [XYZ Tiles], [ALS], [5], [25832], [DHHN2016 / NHN]),
    ([@DE-BW], [DGM1 / LGL], [XYZ Tiles], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([@DE-HE], [ATKIS DGM1 / HVBG], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([@DE-NW], [DGM1 / Geobasis NRW], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([@DE-RP], [DGM1 / LVermGeo], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([@DE-SL], [DGM1 / LVGL], [GeoTIFF], [ALS], [1], [25832], [DHHN2016 / NHN]),
    ([@FR], [RGE ALTI 5 m / IGN], [ASCII Grid],
      [Mixed#footnote[IGN uses ALS in flood-prone areas, coastal zones and large forests combined with radar in mountainous areas
    (Alps, Pyrenees, Cévennes and Corsica), and aerial image correlation elsewhere. In some areas processed by image    correlation, older elevation data fill gaps where vegetation or other surface objects prevent ground measurements.]]
      , [5], [2154], [IGN69]),
    ([@LU], [LiDAR 2024 MNT / ACT], [GeoTIFF], [ALS], [0.5], [2169], [n/a]),
    ([@LI], [swissALTI3D / swisstopo], [GeoTIFF], [Mixed#footnote[swissALTI3D combines airborne laser scanning with
    aerial photogrammetry, including automatic stereo correlation
    and manual stereoscopic measurements. The source methods
    vary spatially.]<ftnt>], [2], [2056], [LN02]),
    ([@CH], [swissALTI3D / swisstopo], [GeoTIFF], [Mixed@ftnt], [2], [2056], [LN02]),
  )



  // #show figure.where(kind: table): set figure.caption(position: top)
  // #show figure.caption.where(position: top): set text(size: 9pt)
  #figure(
    placement: auto,
    kind: table,
    supplement: [Table],
    caption: [Characteristics of the source elevation datasets used in the study.],
    // gap: 15pt,
    [
      #table(
        columns: (auto, auto, auto, 1fr, 0.85fr, 1fr, 1.65fr),
        // inset: (x: 2pt, y: 5pt),
        align: left + horizon,
        stroke: 0.35pt + rgb("bcc3cb"),
        fill: (x, y) => if y == 0 { rgb("edf0f3") },
        table.header(..fields.map(field => strong(field))),
        ..rows.flatten(),
      )
    ]
  ) <tab:elevation-data>

  // #v(5pt)
  // #set text(size: 7.5pt)
