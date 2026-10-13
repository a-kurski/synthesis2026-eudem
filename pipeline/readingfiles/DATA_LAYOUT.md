# Country and region data layout

All configs use `cache_root: "data"`, `output_root: "data"`,
`old_runs_root: "data/old_runs"` and `logs_dir: "logs/preparation"`.
`old_runs_root` is used only by the one-time migration script.
Paths resolve relative to the config. Country and region identifiers are appended
automatically, using the lowercase names of the existing directories.
France uses `France` for its data directory, as requested, and lowercase
`france` for logs. Raw ASC files live in `data/France/raw_tiles/<department>/`;
archives are in `data/France/source_archive/<department>/`. Its run products
use `data/France/<run_id>/processed/` and `stitched/`, with department receipts
under `logs/preparation/france/raw_receipts/<department>/`.
See [France preparation](FRANCE_PREPARATION.md) for acquisition and cache details.

Luxembourg keeps one original national COG at
`data/luxembourg/raw_tiles/MNT_Lidar2024.tif`, reused across all AOIs.
Its standard per-run outputs and log receipts use the `luxembourg` namespace.
An absolute `source.path` may reference an external local cache; receipts still
stay in logs. Missing sources download automatically, using a temporary `.tif.part`
file beside the destination until validation succeeds. See [Luxembourg preparation](LUXEMBOURG_PREPARATION.md).

```text
data/
  netherlands/
    raw_tiles/                 shared native TIFF cache
    <run_id>/
      processed/               intermediate/target tiles, metadata and _work
      stitched/                final DTMs and associated VRTs
  germany/
    nrw/
      raw_tiles/
      <run_id>/
        processed/
        stitched/
    rlp/                       same structure as NRW
    saarland/                  same structure as NRW
    hessen/                    same structure, plus source_archive/
    bw/                        original ZIPs in source_archive/; same run outputs
    bavaria/                   original ZIPs in source_archive/; native 5 m TIFFs in raw_tiles/
  old_runs/                    preserved older-version runs only
    netherlands/<run_id>/
    germany/<region>/<run_id>/
```

Switzerland and Liechtenstein share `data/switzerland/raw_tiles/`, with edition
and asset identities in filenames. Both use `logs/preparation/switzerland/` for
`raw_receipts/` and the cache writer lock. Processing outputs remain country
scoped: `data/switzerland/<run_id>/` or `data/liechtenstein/<run_id>/`.
The combined Swiss config already includes Liechtenstein's study area.
Each acquisition saves `swissalti3d_manifest.json` before raster transfers;
`--source-manifest` resumes its editions. Copy shared receipts with the cache.
Swiss temporary transfers live beside raw files for atomic replacement, even
when logs and cache are on different drives. All are under ignored directories.

Runtime cache lookup uses only the matching `raw_tiles` directory, never other
regions, old runs, pilots or legacy caches. Validation metadata stays outside raw:

```text
logs/preparation/<country>/[<region>/]
  raw_receipts/<tile>.json      source/request/checksum validation records
  download_work/               temporary downloads
  latest_run.json              latest successful run and its output paths
  latest_plan.json
  <run_id>/                    plans, config, source manifest, logs and result
```

Keep `raw_receipts` when transferring a raw cache to another machine. Netherlands,
NRW and RLP require these records for cache reuse. Saarland also accepts manually
extracted TIFFs and creates local validation receipts; these do not claim archive
checksum verification. Probe TIFFs use `raw_tiles`, with metadata kept in logs.

`--fresh-download` bypasses reuse and atomically replaces a same-name TIFF only
after validation. Failed requests preserve the existing TIFF and receipt.
Saarland checks local TIFFs first. Its optional TAR cache is
`data/germany/saarland/source_archive/desaarland.tar`, never in logs. Local TIFFs
are treated as the supplied collection; use the full extraction or explicitly
request `--fresh-download` when tiles need replenishing.

Hessen uses `data/germany/hessen/source_archive/official/<date>/<KREIS_NR>/` for
regional ZIPs and complete original extractions (including TFWs). Selected TIFFs
are copied to `raw_tiles/` with district-scoped unique names. Archive receipts and
completion/tile indexes live under `logs/preparation/germany/hessen/regional_packages/`.
The old Mapterhorn TAR and index are ignored. See [Hessen preparation](GERMANY_HESSEN_PREPARATION.md).

Baden-Württemberg retains original LGL ZIPs in `data/germany/bw/source_archive/`.
Statewide `--prefetch` and AOI acquisition share this cache. The availability
inventory, archive receipts and completeness summary live under
`logs/preparation/germany/bw/`. Only selected XYZs are converted, in each run's
`source_tiles/` log subdirectory; these derivatives are not a second durable cache.
Source provenance is copied to `processed/source_provenance.json` before publication
results are recorded. See [Baden-Württemberg preparation](GERMANY_BW_PREPARATION.md).

## Run products and legacy runs

Bavaria caches its Metalink catalogue and validation receipts under
`logs/preparation/germany/bavaria/`. Selected original ZIPs and converted TIFFs
are both persistent, with per-run outputs following the same regional layout.
See [Bavaria preparation](GERMANY_BAVARIA_PREPARATION.md).

Within each run folder, `processed/` contains `run.json`, `result.json`, `target_grid.json`,
`target_grid.vrt`, published target tiles and `tiles.json`. Intermediate mosaics,
warps, masks and reports live in `processed/_work/`. Final COGs and VRTs are in
`stitched/`, including AHN's baseline/fill-status products when enabled.

`data/old_runs/` holds runs from the older pipeline version only. Normal runs
never write there or move outputs there.

After successful acquisition, processing creates a new folder beside `raw_tiles/`
using the existing Amsterdam run ID (`YYYY-MM-DD_HH-MM-SS`, with a numeric suffix
for collisions). Its `processed/` and `stitched/` folders belong only to that run.
Previous run folders are never cleared, overwritten or moved automatically.
New downloads accumulate in the shared regional raw cache.

`latest_run.json` is updated only after successful processing. A failed run may
leave partial products in its own folder; earlier successful outputs and their
latest-success pointer remain intact. New pilot outputs default to the regional
`logs/preparation/.../pilots/` directory.

`--plan` and `--probe` do not create processing run folders. A regional lock
protects the shared cache from concurrent writers. After forcibly killing a
process, remove its `active.lock` only after confirming it is no longer running.

## Migration and remote copies

```bash
python3 scripts/migrate_data_layout.py
```

This standard-library script requires Python 3.11+. It moves old `data/prepared`
runs into `old_runs`, preserves historical products, and copies checksum-verified
raw TIFFs into the new country/region caches. Receipts go into logs. Existing cache
files are not overwritten; conflicts are reported in `logs/data_layout_migration.json`.
Historical pilots move to their country/region's `old_runs/.../pilots/` folder.
The runtime downloader does not repeat this one-time search of legacy data.

The migration has already been applied locally. To migrate a remote workspace,
copy the updated `dtm/`, `scripts/`, configs and documentation, then run the command
there. Preserve the remote Python environment and data. Copy `tests/` if you want
to run the verification suite:

```bash
python3 main.py config.germany.saarland.json --self-test
python3 main.py config.netherlands.json --plan
python3 main.py config.germany.nrw.json --plan
python3 main.py config.germany.rlp.json --plan
python3 main.py config.germany.saarland.json --plan
python3 main.py config.germany.hessen.json --plan
```
