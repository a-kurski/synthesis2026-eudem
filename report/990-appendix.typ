#import "@preview/timeliney:0.4.0"

#set heading(numbering: "A.1.1", supplement: [Appendix])
#counter(heading).update(0)

#include "991-contributors.typ"

= Project Planning

== Prioritisation <sec:requirements>
#let moscow(value) = {
  let color = if value == "Must" {
    rgb("#b3ef88")
  } else if value == "Should" {
    rgb("#f0e876")
  } else if value == "Could" {
    rgb("#f1ac6f")
  } else if value == "Will not have" {
    rgb("#ed7e7e")
  } else {
    none
  }

  box(
    fill: color,
    inset: 4pt,
    width: 100%,
    align(center)[#value]
  )
}

#let status(value) = {
  let color = if value == "Not done" {
    rgb("#ed7e7e")
  } else if value == "In progress" {
    rgb("#f1ac6f")
  } else if value == "Done" {
    rgb("#b3ef88")
  } else {
    none
  }

  box(
    fill: color,
    inset: 4pt,
    width: 100%,
    align(center)[#value]
  )

}

#figure(
  caption: [Prioritisation of data requirements using @MoSCoW],
  table(
    columns: (auto,auto, auto,100pt),
    inset: 4pt,
    stroke: (x: none),
    align: horizon,
    table.header([Req ID],[Description], [@MoSCoW:s], [Status]),
    [DT-01],[Global / @EU:s @DEM:s], moscow("Must"),status("Done"),
    [DT-02],[Rhine Watershed Mask], moscow("Must"),status("Done"),
    [DT-03],[Rhine Bathymetry], moscow("Will not have"),status("Not done"),
    [DT-04], [National/regional @PC:s], moscow("Must"),status("In progress"),
    [DT-05], [National/regional @DTM:s], moscow("Must"),status("Done"),
    [DT-06], [National/regional @DSM:s], moscow("Should"),status("Not done"),
    [DT-07], [National/regional topographic map], moscow("Could"),status("Not done"),
    table.hline(stroke: 2pt),
    [CT-01],[The Netherlands is included], moscow("Must"),status("Done"),
    [CT-02],[Germany is included], moscow("Must"),status("Done"),
    [CT-03],[Belgium is included], moscow("Should"),status("Not done"),
    [CT-04],[Switzerland is included], moscow("Must"),status("Done"),
    [CT-05],[France is included], moscow("Must"),status("Done"),
    [CT-06],[Luxembourg is included], moscow("Must"),status("Done"),
    [CT-07],[Austria is included], moscow("Should"),status("Not done"),
    [CT-08],[Liechtenstein is included], moscow("Must"),status("Done"),
    [CT-09],[Italy is included], moscow("Will not have"),status("Not done"),
    table.hline(stroke: 2pt),
    [MP-01],[@DTM:s raster], moscow("Must"),status("Done"),
    [MP-02],[@DSM:s raster], moscow("Should"),status("Not done"),
    [MP-04],[Auxiliary masks and maps], moscow("Should"),status("Done"), //what is a bathymetry mask? is it just water/no water?
    table.hline(stroke: 2pt),
    [TC-01],[Workflow is fully automated], moscow("Must"),status("Done"),
    [TC-02],[Workflow is efficient], moscow("Should"),status("Done"),
    [TC-03],[Workflow is reproducible], moscow("Must"),status("Done"),
    table.hline(stroke: 2pt),
    [RP-01],[Report on findings], moscow("Must"),status("In progress"),
    [RP-02],[Report details the workflow], moscow("Must"),status("Done"),
    [RP-03],[Report details the issues with cross-border data], moscow("Must"),status("In progress"),
    [RP-04],[Report details the limitations of the workflow], moscow("Must"),status("In progress")
  )
) <Moscow_Prioritization>

== Timeline

