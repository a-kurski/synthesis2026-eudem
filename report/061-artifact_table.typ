#pagebreak()

#set page(
  paper: "a4",
  flipped: true,
  margin: 1cm,
)

#set text(size: 9pt)

#let err = [●]

#let vlabel(txt) = rotate(90deg, reflow: true)[#txt]

#place(center + horizon)[
  #figure(
    table(
      columns: (2fr,) + (1.5fr,) * 13,

      inset: 3pt,
      align: center + horizon,

      stroke: 0.5pt + rgb("aab2bb"),

      fill: (x, y) => {
        if y <= 1 { rgb("e9eef3") }
      },

      // ============================================================
      // CATEGORY HEADER
      // ============================================================

      table.cell(rowspan: 2)[*Region pair*],

      table.cell(colspan: 2)[*Tile artifacts*],
      table.cell(colspan: 2)[*Watermask*],
      table.cell(colspan: 1)[*Interpolation*],
      table.cell(colspan: 2)[*Ground filtering*],
      table.cell(colspan: 4)[*Temporal*],
      table.cell(colspan: 2)[*Border*],

      // ============================================================
      // ARTIFACT HEADER (ROTATED)
      // ============================================================

      [#vlabel([Acquisition striping])],
      [#vlabel([Tile seam])],

      [#vlabel([Water modelling mismatch])],
      [#vlabel([River mask failure])],

      [#vlabel([Interpolation artifact])],

      [#vlabel([Overpass])],
      [#vlabel([Steep slopes])],

      [#vlabel([Snow cover])],
      [#vlabel([Storage changes])],
      [#vlabel([Quarry activity])],
      [#vlabel([Construction activity])],

      [#vlabel([Extrapolation])],
      [#vlabel([Border edge artifact])],

      // ============================================================
      // SEPARATORS
      // ============================================================

      table.vline(x: 3, stroke: 2pt),
      table.vline(x: 5, stroke: 2pt),
      table.vline(x: 6, stroke: 2pt),
      table.vline(x: 8, stroke: 2pt),
      table.vline(x: 12, stroke: 2pt),

      table.hline(y: 2, stroke: 1.2pt),

      // ============================================================
      // DATA
      // ============================================================

      [Netherlands–NRW], [], [], [], [], [#err], [], [], [], [#err], [], [], [#err], [#err],

      [NRW–RLP], [#err], [#err], [], [#err], [#err], [#err], [#err], [], [], [#err], [#err], [#err], [],

      [NRW–Hessen], [], [], [], [], [#err], [#err], [#err], [#err], [], [#err], [#err], [], [],

      [RLP–Saar], [], [], [], [#err], [#err], [], [#err], [], [], [#err], [#err], [#err], [#err],

      [RLP–BW], [], [#err], [], [#err], [#err], [#err], [], [], [#err], [], [#err], [], [],

      [RLP–Hessen], [], [#err], [], [], [#err], [], [], [], [], [], [], [#err], [],

      [RLP–France], [#err], [], [#err], [#err], [#err], [#err], [#err], [], [], [], [], [], [],

      [RLP–Lux], [], [], [], [#err], [#err], [], [#err], [], [#err], [], [#err], [], [#err],

      [Saar–France], [], [], [#err], [#err], [#err], [], [#err], [], [], [#err], [#err], [], [],

      [Saar–Lux], [], [], [], [#err], [#err], [], [#err], [], [#err], [#err], [], [], [],

      [Hessen–BW], [], [], [], [#err], [#err], [], [#err], [], [], [#err], [#err], [], [#err],

      [Hessen–Bav], [], [], [#err], [#err], [#err], [], [#err], [], [], [], [#err], [], [],

      [BW–Bav], [], [#err], [], [#err], [#err], [#err], [], [], [], [#err], [#err], [#err], [#err],

      [BW–France], [#err], [], [#err], [#err], [#err], [], [#err], [], [#err], [#err], [], [], [],

      [BW–Swi], [], [], [#err], [#err], [#err], [], [#err], [], [], [#err], [#err], [], [],

      [France–Lux], [], [], [], [#err], [#err], [], [#err], [], [], [#err], [#err], [], [],

      [France–Swi], [#err], [], [], [], [#err], [], [#err], [], [], [], [], [], [],

      [Swi–Lie], [], [], [], [], [], [], [], [], [], [], [], [], [],
    ),

    caption: [
      Overview of border region artifacts encountered in valid country pairs
    ]
  ) <tab:artifacts_table>
]