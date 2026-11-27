# Luxembourg LiDAR 2024 MNT

`config.luxembourg.json` selects the bare-earth national MNT, originally a
0.5 m Float64 COG in EPSG:2169. The example AOI is the existing Luxembourg
country mask. Change `aoi` for a study area; `country_mask` always limits output
to Luxembourg. Both resolve relative to the config. `enabled: false` skips the
handler. Non-intersecting AOIs skip before source validation or processing.

The pipeline downloads the entire original source once when it is missing:

```text
data/luxembourg/raw_tiles/MNT_Lidar2024.tif
```

This is one national COG, not a TAR/ZIP or a tile collection. `source.path`
defaults to that filename under the existing country raw cache. An absolute
path can point to another persistent local cache without copying the file.
`source.url` is the configurable download address; `source.version` records
provenance. A missing file downloads automatically using the existing requests
dependency, timeout, retry count and byte-progress helper. Transfers stream to
`MNT_Lidar2024.tif.part` beside the destination and are validated before atomic
rename. Incomplete transfers are preserved; network retries start from the
beginning. Complete files that fail validation are preserved without another
HTTP transfer. A later run validates a complete `.tif.part` in place and promotes
it to the cache if valid. The complete national file is about 40.13 GB (37.37 GiB).

```powershell
python main.py config.luxembourg.json --plan
python main.py config.luxembourg.json --probe
python main.py config.luxembourg.json --yes
```

`--plan` is offline and does not open the source. `--probe` downloads the entire
national COG if missing and validates it in place. `--yes` does the same before
processing. Subsequent runs reuse the validated cache without HTTP requests. `--fresh-download`
is unsupported: every run must reuse the same original source.

Validation checks the documented 40,131,787,860-byte file size, successful GDAL
opening, national dimensions (114,617 × 163,687), origin (48,880.5, 138,809),
0.5 m spacing, EPSG:2169, single-band Float64, NoData=-9999 and COG layout.
These checks reject truncation and mismatched products; they are not a full
checksum or scan of every compressed block. Acquisition must supply a complete
original file. Receipts explicitly record that no checksum was verified.
An invalid existing cache or completed `.part` is reported and preserved;
inspect its metadata before replacing it. The official COG's east/north CRS
axis order is accepted alongside EPSG:2169's north/east order. Validation still
compares the datum, projection parameters and units.
Changed publisher products need their source contract reviewed before reuse.

One GDAL average warp reads the local source directly and performs horizontal
reprojection, downsampling and exact alignment to `target_grid.vrt`. It uses
the reference bounds and dimensions, `-ovr NONE`, `-novshift`, and `-et 0`.
The shared grid planner defines the reference or AOI grid exactly as for other
countries. GDAL samples each chunk's source window with `SAMPLE_GRID=YES` and
adds `SOURCE_EXTRA=20` (10 m at source resolution). The input remains uncut so
border averages retain source support. No source-resolution intermediate is
written. AOI and country geometries use the shared densifying reprojection
helper and pixel-centre masking. Missing source coverage remains NoData.

Interactive terminals show warp percentage, elapsed time and estimated remaining
time through the shared GDAL progress helper. AOI counting, masking, COG writing,
tile publication and pixel verification also use the existing progress bars.
The warp estimate can fluctuate; it is GDAL's reported work progress, not a
guaranteed time estimate. Redirected output omits animated bars. Updates apply
to new processes only, not a warp already running on a server.

The standard publisher writes 5 m EPSG:25832 Float32 COG tiles with DEFLATE
compression and average display overviews, validates COG layout, and verifies
stitched pixels and alignment. Source heights receive no vertical correction;
the 2024 vertical reference remains unconfirmed. Product/version, URL, source
and target CRSs, resampling and the horizontal-only operation are recorded.

```text
data/luxembourg/<run_id>/processed/             target tiles, grid, coverage.json
data/luxembourg/<run_id>/processed/_work/       AOI-sized warp and masks
data/luxembourg/<run_id>/stitched/mnt_lidar2024.tif
logs/preparation/luxembourg/raw_receipts/       source validation receipts
logs/preparation/luxembourg/<run_id>/           plan, config, manifest, result
```

Earlier runs and the original COG stay untouched. A skipped run records its
reason in logs and does not create output rasters or replace `latest_run.json`.
Offline tests use scaled synthetic COGs to exercise cache reuse, rejection,
masking, exact reference alignment, ignored source overviews and publication.
Download tests use mocked HTTP streams and real GDAL validation of small COGs;
they do not transfer the 40 GB production source.
