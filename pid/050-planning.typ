= Planning

== Phases


== Communication

Communication is key to the success of this project. To ensure communication is maintained, both within the team and with stakeholders, regular meetings will be held. The team will meet on a weekly basis to discuss progress, issues and questions. These meetings will be held on Fridays. There will be an additional opertunity to meet on Mondays if neccesary. For each meeting, key talking points will be shared in advance. Meeting minutes will be kept and distributed after each meeting. These meetings will be held online via Microsoft Teams. The team will also communicate internally outside of these meetings, either through Whatsapp or in person.


== Risk Analysis

#figure(
  table(
    columns: (auto, auto, auto,auto,auto),
    inset: 4pt,
    align: horizon,
    table.header(
      [*Risk ID*], [*Description*], [*Impact*],[*Likelyhood*],[*Mitigation*]
    ),
    [1.],[Pipeline too computationally taxing or insufficient computational resources.],[Critical],[Possible],[Test with small dataset and adjust spatial extent if necessary.],
    [2.],[Insufficient quality/availability of pointcloud data.],[Marginal],[Rare],[Shift focus to regions with available high-quality data.],
    [3.],[CRS transformations are inaccurate.],[Critical],[Unlikely],[TODO: Test CRS alignment on select border regions],
    [4.],[Missing/conflicting data on border areas.],[Critical],[Likely],[Check spatial overlap of datasets and prioritize one dataset.],
    [5.],[Task is too ambitious given timeframe/team size.],[Unlikely],[ Catastrophic],[Check if internal deadlines are met and adjust scope if necessary.],
    [6.],[Edge cases not properly assessed due to data quantity and variability.],[Minor],[Possible],[Unideal but acceptable within scope of project.],
    [7.],[Task is insufficiently constrained/defined.],[Critical],[Unlikely],[Regular meetings with team and stakeholders to assess and adjust scope and requirements if necessary.],
    [8.],[Lacking/inadequate communication within the team and/or with stakeholders.],[Critical],[Possible],[Schedule regular meetings and maintain open communication channels.],
    [9.],[Discovery of unexpected issues.],[Marginal],[Possible],[Regular meetings with team and stakeholders to assess impact and devise mitigation strategies if necessary.],
    [10.],[Temporary or permanent absence of team members.],[Critical],[Rare],[Set internal deadlines early to allow for adjustments in case of absence.],
    [11.],[Data loss.],[Catastrophic],[Possible],[Implement regular backup procedures.]
  ),
  caption: "Risk Assessment Table."
)
#figure(
  image("assets/image.png", width: 70%),
  caption: "Risk Assessment Matrix."
)

https://en.wikipedia.org/wiki/Risk_matrix