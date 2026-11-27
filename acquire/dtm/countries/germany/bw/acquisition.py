"""Official LGL inventory, durable ZIP cache and AOI-only XYZ conversion."""
import csv
from concurrent.futures import CancelledError, FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import closing
import io
import json
import logging
import math
from pathlib import PurePosixPath
import re
import shutil
import stat
import threading
import time
import zipfile

from osgeo import gdal, ogr
import requests

from ....acquire import sha256, write_json
from ....downloads import RequestGate, worker_count
from ....geo import bounds, rectangle
from ....paths import raw_directory, receipt_path, scoped_root
from ....progress import track
from .processing import convert_xyz

LOG = logging.getLogger('dtm')
PORTAL = 'https://opengeodata.lgl-bw.de'
LAYERS_URL = PORTAL + '/assets/config/local/core-layerconfig.json'
GRID_URL = PORTAL + '/tiles/vts/2x2Gitter/{z}/{x}/{y}.pbf'
ARCHIVE = re.compile(r'dgm1_32_(\d{3})_(\d{4})_2_bw\.zip')
CHILD = re.compile(r'dgm1_32_(\d{3})_(\d{4})_1_bw_\d{4}\.xyz')
# Increment when conversion semantics change, invalidating derived TIFFs only.
CONVERSION_VERSION = 1


def archive_url(name):
    return f'{PORTAL}/data/dgm/{name}?customerGroup=hochschulen-wissenschaft'


def filename_bounds(name, pattern=ARCHIVE, size=2000):
    match = pattern.fullmatch(name)
    if not match:
        raise ValueError(f'Unexpected LGL filename: {name}')
    x, y = (int(v) * 1000 for v in match.groups())
    return [x, y, x + size, y + size]


