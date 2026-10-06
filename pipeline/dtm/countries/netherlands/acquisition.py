"""Download only AHN; keep the original cache keys, receipts and validation."""
from ...paths import raw_directory as regional_raw_directory

import requests

from ...downloads import download_tiles
from ...acquire import metadata, download_tile


def raw_directory(config, log_dir=None):
    return regional_raw_directory(config)


def cache_directories(config):
    return [regional_raw_directory(config)]


def download(config, source_plan, log_dir):
    directory = raw_directory(config, log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    candidates = cache_directories(config) if config.get('reuse_cache', True) else []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        metadata(session, config['source'], log_dir, 'ahn', config)
    return download_tiles(config, source_plan['tiles'], directory, candidates,
                          'AHN acquisition', download_tile)


def probe(config, source_plan, log_dir):
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = source_plan['aoi_extent']
    x, y = round((x0 + x1) / 2), round((y0 + y1) / 2)
    tile = {'id': 'ahn_probe', 'bounds': [x, y, x + 16, y + 16]}
    with requests.Session() as session:
        return download_tile(session, config['source'], tile, directory, config)
