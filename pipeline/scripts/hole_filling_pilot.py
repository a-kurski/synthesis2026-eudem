"""Offline cached-AHN pilot: real gaps, hidden known patches, full preparation.

Run from the workspace: python scripts/hole_filling_pilot.py config.netherlands.json
Historical native-grid interpolation experiment using three cached tiles.
The integrated preparation check uses the current post-resampling pipeline.
Never calls the download services.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    import argparse
    from datetime import datetime, timezone
    import json
    import time

    import numpy as np
    from osgeo import gdal

    from dtm.acquire import cached, sha256, write_json
    from dtm.paths import raw_directory, receipt_path, scoped_root
    from dtm.coordinator import load_config
    from dtm.countries.netherlands.hole_filling import fill_holes
    from dtm.countries.netherlands.processing import prepare, VERTICAL_NOTE
    from dtm.geo import project, read_aoi, rectangle, srs, verify_alignment
    from dtm.process import clean, create_raster
    from dtm.target_grid import plan_grid, write_reference

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    geometry, _, _ = read_aoi(config['aoi'], config['layer'])
    native_geometry = project(geometry, srs(28992))
    candidates = []
    print('Selecting pilot tiles from the local cache (no acquisition planning or network).', flush=True)
    for path in sorted(raw_directory(config).glob('*.tif')):
        receipt = receipt_path(path, config)
        if not receipt.exists():
            continue
        record = json.loads(receipt.read_text(encoding='utf-8'))
        coverage = record['valid_cells'] / (record['grid']['cols'] * record['grid']['rows'])
        if .2 < coverage < .995 and record['source'] == config['source']:
            # Native chunk plans use integer metre edges. Preserve the request's
            # number formatting so receipt/cache validation compares identically.
            tile = {'id': path.stem, 'bounds': [int(v) if float(v).is_integer() else v for v in record['grid']['extent']]}
            if native_geometry.Intersection(rectangle(tile['bounds'])).GetArea() > 0:
                candidates.append((coverage, tile, path))
    if len(candidates) < 3:
        raise RuntimeError('Need three cached tiles intersecting the AOI with 20–99.5% valid coverage; no downloads attempted.')
    # Deliberately varied coverage, not a random national accuracy sample.
    selected = []
    for desired in (.4, .7, .95):
        item = min(candidates, key=lambda item: abs(item[0] - desired))
        selected.append(item)
        candidates.remove(item)
    output = (args.output or scoped_root(config, 'logs_dir') / 'pilots/hole_filling' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'config.json', config)
    started = time.perf_counter()
    reports, patch_rows, checksums = [], [], []
    all_errors = {distance: [] for distance in (5, 10, 20)}
    withheld_total = 0
    for index, (coverage, tile, raw) in enumerate(selected, 1):
        if not cached(raw, config['source'], tile, config):
            raise RuntimeError(f'Cache validation failed: {raw}')
        before = sha256(raw)
        tile_dir = output / f'tile_{index}_{tile["id"]}'
        tile_dir.mkdir()
        cleaned = tile_dir / 'clean.tif'
        clean(raw, cleaned, config, VERTICAL_NOTE)
        x0, y0, x1, y1 = tile['bounds']
        inner = rectangle([x0 + 25, y0 + 25, x1 - 25, y1 - 25])
        inner.AssignSpatialReference(srs(28992))
        pilot_aoi = native_geometry.Intersection(inner)
        pilot_aoi.AssignSpatialReference(srs(28992))
        if pilot_aoi.IsEmpty() or pilot_aoi.GetArea() <= 0:
            raise RuntimeError('Selected tile has no interior AOI intersection.')
        print(f'Tile {index}: {tile["id"]}; original whole-tile coverage {coverage:.1%}', flush=True)
        for distance in (5, 10, 20):
            trial = {**config, 'hole_filling': {'enabled': True, 'max_distance_m': distance}}
            report = fill_holes(cleaned, pilot_aoi, tile_dir / f'natural_{distance}m', trial)
            report['tile_id'] = tile['id']
            reports.append(report)
            print(f"  {distance} m: filled {report['filled_cell_count']:,}/{report['candidate_cell_count']:,} cells ({report['percent_candidates_filled']:.1f}%)", flush=True)

        # Place separated square patches in known valid terrain. The patch and
        # an 8-pixel ring must be fully valid; no truth exists under real gaps.
        with gdal.Open(str(cleaned)) as ds:
            truth = ds.ReadAsArray()
            withheld = truth.copy()
            occupied = np.zeros(truth.shape, dtype=bool)
            patches = []
            for side in (8, 16, 32):  # 4, 8, 16 metres.
                found = 0
                for row in range(64, truth.shape[0] - 64, 64):
                    for col in range(64, truth.shape[1] - 64, 64):
                        ring = (slice(row - 8, row + side + 8), slice(col - 8, col + side + 8))
                        spacing = (slice(row - 48, row + side + 48), slice(col - 48, col + side + 48))
                        if np.any(truth[ring] == -9999) or np.any(occupied[spacing]):
                            continue
                        patch = (slice(row, row + side), slice(col, col + side))
                        withheld[patch] = -9999
                        occupied[patch] = True
                        patches.append((row, col, side))
                        found += 1
                        if found == 6:
                            break
                    if found == 6:
                        break
                if not found:
                    raise RuntimeError(f'No valid holdout patches for {side} px on {raw}')
            holdout = tile_dir / 'holdout.tif'
            with create_raster(holdout, ds, -9999, VERTICAL_NOTE) as masked:
                masked.GetRasterBand(1).WriteArray(withheld)
        withheld_total += sum(side * side for _, _, side in patches)
        write_json(tile_dir / 'holdout_patches.json', [{'row': row, 'col': col, 'side_pixels': side} for row, col, side in patches])
        for distance in (5, 10, 20):
            trial = {**config, 'hole_filling': {'enabled': True, 'max_distance_m': distance}}
            report = fill_holes(holdout, inner, tile_dir / f'holdout_{distance}m', trial)
            with gdal.Open(report['filled_raster']) as ds:
                for row, col, side in patches:
                    prediction = ds.GetRasterBand(1).ReadAsArray(col, row, side, side)
                    valid = prediction != -9999
                    actual = truth[row:row + side, col:col + side]
                    errors = prediction[valid].astype('float64') - actual[valid].astype('float64')
                    all_errors[distance].append(errors)
                    patch_rows.append({'tile_id': tile['id'], 'row': row, 'col': col,
                                       'hole_width_m': side * .5, 'distance_m': distance,
                                       'withheld_cells': side * side, 'reconstructed_cells': int(valid.sum()),
                                       'bias_m': float(errors.mean()) if errors.size else None,
                                       'mae_m': float(np.abs(errors).mean()) if errors.size else None,
                                       'rmse_m': float(np.sqrt(np.square(errors).mean())) if errors.size else None})
        after = sha256(raw)
        if before != after:
            raise RuntimeError('Original cached tile changed during pilot.')
        checksums.append({'tile': str(raw), 'before': before, 'after': after})
        if index == 1:
            # Complete current preparation: resample, fill, and publish target pixels.
            reference = write_reference(plan_grid(pilot_aoi, {}), tile_dir / 'target.vrt')
            result = prepare([raw], pilot_aoi, reference, tile_dir / 'integrated',
                             {**config, 'hole_filling': {'enabled': True, 'max_distance_m': 10}})
            verify_alignment(result['prepared_filled_raster'], reference)
            with gdal.Open(result['prepared_filled_raster']) as heights, gdal.Open(result['fill_fraction']) as fractions:
                height_valid = heights.ReadAsArray() != -9999
                shares = fractions.ReadAsArray()
                if not np.array_equal(height_valid, shares != -9999):
                    raise RuntimeError('Real-data fill fraction validity differs from elevations.')
                if not np.all((shares[height_valid] >= 0) & (shares[height_valid] <= 1)):
                    raise RuntimeError('Real-data fractions outside [0, 1].')
            write_json(tile_dir / 'integrated/result.json', result)
            integration_result = result
        del truth, withheld, occupied
    summaries = []
    for distance in (5, 10, 20):
        subset = [r for r in reports if r['settings']['max_distance_m'] == distance]
        candidates_count = sum(r['candidate_cell_count'] for r in subset)
        filled_count = sum(r['filled_cell_count'] for r in subset)
        errors = np.concatenate(all_errors[distance])
        summaries.append({'distance_m': distance, 'natural_candidates': candidates_count,
                          'natural_filled': filled_count, 'natural_remaining': candidates_count - filled_count,
                          'natural_percent_filled': filled_count / candidates_count * 100 if candidates_count else 0,
                          'natural_filled_area_m2': filled_count * .25,
                          'holdout_withheld': withheld_total, 'holdout_reconstructed': int(errors.size),
                          'bias_m': float(errors.mean()), 'mae_m': float(np.abs(errors).mean()),
                          'rmse_m': float(np.sqrt(np.square(errors).mean())),
                          'p95_absolute_error_m': float(np.percentile(np.abs(errors), 95))})
    result = {'status': 'complete', 'config_aoi': config['aoi'], 'aoi_sha256': sha256(config['aoi']),
              'radii': summaries, 'natural_gap_reports': reports, 'holdout_patches': patch_rows,
              'raw_checksums': checksums, 'integration': integration_result,
              'elapsed_seconds': time.perf_counter() - started,
              'artifact_bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file()),
              'limitations': 'Three deliberately selected cached tiles; not a national accuracy benchmark. Natural gaps have no truth. Holdout square patches on known valid AHN are proxies, not validation of water depths or ground beneath buildings. All radii are exploratory; no independent final evaluation set.'}
    write_json(output / 'pilot_report.json', result)
    lines = ['# Cached AHN hole-filling pilot', '', result['limitations'], '',
             '| Search (m) | Natural cells filled | Remaining | Filled area (m²) | Hidden cells recovered | Bias (m) | MAE (m) | RMSE (m) | P95 absolute (m) |',
             '|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f"| {r['distance_m']} | {r['natural_filled']:,} ({r['natural_percent_filled']:.1f}%) | {r['natural_remaining']:,} | {r['natural_filled_area_m2']:,.2f} | {r['holdout_reconstructed']:,}/{r['holdout_withheld']:,} | {r['bias_m']:.4f} | {r['mae_m']:.4f} | {r['rmse_m']:.4f} | {r['p95_absolute_error_m']:.4f} |")
    lines.extend(['', 'Original cached TIFF checksums were unchanged. Full preparation and target fill-fraction checks passed on the first cached tile.',
                  '', f"Runtime: {result['elapsed_seconds']:.1f} seconds. Saved artifacts: {result['artifact_bytes'] / 1e9:.2f} GB.", '',
                  'Per-tile, per-hole and output paths are recorded in pilot_report.json.'])
    (output / 'PILOT_REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summaries, indent=2), flush=True)
    print(f'Pilot report: {output / "PILOT_REPORT.md"}', flush=True)


if __name__ == '__main__':
    bootstrap(__file__, 'config.netherlands.json')
    main()