def fetch(session, url, path, config, validate, *, request_gate=None, stop_event=None):
    """Paced streaming with validated atomic replacement on success."""
    part = path.with_name(path.name + '.part')
    for attempt in range(config['download_attempts']):
        retry_after = 0
        try:
            if request_gate is None:
                time.sleep(config['request_pause_seconds'])
            else:
                request_gate.wait(stop_event)
            with session.get(url, stream=True, timeout=(30, config['timeout_seconds'])) as response:
                if response.headers.get('Retry-After', '').isdigit():
                    retry_after = int(response.headers['Retry-After'])
                response.raise_for_status()
                with part.open('wb') as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        if stop_event is not None and stop_event.is_set():
                            raise CancelledError('BW acquisition stopped.')
                        stream.write(chunk)
                record = validate(part)
                record.update(url=url, downloaded_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                              headers={k: v for k, v in response.headers.items()
                                       if k.lower() in ('etag', 'last-modified', 'content-type')})
            part.replace(path)
            return record
        except (requests.RequestException, OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
            status = exc.response.status_code if isinstance(exc, requests.HTTPError) and exc.response is not None else None
            # These URLs come from an authoritative inventory, not guessed cells.
            # A listed 404 is an inconsistency, never proof of absent terrain.
            if status in (400, 401, 403, 404) or retry_after > 60 or attempt + 1 == config['download_attempts']:
                raise RuntimeError(f'LGL request failed ({status or type(exc).__name__}): {url}: {exc}') from exc
            LOG.warning('Retrying LGL request after %s: %s', exc, url)
            time.sleep(max(retry_after, min(2 ** attempt, 30)))
        finally:
            part.unlink(missing_ok=True)


def index_tiles(extent, zoom=7):
    """Cover the official portal layer extent in Web Mercator tile coordinates."""
    half = 20037508.342789244
    step = 2 * half / 2 ** zoom
    x0, y0, x1, y1 = extent
    return [(zoom, x, y)
            for x in range(math.floor((x0 + half) / step), math.ceil((x1 + half) / step))
            for y in range(math.floor((half - y1) / step), math.ceil((half - y0) / step))]


def read_index_tile(path):
    records = {}
    with gdal.OpenEx('MVT:' + str(path), gdal.OF_VECTOR) as ds:
        if ds is None or ds.GetLayerCount() != 1:
            raise ValueError(f'Unexpected LGL coverage grid: {path}')
        for feature in ds.GetLayer(0):
            metadata = json.loads(feature.GetField('metadata'))
            e, n = metadata['name'].split('-')
            name = f'dgm1_32_{e}_{n}_2_bw.zip'
            extent = filename_bounds(name)
            products = [t for p in metadata['products'] if p['name'] == 'DGM'
                        for t in p['types'] if t['type'] == 'DGM1']
            if len(products) > 1:
                raise ValueError(f'Duplicate DGM1 entries in LGL index: {name}')
            if products and (products[0]['fileName'] != name
                             or products[0]['downloadURL'] != '/data/dgm/' + name):
                raise ValueError(f'LGL index URL/name mismatch: {name}')
            records[name] = {'name': name, 'bounds': extent, 'available': bool(products)}
    return records


def validate_inventory(record):
    tiles = record['tiles']
    if record['source'] != LAYERS_URL or not tiles or not any(t['available'] for t in tiles):
        raise ValueError('Missing or unexpected LGL DGM1 inventory.')
    if len({t['name'] for t in tiles}) != len(tiles):
        raise ValueError('Duplicate LGL inventory archives.')
    origins = set()
    for tile in tiles:
        if tile['bounds'] != filename_bounds(tile['name']) or type(tile['available']) is not bool:
            raise ValueError('LGL inventory filename/extent mismatch.')
        origins.add((tile['bounds'][0] % 2000, tile['bounds'][1] % 2000))
    if len(origins) != 1:
        raise ValueError(f'LGL inventory does not use a consistent 2 km origin: {origins}')
    expected_urls = [GRID_URL.format(z=z, x=x, y=y) for z, x, y in index_tiles(record['portal_extent'])]
    if record['index_urls'] != expected_urls:
        raise ValueError('Incomplete LGL index tile inventory.')
    return record


def inventory(config, session):
    directory = scoped_root(config, 'logs_dir')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'bw_inventory.json'
    if config.get('reuse_cache', True) and path.exists():
        return validate_inventory(json.loads(path.read_text(encoding='utf-8')))
    work = directory / 'download_work'
    work.mkdir(exist_ok=True)
    layers = work / 'bw_layers.json'
    fetch(session, LAYERS_URL, layers, config,
          lambda p: {'layers': json.loads(p.read_text(encoding='utf-8'))})
    layer = next(l for l in json.loads(layers.read_text(encoding='utf-8'))['body']['layers']
                 if l.get('lid') == 'zwei_km_gitter')
    if layer['sourceOptions']['url'] != GRID_URL:
        raise ValueError('LGL coverage service changed; review the portal inventory endpoint.')
    records, urls = {}, []
    for z, x, y in index_tiles(layer['extent']):
        url = GRID_URL.format(z=z, x=x, y=y)
        pbf = work / f'bw_{z}_{x}_{y}.pbf'
        result = fetch(session, url, pbf, config, lambda p: {'tiles': read_index_tile(p)})
        for name, tile in result['tiles'].items():
            if name in records and tile != records[name]:
                raise ValueError(f'Conflicting neighbouring LGL index entries: {name}')
            records[name] = tile
        urls.append(url)
    record = validate_inventory({'source': LAYERS_URL, 'portal_extent': layer['extent'],
                                 'index_urls': urls, 'discovered_utc': result['downloaded_utc'],
                                 'tiles': sorted(records.values(), key=lambda t: t['name'])})
    write_json(path, record)
    return record


def zip_members(package, tile):
    """Validate paths and child extents before any archive contents reach disk."""
    names, children, cells = set(), [], set()
    for member in package.infolist():
        name = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        if (name.is_absolute() or '..' in name.parts or '\\' in member.filename
                or ':' in member.filename or stat.S_ISLNK(mode)):
            raise ValueError(f'Unsafe LGL ZIP member: {member.filename}')
        if member.is_dir():
            continue
        if name.name.casefold() in names:
            raise ValueError(f'Duplicate LGL ZIP basename: {name.name}')
        names.add(name.name.casefold())
        if name.suffix.lower() == '.xyz':
            extent = filename_bounds(name.name, CHILD, 1000)
            x0, y0, x1, y1 = tile['bounds']
            if not (x0 <= extent[0] < extent[2] <= x1 and y0 <= extent[1] < extent[3] <= y1):
                raise ValueError(f'Child extent outside archive: {name.name}')
            if tuple(extent) in cells:
                raise ValueError(f'Duplicate XYZ coverage/editions: {name.name}')
            cells.add(tuple(extent))
            children.append({'member': member.filename, 'name': name.name, 'bounds': extent})
    for child in children:
        csv_name = str(PurePosixPath(child['member']).with_suffix('.csv'))
        if csv_name not in package.namelist():
            raise ValueError(f'Missing matching CSV metadata: {child["name"]}')
    if not any(n.endswith('.csv') for n in names) or not any(n.endswith('.pdf') for n in names) or not any(n.endswith('.txt') for n in names):
        raise ValueError(f'Unexpected LGL archive contents (XYZ/CSV, licence PDF and metadata TXT required): {tile["name"]}')
    if not children:
        LOG.warning('LGL archive %s contains metadata but no XYZ elevations; continuing without coverage from this archive.', tile['name'])
    return sorted(children, key=lambda c: c['name'])


def validate_zip(path, tile):
    with zipfile.ZipFile(path) as package:
        children = zip_members(package, tile)
        bad = package.testzip()
        if bad is not None:
            raise ValueError(f'ZIP CRC failed: {bad}')
    return {'sha256': sha256(path), 'bytes': path.stat().st_size, 'children': children,
            'has_elevation_data': bool(children)}


def cached_archive(session, tile, config, *, request_gate=None, stop_event=None):
    directory = scoped_root(config, 'cache_root') / 'source_archive'
    receipts = scoped_root(config, 'logs_dir') / 'archive_receipts'
    directory.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)
    path, receipt = directory / tile['name'], receipts / (tile['name'] + '.json')
    url = archive_url(tile['name'])
    if config.get('reuse_cache', True) and path.exists():
        try:
            if receipt.exists():
                saved = json.loads(receipt.read_text(encoding='utf-8'))
                if (saved['bytes'] != path.stat().st_size or saved['sha256'] != sha256(path)
                        or saved['url'] != url):
                    raise ValueError('ZIP differs from cached source receipt')
                # Identical bytes already passed CRC validation. Reading the ZIP
                # directory rechecks structure without decompressing every XYZ.
                with zipfile.ZipFile(path) as package:
                    zip_members(package, tile)
            else:
                record = validate_zip(path, tile)
                write_json(receipt, {**record, 'url': url, 'validation': 'local ZIP CRC and structure'})
            return path, True
        except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
            LOG.warning('Invalid cached LGL archive %s; fetching replacement: %s', path, exc)
    record = fetch(session, url, path, config, lambda p: validate_zip(p, tile),
                   request_gate=request_gate, stop_event=stop_event)
    write_json(receipt, record)
    return path, False


