"""Coordinate country preparation. Country modules own their data/transform rules."""
import argparse
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import platform
import sys
import uuid

import numpy as np
from osgeo import gdal
import requests

from .acquire import sha256, write_json
from .countries import netherlands
from .geo import bounds, read_aoi
from .process import command
from .target_grid import plan_grid, write_reference

# Future country packages implement validate_config, plan, download, probe and
# prepare. A country is selected per invocation; all use the same target grid.
COUNTRIES = {'netherlands': netherlands}
DEFAULTS = {'layer': None, 'cache_root': 'data', 'output_root': 'data/prepared',
            'logs_dir': 'logs/preparation', 'nodata': -9999, 'block_size': 512,
            'alignment_tolerance_m': 1e-8, 'timeout_seconds': 300,
            'download_attempts': 4, 'request_pause_seconds': 0.25, 'reuse_cache': True}


def load_config(path):
    path = Path(path).resolve()
    config = {**DEFAULTS, **json.loads(path.read_text(encoding='utf-8-sig'))}
    if config.get('country') not in COUNTRIES:
        raise ValueError(f"Unsupported country: {config.get('country')!r}. Available: {', '.join(COUNTRIES)}")
    for key in ('aoi', 'cache_root', 'output_root', 'logs_dir'):
        config[key] = str((path.parent / config[key]).resolve())
    target = dict(config.get('target', {}))
    if target.get('reference_raster'):
        target['reference_raster'] = str((path.parent / target['reference_raster']).resolve())
    config['target'] = target
    if config['nodata'] != -9999:
        raise ValueError('nodata must be -9999.')
    for key in ('block_size', 'download_attempts'):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f'{key} must be a positive integer.')
    for key in ('alignment_tolerance_m', 'timeout_seconds', 'request_pause_seconds'):
        if not isinstance(config[key], (float, int)) or not math.isfinite(config[key]):
            raise ValueError(f'{key} must be a finite number.')
    if not 0 < config['alignment_tolerance_m'] <= 1e-5:
        raise ValueError('alignment_tolerance_m must be in (0, 1e-5].')
    if config['timeout_seconds'] <= 0 or config['request_pause_seconds'] < 0:
        raise ValueError('Invalid HTTP timeout or request pause.')
    COUNTRIES[config['country']].validate_config(config)
    return config


