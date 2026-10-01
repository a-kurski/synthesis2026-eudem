#set page(
  paper: "a4",
  margin: (
    top: 2.5cm,
    bottom: 2.5cm,
    left: 2.5cm,
    right: 3cm,
  ),
)



= Appendix <chap:appendix>

#counter(heading).update((0, 0))
#show heading.where(level: 2): it => {
  let n = counter(heading).get().last()
  let letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  let label = if n <= letters.len() { letters.at(n - 1) } else { str(n) }
  [#label. #it.body]
}

== MOSCOW
#let moscow(value) = {
  let color = if value == "Must" {
    rgb("#b3ef88")
  } else if value == "Should" {
    rgb("#f0e876")
  } else if value == "Could" {
    rgb("#f1ac6f")
  } else if value == "Will not have" {
    rgb("#ed7e7e")
  } else {
    none
  }

  box(
    fill: color,
    inset: 4pt,
    width: 100%,
    align(center)[#value]
  )
}

#figure(
  caption: "MoSCoW prioritisation of data requirements for the project",
  table(
    columns: (auto,auto, auto),
    inset: 4pt,
    stroke: (x: none),
    align: horizon,
    table.header([Req ID],[Description], [MoSCoW]),
    [DT-01],[Global/EU DEM], moscow("Must"),
    [DT-02],[Rhine Watershed Mask], moscow("Must"),
    [DT-03],[Rhine Bathymetry], moscow("Will not have"),
    [DT-04], [National/regional PC], moscow("Must"),
    [DT-05], [National/regional DTM], moscow("Must"),
    [DT-06], [National/regional DSM], moscow("Should"),
    [DT-07], [National/regional topographic map], moscow("Could"),
    table.hline(stroke: 2pt),
    [CT-01],[The Netherlands is included], moscow("Must"),
    [CT-02],[Germany is included], moscow("Must"),
    [CT-03],[Belgium is included], moscow("Should"),
    [CT-04],[Switzerland is included], moscow("Must"),
    [CT-05],[France is included], moscow("Must"),
    [CT-06],[Luxembourg is included], moscow("Must"),
    [CT-07],[Austria is included], moscow("Should"),
    [CT-08],[Liechtenstein is included], moscow("Must"),
    [CT-09],[Italy is included], moscow("Will not have"),
    table.hline(stroke: 2pt),
    [MP-01],[DSM raster], moscow("Must"),
    [MP-02],[DTM raster], moscow("Should"),
    [MP-04],[Auxiliary masks and maps], moscow("Should"), //what is a bathymetry mask? is it just water/no water?
    table.hline(stroke: 2pt),
    [TC-01],[Workflow is fully automated], moscow("Must"),
    [TC-02],[Workflow is efficient], moscow("Should"),
    [TC-03],[Workflow is reproducible], moscow("Must"),
    table.hline(stroke: 2pt),
    [RP-01],[Report on findings], moscow("Must"),
    [RP-02],[Report details the workflow], moscow("Must"),
    [RP-03],[Report details the issues with cross-border data], moscow("Must"),
    [RP-04],[Report details the limitations of the workflow], moscow("Must")
  )
) <Moscow_Prioritization>

== Gantt chart
#import "@preview/timeliney:0.4.0"

#timeliney.timeline(
  show-grid: true,
  spacing: 6pt,
  line-style: (stroke: 4pt),

  {
    import timeliney: *

    // ─────────────────────────────────────────────
    // HEADER
    // ─────────────────────────────────────────────

    headerline(
      group(
        ("1", 1),
        ("2", 1),
        ("3", 1),
        ("4", 1),
        ("5", 1),
        ("6", 1),
        ("7", 1),
        ("8", 1),
        ("9", 1),
        ("10", 1),
      ),
    )

    // ─────────────────────────────────────────────
    // ORGANISATION
    // ─────────────────────────────────────────────

    taskgroup(title: [*Organisation*], {
      task(
        "Project Initiation Document (PID)",
        (0, 2),
        style: (stroke: 8pt + rgb("#b3ef88")),
      )

      task(
        "Project planning and scheduling",
        (0, 2),
        style: (stroke: 8pt + rgb("#94c571")),
      )

      task(
        "Meetings",
        (0, 10),
        style: (stroke: 8pt + rgb("#618249")),
      )
    })

    milestone(
      at: 2,
      style: (stroke: (dash: "dashed")),
      [PID deadline],
    )

    // ─────────────────────────────────────────────
    // RESEARCH
    // ─────────────────────────────────────────────

    taskgroup(title: [*Research and Data Collection*], {
      task(
        "Literature study approach",
        (1, 4),
        style: (stroke: 8pt + rgb("#f0e876")),
      )

      task(
        "Review CRS transformation",
        (1, 4),
        style: (stroke: 8pt + rgb("#d2cb67")),
      )

      task(
        "Methodology refinement",
        (1, 4),
        style: (stroke: 8pt + rgb("#a9a453")),
      )

      task(
        "Data collection",
        (1, 4),
        style: (stroke: 8pt + rgb("#878342")),
      )
    })

    // ─────────────────────────────────────────────
    // PROTOTYPE / PRODUCTION
    // ─────────────────────────────────────────────

    taskgroup(title: [*Pipeline Creation*], {
      task(
        "Make prototype",
        (2, 5),
        style: (stroke: 8pt + rgb("#f1ac6f")),
      )

      task(
        "Test prototype parts",
        (3, 5),
        style: (stroke: 8pt + rgb("#cb905d")),
      )

      task(
        "Make production",
        (5, 8),
        style: (stroke: 8pt + rgb("#b07d51")),
      )

      task(
        "Test production parts",
        (6, 7),
        style: (stroke: 8pt + rgb("#946943")),
      )

      task(
        "Test production fully",
        (6, 8),
        style: (stroke: 8pt + rgb("#5a4029")),
      )

      task(
        "Documentation",
        (3, 8),
        style: (stroke: 8pt + rgb("#312316")),
      )
    })

    milestone(
      at: 5,
      style: (stroke: (dash: "dashed")),
      [Prototype completed],
    )

    // ─────────────────────────────────────────────
    // MIDTERM
    // ─────────────────────────────────────────────

    taskgroup(title: [*Midterm*], {
      task(
        "Midterm report",
        (1, 5),
        style: (stroke: 8pt + rgb("#ed7e7e")),
      )

      task(
        "Midterm presentation",
        (1, 5),
        style: (stroke: 8pt + rgb("#c06666")),
      )
    })

    milestone(
      at: 5,
      style: (stroke: (dash: "dashed")),
      [Midterm deliverables],
    )


    // ─────────────────────────────────────────────
    // FINAL
    // ─────────────────────────────────────────────

    taskgroup(title: [*Final*], {
      task(
        "Final report",
        (5, 9),
        style: (stroke: 8pt + rgb("#9f5555")),
      )

      task(
        "Final presentation",
        (5, 10),
        style: (stroke: 8pt + rgb("#723c3c")),
      )
    })

    milestone(
      at: 9,
      style: (stroke: (dash: "dashed")),
      [Final report],
    )

    milestone(
      at: 10,
      style: (stroke: (dash: "dashed")),
      [Final deliverables],
    )
  },
)