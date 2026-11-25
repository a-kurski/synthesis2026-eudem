"""Recover a completed AHN alignment into a new run, with nearest fallback OFF."""
import argparse
import json
import logging
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def preflight(source_run, source_logs):
    import numpy as np
    from osgeo import gdal, osr
    from dtm.acquire import sha256
    from dtm.coordinator import load_config
    from dtm.geo import grid
    from dtm.progress import blocks

    source_run, source_logs = Path(source_run).resolve(), Path(source_logs).resolve()
    config = load_config(source_logs / 'config.json')
    if config['country'] != 'netherlands' or not config['hole_filling']['enabled']:
        raise ValueError('Recovery requires a Netherlands run with hole filling enabled.')
    plan = json.loads((source_logs / 'plan.json').read_text(encoding='utf-8-sig'))
    if sha256(Path(config['aoi'])) != plan['aoi_sha256']:
        raise ValueError('AOI changed since the source run; recovery refused.')
    target = json.loads((source_run / 'processed/target_grid.json').read_text(encoding='utf-8-sig'))
    for key in ('cols', 'rows', 'transform', 'crs'):
        if target[key] != plan['target_grid'][key]:
            raise ValueError('Saved target grid does not match this run plan.')
    context = source_run / 'processed/_work/aligned/ahn_resampled_with_context.tif'
    completed_log = (source_logs / 'processing.log').read_text(encoding='utf-8')
    if str(context) not in completed_log or 'Alignment verified:' not in completed_log:
        raise ValueError('Saved log does not confirm the completed contextual alignment.')
    padding = math.ceil(config['hole_filling']['max_distance_m'] / target['transform'][1]) + 1
    expected_transform = list(target['transform'])
    expected_transform[0] -= padding * target['transform'][1]
    expected_transform[3] += padding * target['transform'][1]
    actual = grid(context)
    if (actual['cols'] != target['cols'] + 2 * padding
            or actual['rows'] != target['rows'] + 2 * padding
            or actual['nodata'] != config['nodata'] or actual['dtype'] != 'Float32'
            or not np.allclose(actual['transform'], expected_transform, rtol=0, atol=1e-8)
            or not osr.SpatialReference(wkt=actual['crs']).IsSame(osr.SpatialReference(wkt=target['crs']))):
        raise ValueError('Completed raster grid does not match the saved configuration.')
    with gdal.Open(str(context)) as ds:
        if ds.RasterCount != 1:
            raise ValueError('Expected one elevation band.')
        for window in blocks(ds, config['block_size'], 'Checking saved alignment'):
            values = ds.GetRasterBand(1).ReadAsArray(*window)
            if values is None or values.shape != (window[3], window[2]):
                raise ValueError('Completed alignment contains unreadable blocks.')
    config['hole_filling']['nearest_fallback'] = False
    return config, plan, target, context, padding


def recover(source_run, source_logs, check_only=False):
    from dtm.acquire import write_json
    from dtm.coordinator import create_log_directory, load_config
    from dtm.countries.netherlands.processing import finish_from_alignment
    from dtm.geo import read_aoi
    from dtm.paths import region_lock, scoped_root
    from dtm.target_grid import write_reference

    source_run, source_logs = Path(source_run).resolve(), Path(source_logs).resolve()
    # Use the same writer lock as the normal pipeline, before reading inputs.
    saved_config = load_config(source_logs / 'config.json')
    with region_lock(saved_config):
        config, plan, target, context, padding = preflight(source_run, source_logs)
        if check_only:
            print(f'Recoverable: {context}; nearest fallback will be OFF.')
            return
        logs = create_log_directory(config)
        run_dir = scoped_root(config, 'output_root') / logs.name
        processed = run_dir / 'processed'
        processed.mkdir(parents=True)
        metadata = {'source_run': str(source_run), 'source_logs': str(source_logs),
                    'reused_alignment': str(context), 'nearest_fallback': False}
        state = {'country': 'netherlands', 'run_id': logs.name, 'recovery': metadata}
        write_json(logs / 'config.json', config)
        write_json(logs / 'plan.json', plan)
        write_json(logs / 'recovery.json', metadata)
        write_json(processed / 'target_grid.json', target)
        write_json(processed / 'run.json', {**state, 'status': 'processing'})
        logger = logging.getLogger('dtm')
        handler = logging.FileHandler(logs / 'processing.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        try:
            reference = write_reference(target, processed / 'target_grid.vrt')
            geometry, _, _ = read_aoi(config['aoi'], config['layer'])
            logger.info('Recovering %s; skipping acquisition, cleaning, mosaic and warp; nearest OFF', context)
            result = finish_from_alignment(context,
                source_run / 'processed/_work/mosaics/ahn_merged.tif',
                geometry, reference, run_dir, config, padding)
            result.update(state, status='complete', stage='prepared', log_directory=str(logs),
                          target_reference=str(reference), plan_file=str(logs / 'plan.json'))
            for path in (processed / 'result.json', logs / 'result.json', logs.parent / 'latest_run.json'):
                write_json(path, result)
            write_json(processed / 'run.json', {**state, 'status': 'complete'})
            print(f"Recovered: {result['comparison_ready_raster']}")
            print(f"Remaining NoData cells: {result['hole_filling']['remaining_nodata_cell_count']}")
            return result
        except BaseException:
            write_json(processed / 'run.json', {**state, 'status': 'failed'})
            logger.exception('Recovery stopped; source run preserved')
            raise
        finally:
            logger.removeHandler(handler)
            handler.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--source-logs', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    recover(args.source_run, args.source_logs, args.check_only)


if __name__ == '__main__':
    from dtm.runtime import bootstrap
    bootstrap(__file__, str(ROOT / 'config.netherlands.json'))
    main()
