#import "@preview/timeliney:0.4.0"

#set page(
  paper: "a4",
  margin: 0pt,
)

#image(
  "PID_cover.png",
  width: 100%,
  height: 100%,
  fit: "cover",
)

#pagebreak()

#set page(
  paper: "a4",
  margin: (x: 25mm, y: 25mm),
)

#set heading(numbering: "1.1")
#show heading.where(level:1): it => {pagebreak(weak: true)
 it}
#show figure: set block(breakable: true)

#outline()

#include "010-introduction.typ"
#include "020-contributors.typ"
#include "030-project-definition.typ"
#include "040-methodology.typ"
#include "050-planning.typ"

#bibliography("references.bib", style: "apa", title: [References])

#include "990-appendix.typ"