def execute(config, mode='run'):
    """Plan/prepare one country and return its result. No comparison is performed."""
    if mode not in ('run', 'plan', 'probe', 'yes'):
        raise ValueError(f'Unknown execution mode: {mode}')
    country = COUNTRIES[config['country']]
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    log_dir = Path(config['logs_dir']) / config['country'] / run_id
    log_dir.mkdir(parents=True)
    # Use a scoped handler: library callers retain their logging configuration.
    logger = logging.getLogger('dtm')
    old_level = logger.level
    handler = logging.FileHandler(log_dir / 'processing.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        write_json(log_dir / 'config.json', config)
        logger.info('Invocation %s; Python=%s GDAL=%s NumPy=%s requests=%s',
                    sys.argv, platform.python_version(), gdal.VersionInfo('--version'), np.__version__, requests.__version__)
        geometry, crs, layer = read_aoi(config['aoi'], config['layer'])
        target = plan_grid(geometry, config['target'])
        source = country.plan(geometry, config)
        plan = {'country': config['country'], 'aoi': config['aoi'], 'aoi_sha256': sha256(config['aoi']),
                'layer': layer, 'aoi_crs': crs.ExportToWkt(), 'aoi_extent': bounds(geometry),
                'source': source, 'target_grid': target, 'metadata_requests': 2,
                'vertical_datum_note': country.VERTICAL_NOTE}
        write_json(log_dir / 'plan.json', plan)
        write_json(log_dir.parent / 'latest_plan.json', plan)
        print(f"Country: {config['country']}; AOI layer: {layer}")
        print(f"Source: {source['chunks']} tiles; {source['uncompressed_bytes'] / 1e9:.2f} GB uncompressed before cache reuse")
        print(f"Target: EPSG:25832, 1 m, {target['cols']} x {target['rows']} cells; mode={target['mode']}")
        print(country.VERTICAL_NOTE)
        fill = config.get('hole_filling', {})
        print(f"Hole filling: {'on' if fill.get('enabled') else 'off'}; cache reuse: {config.get('reuse_cache', True)}")
        if fill.get('enabled'):
            print(f"Fill search: {fill['max_distance_m']} m; acquisition context: {source.get('context_buffer_m', 0)} m; water gaps included")
        print(f'Plan: {log_dir / "plan.json"}')
        if mode == 'plan':
            return plan
        if mode == 'probe':
            path = country.probe(config, source, log_dir)
            print(f'AHN probe: {path}')
            return {'probe': str(path)}
        if mode != 'yes':
            if not sys.stdin.isatty():
                print('Plan only: use --yes for unattended acquisition and preparation.')
                return plan
            if input('Download and prepare the planned terrain? Type DOWNLOAD: ').strip() != 'DOWNLOAD':
                return plan
        for executable in ('gdalbuildvrt', 'gdal_translate', 'gdalwarp'):
            command([executable, '--version'])
        tiles = country.download(config, source, log_dir)
        write_json(log_dir / 'source_manifest.json', {
            'country': config['country'], 'tiles': [
                {'path': str(p), 'receipt': json.loads(p.with_suffix('.json').read_text(encoding='utf-8'))} for p in tiles]})
        run_dir = Path(config['output_root']) / config['country'] / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        reference = write_reference(target, run_dir / 'target_grid.vrt')
        write_json(run_dir / 'target_grid.json', target)
        result = country.prepare(tiles, geometry, reference, run_dir, config)
        result.update(status='complete', stage='prepared', country=config['country'], run_id=run_id,
                      log_directory=str(log_dir), target_reference=str(reference), plan_file=str(log_dir / 'plan.json'))
        write_json(run_dir / 'result.json', result)
        write_json(log_dir / 'result.json', result)
        write_json(run_dir.parent / 'latest_run.json', result)
        print(f"Prepared: {result.get('comparison_ready_raster', result['prepared_raster'])}")
        if result.get('hole_filling_enabled'):
            report = result['hole_filling']
            print(f"Native gaps: {report['filled_cell_count']} cells filled; {report['remaining_nodata_cell_count']} still NoData. Report: {report['report_path']}")
        return result
    except Exception:
        logger.exception('Country preparation stopped. Completed raw tiles are preserved.')
        raise
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(old_level)


def main():
    parser = argparse.ArgumentParser(description='Prepare country terrain on a shared German grid for later comparison.')
    parser.add_argument('config', nargs='?', default='config.netherlands.json', type=Path)
    modes = parser.add_mutually_exclusive_group()
    for flag, help_text in [('plan', 'Offline plan only.'), ('probe', 'Download one tiny AHN test tile.'),
                            ('yes', 'Run acquisition and preparation without prompting.'),
                            ('self-test', 'Run offline country-preparation tests.')]:
        modes.add_argument('--' + flag, action='store_true', help=help_text)
    filling = parser.add_mutually_exclusive_group()
    filling.add_argument('--fill-holes', dest='fill_holes', action='store_true', default=None, help='Enable native AHN gap interpolation.')
    filling.add_argument('--no-fill-holes', dest='fill_holes', action='store_false', help='Prepare AHN without hole interpolation.')
    caching = parser.add_mutually_exclusive_group()
    caching.add_argument('--fresh-download', dest='reuse_cache', action='store_false', default=None, help='Download into this run instead of reusing or replacing the existing cache.')
    caching.add_argument('--reuse-cache', dest='reuse_cache', action='store_true', help='Reuse validated source tiles.')
    args = parser.parse_args()
    if args.self_test:
        import unittest
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parents[1] / 'tests'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    mode = 'plan' if args.plan else 'probe' if args.probe else 'yes' if args.yes else 'run'
    config = load_config(args.config)
    if args.fill_holes is not None:
        config['hole_filling']['enabled'] = args.fill_holes
    if args.reuse_cache is not None:
        config['reuse_cache'] = args.reuse_cache
    execute(config, mode)
