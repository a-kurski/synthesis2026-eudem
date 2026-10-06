"""AOI-filtered STAC editions and checksum-verified, immutable source assets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
from pathlib import Path
import re
import threading
import time
from urllib.parse import urljoin

from osgeo import ogr
import requests

from ...acquire import sha256, write_json
from ...downloads import RequestGate, worker_count
from ...geo import srs
from ...paths import raw_directory, receipt_path
from .processing import validate_native

LOG = logging.getLogger('dtm')
ITEM_ID = re.compile(r'^swissalti3d_(\d{4})_(\d+-\d+)$')


def checksum_digest(checksum):
    if checksum is None:
        return None
    # Explicitly support SHA-256 multihash; fail closed on a new algorithm/schema.
    if not isinstance(checksum, str) or not re.fullmatch(r'1220[0-9a-fA-F]{64}', checksum):
        raise ValueError(f'Unsupported swissALTI3D checksum multihash: {checksum!r}')
    return checksum[4:].lower()


def retry_delay(response, attempt):
    value = response.headers.get('Retry-After') if response is not None else None
    if value:
        try:
            return max(0, float(value))
        except ValueError:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
    return min(2 ** attempt, 30)


def transfer(session, url, config, consume, *, params=None, gate=None, stopped=None):
    """Retry the whole transfer, including interrupted streaming responses."""
    for attempt in range(1, config['download_attempts'] + 1):
        response = None
        try:
            if gate is not None:
                gate.wait(stopped)
            with session.get(url, params=params, stream=True,
                             timeout=(10, config['timeout_seconds'])) as response:
                response.raise_for_status()
                return consume(response)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            status = response.status_code if response is not None else None
            if status is not None and 400 <= status < 500 and status not in (408, 429):
                raise
            if attempt == config['download_attempts']:
                raise
            delay = retry_delay(response, attempt)
            LOG.warning('swissALTI3D request failed (%s); retry in %.1f s: %s', exc, delay, url)
            time.sleep(delay)


def select_items(items, query_geometry):
    area = ogr.CreateGeometryFromJson(json.dumps(query_geometry))
    area.AssignSpatialReference(srs(4326))
    latest = {}
    for item in items:
        match = ITEM_ID.fullmatch(item.get('id', ''))
        if not match:
            raise ValueError(f'Ambiguous swissALTI3D item ID: {item.get("id")}')
        stamp = datetime.fromisoformat(item['properties']['datetime'].replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.year != int(match[1]):
            raise ValueError(f'Edition year/date mismatch: {item["id"]}')
        footprint = ogr.CreateGeometryFromJson(json.dumps(item['geometry']))
        if footprint is None or footprint.IsEmpty() or not footprint.IsValid():
            raise ValueError(f'Invalid STAC footprint: {item["id"]}')
        if not area.Intersection(footprint).GetArea() > 0:
            continue
        key = match[2]
        previous = latest.get(key)
        if previous and stamp == previous[0] and item != previous[1]:
            raise ValueError(f'Conflicting same-edition candidates for {key}')
        if previous is None or stamp > previous[0]:
            latest[key] = (stamp, item)
    tiles = []
    for spatial_id, (stamp, item) in sorted(latest.items()):
        assets = []
        for name, asset in sorted(item['assets'].items()):
            media = {part.strip().lower() for part in asset.get('type', '').split(';')}
            if (asset.get('gsd') == 2 and asset.get('proj:epsg') == 2056
                    and {'image/tiff', 'application=geotiff', 'profile=cloud-optimized'} <= media):
                assets.append((name, asset))
        if not assets:
            raise ValueError(f'Newest edition lacks a 2 m EPSG:2056 COG: {item["id"]}')
        name, asset = assets[0]
        if any(a != asset for _, a in assets[1:]):
            raise ValueError(f'Conflicting 2 m COG assets: {item["id"]}')
        digest = checksum_digest(asset.get('file:checksum'))
        identity = hashlib.sha256((name + '\n' + asset['href']).encode()).hexdigest()[:16]
        tiles.append({'id': item['id'] + '_' + identity, 'item_id': item['id'],
                      'spatial_tile_id': spatial_id, 'edition_date': stamp.isoformat(),
                      'asset_name': name, 'url': asset['href'], 'checksum': asset.get('file:checksum'),
                      'sha256': digest, 'resolution': 2, 'epsg': 2056, 'vertical_epsg': 5728,
                      'attribution': '©swisstopo', 'item': item})
    if not tiles:
        raise ValueError('No swissALTI3D source tiles intersect the study area.')
    return tiles


def discover(session, source_plan, config):
    url = source_plan['items_url']
    params = {'bbox': ','.join(map(str, source_plan['query_bounds_wgs84'])),
              'limit': config['source'].get('page_limit', 100)}
    items, visited = [], set()
    while url:
        if url in visited:
            raise ValueError('STAC pagination repeated a URL.')
        visited.add(url)
        page = transfer(session, url, config, lambda response: response.json(), params=params)
        if page.get('type') != 'FeatureCollection' or not isinstance(page.get('features'), list):
            raise ValueError('Expected a STAC FeatureCollection.')
        items.extend(page['features'])
        links = [link['href'] for link in page.get('links', []) if link.get('rel') == 'next']
        if len(links) > 1:
            raise ValueError('Ambiguous STAC next-page links.')
        url = urljoin(url, links[0]) if links else None
        params = None
    tiles = select_items(items, source_plan['query_geometry'])
    LOG.info('STAC discovery: %d pages, %d items, %d selected spatial tiles', len(visited), len(items), len(tiles))
    return tiles


def manifest(config, source_plan, log_dir):
    query = {key: source_plan[key] for key in ('items_url', 'query_geometry', 'query_bounds_wgs84')}
    if config.get('source_manifest'):
        saved = json.loads(Path(config['source_manifest']).read_text(encoding='utf-8'))
        if saved.get('query') != query:
            raise ValueError('Saved source manifest does not match this study area/catalogue.')
        tiles = select_items([t['item'] for t in saved['tiles']], query['query_geometry'])
        if tiles != saved['tiles']:
            raise ValueError('Saved source manifest contains inconsistent or duplicate assets.')
        record = saved
    else:
        with requests.Session() as session:
            tiles = discover(session, source_plan, config)
        record = {'provider': 'swissALTI3D', 'attribution': '©swisstopo', 'query': query,
                  'discovered_utc': datetime.now(timezone.utc).isoformat(), 'tiles': tiles}
    # Freeze editions before any raster download so failed acquisition can resume.
    write_json(log_dir / 'swissalti3d_manifest.json', record)
    return tiles


def download_one(tile, directory, config, gate, stopped):
    path = directory / (tile['id'] + '.tif')
    receipt = receipt_path(path, config)
    if config.get('reuse_cache', True) and path.exists() and receipt.exists():
        try:
            saved = json.loads(receipt.read_text(encoding='utf-8'))
            digest = sha256(path)
            if saved['asset'] == tile and saved['sha256'] == digest and (not tile['sha256'] or tile['sha256'] == digest):
                validate_native(path, tile['spatial_tile_id'])
                LOG.info('Reusing validated swissALTI3D asset %s', path)
                return path
        except (KeyError, ValueError, RuntimeError, OSError):
            pass
    # Same filesystem as final TIFF, so replacement is atomic even with logs elsewhere.
    part = path.with_suffix('.tif.part')

    def consume(response):
        with part.open('wb') as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
        digest = sha256(part)
        if tile['sha256'] and digest != tile['sha256']:
            raise ValueError(f'SHA-256 checksum mismatch: {tile["item_id"]}')
        info = validate_native(part, tile['spatial_tile_id'])
        return {'asset': tile, 'sha256': digest, 'grid': info, 'local_path': str(path),
                'downloaded_utc': datetime.now(timezone.utc).isoformat(), 'attribution': '©swisstopo'}

    try:
        with requests.Session() as session:
            record = transfer(session, tile['url'], config, consume, gate=gate, stopped=stopped)
        part.replace(path)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        write_json(receipt, record)
        LOG.info('Downloaded and validated swissALTI3D asset %s', path)
        return path
    finally:
        part.unlink(missing_ok=True)


def acquire(config, tiles):
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    gate, stopped = RequestGate(config['request_pause_seconds']), threading.Event()
    with ThreadPoolExecutor(max_workers=min(worker_count(config), len(tiles))) as pool:
        try:
            return list(pool.map(lambda tile: download_one(tile, directory, config, gate, stopped), tiles))
        except BaseException:
            stopped.set()
            raise


def download(config, source_plan, log_dir):
    return acquire(config, manifest(config, source_plan, log_dir))


def probe(config, source_plan, log_dir):
    return acquire(config, manifest(config, source_plan, log_dir)[:1])[0]
