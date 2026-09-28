# Rhine catchment terrain preparation

The active workflow prepares national terrain data on a shared comparison grid.
The Netherlands is the first implemented country. Start with
[Netherlands preparation](NETHERLANDS_PREPARATION.md).

```powershell
python main.py config.netherlands.json --plan
python main.py config.netherlands.json --self-test
```

Hole filling is enabled by default at a 20 m search distance, including when
the configuration omits hole-filling settings. It
retains an unfilled baseline and flags interpolated contributions. See
[hole-filling validation](HOLE_FILLING_VALIDATION.md) for the cached-tile pilot.

```powershell
# Reuse downloads and fill gaps (current configuration)
python main.py config.netherlands.json --yes
# Reuse downloads but leave gaps unfilled
python main.py config.netherlands.json --no-fill-holes --yes
# Fresh downloads, no filling; old cached files remain intact
python main.py config.netherlands.json --fresh-download --no-fill-holes --yes
```

## Current workspace

| Location | Purpose |
|---|---|
| `main.py` | Current entry point. |
| `config.netherlands.json` | Netherlands input, source and target settings. |
| `dtm/` | Coordinator, shared helpers and country modules. |
| `tests/` | Current preparation tests. |
| `data/prepared/` | New outputs, created when preparation runs. |
| `logs/preparation/` | Current run logs and plans. |
| `netherlands.gpkg`, `small_study_area.gpkg`, `borders_masks/` | Available GIS inputs/supporting work; not automatically selected. |
| `version_1/` | Original AHN–NRW comparison, code snapshot, data, outputs, tests and documentation. |

The current config selects `netherlands.gpkg` and reuses downloads in `version_1/data/ahn_tiles`.
Each new run uses `data/prepared/netherlands/<run_id>/` with:

- `raw_ahn_tiles/`: new downloads and their validation receipts.
- `processed_tiles/`: finished, filled, transformed and aligned target-grid tiles;
  intermediate work is in the `_work` subfolder.
- `ahn_stitched/ahn.tif`: the selected tiles stitched into one GeoTIFF.

The final interpolation fractions are saved only as
`ahn_stitched/ahn_fill_fraction.tif`, without separate fill-fraction tiles.
The unfilled baseline is saved directly as `ahn_stitched/ahn_unfilled.tif`,
without separate unfilled tiles.

New run and log folders share a readable Amsterdam date/time name, for example
`2026-09-27_20-49-10`. Same-second collisions receive `_02`, `_03`, etc.
Existing folders keep their original names. Timezone support uses `tzdata` when
the operating system does not provide the timezone database.

Validated cached downloads are reused in place, including older runs and the
version 1 cache. New downloads always go into the new run's `raw_ahn_tiles`.
Change `aoi` to use another polygon. Disable filling with `--no-fill-holes`.

See [the version 1 archive guide](../version_1/ARCHIVE.md) to run or inspect the old
comparison. The old code has its own copies of shared utilities, so current
development does not change its implementation.
