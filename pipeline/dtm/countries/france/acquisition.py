"""Cache native ASC tiles by department; recover missing coverage from IGN archives."""
import hashlib
from concurrent.futures import CancelledError, ThreadPoolExecutor
import json
import logging
from pathlib import Path, PurePosixPath
import re
import time
import threading
import xml.etree.ElementTree as ET

import requests
from osgeo import gdal, ogr

from ...acquire import sha256, write_json
from ...downloads import RequestGate, worker_count
from ...geo import project, rectangle, srs
from ...paths import raw_directory, receipt_path, scoped_root
from ...progress import bar, track
from .processing import missing_coverage, validate_native

LOG = logging.getLogger('dtm')
CATALOGUE = 'https://data.geopf.fr/telechargement/resource/RGEALTI'
BOUNDARIES = 'https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/geojson/departements-100m.geojson'
ATOM = '{http://www.w3.org/2005/Atom}'
GPF = '{https://data.geopf.fr/annexes/ressources/xsd/gpf_dl.xsd}'
TILE_NAME = re.compile(r'RGEALTI_FXX_(\d{4})_(\d{4})_MNT_LAMB93_IGN69\.asc', re.IGNORECASE)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, value)


def filename_bounds(name):
    match = TILE_NAME.fullmatch(name)
    if not match:
        raise ValueError(f'Not a mainland RGE ALTI MNT tile: {name}')
    x, y = (int(v) * 1000 for v in match.groups())
    # IGN filenames identify the north-west NODE, not the outer pixel corner.
    return [x - 2.5, y - 4997.5, x + 4997.5, y + 2.5]


def intersects(geometry, extent):
    return geometry.Intersection(rectangle(extent)).GetArea() > 0


def get_bytes(session, url, config, **kwargs):
    for attempt in range(1, config['download_attempts'] + 1):
        try:
            time.sleep(config['request_pause_seconds'])
            with session.get(url, timeout=(30, config['timeout_seconds']), **kwargs) as response:
                response.raise_for_status()
                return response.content
        except requests.RequestException:
            if attempt == config['download_attempts']:
                raise
            time.sleep(min(2 ** attempt, 30))


def department_codes(session, geometry, config):
    """Boundaries only limit archive discovery; they never clip the requested AOI."""
    path = scoped_root(config, 'logs_dir') / 'departments_2025.json'
    data = read_json(path)
    if data is None:
        data = json.loads(get_bytes(session, BOUNDARIES, config))
        if data.get('type') != 'FeatureCollection' or not data.get('features'):
            raise ValueError('Invalid department boundary collection.')
        save_json(path, data)
    codes = []
    for feature in data['features']:
        code = feature['properties']['code']
        if code not in config['source']['departments']:
            continue
        boundary = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
        boundary.AssignSpatialReference(srs(4326))
        # Account for simplification and tiles that extend across department borders.
        boundary = project(boundary, srs(2154)).Buffer(7100)
        if geometry.Intersection(boundary).GetArea() > 0:
            codes.append(code)
    return sorted(codes)


def discover_archive(session, department, config):
    path = scoped_root(config, 'logs_dir') / 'catalogue' / f'{department}.json'
    cached = read_json(path) if config.get('reuse_cache', True) else None
    if cached:
        return cached
    entries = []
    page = 1
    while True:
        root = ET.fromstring(get_bytes(session, CATALOGUE, config,
                                     params={'zone': f'D0{department}', 'page': page}))
        entries.extend(root.findall(ATOM + 'entry'))
        if page >= int(root.get(GPF + 'pagecount', '1')):
            break
        page += 1
    pattern = re.compile(rf'RGEALTI_2-0_5M_ASC_LAMB93-IGN69_D0{department}_(\d{{4}}-\d{{2}}-\d{{2}})')
    editions = [(e.findtext(ATOM + 'title', ''), e) for e in entries
                if pattern.fullmatch(e.findtext(ATOM + 'title', ''))]
    if not editions:
        raise ValueError(f'IGN catalogue has no RGE ALTI 5 m IGN69 archive for department {department}.')
    title, entry = max(editions, key=lambda pair: pair[0])
    url = entry.findtext(ATOM + 'id')
    root = ET.fromstring(get_bytes(session, url, config))
    files = root.findall(ATOM + 'entry')
    if len(files) != 1:
        raise ValueError(f'Expected one 5 m department archive, found {len(files)}: {url}')
    link = files[0].find(ATOM + 'link')
    download_url = link.get('href') if link is not None else ''
    digest = files[0].findtext(ATOM + 'content', '').strip()
    if (not download_url.startswith('https://data.geopf.fr/telechargement/download/')
            or not download_url.endswith('.7z') or not re.fullmatch('[0-9a-fA-F]{32}', digest)):
        raise ValueError(f'Invalid IGN archive URL/checksum: {url}')
    record = {'department': department, 'edition': title, 'url': download_url,
              'size': int(link.get(GPF + 'length')), 'md5': digest.lower()}
    save_json(path, record)
    return record


