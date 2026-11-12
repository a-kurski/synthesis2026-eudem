#import "@preview/abbr:0.3.1"

#heading(level: 1, numbering: none)[List of Abbreviations]
#{
  // The package emits its own (level-1) heading; main.typ's show rule adds a pagebreak
  // to those, which is not allowed inside columns. Hide it here (our heading is above).
  set heading(outlined: false)
  show heading: none
  columns(2, gutter: 1.5em, abbr.list(title: none, columns: 1))
}
#abbr.make(
  // Abbreviations
  ("AHN", "Actueel Hoogtebestand Nederland"),
  ("ALOS", "Advanced Land Observing Satellite"),
  ("ALS", "Aerial Laser Scanning"),
  ("AOI", "Area of Interest", "Areas of Interest"),
  ("COG", "Cloud-Optimized GeoTIFF"),
  ("COPC", "Cloud-Optimized Point Cloud"),
  ("CRS", "Coordinate Reference System", "Coordinate Reference Systems"),
  ("CSF", "Cloth Simulation Filtering"),
  ("DEM", "Digital Elevation Model", "Digital Elevation Models"),
  ("DHHN2016", "German Main Height Network 2016"),
  ("DSM", "Digital Surface Model", "Digital Surface Models"),
  ("DTM", "Digital Terrain Model", "Digital Terrain Models"),
  ("EEA", "European Environment Agency"),
  ("ETRS89", "European Terrestrial Reference System 1989"),
  ("ETRS89-GRS80", "ETRS89 using the Geodetic Reference System 1980 ellipsoid"),
  ("ETRS89-LAEA", "ETRS89 Lambert Azimuthal Equal Area"),
  ("ETRS89-LCC", "ETRS89 Lambert Conformal Conic"),
  ("EU", "European Union"),
  ("EVRS", "European Vertical Reference System"),
  ("FEE", "Freshwater Ecosystems Explorer"),
  ("GDAL", "Geospatial Data Abstraction Library"),
  ("GDEM", "Global Digital Elevation Model", "Global Digital Elevation Models"),
  ("GRS80", "Geodetic Reference System 1980"),
  ("GSD", "Ground Sample Distance"),
  ("ICPR", "International Commission for the Protection of the Rhine"),
  ("ICSF", "Improved CSF"),
  ("IDW", "Inverse Distance Weighted to a Power"),
  ("InSAR", "Interferometric Synthetic-Aperture Radar"),
  ("INSPIRE", "Infrastructure for Spatial Information in the European Community"),
  ("LAZ", "LASzip-compressed point-cloud format"),
  ("LE90", "Linear Error at 90th Percentile"),
  ("lidar", "Light Detection and Ranging"),
  ("MAE", "Mean Absolute Error"),
  ("MCC", "Multiscale Curvature Classification"),
  ("MoSCoW", "Must, Should, Could, Won't"),
  ("MSF", "Maximum Slope Filtering"),
  ("NAP", "Normaal Amsterdams Peil"),
  ("NMAD", "Normalized Median Absolute Deviation"),
  ("NNI", "Natural Neighbour Interpolation"),
  ("OSM", "OpenStreetMap"),
  ("PC", "Point Cloud", "Point Clouds"),
  ("PMF", "Progressive Morphological Filter"),
  ("PTIN", "Progressive Triangulated Irregular Network"),
  ("RBF", "Radial Basis Function"),
  ("RMSE", "Root Mean Square Error"),
  ("STD", "Standard Deviation"),
  ("TIN", "Triangulated Irregular Network", "Triangulated Irregular Networks"),
  ("UTM", "Universal Transverse Mercator"),
  ("VCRS", "Vertical Coordinate Reference System"),
  ("WCS", "Web Coverage Service"),
  ("WLS", "Weighted Linear Least Squares"),

  // Countries and German states (ISO 3166)
  ("FR", "France"),
  ("LU", "Luxembourg"),
  ("CH", "Switzerland"),
  ("LI", "Liechtenstein"),
  ("NL", "Netherlands"),
  ("DE", "Germany"),
  ("DE-BW", "Baden-Württemberg, Germany"),
  ("DE-BY", "Bavaria, Germany"),
  ("DE-HE", "Hessen, Germany"),
  ("DE-NW", "North Rhine-Westphalia, Germany"),
  ("DE-RP", "Rhineland-Palatinate, Germany"),
  ("DE-SL", "Saarland, Germany"),
)

#abbr.config(style: it => text(it))
