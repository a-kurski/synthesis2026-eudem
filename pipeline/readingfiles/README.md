# Rhine catchment terrain preparation

The pipeline prepares Luxembourg, France, the Netherlands, Switzerland/Liechtenstein and Germany's
NRW, Rheinland-Pfalz, Saarland, Hessen, Baden-Württemberg and Bavaria regions on a shared 5 m EPSG:25832 grid.

| Config | Guide | Final output |
|---|---|---|
| `config.luxembourg.json` | [Luxembourg](LUXEMBOURG_PREPARATION.md) | `data/luxembourg/<run_id>/stitched/mnt_lidar2024.tif` |
| `config.france.json` | [France](FRANCE_PREPARATION.md) | `data/France/<run_id>/stitched/rge_alti.tif` |
| `config.netherlands.json` | [Netherlands](NETHERLANDS_PREPARATION.md) | `data/netherlands/<run_id>/stitched/ahn.tif` |
| `config.germany.nrw.json` | [NRW](GERMANY_NRW_PREPARATION.md) | `data/germany/nrw/<run_id>/stitched/nrw.tif` |
| `config.germany.rlp.json` | [RLP](GERMANY_RLP_PREPARATION.md) | `data/germany/rlp/<run_id>/stitched/rlp.tif` |
| `config.germany.saarland.json` | [Saarland](GERMANY_SAARLAND_PREPARATION.md) | `data/germany/saarland/<run_id>/stitched/saarland.tif` |
| `config.germany.hessen.json` | [Hessen](GERMANY_HESSEN_PREPARATION.md) | `data/germany/hessen/<run_id>/stitched/hessen.tif` |
| `config.germany.bw.json` | [Baden-Württemberg](GERMANY_BW_PREPARATION.md) | `data/germany/bw/<run_id>/stitched/bw.tif` |
| `config.germany.bavaria.json` | [Bavaria](GERMANY_BAVARIA_PREPARATION.md) | `data/germany/bavaria/<run_id>/stitched/bavaria.tif` |
| `config.switzerland.json` | [Switzerland and Liechtenstein](SWITZERLAND_PREPARATION.md) | `data/switzerland/<run_id>/stitched/swissalti3d.tif` |
| `config.liechtenstein.json` | [Switzerland and Liechtenstein](SWITZERLAND_PREPARATION.md) | `data/liechtenstein/<run_id>/stitched/swissalti3d.tif` |

France stores native ASC tiles by department, for example `data/France/raw_tiles/25/<tile>.asc`.
Baden-Württemberg keeps original ZIPs in `data/germany/bw/source_archive/` and
keeps converted 1 m TIFFs in `data/germany/bw/raw_tiles/`. Countries/regions use a shared `raw_tiles/` cache and a
separate `<run_id>/` folder for each processing run. Every run contains
`processed/` (intermediate and target tiles) and `stitched/` (final DTMs).
Earlier runs stay untouched. `data/old_runs/` contains older-version runs only.
Logs and receipts stay under `logs/preparation/<country>/[<region>/]`. Saarland
uses local raw TIFFs first; its optional source archive lives beside `raw_tiles/`.
See [Data layout and migration](DATA_LAYOUT.md), including remote-copy instructions.

## Commands

Run from the workspace with its Python/GDAL environment activated:

```powershell
python main.py config.netherlands.json --plan
python main.py config.france.json --plan
python main.py config.france.json --yes
python main.py config.netherlands.json --yes
python main.py config.germany.nrw.json --yes
python main.py config.germany.rlp.json --yes
python main.py config.germany.saarland.json --yes
python main.py config.germany.hessen.json --yes
python main.py config.germany.bw.json --prefetch
python main.py config.germany.bw.json --yes
python main.py config.germany.bavaria.json --yes
python main.py config.germany.saarland.json --self-test
```

`--plan` is offline. `--probe` acquires a native sample; Saarland checks local
TIFFs before using its archive fallback. `--yes` runs without the terminal DOWNLOAD prompt. `--reuse-cache`
validates only the region's raw cache; `--fresh-download` commits replacements only
after validation. Netherlands hole filling can be disabled with `--no-fill-holes`.

Luxembourg reuses one complete locally cached national COG for every AOI.
Its `--probe` downloads the entire national COG if missing, then validates it.
See the Luxembourg guide for the cache path and processing commands.

Hessen downloads complete official district ZIPs selected by the local KREIS_LA
boundary layer, preserves all original files, and processes only AOI TIFFs. Regional
packages and extractions are reused. Its Downloadcenter date is configurable; see
the Hessen guide for the official-source workflow and cache layout.

Baden-Württemberg's optional `--prefetch` fills its statewide archive cache once;
normal AOI runs reuse those ZIPs and download only missing selected archives.
See the Baden-Württemberg guide for discovery, refresh and provenance details.

NRW/RLP/Hessen/Baden-Württemberg use exact native 5 × 5 averages; Saarland uses area-weighted average
alignment for its half-metre offset. Dutch data uses the existing horizontal
transformation and average resampling. No vertical datum harmonisation occurs.
A common `target.reference_raster` enforces identical extents and dimensions.

Switzerland's config uses the existing combined `Swiss_liech.gpkg` study mask.
Both Swiss-provider entries share one native 2 m cache. One average warp performs
LV95 to EPSG:25832 reprojection and 5 m alignment; LN02 heights are retained.
STAC edition discovery happens during acquisition, preserving offline `--plan`.
See the Swiss guide for the small live pilot and frozen-manifest resume commands.

Netherlands, NRW and RLP use four download workers in the supplied configs.
Saarland's archive and extraction are sequential. Metadata is fetched once per
acquisition; HTTP requests share configured pacing. Progress bars cover downloads,
cleaning, mosaicking, resampling and publication. `tqdm` is provided in
`.python-packages/` and listed in `requirements.txt`.

See [COG outputs](COG_OUTPUTS.md) for lossless publication and internal overviews.
