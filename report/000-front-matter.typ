#import "@preview/drafting:0.2.2"

// #drafting.inline-note()[This section will contain the title, our names, names of supervisors, the date, etc.]
//
#set align(center + horizon)

#v(2fr)

#text(size: 16pt, weight: "bold")[Harmonising European Elevation Data Across Borders: \
  a Case Study on the Rhine Catchment Area]

#v(2fr)

MSc Geomatics for the Built Environment\
GEOIT1501 Synthesis Project Report

#v(1fr)

#grid(
  columns: (4.5cm, 4.5cm, 4.5cm),
  gutter: 3pt,
  row-gutter: 12pt,
  [*Artemi Kurski*],[*Arda Baysal*],[*Ruben Vons*],
  [6195784],[5484987],[6285880],
)

#v(.5fr)

Supervised by:

#grid(
  columns: (4.5cm, 4.5cm, 4.5cm),
  gutter: 3pt,
  row-gutter: 12pt,

  [*Gina Stavropoulou*],
  [*Maarten Pronk*],
  [*Daan van der Heide*],

  [TU Delft],
  [Deltares],
  [Rijkswaterstaat],

  [#image("assets/tud3dgeoinfo.png", height: 1.2cm, fit: "contain")],
  [#image("assets/Deltares_logo.svg", height: 1.2cm, fit: "contain")],
  [#image("assets/RWS_logo.svg", height: 1.2cm, fit: "contain")],
)

#v(1fr)
Faculty of Architecture and the Built Environment, \
Delft University of Technology, \
The Netherlands
#v(.5fr)
#datetime.today().display("[month repr:long] [day], [year]")

#v(2fr)

The cover image shows a fragment of the DTM of the Rhine catchment area covering parts of Switzerland, France, and Germany.

#text(size: 10pt)[
This work is licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0).\
To view a copy of the license, visit https://creativecommons.org/licenses/by/4.0/.
]

#set align(left)
