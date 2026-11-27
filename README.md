# Harmonising European Elevation Data across Borders: a Case Study on the Rhine Catchment Area

MSc Geomatics for the Built Environment Synthesis Project

TU Delft, 2026

By:
- Artemi Kurski @a-kurski
- Arda Baysal @ardabys
- Ruben Vons @Blacklight1717

Supervised by Gina Stavropoulou (TU Delft), Maarten Pronk (Deltares) and Daan van der Heide (Rijkswaterstaat).

A user-configurable automated pipeline that assembles a harmonised gridded digital terrain model (DTM) of the Rhine catchment area from heterogeneous elevation data by different national/regional data providers. 

**[TU Delft Repository](https://repository.tudelft.nl/record/uuid:fb76432f-8e82-4d42-8dbd-c7c23d430072)**

## Result

- A 5 m DTM in ETRS89-LAEA (EPSG:3035) with EVRF2007 heights (EPSG:5621), stored as a Cloud-Optimised GeoTIFF, plus a river mask on the same grid.
- Covers Switzerland, Liechtenstein, France, Luxembourg, the Netherlands and the German states of Bavaria, Baden-Württemberg, Hessen, Rhineland-Palatinate, Saarland and North Rhine-Westphalia. That is 97.33 % of the catchment, an omission rate of 2.67 %. The Austrian, Belgian, Italian and Thuringian elevation data are missing.
- The source data is kept as-found: no cross-border smoothing or feathering are applied. 
- 15 of the 17 border pairs meet the INSPIRE requirement for vertical accuracy, with a mean RMSE of 0.50 m against the 1.67 m. Errors are best explained by differences in acquisition and processing employed by the data provider.

## Repository layout

| Path | Contents |
|---|---|
| `acquire/` | **Acquisition pipeline** downloads and caches source tiles from each provider, with one JSON config per country or state (`config.*.json`). See the guides for each provider in [`acquire/readingfiles/`](acquire/readingfiles/README.md). |
| `process/` | **Merge pipeline** carries out reprojection, height transformation and resampling to the common grid, gap filling, river masks, overlap resolution and assembly. Also performs the pairwise border comparison. See [`process/README.md`](process/README.md) and [`process/KNOWN_ISSUES.md`](process/KNOWN_ISSUES.md). |
| `report/` | Typst sources and figures of the report. |
| `environment.yml` | One conda environment for everything above. |

## Setup

```bash
conda env create -f environment.yml    # or mamba / micromamba
conda activate eudem
export PROJ_NETWORK=ON                 # let PROJ fetch the height-transformation grids it needs
```

GDAL and its Python bindings _must_ come from conda-forge, not pip. On Windows, the entry points re-launch themselves in the Python of a QGIS installation (the `qgis_root` in the config, `OSGEO4W_ROOT`, or any QGIS found under `C:\Program Files`) instead of the conda environment.

## Running

Rasters and vector files (`*.tif`, `*.gpkg`) are not in the repository. `process/get_osm_masks.py` regenerates the region outlines from OpenStreetMap. The data paths in `process/pipeline.json` point to the team's server, so adjust them before a run.

```bash
# 1. Acquire the source tiles (cached in acquire/data/<region>/raw_tiles/)
cd acquire
python main.py config.netherlands.json --plan    # offline: show what would be downloaded
python main.py config.netherlands.json --yes     # download and prepare; repeat for each config.*.json

# 2. Merge them into one DTM and compare the borders
cd ../process
python main.py pipeline.json                     # vectors → rasters → rivers → overlaps → assemble
python -m dtm.comparison pipeline.json           # border statistics, plots and uncertainty
```

Both steps resume: a rerun skips work that is already finished.

Tests run offline on small synthetic data:

```bash
(cd acquire && python -m unittest discover tests)
(cd process && python -m unittest discover tests)
```

To build the report, run `typst compile report/main.typ`.

## Licence

Report and slides (`report/` and both PDFs) are licensed under [CC BY 4.0](LICENSE-REPORT). 
Code and everything else are licensed under [MIT](LICENSE).