#figure(timeliney.timeline(
  show-grid: true,
  spacing: 6pt,
  line-style: (stroke: 4pt),

  {
    import timeliney: *

    // ─────────────────────────────────────────────
    // HEADER
    // ─────────────────────────────────────────────

    headerline(
      group(
        ("1", 1),
        ("2", 1),
        ("3", 1),
        ("4", 1),
        ("5", 1),
        ("6", 1),
        ("7", 1),
        ("8", 1),
        ("9", 1),
        ("10", 1),
      ),
    )

    // ─────────────────────────────────────────────
    // ORGANISATION
    // ─────────────────────────────────────────────

    taskgroup(title: [*Organisation*], {
      task(
        "Project initiation document",
        (0, 2),
        style: (stroke: 8pt + rgb("#b3ef88")),
      )

      task(
        "Project planning and scheduling",
        (0, 2),
        style: (stroke: 8pt + rgb("#94c571")),
      )

      task(
        "Meetings",
        (0, 10),
        style: (stroke: 8pt + rgb("#618249")),
      )
    })

    milestone(
      at: 2,
      style: (stroke: (dash: "dashed")),
      [@PID deadline],
    )

    // ─────────────────────────────────────────────
    // RESEARCH
    // ─────────────────────────────────────────────

    taskgroup(title: [*Research and Data Collection*], {
      task(
        "Literature study approach",
        (1, 4),
        style: (stroke: 8pt + rgb("#f0e876")),
      )

      task(
        "Review coordinate transformation",
        (1, 4),
        style: (stroke: 8pt + rgb("#d2cb67")),
      )

      task(
        "Methodology refinement",
        (1, 4),
        style: (stroke: 8pt + rgb("#a9a453")),
      )

      task(
        "Data collection",
        (1, 4),
        style: (stroke: 8pt + rgb("#878342")),
      )
    })

    // ─────────────────────────────────────────────
    // PROTOTYPE / PRODUCTION
    // ─────────────────────────────────────────────

    taskgroup(title: [*Pipeline Creation*], {
      task(
        "Make prototype",
        (2, 5),
        style: (stroke: 8pt + rgb("#f1ac6f")),
      )

      task(
        "Test prototype parts",
        (3, 5),
        style: (stroke: 8pt + rgb("#cb905d")),
      )

      task(
        "Make production",
        (5, 8),
        style: (stroke: 8pt + rgb("#b07d51")),
      )

      task(
        "Test production parts",
        (6, 7),
        style: (stroke: 8pt + rgb("#946943")),
      )

      task(
        "Test production fully",
        (6, 8),
        style: (stroke: 8pt + rgb("#5a4029")),
      )

      task(
        "Documentation",
        (3, 8),
        style: (stroke: 8pt + rgb("#312316")),
      )
    })

    milestone(
      at: 5,
      style: (stroke: (dash: "dashed")),
      [Prototype completed],
    )

    // ─────────────────────────────────────────────
    // MIDTERM
    // ─────────────────────────────────────────────

    taskgroup(title: [*Midterm*], {
      task(
        "Midterm report",
        (1, 5),
        style: (stroke: 8pt + rgb("#ed7e7e")),
      )

      task(
        "Midterm presentation",
        (1, 5),
        style: (stroke: 8pt + rgb("#c06666")),
      )
    })

    milestone(
      at: 5,
      style: (stroke: (dash: "dashed")),
      [Midterm deliverables],
    )


    // ─────────────────────────────────────────────
    // FINAL
    // ─────────────────────────────────────────────

    taskgroup(title: [*Final*], {
      task(
        "Final report",
        (5, 9),
        style: (stroke: 8pt + rgb("#9f5555")),
      )

      task(
        "Final presentation",
        (5, 10),
        style: (stroke: 8pt + rgb("#723c3c")),
      )
    })

    milestone(
      at: 9,
      style: (stroke: (dash: "dashed")),
      [Final report],
    )

    milestone(
      at: 10,
      style: (stroke: (dash: "dashed")),
      [Final deliverables],
    )
  },
),
caption:[Gantt chart]
)

== Risk analysis

#figure(
  image("assets/riskmatrix.png", width: 60%),
  caption: "Risk Assessment Matrix."
) <Risk_Assessment_Matrix>

