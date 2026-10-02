#import "template-short.typ"

// Cover page
#set page(
  paper: "a4",
  margin: 0pt,
  numbering: none
)

#image(
  "MidtermCover.pdf",
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

#include "000-front-matter.typ"

#counter(page).update(0)

#set page(
  numbering: "1"
)

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  it
}

#include "010-Abstract.typ"
#include "015-acknowledgements.typ"

#outline(title: "Contents")
#outline(title: "Figures", target: figure.where(kind: image))
#outline(title: "Tables", target: figure.where(kind: table))
#set heading(numbering: "1.1")

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  it
}

#show figure: set block(breakable: true)

#set par(justify: true)

#include "020-introduction.typ"
#include "025-contributors.typ"
#include "030-problem-definition.typ"
#include "040-theory-context.typ"
#include "050-methodology.typ"
#include "060-results.typ"
#include "070-discussion.typ"

#bibliography(
  "references.bib",
  style: "apa",
  title: [References],
)

#include "990-appendix.typ"