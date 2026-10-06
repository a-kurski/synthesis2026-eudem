"""One-off AHN recovery from a completed contextual warp; never used by main.py."""
import argparse
from contextlib import contextmanager
import importlib.util
import json
import logging
import math
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def load_temporary_modules():
    modules = []
    for suffix, filename in [('_temporary_bounded_holes', 'bounded_hole_filling.py'),
                             ('_temporary_recovery_processing', 'recovery_processing.py')]:
        name = 'dtm.countries.netherlands.' + suffix
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


@contextmanager
def logged_progress(description):
    logger = logging.getLogger('dtm')
    start = time.monotonic()
    last = [-5]
    logger.info('%s started', description)
    def callback(fraction, message, data):
        percent = int(fraction * 100)
        if percent >= last[0] + 5 or percent == 100 and last[0] != 100:
            logger.info('%s: %d%%; %.1f seconds', description, percent, time.monotonic() - start)
            last[0] = percent
        return 1
    yield callback
    logger.info('%s finished in %.1f seconds', description, time.monotonic() - start)


def validate_saved_grid(actual, expected):
    import numpy as np
    from osgeo import osr
    if (any(actual[k] != expected[k] for k in ('cols', 'rows', 'nodata', 'dtype'))
            or not np.allclose(actual['transform'], expected['transform'], rtol=0, atol=1e-8)
            or not osr.SpatialReference(wkt=actual['crs']).IsSame(osr.SpatialReference(wkt=expected['crs']))):
        raise ValueError('Saved raster does not match the completed run grid.')


def preflight(source_run):
    from osgeo import gdal
    from dtm.acquire import sha256
    from dtm.geo import grid
    source_run = Path(source_run).resolve()
    if source_run.parent != (ROOT / 'data/netherlands').resolve():
        raise ValueError('Source run must be directly under this workspace data/netherlands.')
    logs = ROOT / 'logs/preparation/netherlands' / source_run.name
    config = json.loads((logs / 'config.json').read_text(encoding='utf-8-sig'))
    plan = json.loads((logs / 'plan.json').read_text(encoding='utf-8-sig'))
    target = json.loads((source_run / 'processed/target_grid.json').read_text())
    if config['country'] != 'netherlands' or not config['hole_filling']['enabled']:
        raise ValueError('This temporary recovery is only for AHN with filling enabled.')
    distance = config['hole_filling']['max_distance_m']
    if not 0 < distance <= 100:
        raise ValueError('This one-off recovery permits at most 100 m for both filling passes.')
    if sha256(Path(config['aoi'])) != plan['aoi_sha256']:
        raise ValueError('AOI changed since the source run; refusing incompatible recovery.')
    context = source_run / 'processed/_work/aligned/ahn_resampled_with_context.tif'
    completed_log = (logs / 'processing.log').read_text(encoding='utf-8')
    if 'Alignment verified:' not in completed_log:
        raise ValueError('Source log does not confirm completed alignment.')
    validate_saved_grid(grid(source_run / 'processed/target_grid.vrt'), target)
    padding = math.ceil(distance / target['transform'][1]) + 1
    expected = {**target, 'cols': target['cols'] + 2 * padding,
                'rows': target['rows'] + 2 * padding, 'transform': list(target['transform'])}
    expected['transform'][0] -= padding * target['transform'][1]
    expected['transform'][3] += padding * target['transform'][1]
    validate_saved_grid(grid(context), expected)
    logging.getLogger('dtm').info('Reading every block of completed alignment raster for validation')
    with gdal.Open(str(context)) as ds:
        if ds.RasterCount != 1 or ds.GetRasterBand(1).Checksum() < 0:
            raise ValueError('Completed alignment raster is unreadable.')
    digest = sha256(context)
    return config, plan, target, context, digest


