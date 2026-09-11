#set heading(numbering: "A.1.1", supplement: [Appendix])
#counter(heading).update(0)

= Data Source List <appx-data-sources>

#table(
  columns: (auto, auto, auto),
  table.header([*Dataset*], [*URL*], [*Notes*]),
  [Netherlands: DTM], [see https://www.ahn.nl/dataroom], [Map tiles — COG, 0.5m resolution, not interpolated; also available at 5m resolution],
  [Netherlands: DSM], [see https://www.ahn.nl/dataroom], [Map tiles — COG, 0.5m resolution, not interpolated; also available at 5m resolution],
  [Netherlands: PC], [], [Map tiles — LAZ, 10–14 pt/cm#super[2]],
  [Switzerland: DTM], [https://www.swisstopo.admin.ch/en/height-model-swissalti3d], [Map tiles — COG, 0.5m and 2m resolution, interpolated],
  [Switzerland: DSM], [https://www.swisstopo.admin.ch/en/height-model-swisssurface3d-raster], [Map tiles — COG, 0.5m resolution only, interpolated],
  [Switzerland: PC], [https://www.swisstopo.admin.ch/en/height-model-swisssurface3d], [Map tiles — LAZ or COPC, point density 15–40 pt/cm#super[2] (region-dependent)],
  [Germany, Niedersachsen: DTM], [https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-gel-ndemodell-dgm1], [Map tiles — COG, 1m resolution],
  [Germany, Niedersachsen: DSM], [https://ni-lgln-opengeodata.hub.arcgis.com/pages/digitales-oberfl-chenmodell-dom1], [Map tiles — COG, 1m resolution],
  [Germany, Niedersachsen: PC], [https://lgln-geodaten.niedersachsen.de/startseite/luftbilder_und_3d_produkte/3d_produkte/3d_messdaten/3d-messdaten-142870.html], [not freely available?],
  [Germany, Nordrhein-Westfalen: DTM], [https://www.opengeodata.nrw.de/produkte/geobasis/hm/dgm1_tiff/dgm1_tiff/], [Map tiles — GeoTIFF, 1m resolution],
  [Germany, Nordrhein-Westfalen: DSM], [https://www.opengeodata.nrw.de/produkte/geobasis/hm/dom1_tiff/dom1_tiff/], [Map tiles — GeoTIFF, 1m resolution],
  [Germany, Nordrhein-Westfalen: PC], [https://www.opengeodata.nrw.de/produkte/geobasis/hm/3dm_l_las/3dm_l_las/], [LAZ],
  [Germany, Rheinland-Pfalz: DTM], [https://geoshop.rlp.de/digitale_gelaendemodelle/digitale_gelaendemodelle_dgm.html], [Map tiles — GeoTIFF, 1m resolution],
  [Germany, Rheinland-Pfalz: DSM], [https://geoshop.rlp.de/digitale_oberflaechenmodelle/digitales_oberflaechenmodell_domb.html], [Map tiles — GeoTIFF, 0.2m resolution],
  [Germany, Rheinland-Pfalz: PC — surface], [https://geoshop.rlp.de/digitale_oberflaechenmodelle/laserpunkte_objekte_lpo.html], [LAZ],
  [Germany, Rheinland-Pfalz: PC — terrain], [https://geoshop.rlp.de/digitale_gelaendemodelle/laserpunkte_gelaende_lpg.html], [LAZ],
  [Germany, Saarland: DTM], [https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1060&Itemid=475], [GeoTIFF, 1m resolution],
  [Germany, Saarland: DSM], [https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1066&Itemid=475], [GeoTIFF, 1m resolution],
  [Germany, Saarland: PC], [https://www.shop.lvgl.saarland.de/index.php?option=com_virtuemart&view=category&virtuemart_category_id=1067&Itemid=475], [LAZ],
  [Germany, Baden-Württemberg: DTM], [https://www.lgl-bw.de/Produkte/3D-Produkte/Digitale-Gelaendemodelle/], [Map tiles — GeoTIFF, 0.25m resolution],
  [Germany, Baden-Württemberg: DSM], [https://www.lgl-bw.de/Produkte/3D-Produkte/Digitale-Oberflaechenmodelle/DOM1/], [Map tiles — GeoTIFF (1m resolution)],
  [Germany, Baden-Württemberg: PC], [https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/], [paid only?],
  [Germany, Hessen: DTM], [https://hvbg.hessen.de/landesvermessung/geotopographie/3d-daten/digitale-gelaendemodelle], [Map tiles — GeoTIFF (1m resolution)],
  [Germany, Hessen: DSM], [https://hvbg.hessen.de/landesvermessung/geotopographie/3d-daten/digitale-oberflaechenmodelle], [Map tiles — GeoTIFF (1m resolution)],
  [Germany, Hessen: PC], [https://hvbg.hessen.de/landesvermessung/geotopographie/3d-daten/airborne-laserscanning], [paid only?],
  [Germany, Bayern: DTM], [https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dgm1], [Map tiles — GeoTIFF, 1m resolution],
  [Germany, Bayern: DSM], [https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dom20], [Map tiles — GeoTIFF, 0.2m resolution],
  [Germany, Bayern: PC], [https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=laserdaten], [Map tiles — LAZ],
  [Liechtenstein: DTM, DSM, PC], [], [Included in Swiss datasets],
  [France: DTM], [https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_MNT-LIDAR-HD], [Map tiles — GeoTIFF, 0.5m resolution],
  [France: DSM], [https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_MNS-LIDAR-HD], [Map tiles — GeoTIFF, 0.5m resolution],
  [France: PC], [https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_NUAGES-DE-POINTS-LIDAR-HD?redirected_from=geoservices.ign.fr], [Map tiles — LAZ],
  [Luxembourg: DTM],[https://data.public.lu/fr/datasets/lidar-2024-releve-3d-du-territoire-luxembourgeois/],[Map tiles — GeoTIFF, 0.5m resolution],
  [Luxembourg: DSM],[https://data.public.lu/fr/datasets/lidar-2024-releve-3d-du-territoire-luxembourgeois/],[Map tiles — GeoTIFF, 0.5m resolution],
  [Luxembourg: PC],[https://data.public.lu/fr/datasets/lidar-2024-releve-3d-du-territoire-luxembourgeois/],[Map tiles — LAZ]
)

#pagebreak()
= Literature List <appx-literature>

#linebreak()
*Repetitive interpolation: A robust algorithm for DTM generation from Aerial Laser Scanner Data in forested terrain,
Remote Sensing of Environment,*
Andrej Kobler, Norbert Pfeifer, Peter Ogrinc, Ljupčo Todorovski, Krištof Oštir, Sašo Džeroski,
Volume 108, Issue 1,
2007,
Pages 9-23,
ISSN 0034-4257,
https://doi.org/10.1016/j.rse.2006.10.013

#linebreak()
*LiDAR DTM: artifacts, and correction for river altitudes,*
Jean-François Parrot, Carolina Ramírez Núñez,
Investigaciones Geográficas, Boletín del Instituto de Geografía,
Volume 2016, Issue 90,
2016,
Pages 28-39,
ISSN 0188-4611,
https://www.sciencedirect.com/science/article/pii/S0188461116300346

#linebreak()
*MERGING LOCAL DTMS: HELI-DEM PROJECT, PROBLEMS AND SOLUTIONS,*
Laura CARCANO,
Department of Civil and Environmental Engineering
Ph.D. course in Environmental and Infrastructure Engineering,
https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://www.politesi.polimi.it/bitstream/10589/89463/1/2014_03_PhD_Carcano.pdf&ved=2ahUKEwif34GJveaWAxX2zAIHHWw9MWAQFnoECCYQAQ&usg=AOvVaw2D3-oPLBzGNwDkCpo2nEX_

#linebreak()
*Cartographic data harmonisation for a cross-border project development.* Noardo, Francesca & LINGUA, Andrea & Aicardi, Irene & Vigna, Bartolomeo. 
(2016). 
Applied Geomatics. 
8. 133-150. 10.1007/s12518-016-0172-9. 
https://www.researchgate.net/publication/304064666_Cartographic_data_harmonisation_for_a_cross-border_project_development

#linebreak()
*TERRAIN MODELLING AND ANALYSIS USING LASER SCANNER DATA.*
Elmqvist, M., Jungert, E., & Lantz, F. 
(2001). 
 International Archives of Photogrammetry and Remote Sensing, Volume XXXIV-3/W4 Annapolis, MD, 22-24 Oct. 2001 219. http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.150.5538
https://www.isprs.org/proceedings/xxxiv/3-w4/pdf/elmqvist.pdf