#import "@preview/drafting:0.2.2"

// #drafting.inline-note()[This section will contain the title, our names, names of supervisors, the date, etc.]
//
#set align(center + horizon)

#v(2fr)

#text(size: 16pt, weight: "bold")[Harmonising European Elevation Data Across Borders]

#v(1cm)

MSc Geomatics for the Built Environment\
GEOIT1501 Synthesis Project Report

#v(4em)

#grid(
  columns: (4.5cm, 4.5cm, 4.5cm),
  gutter: 3pt,
  row-gutter: 12pt,
  [*Artemi Kurski*],[*Arda Baysal*],[*Ruben Vons*],
  [6195784],[5484987],[6285880],
)

#v(2em)

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

#v(5em)

#grid(
  columns: (5cm, 5cm, 5cm),

)

#v(1fr)
Faculty of Architecture and the Built Environment, \
Delft University of Technology, \
The Netherlands
#v(4em)
#datetime.today().display("[month repr:long] [day], [year]")

#v(1fr)



#set align(left)
