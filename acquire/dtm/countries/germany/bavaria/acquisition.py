"""Official Metalink discovery, verified ZIP cache and persistent DGM5 tiles."""
from concurrent.futures import CancelledError
import json
import logging
import math
from pathlib import PurePosixPath
import re
import shutil
import stat
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

from osgeo import ogr
import requests

from ....acquire import sha256, write_json
from ....downloads import download_tiles
from ....geo import bounds, rectangle
from ....paths import raw_directory, receipt_path, scoped_root
from .processing import CONVERSION_VERSION, convert_xyz, validate_native

LOG = logging.getLogger('dtm')
CATALOGUE_URL = 'https://geodaten.bayern.de/odd/a/dgm/dgm5xyz/meta/metalink/09.meta4'
NS = '{urn:ietf:params:xml:ns:metalink}'
NAME = re.compile(r'(-?\d+)_(-?\d+)\.zip')


def filename_bounds(name):
    match = NAME.fullmatch(name)
    if not match or name != f'{int(match[1])}_{int(match[2])}.zip':
        raise ValueError(f'Unexpected DGM5 archive name: {name}')
    x, y = (int(v) * 1000 for v in match.groups())
    return [x, y, x + 1000, y + 1000]


def parse_catalogue(path):
    content = path.read_text(encoding='utf-8-sig')
    if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():
        raise ValueError('DTD/entities are not permitted in the DGM5 catalogue.')
    root = ET.fromstring(content)
    if root.tag != NS + 'metalink':
        raise ValueError('Expected Metalink 4 namespace.')
    tiles = {}
    for node in root.findall(NS + 'file'):
        name = node.get('name', '')
        extent = filename_bounds(name)
        size = int(node.findtext(NS + 'size', '0'))
        hashes = [n.text.strip().lower() for n in node.findall(NS + 'hash')
                  if n.get('type') == 'sha-256' and n.text]
        urls = [n.text.strip() for n in node.findall(NS + 'url') if n.text]
        if name in tiles or size <= 0 or len(hashes) != 1 or not re.fullmatch(r'[0-9a-f]{64}', hashes[0]) or not urls:
            raise ValueError(f'Incomplete/duplicate Metalink record: {name}')
        for url in urls:
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or not re.fullmatch(r'download\d+\.bayernwolke\.de', parsed.netloc)
                    or parsed.path != '/a/dgm/dgm5xyz/' + name or parsed.query or parsed.fragment):
                raise ValueError(f'Unexpected DGM5 catalogue URL: {url}')
        tiles[name] = {'name': name, 'bounds': extent, 'size': size, 'sha256': hashes[0], 'urls': urls}
    if not tiles:
        raise ValueError('Empty DGM5 catalogue.')
    return {'published': root.findtext(NS + 'published'), 'tiles': tiles}


