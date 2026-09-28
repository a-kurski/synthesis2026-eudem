"""Download only AHN; keep the original cache keys, receipts and validation."""
from pathlib import Path
import logging

import requests

from ...acquire import cached, metadata, download_tile

LOG = logging.getLogger('dtm')


def raw_directory(config, log_dir):
    return Path(config['output_root']) / config['country'] / log_dir.name / 'raw_ahn_tiles'


def cache_directories(config):
    """Read new run caches and older layouts without moving or overwriting them."""
    runs = Path(config['output_root']) / config['country']
    configured = Path(config['cache_root'])
    directories = [*sorted(runs.glob('*/raw_ahn_tiles'), reverse=True),
                   configured / 'raw_ahn_tiles', configured / 'ahn_tiles', configured]
    # The previous preparation layout used <run>/raw/ahn_tiles for fresh data.
    directories.extend(sorted(runs.glob('*/raw/ahn_tiles'), reverse=True))
    return list(dict.fromkeys(path.resolve() for path in directories if path.is_dir()))


def download(config, source_plan, log_dir):
    directory = raw_directory(config, log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    candidates = cache_directories(config) if config.get('reuse_cache', True) else []
    paths = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        metadata(session, config['source'], log_dir, 'ahn', config)
        for index, tile in enumerate(source_plan['tiles'], 1):
            LOG.info('AHN tile %d/%d', index, len(source_plan['tiles']))
            for cache in candidates:
                path = cache / f"{tile['id']}.tif"
                if cached(path, config['source'], tile):
                    LOG.info('Reusing validated source tile %s', path)
                    paths.append(path)
                    break
            else:
                paths.append(download_tile(session, config['source'], tile, directory, config))
    return paths


def probe(config, source_plan, log_dir):
    directory = raw_directory(config, log_dir) / 'probe'
    directory.mkdir(parents=True)
    x0, y0, x1, y1 = source_plan['aoi_extent']
    x, y = round((x0 + x1) / 2), round((y0 + y1) / 2)
    tile = {'id': 'ahn_probe', 'bounds': [x, y, x + 16, y + 16]}
    with requests.Session() as session:
        return download_tile(session, config['source'], tile, directory, config)
