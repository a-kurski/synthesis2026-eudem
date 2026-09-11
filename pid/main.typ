#import "@preview/timeliney:0.4.0"

// Cover page
#set page(
  margin: 0pt,
)

#image(
  "PID_Cover_v2.pdf",
  page: 1,
  width: 100%,
  height: 100%,
  fit: "cover",
)

#pagebreak()

// Main document
#set page(
  margin: (
    top: 2.5cm,
    bottom: 2.5cm,
    left: 2.5cm,
    right: 3cm,
  ),
)

#set heading(numbering: "1.1")

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  it
}

#show figure: set block(breakable: true)

#include "000-front-matter.typ"

#pagebreak()

#outline()



#include "010-introduction.typ"
#include "020-contributors.typ"
#include "030-project-definition.typ"
#include "040-methodology.typ"
#include "050-planning.typ"

#bibliography(
  "references.bib",
  style: "apa",
  title: [References],
)

#include "990-appendix.typ"
