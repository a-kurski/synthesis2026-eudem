// Source-data characteristics: one header row and eleven named region rows.
// Acquisition years refer to surveying, not download dates.
// Report vertical accuracy with its metric (e.g. RMSE) and units.
// Coverage refers to the study area; distinguish source gaps from later filling.
#set page(paper: "a4", flipped: true, margin: 12mm)
#set text(size: 8pt)

#let fields = (
  [Region],
  [Dataset / version and provider],
  [Model type (DTM / DSM)],
  [Acquisition method],
  [Acquisition year(s)],
  [Native resolution (m)],
  [Horizontal CRS (EPSG)],
  [Vertical datum / height system],
  [Vertical accuracy (metric; m)],
  [Study-area coverage (%)],
  [Gaps / NoData treatment],
)

#let regions = (
  [France],
  [Germany — Bavaria],
  [Germany — Baden-Württemberg],
  [Germany — Hessen],
  [Germany — North Rhine-Westphalia],
  [Germany — Rhineland-Palatinate],
  [Germany — Saarland],
  [Liechtenstein],
  [Luxembourg],
  [Netherlands],
  [Switzerland],
)
#place(center + horizon)[
#figure(
  table(
    columns: (1fr,) * fields.len(),
    rows: (auto,) + (11mm,) * 11,
    inset: 5pt,
    align: left + horizon,
    stroke: 0.5pt + rgb("aab2bb"),
    fill: (x, y) => if y == 0 { rgb("e9eef3") },
    table.header(..fields.map(field => strong(field))),
    ..regions.map(region => (region,) + ([],) * (fields.len() - 1)).flatten(),
  ),
  caption:[Dataset specifications]
)]
