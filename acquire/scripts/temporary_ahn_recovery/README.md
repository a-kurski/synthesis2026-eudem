# Temporary Netherlands recovery — 4 October 2026

This isolated script reuses the completed alignment raster from
`data/netherlands/2026-10-04_17-18-55`. It does not modify the normal pipeline or
the country configuration. `main.py` never imports this directory.

Both IDW and nearest fallback are limited to the original configured 100 m
(20 pixels on the 5 m grid). NoData beyond this search remains NoData. Reports
include the cap, remaining gaps and temporary-recovery provenance. Only original
valid cells are donors; already-filled cells are not promoted to donors.

Preflight checks the saved AOI checksum, target and contextual grid, completion
log, every raster block and source SHA256. The old partially written hole-filling
files are not reused. Downloaded sources, cleaned tiles and mosaic are preserved;
acquisition, cleaning, mosaicking and horizontal resampling are skipped. Filling,
masking and output publication are rerun in a NEW timestamped directory.

The actual completed alignment passed preflight with SHA256:
`39524d2f295f8ee0d06f68ac3f9c1d5f9e8866681cc91cec32ff058fcca6b06a`.

## Invocation (already launched by Codex)

Do not launch a second instance while the regional lock is held.

```powershell
python scripts/temporary_ahn_recovery/recover.py --source-run data/netherlands/2026-10-04_17-18-55
```

The explicit command above is the only entry point. After success, the script
writes `COMPLETED.json` beside itself and refuses subsequent processing runs.
There is nothing to revert in the normal pipeline. Keeping these scripts as an
audit trail does not enable their behavior in future normal runs.

## Status

```powershell
Get-Content scripts/temporary_ahn_recovery/stderr.log -Tail 20 -Wait
```

The new run also has `logs/preparation/netherlands/<run_id>/processing.log`.
Progress during both GDAL filling passes is logged every 5 percentage points,
and a heartbeat records process CPU time every minute. A final `result.json`
and `latest_run.json` are written only on success, with the remaining NoData
count. `COMPLETED.json` records the successful run and confirms that the normal
source files and config hashes were unchanged. Failed/interrupted recovery can
be restarted after verifying that its lock is stale; it will use a fresh run.

## Validation

Three synthetic tests pass with the local QGIS GDAL 3.11.3 installation:
finite search / distant gaps / unchanged donors; end-to-end recovery publication
without cleaning, mosaicking or warping; grid mismatch rejection and normal
module isolation. The completed real contextual raster also passed a full-read
preflight. GDAL cache is capped at 128 MiB for this process.

```powershell
python main.py config.netherlands.json --self-test
```

The normal self-test discovers `tests/test_temporary_ahn_recovery.py` along with
the other offline tests. No raw raster or old output is deleted by recovery.