def fetch(session, urls, path, config, validate, *, request_gate=None, stop_event=None):
    """Try catalogue mirrors in order; only atomically commit validated bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + '.part')
    errors = []
    for attempt in range(config['download_attempts']):
        for url in urls:
            try:
                if request_gate is None:
                    time.sleep(config['request_pause_seconds'])
                else:
                    request_gate.wait(stop_event)
                with session.get(url, stream=True, timeout=(30, config['timeout_seconds'])) as response:
                    response.raise_for_status()
                    with part.open('wb') as stream:
                        for chunk in response.iter_content(1024 * 1024):
                            if stop_event is not None and stop_event.is_set():
                                raise CancelledError('Bavaria acquisition stopped.')
                            stream.write(chunk)
                    length = response.headers.get('Content-Length')
                    if length and not response.headers.get('Content-Encoding') and part.stat().st_size != int(length):
                        raise ValueError('HTTP Content-Length mismatch.')
                    record = validate(part)
                part.replace(path)
                return record, url
            except (requests.RequestException, OSError, ValueError, RuntimeError, ET.ParseError, zipfile.BadZipFile) as exc:
                errors.append(f'{url}: {exc}')
                LOG.warning('DGM5 request failed: %s', errors[-1])
            finally:
                part.unlink(missing_ok=True)
        if attempt + 1 < config['download_attempts']:
            delay = min(2 ** attempt, 30)
            if stop_event is None:
                time.sleep(delay)
            elif stop_event.wait(delay):
                raise CancelledError('Bavaria acquisition stopped.')
    raise RuntimeError('DGM5 acquisition failed; validated cache preserved. ' + '; '.join(errors))


def catalogue(config, session):
    path = scoped_root(config, 'logs_dir') / '09.meta4'
    cached = None
    if path.exists():
        try:
            cached = parse_catalogue(path)
        except (ValueError, OSError, ET.ParseError) as exc:
            LOG.warning('Invalid cached DGM5 catalogue: %s', exc)
    age = config.get('catalogue_max_age_days', 30)
    expired = age is not None and path.exists() and time.time() - path.stat().st_mtime >= age * 86400
    if cached is not None and not expired and not config.get('catalogue_refresh') and config.get('reuse_cache', True):
        return cached
    try:
        result, _ = fetch(session, [CATALOGUE_URL], path, config, parse_catalogue)
        return result
    except RuntimeError:
        if cached is None:
            raise
        LOG.warning('Catalogue refresh failed; using the last valid catalogue (%s).', path)
        return cached


def select_tiles(geometry, index):
    x0, y0, x1, y1 = bounds(geometry)
    selected, unavailable = [], []
    for x in range(math.floor(x0 / 1000), math.ceil(x1 / 1000)):
        for y in range(math.floor(y0 / 1000), math.ceil(y1 / 1000)):
            name = f'{x}_{y}.zip'
            if geometry.Intersection(rectangle(filename_bounds(name))).GetArea() <= 0:
                continue
            if name in index['tiles']:
                selected.append(index['tiles'][name])
            else:
                unavailable.append(name)
    return selected, unavailable


def xyz_member(package, tile):
    """Allow nested folders/support documents, but exactly one matching grid."""
    seen, candidates = set(), []
    for member in package.infolist():
        name = PurePosixPath(member.filename)
        if (name.is_absolute() or '..' in name.parts or '\\' in member.filename or ':' in member.filename
                or stat.S_ISLNK(member.external_attr >> 16) or member.filename.casefold() in seen):
            raise ValueError(f'Unsafe/duplicate ZIP member: {member.filename}')
        seen.add(member.filename.casefold())
        if member.is_dir():
            continue
        if name.name == tile['name'].replace('.zip', '.txt'):
            if member.file_size > 16 * 1024 * 1024:
                raise ValueError('DGM5 XYZ exceeds the supported 1 km tile size.')
            candidates.append(member.filename)
        elif name.suffix.lower() in ('.xyz', '.tif', '.tiff') or re.fullmatch(r'-?\d+_-?\d+\.txt', name.name):
            raise ValueError(f'Unexpected additional terrain member: {name}')
    if len(candidates) != 1:
        raise ValueError(f'Expected exactly one matching DGM5 TXT: {tile["name"]}')
    return candidates[0]


def validate_zip(path, tile):
    if path.stat().st_size != tile['size'] or sha256(path) != tile['sha256']:
        raise ValueError(f'DGM5 size/SHA-256 mismatch: {tile["name"]}')
    with zipfile.ZipFile(path) as package:
        member = xyz_member(package, tile)
        # Reading the selected member checks its CRC without extracting support files.
        with package.open(member) as stream:
            while stream.read(1024 * 1024):
                pass
    return {'member': member}


def cached_archive(session, tile, config, *, request_gate=None, stop_event=None):
    path = scoped_root(config, 'cache_root') / 'source_archive' / tile['name']
    receipt = scoped_root(config, 'logs_dir') / 'archive_receipts' / (tile['name'] + '.json')
    if config.get('reuse_cache', True) and path.exists():
        try:
            validate_zip(path, tile)
            return path
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
            LOG.warning('Invalid/stale DGM5 archive %s: %s', path, exc)
    record, url = fetch(session, tile['urls'], path, config, lambda p: validate_zip(p, tile),
                        request_gate=request_gate, stop_event=stop_event)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    write_json(receipt, {**tile, **record, 'url': url,
                         'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    return path


def converted_tile(archive, tile, config):
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / tile['name'].replace('.zip', '.tif')
    receipt = receipt_path(path, config)
    identity = {'archive_sha256': tile['sha256'], 'conversion_version': CONVERSION_VERSION,
                'source': config['source'], 'output_nodata': config['nodata']}
    if config.get('reuse_cache', True) and path.exists() and receipt.exists():
        try:
            record = json.loads(receipt.read_text(encoding='utf-8'))
            if all(record.get(k) == v for k, v in identity.items()) and record['sha256'] == sha256(path):
                validate_native(path, tile['bounds'])
                return path
        except (OSError, ValueError, RuntimeError, KeyError):
            pass
    # Extract to a chosen path, never one supplied by the ZIP.
    temporary = path.with_suffix('.txt.part')
    try:
        with zipfile.ZipFile(archive) as package:
            member = xyz_member(package, tile)
            support = package.namelist()
            with package.open(member) as src, temporary.open('wb') as dst:
                shutil.copyfileobj(src, dst)
        info = convert_xyz(temporary, path, tile['bounds'], config)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        write_json(receipt, {**identity, **info, 'archive': str(archive), 'catalogue': CATALOGUE_URL,
                             'urls': tile['urls'], 'member': member, 'archive_members': support,
                             'sha256': sha256(path)})
    finally:
        temporary.unlink(missing_ok=True)
    return path


def acquire_tile(session, source, tile, directory, config, *, request_gate, stop_event):
    # Archive validation must precede derivative reuse, including in worker threads.
    archive = cached_archive(session, tile, config, request_gate=request_gate, stop_event=stop_event)
    if stop_event.is_set():
        raise CancelledError('Bavaria acquisition stopped.')
    return converted_tile(archive, tile, config)


def acquire(config, source_plan, log_dir, probe_only=False):
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    with requests.Session() as session:
        index = catalogue(config, session)
        selected, unavailable = select_tiles(geometry, index)
        write_json(log_dir / 'bavaria_selection.json', {'catalogue': CATALOGUE_URL,
                   'catalogue_sha256': sha256(scoped_root(config, 'logs_dir') / '09.meta4'),
                   'published': index['published'], 'archives': selected, 'unavailable': unavailable})
        if unavailable:
            LOG.warning('DGM5 catalogue coverage gaps retained as NoData: %s', unavailable)
    if not selected:
        raise ValueError('No catalogue-backed Bavaria DGM5 tiles intersect the AOI; see bavaria_selection.json.')
    jobs = [{**tile, 'id': tile['name'][:-4]} for tile in (selected[:1] if probe_only else selected)]
    # Empty generic cache candidates: Bavaria must check BOTH ZIP and conversion.
    return download_tiles(config, jobs, raw_directory(config), [], 'Bavaria AOI tiles',
                          acquire_tile, completed_label='completed')


def download(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir, probe_only=True)[0]
