# Data

## Input

| Data | MoSCoW |
| ---- | ------ |
| Global EU DEM (as ground truth) | Must |
| Rhine Watershed Mask | Must |
| PC: Netherlands | Must | 
| PC: Germany | Must | 
| PC: Belgium | Should |
| PC: Switzerland | Must | 
| PC: France | Must |
| PC: Luxembourg | Must | 
| PC: Austria | Must | 
| PC: Liechtenstein | Must | 
| PC: Italy | Could | 
| Rhine Bathymetry | Could? |

## Output 

| Data | MoSCoW |
| --- | --- |
| DSM | Must |
| DTM | Should |

# Questions 
- Pre-classified PCs: can we use them for DTM? Is the classification reliable? 
- DTM: interpolate gaps / NoData? How? 
- Output format: tiled, COG, or something else?
- **Do the clients want bathymetry?**
- **Metadata: what, how? Global or perhaps also some per-pixel data?**
- What prevents us from using CRS transformations for the pointclouds?
- Any extra stuff the client wants other than required submission files? 
- **Output: CRS, resolution?**
- RDNAPTRANS for Dutch PC? And are there equivalent conversion tools for other CRS? 
- How to ensure input data quality? 
- How to ensure output data quality? 
- How to actually get the data — stream it? 
- RA: what are the risks? And how do we want to present them? 

# Research Questions: 

**How to create a harmonised cross-border DEM (of the Rhine catchment area) in an automated (and efficient) way?**

Secondary questions: 
- What are the limitions of an automated harmonisation pipeline? 
- What are the unknowns/variables in the data we need to consider? 
- What are the existing DEMs (local/global)? 
- What, if any, are the existing workflows for processing point clouds from heterogeneous sources? 

# Risks: 

- computation might take too long
- data might be of low quality
- some of the data may not be possible to acquire
- there may be barriers (e.g. language barriers) when trying to acquire data
- CRS transformation may not be accurate
- there may be missing / conflicting data on the borders
- task might be too ambitious given the timeframe or team size
- datasets are massive -> QA is challenging, some edge cases may not be considered
