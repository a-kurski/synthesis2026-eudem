## Executive Summary
- defines elevation
- describes uses of elevation data
- defines DEM, DSM, DTM (broadly)
- INSPIRE data model allows for either DEM or DSM
- INSPIRE data model is 2.5D
- **grid, of mandatory provision**
- recommended CRS: **ETRS89**
- recommended vertical datum: **EVRS**
- Data format: **GML Coverage** or alternatively **TIFF**

## 2. Overview
Scope (pp. 15–16): 
- land-elevation
- bathymetry (sea and navigable inland water bodies)
- only supports 2.5D
Spatial extent: all areas where an EU Member State "has and/or exercises jurisdictional rights". (p. 16)
Spatial resolution: no restriction established (p. 16)
Spatial representation (p. 16): 
- "The provision of grid data is mandatory for land elevation"
- "provision of vector and TIN data is recommended (optional) \[for land elevation]."
- anything goes for bathymetry
**p. 17 provides a full INSPIRE definition of elevation and DEM**, see https://op.europa.eu/en/web/eu-vocabularies/concept/-/resource?uri=http://inspire.ec.europa.eu/theme/el
**sec. 2.4** (pp. 18–21) **provides definitions** (Elevation, DTM, DSM, DEM, etc)
**sec. 2.5** (pp. 21–22) provides a list of symbols and abbreviations
Annex A has an abstract test suite to test conformance

## 5. Data content and structure

- sec. 5.1 defines requirements for codes. Probably something to look into deeper
- Identifier management (sec. 5.2.5) — do we even care about that or is it for nations publishing their datasets? 
-  

### 5.2.4 Consistency between spatial data sets
Defines: 
- coherence between spatial objects of the same theme at different LoD
- coherence between spatial objects within the same area
- coherence at state boundary

### 5.2.8 Coverages

INSPIRE only allows: 
- _RectifiedGridCoverage_
- _ReferenceableGridCoverage_

### 5.3.1 Description
- height: z-axis opposite to Earth's gravity field
- depth: z-axis coincident with Earth's gravity field
- "Land-elevation": describes height of the Earth's surface
- "Bathymetry": describes depth of
  - the sea floor
  - the floor of inland standing water bodies
  - bed of navigable rivers
- land-sea models combine land-elevation as positive height and depth as negative height
- figs 4–9 illustrate above
- DTM describes Earth's bare surface
- DSM describes Earth's surface with all _static_ features
- dimensionality: surface can only be modelled in 2.5D
- spatial representation types: 
  - gridded data
  - vector data
  - TIN data
- **requirement that land elevation is a grid**

### 5.5 Application: Grid
- "grid is a kind of raster data"
- regular quadrilateral grid
- grid defined by origin and axes
- grid is geo-rectified per ISO 19123, i.e. related to the Earth through an affine relationship
- tiling: can be internal (inside tiff) or external (split one big tiff into smaller tiles, overlapping or not)
  - see  "_elevation grid coverage aggregation_"
- **Pan-European project: EuroDEM**
- Recommends **bilinear interpolation**
- "edge matching \[...] along \[...] boundaries is mostly impossible to achieve"
- **Common European Grid** — see Annex C

## 6 Reference Systems, Units, Grids
- Use ETRS89 for datum
- Use ETRS89 Lambert Azimuthal Equal Area, Lambert Conformal Conic or Transverse Mercator
- Use EVRS
- Use SI units where possible
