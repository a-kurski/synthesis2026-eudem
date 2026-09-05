= Planning

== Phases
=== Organisation phase

The organisation phase is the first phase of the project. During this phase, the project will be defined and planned. This phase will be used to define the project scope, objectives, deliverables, and timeline. The project team will be formed and roles and responsibilities will be assigned. The project plan will be created and approved by the stakeholders. This phase will last approximately 2 weeks.

The phase consists of the following tasks:
- Project Initiation Document (PID) creation and approval;
- Project planning and scheduling;
- Meeting with stakeholders to discuss project scope, objectives, deliverables, and timeline.

This report is the PID and includes most information aquired during this first phase. The project plan and schedule can be found at the end of this chapter in the form of a Gantt chart. The meeting minutes can be found on the project repository. While elements discussed in this first phase are not final, they will be used as a basis for the project plan and schedule.

=== Research phase

The research phase is the second phase of the project. During this phase, existing approaches and methods will be evaluated. Additionally, during this phase, data will be collected and evaluated for fitness of use and quality. It is expected that this phase will last approximately 2 weeks.

The phase consists of the following tasks:
- Literature review of existing approaches and methods;
- Review of CRS transformations and their accuracy;
- Refinement of the methodology and approach based on the literature review;
- Data collection and evaluation for fitness of use and quality.

It is likely that other projects have developed different approaches to the problem of creating a cross-border DEM. This will be the main focus of the literature study. Additionally, since each country has its data in a different CRS, it is important to learn how to transform the data into a common CRS. This will be done by reviewing CRS transformations and their accuracy. The methodology and approach described in this PID is based on an intial assumption of the problem and will be refined based on our findings. Lastly, data for both the ground truth and the point clouds will be collected and evaluated in preparation for the next phase.

#pagebreak()
=== Software development and data collection phase

The software development and data collection phase is the third phase of the project. During this phase, the software will be developed and tested. This includes both a pipeline prototype and a production version. It is expected that this phase will last approximately 4 weeks.

The phase consists of the following tasks:
- Development of a pipeline prototype;
- Testing of the pipeline prototype on a data subset;
- Development of a production version of the pipeline;
- Testing of the production version of the pipeline a data subset;
- Testing of the production version of the pipeline on the full dataset;
- Software documentation and user manual creation.

The pipeline prototype will be developed as a proof of concept and will be test on a small data subset. For the production version, the pipeline will be developed to handle the full dataset. The production version will be tested on a small data subset and then on the full dataset. The software documentation and user manual will be created to ensure that the software can be used by others.

=== Midterm presentation phase
The midterm presentation phase is the fourth phase, but will be executed in parallel with the software development and data collection phase. During this phase, the project will be presented to the stakeholders to show the progress made and to receive feedback. In addition, this opertunity may be used to adjust the project scope or objectives. There is no set duration for this phase.

The phase consists of the following tasks:
- Midterm presentation preparation;
- Midterm report creation.

The midterm presentation will be prepared to show the progress made up until that point. The midterm report will be the progress of the final report and will contain the results of the research phase and the software development in its current state. Both the presentation and report will be presented to the stakeholders to receive feedback and to adjust the project scope and/or objectives if neccesary.

=== Final presentation phase
The final presentation phase is the fifth and final phase of the project. During this phase, the project will be presented to the stakeholders to show the final results and the report. In addition, this will contain the final geomatics day presentation. There is no set duration for this phase.

The phase consists of the following tasks:
- Final presentation preparation;
- Final report creation.

The final presentation will be prepared to show the final results and conclusions of the project. The final report will contain the results of the research phase and the software development in its final state. 

#pagebreak()
== Communication

Communication is key to the success of this project. To ensure communication is maintained, both within the team and with stakeholders, regular meetings will be held. The team will meet on a weekly basis to discuss progress, issues and questions. These meetings will be held on Fridays. There will be an additional opertunity to meet on Mondays if neccesary. For each meeting, key talking points will be shared in advance. Meeting minutes will be kept and distributed after each meeting. These meetings will be held online via Microsoft Teams. The team will also communicate internally outside of these meetings, either through Whatsapp or in person.


== Risk Analysis

In order to identify and mitigate risks, a risk analysis will be conducted. The method used is the risk matrix method. It is important to mention that this method is not infalible and that it is possible that risks are not identified or that the impact and likelihood are wrongly assessed. However, this method does allow for a more structured approach to risk analysis. #ref(<Risk_Assessment_Table>) shows the identified risks, their impact and likelihood, and what can be done to mitigate them. 

#let impact(value) = {
  let color = if value == "Minor" {
    rgb("b3ef88")
  } else if value == "Marginal" {
    rgb("#f0e876")
  } else if value == "Critical" {
    rgb("#f1ac6f")
  } else if value == "Catastrophic" {
    rgb("#ed7e7e")
  } else {
    none
  }

  box(
    fill: color,
    inset: 2.5pt,
    width: 100%,
    align(center)[#value]
  )
}
#let likelyhood(value) = {
  let color = if value == "Rare" {
    rgb("#b3ef88")
  } else if value == "Unlikely" {
    rgb("#f0e876")
  } else if value == "Possible" {
    rgb("#f1ac6f")
  } else if value == "Likely" {
    rgb("#ed7e7e")
  } else if value == "Almost Certain" {
    rgb("#e972a6")
  } else {
    none
  }

  box(
    fill: color,
    inset: 2.5pt,
    width: 100%,
    align(center)[#value]
  )
}