def main():
    from osgeo import gdal
    # Bound the recovery's raster cache, including the full-read preflight.
    gdal.SetCacheMax(128 * 1024 * 1024)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    log = logging.getLogger('dtm')
    completed = Path(__file__).with_name('COMPLETED.json')
    if completed.exists() and not args.check_only:
        raise RuntimeError('This temporary recovery already completed; it is disabled. See COMPLETED.json.')
    config, plan, target, context, digest = preflight(args.source_run)
    log.info('Validated recovery source %s; SHA256=%s; bounded search=%s m',
             context, digest, config['hole_filling']['max_distance_m'])
    if args.check_only:
        return
    from dtm.acquire import write_json, sha256
    from dtm.coordinator import create_log_directory
    from dtm.geo import read_aoi
    from dtm.paths import region_lock, scoped_root
    from dtm.target_grid import write_reference
    bounded, processing = load_temporary_modules()
    bounded.gdal_progress = logged_progress
    canonical = [ROOT / 'dtm/countries/netherlands/hole_filling.py',
                 ROOT / 'dtm/countries/netherlands/processing.py', ROOT / 'config.netherlands.json']
    original_hashes = {str(p): sha256(p) for p in canonical}
    with region_lock(config):
        logs = create_log_directory(config)
        run_dir = scoped_root(config, 'output_root') / logs.name
        processed = run_dir / 'processed'
        processed.mkdir(parents=True)
        handler = logging.FileHandler(logs / 'processing.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        log.addHandler(handler)
        stop = threading.Event()
        def heartbeat():
            while not stop.wait(60):
                log.info('Recovery process alive; CPU time %.1f seconds', time.process_time())
        worker = threading.Thread(target=heartbeat, daemon=True)
        worker.start()
        metadata = {'temporary_recovery': True, 'source_run': str(args.source_run.resolve()),
                    'reused_alignment': str(context), 'alignment_sha256': digest,
                    'nearest_max_distance_m': config['hole_filling']['max_distance_m'],
                    'unfilled_gaps': 'Retained as NoData; no unlimited search',
                    'canonical_hashes_before': original_hashes}
        try:
            write_json(logs / 'config.json', config)
            write_json(logs / 'plan.json', plan)
            write_json(logs / 'recovery.json', metadata)
            write_json(processed / 'run.json', {'run_id': logs.name, 'status': 'processing', **metadata})
            write_json(processed / 'target_grid.json', target)
            reference = write_reference(target, processed / 'target_grid.vrt')
            geometry, _, _ = read_aoi(config['aoi'], config['layer'])
            log.info('RECOVERY RUN %s: skipping acquisition, cleaning, mosaic and warp', logs.name)
            result = processing.recover(context,
                args.source_run.resolve() / 'processed/_work/mosaics/ahn_merged.tif',
                geometry, reference, run_dir, config)
            if sha256(context) != digest:
                raise RuntimeError('Recovery source checksum changed during processing.')
            if {str(p): sha256(p) for p in canonical} != original_hashes:
                raise RuntimeError('Normal pipeline files changed during recovery; inspect before accepting.')
            result.update(metadata, country='netherlands', status='complete', stage='prepared',
                          run_id=logs.name, log_directory=str(logs),
                          target_reference=str(reference), plan_file=str(logs / 'plan.json'))
            for path in (processed / 'result.json', logs / 'result.json', logs.parent / 'latest_run.json'):
                write_json(path, result)
            write_json(processed / 'run.json', {'run_id': logs.name, 'status': 'complete', **metadata})
            write_json(completed, {'run_id': logs.name, 'result': str(logs / 'result.json'),
                                  'disabled': True, 'canonical_files_unchanged': True})
            log.info('RECOVERY COMPLETE: %s; remaining AOI NoData cells=%s',
                     result['comparison_ready_raster'], result['hole_filling']['remaining_nodata_cell_count'])
        except BaseException:
            log.exception('Recovery stopped; completed source alignment preserved')
            write_json(processed / 'run.json', {'run_id': logs.name, 'status': 'failed', **metadata})
            raise
        finally:
            stop.set()
            worker.join(timeout=2)
            log.removeHandler(handler)
            handler.close()


if __name__ == '__main__':
    from dtm.runtime import bootstrap
    bootstrap(__file__, str(ROOT / 'config.netherlands.json'))
    main()
