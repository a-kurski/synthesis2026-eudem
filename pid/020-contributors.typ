#import "@preview/drafting:0.2.2"

= Contributors <Contributors>

This section provides an overview of the student members of the team and their roles; as well as the clients and the supervision team.

== Team Members

#grid(
  columns: (5cm, 1fr),
  rows: (6cm, 6cm, 6cm),
  gutter: 5pt,
  align: (alignment.horizon),
  [#rect(height: 5cm, width: 4cm)], [
    *Arda Baysal*\
    a.baysal\@student.tudelft.nl

    Background: \
    Turkey \
    BSc Electrical Engineering, TU Eindhoven, The Netherlands

    Interests: Point clouds, geospatial data visualization, digital terrain modelling
  ],
  [#rect(height: 5cm, width: 4cm)], [
    *Artemi Kurski* \
    a.kurski\@student.tudelft.nl

    Background: \
    Estonia \
    BSc Architecture, University of Bath, United Kingdom

    Interests: Computational modelling of terrains and the built environment
  ],
  [#rect(height: 5cm, width: 4cm)], [
    *Ruben Vons* \
    r.m.b.vons\@student.tudelft.nl

    Background: \
    The Netherlands \
    BSc Aeronautical Engineering, Inholland, The Netherlands

    Interests: Solving programming challenges and creating nice visuals.
  ],
)

== Roles

- *Project manager:* Ruben Vons \ A project manager oversees the work plan ensuring the deadlines are realistic and the team is on track to meet them. Project manager is also chairing the meetings.
- *Technical lead:* Artemi Kurski \ A technical lead is in charge of the software architecture and implementation and in this case, the data collection pipeline.
- *Quality assurance lead:* Arda Baysal \ A quality assurance lead defines the checks to ensure the quality of the intermediate and final output.
- *Report lead:* Arda Baysal \ A report lead is responsible for coordinating the text and the visuals in the written report and the presentation.
- *Secretary:* Artemi Kurski \ A secretary supplies agenda and takes notes in the meetings.
- *Communication lead:* role currently vacant \ A communication lead is responsible for talking to the client and the supervision team.

== Supervision Team

The supervision team for this project consists of Gina Stavropoulou, representing TU Delft's 3D Geoinformation Group, Maarten Pronk, representing Deltares, and Daan van der Heide, representing Rijkswaterstaat; Maarten Pronk and Daan van der Heide are also PhD candidates in the 3D Geoinformation Group. The supervisors provide feedback on the team's work, help define scope and desired outcomes, and share their experience with existing approaches to the problem.

== Clients

Rijkswaterstaat are a government agency for infrastructure and water management of the Netherlands. Originally created in 1798 for flood prevention, it now also oversees the construction and maintenance of national infrastructure @rijkswaterstaat-About. Some of the notable projects completed by the agency include the Afsluitdijk, built in the interwar period, and the Delta Works, the construction of which finished in 1997. Flooding still remains a key priority for Rijkswaterstaat.

Deltares are an independent research institute specialising in water and subsurface research @deltares-About. Their key mission is 'Enabling Delta Life', which encompasses five key areas focusing on health, safety, and sustainability of life in river deltas. Creating a more accurate river model contributes to several of these areas — in particular, "Safer from flooding" and "Healthy water systems".

== Client Responsibilities

Since the project involves massive amounts of data (on the scale of several terabytes, exact size to be determined later), it is expected that the client will provide compute and storage facilities. They will host the resulting elevation model. The client will also participate in meetings and provide feedback and input on the team's progress and proposed solutions.