def valid_archive(path, record):
    if not path.is_file() or path.stat().st_size != record['size']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'md5').hexdigest() == record['md5']


def acquire_archive(session, record, config, *, request_gate=None, stop_event=None):
    path = scoped_root(config, 'cache_root') / 'source_archive' / record['department'] / (record['edition'] + '.7z')
    path.parent.mkdir(parents=True, exist_ok=True)
    if config.get('reuse_cache', True) and valid_archive(path, record):
        return path
    part = path.with_suffix('.7z.part')
    for attempt in range(1, config['download_attempts'] + 1):
        try:
            if request_gate is not None:
                request_gate.wait(stop_event)
            else:
                time.sleep(config['request_pause_seconds'])
            with session.get(record['url'], stream=True, timeout=(30, config['timeout_seconds'])) as response:
                response.raise_for_status()
                with part.open('wb') as output, bar('France ' + record['department'], record['size'], 'bytes') as progress:
                    for chunk in response.iter_content(1024 * 1024):
                        if stop_event is not None and stop_event.is_set():
                            raise CancelledError('France archive acquisition stopped.')
                        output.write(chunk)
                        progress.update(len(chunk))
            if not valid_archive(part, record):
                raise ValueError('IGN archive size/MD5 mismatch.')
            part.replace(path)
            return path
        except (requests.RequestException, OSError, ValueError):
            if attempt == config['download_attempts']:
                raise
            time.sleep(min(2 ** attempt, 30))
        finally:
            part.unlink(missing_ok=True)


def acquire_archives(records, config):
    """Download one bounded batch with private sessions and shared request pacing."""
    if not records:
        return []
    workers = min(worker_count(config), len(records))
    gate = RequestGate(config['request_pause_seconds'])
    stopped = threading.Event()

    def fetch(record):
        try:
            with requests.Session() as session:
                session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
                return acquire_archive(session, record, config, request_gate=gate, stop_event=stopped)
        except BaseException:
            stopped.set()
            raise

    LOG.info('France: acquiring %d department archives with %d workers.', len(records), workers)
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='france-download')
    try:
        # map preserves department order, independent of transfer completion order.
        return list(pool.map(fetch, records))
    except BaseException:
        stopped.set()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def validate_cached(path, config, provenance=None):
    """Adopt supplied tiles, but never silently rebaseline an altered cached tile."""
    receipt = receipt_path(path, config)
    record = read_json(receipt)
    digest = sha256(path)
    if record and record.get('sha256') != digest:
        raise ValueError(f'Cached ASC differs from its receipt: {path}')
    info = validate_native(path, read_values=True)
    if info['extent'] != filename_bounds(path.name):
        raise ValueError(f'RGE ALTI header disagrees with filename footprint: {path}')
    if not record:
        record = {'product': 'IGN RGE ALTI 5 m', 'vertical_datum': 'IGN69',
                  'sha256': digest, 'origin': 'supplied_local_tile', 'grid': info}
    if provenance:
        record.update(provenance)
    save_json(receipt, record)
    return {'path': str(path), 'bounds': info['extent'], 'sha256': digest}


def local_tiles(geometry, config):
    result = []
    for department in config['source']['departments']:
        directory = raw_directory(config) / department
        for path in sorted(directory.glob('*')):
            if path.suffix.lower() != '.asc':
                continue
            if not intersects(geometry, filename_bounds(path.name)):
                continue
            try:
                result.append(validate_cached(path, config))
            except (ValueError, RuntimeError, OSError) as exc:
                LOG.warning('Cannot reuse %s; acquisition will recover missing coverage: %s', path, exc)
    return result


