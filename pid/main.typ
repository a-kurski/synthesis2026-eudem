#import "@preview/timeliney:0.4.0"

#set heading(numbering: "1")
#show heading.where(level:1): it => {pagebreak(weak: true)
 it}
#show figure: set block(breakable: true)

#include "010-introduction.typ"
#include "020-contributors.typ"
#include "030-project-definition.typ"
#include "040-methodology.typ"
#include "050-planning.typ"

#bibliography("bib.bib", style: "ieee")

#include "990-appendix.typ"
