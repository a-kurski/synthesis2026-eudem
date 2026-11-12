#let err = [●]

#let vlabel(txt) = rotate(90deg, reflow: true)[#txt]

#figure(
  {
    set text(size: 9pt)
    table(
      columns: (2.2fr,) + (1fr,) * 13,

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

      table.cell(colspan: 1)[*Interpolation*],
      table.cell(colspan: 2)[*Ground\ filtering*],
      table.cell(colspan: 4)[*Temporal*],
      table.cell(colspan: 2)[*Water mask*],
      table.cell(colspan: 2)[*Pre-\ processing*],
      table.cell(colspan: 2)[*Post-\ processing*],

      // ============================================================
      // artefact HEADER (ROTATED)
      // ============================================================

      [#vlabel([Interpolation])],

      [#vlabel([Overpass])],
      [#vlabel([Steep slopes])],

      [#vlabel([Snow cover])],
      [#vlabel([Bulk storage])],
      [#vlabel([Excavation])],
      [#vlabel([Construction works])],

      [#vlabel([Water modelling])],
      [#vlabel([River mask failure])],

      [#vlabel([ALS striping])],
      [#vlabel([Tile seam])],

      [#vlabel([Extrapolation])],
      [#vlabel([Edge resampling])],

      // ============================================================
      // SEPARATORS
      // ============================================================

      table.vline(x: 2, stroke: 2pt),
      table.vline(x: 4, stroke: 2pt),
      table.vline(x: 8, stroke: 2pt),
      table.vline(x: 10, stroke: 2pt),
      table.vline(x: 12, stroke: 2pt),

      // ============================================================
      // DATA
      // ============================================================

      [NL/DE-NW], [#err], [], [], [], [#err], [], [], [], [#err], [], [], [#err], [#err],
      [DE-NW/DE-RP], [#err], [#err], [#err], [], [], [#err], [#err], [], [#err], [#err], [#err], [#err], [],
      [DE-NW/DE-HE], [#err], [#err], [#err], [#err], [], [#err], [#err], [], [], [], [], [], [],
      [DE-RP/DE-SL], [#err], [#err], [#err], [], [], [#err], [#err], [], [#err], [], [], [#err], [#err],
      [DE-RP/DE-BW], [#err], [#err], [], [], [#err], [], [#err], [], [#err], [], [#err], [], [],
      [DE-RP/DE-HE], [#err], [], [], [], [], [], [], [], [], [], [#err], [#err], [],
      [DE-RP/FR], [#err], [#err], [#err], [], [], [], [], [#err], [#err], [#err], [], [], [],
      [DE-RP/LU], [#err], [], [#err], [], [#err], [], [#err], [], [#err], [], [], [], [#err],
      [DE-SL/FR], [#err], [], [#err], [], [], [#err], [#err], [#err], [#err], [], [], [], [],
      [DE-SL/LU], [#err], [], [#err], [], [#err], [#err], [], [], [#err], [], [], [], [],
      [DE-HE/DE-BW], [#err], [], [#err], [], [], [#err], [#err], [], [#err], [], [], [], [#err],
      [DE-HE/DE-BY], [#err], [], [#err], [], [], [#err], [#err], [#err], [#err], [], [], [], [],
      [DE-BW/DE-BY], [#err], [#err], [], [], [], [#err], [#err], [], [#err], [], [#err], [#err], [#err],
      [DE-BW/FR], [#err], [], [#err], [], [#err], [#err], [], [#err], [#err], [#err], [], [], [],
      [DE-BW/CH], [#err], [], [#err], [], [], [#err], [#err], [#err], [#err], [], [], [], [],
      [FR/LU], [#err], [], [#err], [], [], [#err], [#err], [], [#err], [], [], [], [],
      [FR/CH], [#err], [], [#err], [], [], [], [], [], [], [#err], [], [], [],
    )
  },

  caption: [
    Overview of border region artefacts. Cells marked with #err imply the subcategory artefact occurs at the border pair.
  ]
) <tab:artefacts_table>
// ]