#pagebreak()
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
    columns: (50pt, auto, auto, auto, auto),
    inset: 2pt,
    stroke: (x: none),
    align: horizon,
    table.header(
      [*Risk ID*], [*Description*], [*Impact*],[*Likelihood*],[*Mitigation*]
    ),
    risk-id([1.],"Critical","Possible"),[Pipeline too computationally taxing or insufficient computational resources.],impact("Critical"),likelyhood("Possible"),[Test with small dataset and adjust spatial extent if necessary.],
    risk-id([2.],"Marginal","Rare"),[Insufficient quality/availability of point cloud data.],impact("Marginal"),likelyhood("Rare"),[Shift focus to regions with available high-quality data.],
    risk-id([3.],"Critical","Unlikely"),[@CRS:s transformations are inaccurate.],impact("Critical"),likelyhood("Unlikely"),[Test @CRS alignment on select border regions.],
    risk-id([4.],"Critical","Likely"),[Missing/conflicting data on border areas.],impact("Critical"),likelyhood("Likely"),[Check spatial overlap of datasets and prioritise one dataset.],
    risk-id([5.],"Catastrophic","Unlikely"),[Task is too ambitious given timeframe/team size.],impact("Catastrophic"),likelyhood("Unlikely"),[Check if internal deadlines are met and adjust scope if necessary.],
    risk-id([6.],"Minor","Possible"),[Edge cases not properly assessed due to data quantity and variability.],impact("Minor"),likelyhood("Possible"),[Not ideal but acceptable within the scope of the project.],
    risk-id([7.],"Critical","Unlikely"),[Task is insufficiently constrained/defined.],impact("Critical"),likelyhood("Unlikely"),[Regular meetings with team and stakeholders to assess and adjust scope and requirements if necessary.],
    risk-id([8.],"Critical","Possible"),[Lacking/inadequate communication within the team and/or with stakeholders.],impact("Critical"),likelyhood("Possible"),[Schedule regular meetings and maintain open communication channels.],
    risk-id([9.],"Marginal","Possible"),[Discovery of unexpected issues.],impact("Marginal"),likelyhood("Possible"),[Regular meetings with team and stakeholders to assess impact and devise mitigation strategies if necessary.],
    risk-id([10.],"Critical","Rare"),[Temporary or permanent absence of team members.],impact("Critical"),likelyhood("Rare"),[Set internal deadlines early to allow for adjustments in case of absence.],
    risk-id([11.],"Catastrophic","Possible"),[Data loss.],impact("Catastrophic"),likelyhood("Possible"),[Implement regular backup procedures.]
  ),
  caption: "Risk Assessment Table."
) <Risk_Assessment_Table>


