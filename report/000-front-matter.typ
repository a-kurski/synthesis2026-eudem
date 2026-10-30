#import "@preview/drafting:0.2.2"

// #drafting.inline-note()[This section will contain the title, our names, names of supervisors, the date, etc.]
//
#set align(center + horizon)

#v(1fr)

#text(size: 16pt, weight: "bold")[Harmonising European Elevation Data Across Borders]

#v(1cm)

MSc Geomatics Synthesis Project Report

#v(4em)

#grid(
  columns: (4cm, 4cm, 4cm),
  gutter: 3pt,
  [Arda Baysal],[Artemi Kurski],[Ruben Vons],
  [5484987],[6195784],[6285880],
)

#v(2em)

Supervised by

#grid(
  columns: (4cm, 4cm, 4cm),
  gutter: 3pt,
  row-gutter: 10pt,

  [Gina Stavropoulou],
  [Maarten Pronk],
  [Daan van der Heide],

  [TU Delft],
  [Deltares],
  [Rijkswaterstaat],
)

#v(3em)

#grid(
  columns: (5cm, 5cm, 5cm),
[#image("assets/tud3dgeoinfo.png", height: 1.5cm, fit: "contain")],
[#image("assets/Deltares_logo.svg", height: 1.5cm, fit: "contain")],
[#image("assets/RWS_logo.svg", height: 1.5cm, fit: "contain")],
)

#v(1fr)
Delft University of Technology, \ Faculty of Architecture and the Built Environment, \ The Netherlands
#v(4em)
#datetime.today().display("[month repr:long] [day], [year]")

#v(1fr)

#set align(left)