def archive_jobs(config, tiles, operation):
    """Bound archive work to the configured workers and share HTTP pacing."""
    workers = worker_count(config)
    gate, stopped = RequestGate(config['request_pause_seconds']), threading.Event()

    def run(tile):
        if stopped.is_set():
            raise CancelledError('BW acquisition stopped.')
        started = time.perf_counter()
        with requests.Session() as session:
            path, reused = cached_archive(session, tile, config, request_gate=gate, stop_event=stopped)
        acquired = time.perf_counter()
        if stopped.is_set():
            raise CancelledError('BW acquisition stopped.')
        result = operation(tile, path, reused)
        LOG.info('BW %s: %s %.2fs; local preparation %.2fs', tile['name'],
                 'cache validation' if reused else 'download and validation',
                 acquired - started, time.perf_counter() - acquired)
        return result

    jobs = iter(tiles)
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='bw-acquisition')
    pending = {}

    def submit_next():
        tile = next(jobs, None)
        if tile is not None:
            pending[pool.submit(run, tile)] = tile

    try:
        for _ in range(workers):
            submit_next()
        while pending:
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                tile = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    raise RuntimeError(f'BW archive {tile["name"]}: {exc}') from exc
                yield result
                submit_next()
    finally:
        stopped.set()
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)


def intersects(tile, geometry):
    x0, y0, x1, y1 = bounds(geometry)
    a, b, c, d = tile['bounds']
    return a < x1 and c > x0 and b < y1 and d > y0 and geometry.Intersection(rectangle(tile['bounds'])).GetArea() > 0


def prefetch(config, log_dir):
    """Cache every advertised statewide archive, resumably, without raster work."""
    summary = {'scope': 'entire LGL statewide inventory', 'complete': False,
               'reused': 0, 'downloaded': 0, 'failed_requests': []}
    try:
        with requests.Session() as session:
            index = inventory(config, session)
            available = [t for t in index['tiles'] if t['available']]
            summary.update(expected_archives=len(available),
                           unavailable_candidates=[t['name'] for t in index['tiles'] if not t['available']],
                           inventory_discovered_utc=index['discovered_utc'])
            with closing(archive_jobs(config, available, lambda tile, path, reused: reused)) as jobs:
                try:
                    for reused in track(jobs, 'BW statewide ZIP cache', total=len(available)):
                        summary['reused' if reused else 'downloaded'] += 1
                except Exception as exc:
                    summary['failed_requests'].append({'error': str(exc)})
                    raise
            summary['complete'] = summary['reused'] + summary['downloaded'] == len(available)
            summary['completeness_basis'] = 'Every archive matches its validated receipt or passed full ZIP CRC and structure checks.'
            return summary
    finally:
        write_json(log_dir / 'bw_prefetch.json', summary)
        write_json(scoped_root(config, 'logs_dir') / 'bw_cache_summary.json', summary)