= Data Source List <appx-data-sources>
#figure(
  table(
    columns: (auto, auto, auto),
    table.header([*Dataset*], [*URL*], [*Notes*]),
    [Netherlands: @DTM:s], [see https://www.ahn.nl/dataroom], [Map tiles — @COG, 0.5m resolution, not interpolated; also available at 5m resolution],
    [Netherlands: @DSM:s], [see https://www.ahn.nl/dataroom], [Map tiles — @COG:s, 0.5m resolution, not interpolated; also available at 5m resolution],
    [Netherlands: @PC:s], [], [Map tiles — @LAZ, 10–14 pt/cm#super[2]],
    [Switzerland: @DTM:s], [https://www.swisstopo.admin.ch/en/height-model-swissalti3d], [Map tiles — @COG:s, 0.5m and 2m resolution, interpolated],
    [Switzerland: @DSM:s], [https://www.swisstopo.admin.ch/en/height-model-swisssurface3d-raster], [Map tiles — @COG:s, 0.5m resolution only, interpolated],
    [Switzerland: @PC:s], [https://www.swisstopo.admin.ch/en/height-model-swisssurface3d], [Map tiles — @LAZ:s or @COPC, point density 15–40 pt/cm#super[2] (region-dependent)],
    [Germany, Niedersachsen: @DTM:s], [https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-gel-ndemodell-dgm1], [Map tiles — @COG:s, 1m resolution],
    [Germany, Niedersachsen: @DSM:s], [https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-oberfl-chenmodell-dom1], [Map tiles — @COG:s, 1m resolution],
    [Germany, Niedersachsen: @PC:s], [https://lgln-geodaten.niedersachsen.de/startseite/luftbilder_und_3d_produkte/3d_produkte/3d_messdaten/3d-messdaten-142870.html], [not freely available?],
    [Germany, Nordrhein-Westfalen: @DTM:s], [https://www.opengeodata.nrw.de/produkte/geobasis/hm/dgm1_tiff/dgm1_tiff/], [Map tiles — GeoTIFF, 1m resolution],
    [Germany, Nordrhein-Westfalen: @DSM:s], [https://www.opengeodata.nrw.de/produkte/geobasis/hm/dom1_tiff/dom1_tiff/], [Map tiles — GeoTIFF, 1m resolution],
    [Germany, Nordrhein-Westfalen: @PC:s], [https://www.opengeodata.nrw.de/produkte/geobasis/hm/3dm_l_las/3dm_l_las/], [@LAZ:s],
    [Germany, Rheinland-Pfalz: @DTM:s], [https://geoshop.rlp.de/digitale_gelaendemodelle/digitale_gelaendemodelle_dgm.html], [Map tiles — GeoTIFF, 1m resolution],
    [Germany, Rheinland-Pfalz: @DSM:s], [https://geoshop.rlp.de/digitale_oberflaechenmodelle/digitales_oberflaechenmodell_domb.html], [Map tiles — GeoTIFF, 0.2m resolution],
    [Germany, Rheinland-Pfalz: @PC:s — surface], [https://geoshop.rlp.de/digitale_oberflaechenmodelle/laserpunkte_objekte_lpo.html], [@LAZ:s],
    [Germany, Rheinland-Pfalz: @PC:s — terrain], [https://geoshop.rlp.de/digitale_gelaendemodelle/laserpunkte_gelaende_lpg.html], [@LAZ:s],
    [Germany, Saarland: @DTM:s], [https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1060&Itemid=475], [GeoTIFF, 1m resolution],
    [Germany, Saarland: @DSM:s], [https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1066&Itemid=475], [GeoTIFF, 1m resolution],
    [Germany, Saarland: @PC:s], [https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1067&Itemid=475], [@LAZ:s],
    [Germany, Baden-Württemberg: @DTM:s], [https://www.lgl-bw.de/Produkte/3D-Produkte/Digitale-Gelaendemodelle/], [Map tiles — GeoTIFF, 0.25m resolution],
    [Germany, Baden-Württemberg: @DSM:s], [https://www.lgl-bw.de/Produkte/3D-Produkte/Digitale-Oberflaechenmodelle/DOM1/], [Map tiles — GeoTIFF (1m resolution)],
    [Germany, Baden-Württemberg: @PC:s], [https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/], [paid only?],
    [Germany, Hessen: @DTM:s], [https://hvbg.hessen.de/landesvermessung/geotopographie/3d-daten/digitale-gelaendemodelle], [Map tiles — GeoTIFF (1m resolution)],
    [Germany, Hessen: @DSM:s], [https://hvbg.hessen.de/landesvermessung/geotopographie/3d-daten/digitale-oberflaechenmodelle], [Map tiles — GeoTIFF (1m resolution)],
    [Germany, Hessen: @PC:s], [https://hvbg.hessen.de/landesvermessung/geotopographie/3d-daten/airborne-laserscanning], [paid only?],
    [Germany, Bayern: @DTM:s], [https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dgm1], [Map tiles — GeoTIFF, 1m resolution],
    [Germany, Bayern: @DSM:s], [https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dom20], [Map tiles — GeoTIFF, 0.2m resolution],
    [Germany, Bayern: @PC:s], [https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=laserdaten], [Map tiles — @LAZ:s],
    [Liechtenstein: @DTM:s, @DSM:s, @PC:s], [], [Included in Swiss datasets],
    [France: @DTM:s], [https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_MNT-LIDAR-HD], [Map tiles — GeoTIFF, 0.5m resolution],
    [France: @DSM:s], [https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_MNS-LIDAR-HD], [Map tiles — GeoTIFF, 0.5m resolution],
    [France: @PC:s], [https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_NUAGES-DE-POINTS-LIDAR-HD?redirected_from=geoservices.ign.fr], [Map tiles — @LAZ:s],
    [Luxembourg: @DTM:s],[https://data.public.lu/fr/datasets/lidar-2024-releve-3d-du-territoire-luxembourgeois/],[Map tiles — GeoTIFF, 0.5m resolution],
    [Luxembourg: @DSM:s],[https://data.public.lu/fr/datasets/lidar-2024-releve-3d-du-territoire-luxembourgeois/],[Map tiles — GeoTIFF, 0.5m resolution],
    [Luxembourg: @PC:s],[https://data.public.lu/fr/datasets/lidar-2024-releve-3d-du-territoire-luxembourgeois/],[Map tiles — @LAZ:s]
  ),
  caption:[Dataset availability]
)

= Border pair analysis <sec:border_pairs>
#include "992-borderpairs.typ"