def extract_tiles(archive, record, geometry, config, *, probe_only=False):
    if '/vsi7z/' not in gdal.GetFileSystemsPrefixes():
        raise RuntimeError('France archive acquisition requires GDAL >= 3.7 built with libarchive /vsi7z support.')
    root = '/vsi7z/' + archive.resolve().as_posix()
    names = gdal.ReadDirRecursive(root)
    if not names:
        raise ValueError(f'Cannot list IGN archive: {archive}')
    members, basenames = [], set()
    for name in names:
        member = PurePosixPath(name)
        if member.is_absolute() or '..' in member.parts or '\\' in name or ':' in name:
            raise ValueError(f'Unsafe archive path: {name}')
        if member.suffix.lower() != '.asc' or not TILE_NAME.fullmatch(member.name):
            continue
        if member.name.lower() in basenames:
            raise ValueError(f'Duplicate ASC member: {member.name}')
        basenames.add(member.name.lower())
        if intersects(geometry, filename_bounds(member.name)):
            members.append(name)
    result = []
    if probe_only:
        members = members[:1]
    for name in track(members, 'France ' + record['department'] + ' selected tiles'):
        path = raw_directory(config) / record['department'] / PurePosixPath(name).name
        path.parent.mkdir(parents=True, exist_ok=True)
        if config.get('reuse_cache', True) and path.is_file():
            try:
                result.append(validate_cached(path, config))
                continue
            except (OSError, ValueError, RuntimeError):
                pass
        part = path.with_suffix('.part.asc')
        source = root + '/' + name
        # This also reads an archive PRJ sidecar when present; a conflicting
        # source CRS must not disappear when the ASC is copied out on its own.
        validate_native(source)
        stream = gdal.VSIFOpenL(source, 'rb')
        if stream is None:
            raise ValueError(f'Cannot read IGN member: {name}')
        try:
            with part.open('wb') as output:
                while chunk := gdal.VSIFReadL(1, 1024 * 1024, stream):
                    output.write(chunk)
            if part.stat().st_size != gdal.VSIStatL(source).size:
                raise ValueError(f'Incomplete ASC extraction: {name}')
            info = validate_native(part, read_values=True)
            if info['extent'] != filename_bounds(path.name):
                raise ValueError(f'IGN filename/header mismatch: {name}')
            digest = sha256(part)
            part.replace(path)
            save_json(receipt_path(path, config), {
                'product': 'IGN RGE ALTI 5 m', 'vertical_datum': 'IGN69', 'grid': info,
                'sha256': digest, 'origin': 'verified_ign_archive', 'archive': record, 'member': name})
            result.append({'path': str(path), 'bounds': info['extent'], 'sha256': digest})
        finally:
            gdal.VSIFCloseL(stream)
            part.unlink(missing_ok=True)
    if not basenames:
        raise ValueError(f'No RGE ALTI mainland MNT tiles in {archive}')
    return result


def acquire(config, source_plan, log_dir, *, probe_only=False):
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    geometry.AssignSpatialReference(srs(2154))
    tiles = local_tiles(geometry, config) if config.get('reuse_cache', True) else []
    missing = missing_coverage(geometry, tiles)
    if missing.GetArea() > 1e-4 and not (probe_only and tiles):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
            departments = department_codes(session, missing, config)
            batch_size = 1 if probe_only else worker_count(config)
            for start in range(0, len(departments), batch_size):
                records = [discover_archive(session, department, config)
                           for department in departments[start:start + batch_size]]
                archives = acquire_archives(records, config)
                # Keep GDAL archive reads and raw-tile writes on the main thread.
                for record, archive in zip(records, archives):
                    tiles.extend(extract_tiles(archive, record, geometry, config, probe_only=probe_only))
                missing = missing_coverage(geometry, tiles)
                if missing.GetArea() <= 1e-4 or (probe_only and tiles):
                    break
    # Adjacent department deliveries can repeat boundary tiles. Pick a stable
    # department/name order, record the choice, and never mosaic duplicates.
    unique = {}
    duplicates = []
    for tile in sorted(tiles, key=lambda tile: tile['path']):
        footprint = tuple(tile['bounds'])
        if footprint in unique:
            duplicates.append(tile['path'])
        else:
            unique[footprint] = tile
    selected = list(unique.values())
    manifest = {'tiles': selected, 'ignored_duplicate_tiles': duplicates,
                'missing_source_area_m2': missing.GetArea(), 'probe_only': probe_only}
    save_json(log_dir / 'rge_alti_manifest.json', manifest)
    if missing.GetArea() > 1e-4:
        LOG.warning('France: %.2f square metres of the AOI have no available tiles. '
                    'Continuing with %d tiles; uncovered areas will remain NoData. '
                    'See rge_alti_manifest.json.', missing.GetArea(), len(selected))
    if probe_only:
        selected = selected[:1]
    return [Path(tile['path']) for tile in selected]


def download(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    tiles = acquire(config, source_plan, log_dir, probe_only=True)
    return tiles[0] if tiles else None
