"""Resolve AOI lattice cells to published RLP TIFF URLs and reuse shared downloads."""
import logging
from pathlib import Path
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

from ....acquire import download_tile, write_json
from ....downloads import download_tiles
from ....paths import raw_directory

NS = {'m': 'urn:ietf:params:xml:ns:metalink'}
TILE_NAME = re.compile(r'dgm1_32_(\d{3})_(\d{4})_1_rp_(\d{4})\.tif')


def select_tiles(content, source_plan):
    root = ET.fromstring(content)
    if root.tag != '{' + NS['m'] + '}metalink':
        raise ValueError('Expected an IETF Metalink catalogue.')
    wanted = {tuple(tile['bounds']): tile for tile in source_plan['tiles']}
    selected = {}
    for entry in root.findall('m:file', NS):
        name = entry.get('name', '')
        # The TIFF catalogue also includes optional world files / sidecars.
        if not name.lower().endswith(('.tif', '.tiff')):
            continue
        match = TILE_NAME.fullmatch(name)
        if not match:
            raise ValueError(f'Unexpected RLP DGM1 catalogue filename: {name!r}')
        x, y, year = map(int, match.groups())
        box = (x * 1000, y * 1000, (x + 1) * 1000, (y + 1) * 1000)
        if box not in wanted:
            continue
        url = entry.findtext('m:url', default='', namespaces=NS).strip()
        digest = entry.findtext("m:hash[@type='sha-256']", default='', namespaces=NS).strip().lower()
        size = int(entry.findtext('m:size', default='0', namespaces=NS))
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or not parsed.netloc or Path(parsed.path).name != name
                or size <= 0 or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise ValueError(f'Invalid URL, size or SHA-256 for {name}')
        tile = {'id': name[:-4], 'bounds': list(box), 'url': url,
                'size': size, 'sha256': digest, 'year': year}
        previous = selected.get(box)
        if previous and previous['year'] == year and previous != tile:
            raise ValueError(f'Conflicting catalogue entries for {name}')
        if previous is None or year > previous['year']:
            selected[box] = tile
    if not selected:
        raise ValueError('AOI does not intersect any published RLP DGM1 tiles.')
    return [selected[box] for box in wanted if box in selected]


def catalogue(config, source_plan, log_dir):
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        with session.get(config['source']['metalink_url'], timeout=(30, config['timeout_seconds'])) as response:
            response.raise_for_status()
            content = response.content
    tiles = select_tiles(content, source_plan)
    (log_dir / 'rlp_dgm1.meta4').write_bytes(content)
    available = {tuple(tile['bounds']) for tile in tiles}
    write_json(log_dir / 'rlp_selected_tiles.json', {
        'metalink_url': config['source']['metalink_url'], 'tiles': tiles,
        'candidate_count': source_plan['chunks'], 'selected_count': len(tiles),
        'unavailable_bounds': [tile['bounds'] for tile in source_plan['tiles']
                               if tuple(tile['bounds']) not in available]})
    logging.getLogger('dtm').info('RLP catalogue: %d available tiles from %d candidate cells',
                                 len(tiles), source_plan['chunks'])
    return tiles


def download(config, source_plan, log_dir):
    tiles = catalogue(config, source_plan, log_dir)
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    candidates = [directory] if config.get('reuse_cache', True) else []
    return download_tiles(config, tiles, directory, candidates, 'RLP acquisition', download_tile)


def probe(config, source_plan, log_dir):
    tile = catalogue(config, source_plan, log_dir)[0]
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        return download_tile(session, config['source'], tile, directory, config)