def cached_conversion(path, identity, config):
    if not config.get('reuse_cache', True):
        return False
    try:
        record = json.loads(receipt_path(path, config).read_text(encoding='utf-8'))
        return (all(record.get(key) == value for key, value in identity.items())
                and record['bytes'] == path.stat().st_size and record['sha256'] == sha256(path))
    except (OSError, ValueError, KeyError):
        return False


def extract_tiles(tile, path, geometry, work, config, probe_only=False):
    paths = []
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    receipt = scoped_root(config, 'logs_dir') / 'archive_receipts' / (path.name + '.json')
    archive_digest = json.loads(receipt.read_text(encoding='utf-8'))['sha256']
    with zipfile.ZipFile(path) as package:
        children = zip_members(package, tile)
        if not children:
            return []
        covered = {tuple(c['bounds'][:2]) for c in children}
        x0, y0, _, _ = tile['bounds']
        for x in (x0, x0 + 1000):
            for y in (y0, y0 + 1000):
                if (x, y) not in covered and intersects({'bounds': [x, y, x + 1000, y + 1000]}, geometry):
                    LOG.warning('Missing child coverage in %s at %s,%s; retain NoData.', path.name, x, y)
        support = [n for n in package.namelist() if n.lower().endswith(('.pdf', '.txt'))]
        for child in children:
            if not intersects(child, geometry):
                continue
            source = work / child['name']
            destination = directory / source.with_suffix('.tif').name
            identity = {'source': config['source'], 'archive_sha256': archive_digest,
                        'member': child['member'], 'conversion_version': CONVERSION_VERSION,
                        'bounds': child['bounds'], 'output_nodata': config['nodata']}
            if cached_conversion(destination, identity, config):
                LOG.info('Reusing converted BW tile %s', destination.name)
                paths.append(destination)
                if probe_only:
                    break
                continue
            with package.open(child['member']) as src, source.open('wb') as dst:
                shutil.copyfileobj(src, dst)
            csv_member = str(PurePosixPath(child['member']).with_suffix('.csv'))
            content = package.read(csv_member)
            source.with_suffix('.csv').write_bytes(content)
            rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig')), delimiter=';'))
            if len(rows) != 1:
                raise ValueError(f'Expected one metadata row: {csv_member}')
            info = convert_xyz(source, destination, child['bounds'], rows[0], config)
            converted_receipt = receipt_path(destination, config)
            converted_receipt.parent.mkdir(parents=True, exist_ok=True)
            write_json(converted_receipt, {
                **identity, 'url': archive_url(tile['name']), 'archive': str(path),
                'csv_member': csv_member, 'csv': rows[0], 'support_members': support,
                'sha256': sha256(destination), 'bytes': destination.stat().st_size, **info})
            source.unlink()  # Original XYZ, CSV and licence remain in the cached ZIP.
            paths.append(destination)
            if probe_only:
                break
    return paths


def acquire(config, source_plan, log_dir, probe_only=False):
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    # Extraction scratch is per invocation; converted TIFFs persist in raw_tiles.
    work = log_dir / 'source_tiles'
    work.mkdir(parents=True, exist_ok=True)
    paths, selected, unavailable = [], [], []
    with requests.Session() as session:
        index = inventory(config, session)
        for tile in index['tiles']:
            if not intersects(tile, geometry):
                continue
            if tile['available']:
                selected.append(tile)
            else:
                unavailable.append(tile['name'])
        write_json(log_dir / 'bw_selection.json', {'archives': selected, 'unavailable': unavailable,
                                                  'inventory_discovered_utc': index['discovered_utc']})
        if unavailable:
            LOG.warning('LGL inventory has no DGM1 for these AOI units; gaps remain NoData: %s', unavailable)
        local = threading.local()

        def process(tile, path, reused):
            # Each worker owns its OGR geometry and GDAL datasets.
            if not hasattr(local, 'geometry'):
                local.geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
            return extract_tiles(tile, path, local.geometry, work, config, probe_only)

        settings = {**config, 'download_workers': 1} if probe_only else config
        LOG.info('BW acquisition: %d archives, %d workers; progress includes XYZ conversion.',
                 len(selected), worker_count(settings))
        with closing(archive_jobs(settings, selected, process)) as jobs:
            for converted in track(jobs, 'BW archives + XYZ conversion', total=len(selected)):
                paths.extend(converted)
                if probe_only and paths:
                    return paths
    if not paths:
        raise ValueError('No available Baden-Württemberg XYZ coverage intersects the processing AOI.')
    return sorted(paths)


def download(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir, probe_only=True)[0]