#let risk-id(id, impact, likelihood) = {
  let risk = if likelihood == "Eliminated" {
    "Eliminated"
  } else if likelihood == "Certain" {
    if impact == "Minor" or impact == "Marginal" {
      "High"
    } else {
      "Very high"
    }
  } else if likelihood == "Likely" {
    if impact == "Minor" {
      "Medium"
    } else if impact == "Marginal" or impact == "Critical" {
      "High"
    } else {
      "Very high"
    }
  } else if likelihood == "Possible" {
    if impact == "Minor" {
      "Low"
    } else if impact == "Marginal" {
      "Medium"
    } else if impact == "Critical" {
      "High"
    } else if impact == "Catastrophic" {
      "Very high"
    } else {
      none
    }
  } else if likelihood == "Unlikely" {
    if impact == "Minor" {
      "Low"
    } else if impact == "Marginal" or impact == "Critical" {
      "Medium"
    } else if impact == "Catastrophic" {
      "High"
    } else {
      none
    }
  } else if likelihood == "Rare" {
    if impact == "Minor" or impact == "Marginal" {
      "Low"
    } else if impact == "Critical" or impact == "Catastrophic" {
      "Medium"
    } else {
      none
    }
  } else {
    none
  }

  let color = if risk == "Low" {
    rgb("#b3ef88")
  } else if risk == "Medium" {
    rgb("#f0e876")
  } else if risk == "High" {
    rgb("#f1ac6f")
  } else if risk == "Very high" {
    rgb("#ed7e7e")
  } else if risk == "Eliminated" {
    rgb("#d9ffff")
  } else {
    none
  }

  box(
    fill: color,
    inset: 4pt,
    width: 100%,
    align(center)[#id]
  )
}

#figure(
  table(
    columns: (50pt, auto, auto,auto,auto),
    inset: 2pt,
    stroke: (x: none),
    align: horizon,
    table.header(
      [*Risk ID*], [*Description*], [*Impact*],[*Likelyhood*],[*Mitigation*]
    ),
    risk-id([1.],"Critical","Possible"),[Pipeline too computationally taxing or insufficient computational resources.],impact("Critical"),likelyhood("Possible"),[Test with small dataset and adjust spatial extent if necessary.],
    risk-id([2.],"Marginal","Rare"),[Insufficient quality/availability of pointcloud data.],impact("Marginal"),likelyhood("Rare"),[Shift focus to regions with available high-quality data.],
    risk-id([3.],"Critical","Unlikely"),[CRS transformations are inaccurate.],impact("Critical"),likelyhood("Unlikely"),[Test CRS alignment on select border regions],
    risk-id([4.],"Critical","Likely"),[Missing/conflicting data on border areas.],impact("Critical"),likelyhood("Likely"),[Check spatial overlap of datasets and prioritize one dataset.],
    risk-id([5.],"Catastrophic","Unlikely"),[Task is too ambitious given timeframe/team size.],impact("Catastrophic"),likelyhood("Unlikely"),[Check if internal deadlines are met and adjust scope if necessary.],
    risk-id([6.],"Minor","Possible"),[Edge cases not properly assessed due to data quantity and variability.],impact("Minor"),likelyhood("Possible"),[Unideal but acceptable within scope of project.],
    risk-id([7.],"Critical","Unlikely"),[Task is insufficiently constrained/defined.],impact("Critical"),likelyhood("Unlikely"),[Regular meetings with team and stakeholders to assess and adjust scope and requirements if necessary.],
    risk-id([8.],"Critical","Possible"),[Lacking/inadequate communication within the team and/or with stakeholders.],impact("Critical"),likelyhood("Possible"),[Schedule regular meetings and maintain open communication channels.],
    risk-id([9.],"Marginal","Possible"),[Discovery of unexpected issues.],impact("Marginal"),likelyhood("Possible"),[Regular meetings with team and stakeholders to assess impact and devise mitigation strategies if necessary.],
    risk-id([10.],"Critical","Rare"),[Temporary or permanent absence of team members.],impact("Critical"),likelyhood("Rare"),[Set internal deadlines early to allow for adjustments in case of absence.],
    risk-id([11.],"Catastrophic","Possible"),[Data loss.],impact("Catastrophic"),likelyhood("Possible"),[Implement regular backup procedures.]
  ),
  caption: "Risk Assessment Table."
) <Risk_Assessment_Table>

#figure(
  image("assets/image.png", width: 70%),
  caption: "Risk Assessment Matrix."
) <Risk_Assessment_Matrix>

https://en.wikipedia.org/wiki/Risk_matrix