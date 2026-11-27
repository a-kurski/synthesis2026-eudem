"""Official district ZIP acquisition; preserve complete packages and process AOI TIFFs."""
import hashlib
import json
import logging
from pathlib import PurePosixPath
import re
import shutil
import stat
import time
from urllib.parse import quote
import zipfile

import numpy as np
from osgeo import gdal, ogr
import requests

from ....acquire import sha256, write_json
from ....geo import rectangle, windows, valid_values
from ....paths import scoped_root, raw_directory, receipt_path, download_part
from ....progress import bar, track
from .processing import validate_native

LOG = logging.getLogger('dtm')
TILE_NAME = re.compile(r'dgm1_32_(\d{3})_(\d{4})_1_he\.tiff?', re.IGNORECASE)


def filename_bounds(name):
    match = TILE_NAME.fullmatch(name)
    if not match:
        return None
    x, y = (int(v)*1000 for v in match.groups())
    return [x, y, x+1000, y+1000]


def atomic_json(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + '.part')
    write_json(part, record)
    part.replace(path)


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def package_url(source, region):
    parts = [source['download_date'], '3D-Daten', 'Digitales Geländemodell (DGM1)',
             region['name'], f'PKT_{region["name"]}.zip']
    return source['base_url'].rstrip('/') + '/' + '/'.join(quote(p, safe='') for p in parts)


def locations(config, region):
    key = f'official/{config["source"]["download_date"]}/{region["id"]}'
    directory = scoped_root(config, 'cache_root') / 'source_archive' / key
    records = scoped_root(config, 'logs_dir') / 'regional_packages' / key
    directory.mkdir(parents=True, exist_ok=True)
    records.mkdir(parents=True, exist_ok=True)
    return directory, records


def zip_members(package):
    result, names = [], set()
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    for member in package.infolist():
        name = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        if (name.is_absolute() or '..' in name.parts or '\\' in member.filename or ':' in member.filename
                or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                or any(p.endswith((' ', '.')) or p.split('.')[0].upper() in reserved for p in name.parts)):
            raise ValueError(f'Unsafe Hessen ZIP member: {member.filename}')
        if member.is_dir():
            continue
        key = member.filename.casefold()
        if key in names:
            raise ValueError(f'Duplicate Hessen ZIP path: {member.filename}')
        names.add(key)
        result.append(member)
    if not any(PurePosixPath(m.filename).suffix.lower() in ('.tif', '.tiff', '.zip') for m in result):
        raise ValueError('Official Hessen regional ZIP contains no TIFFs or nested ZIPs.')
    return result


def validate_zip(path):
    with zipfile.ZipFile(path) as package:
        zip_members(package)
        failed = package.testzip()
        if failed:
            raise ValueError(f'Hessen ZIP CRC failure: {failed}')
    return {'size': path.stat().st_size, 'sha256': sha256(path)}


def cached_package(session, config, region):
    directory, records = locations(config, region)
    path = directory / f'PKT_{region["name"]}.zip'
    url = package_url(config['source'], region)
    receipt = read_json(records / 'archive.json')
    if config.get('reuse_cache', True) and path.is_file():
        if receipt is None:
            receipt = {**validate_zip(path), 'url': url}
            atomic_json(records / 'archive.json', receipt)
        elif (receipt.get('url') != url or path.stat().st_size != receipt.get('size')
              or sha256(path) != receipt.get('sha256')):
            raise ValueError(f'Hessen ZIP differs from its receipt: {path}; use --fresh-download.')
        return path, receipt
    part = path.with_name(path.name + '.part')
    if not config.get('reuse_cache', True):
        part.unlink(missing_ok=True)
    for attempt in range(1, config['download_attempts']+1):
        try:
            offset = part.stat().st_size if part.exists() else 0
            headers = {'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = f'bytes={offset}-'
            time.sleep(config['request_pause_seconds'])
            LOG.info('Hessen district %s ZIP attempt %d, byte %d: %s', region['id'], attempt, offset, url)
            with session.get(url, headers=headers, stream=True, timeout=(30, config['timeout_seconds'])) as response:
                if response.status_code == 416 and offset and response.headers.get('Content-Range') == f'bytes */{offset}':
                    total = offset
                else:
                    response.raise_for_status()
                    if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                        raise ValueError('Encoded Hessen ZIP response cannot be resumed.')
                    if offset and response.status_code != 206:
                        raise ValueError('Hessen server ignored Range; preserving partial ZIP.')
                    if response.status_code == 206:
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                        if not match or int(match[1]) != offset or int(match[2]) != int(match[3])-1:
                            raise ValueError('Unexpected Hessen ZIP Content-Range.')
                        total = int(match[3])
                    elif response.status_code == 200:
                        value = response.headers.get('Content-Length', '')
                        total = int(value) if value.isdecimal() else None
                    else:
                        raise ValueError(f'Unexpected Hessen ZIP response: {response.status_code}')
                    with part.open('ab' if offset else 'wb') as output, bar(
                            f'Hessen {region["id"]} ZIP', total, 'bytes', initial=offset) as progress:
                        for chunk in response.iter_content(1024*1024):
                            if total is not None and output.tell()+len(chunk) > total:
                                raise ValueError('Hessen ZIP body exceeds declared size.')
                            output.write(chunk)
                            progress.update(len(chunk))
                if total is not None and part.stat().st_size != total:
                    raise ValueError('Incomplete Hessen ZIP; retaining partial for resume.')
            try:
                verified = validate_zip(part)
            except (ValueError, zipfile.BadZipFile):
                part.unlink(missing_ok=True)
                raise
            receipt = {**verified, 'url': url, 'district': region,
                       'download_date': config['source']['download_date'], 'validation': 'ZIP CRC and local SHA-256'}
            part.replace(path)
            atomic_json(records / 'archive.json', receipt)
            return path, receipt
        except (requests.RequestException, OSError, ValueError, zipfile.BadZipFile) as exc:
            LOG.warning('Hessen district %s attempt %d failed (%s): %s', region['id'], attempt, type(exc).__name__, exc)
            status = exc.response.status_code if isinstance(exc, requests.HTTPError) and exc.response is not None else None
            if status in (400, 401, 403, 404) or attempt == config['download_attempts']:
                raise RuntimeError(f'Hessen district {region["id"]} package failed: {url}: {exc}. '
                                   'Check source.download_date against the official Downloadcenter.') from exc
            time.sleep(min(2**attempt, 30))


def source_identity(config, region):
    return {'url': package_url(config['source'], region), 'schema': 1, 'district': region}


def reusable_extraction(config, region):
    directory, records = locations(config, region)
    index = read_json(records / 'extraction.json')
    if not index or index.get('source') != source_identity(config, region) or not index.get('complete'):
        return None
    root = directory / index['directory']
    try:
        # Inner ZIPs are transport containers, not dependencies of an already
        # completed extraction. Keep their receipts for provenance, but allow
        # their removal without invalidating existing schema-1 caches.
        required = [f for f in index['files'] if PurePosixPath(f['name']).suffix.lower() != '.zip']
        if (not index['tiles'] or not required
                or any((root/f['name']).stat().st_size != f['size']
                       for f in [*required, *index['tiles']])):
            return None
    except (OSError, KeyError):
        return None
    return root, index


def extract_contents(archive, root, destination, files, tiles, *, depth=0):
    """Keep original ZIPs and safely expand district packages containing tile ZIPs."""
    if depth > 8:
        raise ValueError('Hessen ZIP nesting exceeds eight levels.')
    with zipfile.ZipFile(archive) as package:
        members = zip_members(package)
        for member in track(members, 'Hessen source extraction', unit='files'):
            # Reserve a separate namespace for nested extraction directories.
            if PurePosixPath(member.filename).parts[0].casefold() == '_nested':
                raise ValueError('Hessen ZIP uses reserved _nested extraction path.')
            path = destination.joinpath(*PurePosixPath(member.filename).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(path.name+'.part')
            try:
                digest = hashlib.sha256()
                with package.open(member) as src, part.open('wb') as dst:
                    while chunk := src.read(1024*1024):
                        dst.write(chunk)
                        digest.update(chunk)
                if part.stat().st_size != member.file_size:
                    raise ValueError(f'Incomplete Hessen extraction: {member.filename}')
                part.replace(path)
            finally:
                part.unlink(missing_ok=True)
            relative = path.relative_to(root).as_posix()
            record = {'name': relative, 'size': member.file_size, 'sha256': digest.hexdigest(), 'crc': member.CRC}
            files.append(record)
            if path.suffix.lower() in ('.tif', '.tiff'):
                extent = filename_bounds(path.name)
                if extent is None:
                    extent = validate_native(path)['extent']
                tiles.append({**record, 'bounds': extent})
            elif path.suffix.lower() == '.zip':
                token = hashlib.sha256(relative.encode()).hexdigest()[:24]
                extract_contents(path, root, root/'_nested'/token, files, tiles, depth=depth+1)


def extract_region(session, config, region):
    if config.get('reuse_cache', True):
        cached = reusable_extraction(config, region)
        if cached:
            LOG.info('Reusing complete official Hessen district %s extraction.', region['id'])
            return cached
    archive, receipt = cached_package(session, config, region)
    directory, records = locations(config, region)
    root = directory / ('extracted_' + receipt['sha256'][:16])
    root.mkdir(parents=True, exist_ok=True)
    files, tiles = [], []
    extract_contents(archive, root, root, files, tiles)
    if not tiles:
        raise ValueError('Official Hessen package contains no TIFFs after nested extraction.')
    index = {'source': source_identity(config, region), 'complete': True, 'directory': root.name,
             'archive': receipt, 'files': files, 'tiles': tiles}
    atomic_json(records/'extraction.json', index)
    return root, index


def compare_rasters(left, right):
    a, b = validate_native(left), validate_native(right)
    if any(a[key] != b[key] for key in ('extent', 'rows', 'cols', 'transform')):
        raise ValueError('Duplicate Hessen tiles do not share the same pixel grid.')
    result = {'different_valid_pixels': 0, 'different_missing_pixels': 0,
              'max_absolute_height_difference_m': 0.0}
    with gdal.Open(str(left)) as src, gdal.Open(str(right)) as other:
        for window in windows(src):
            values, valid = valid_values(src.GetRasterBand(1), window)
            other_values, other_valid = valid_values(other.GetRasterBand(1), window)
            different = valid & other_valid & (values != other_values)
            result['different_valid_pixels'] += int(different.sum())
            result['different_missing_pixels'] += int((valid != other_valid).sum())
            if different.any():
                delta = np.abs(values[different].astype('float64') - other_values[different])
                result['max_absolute_height_difference_m'] = max(result['max_absolute_height_difference_m'], float(delta.max()))
    result['equivalent'] = not (result['different_valid_pixels'] or result['different_missing_pixels'])
    return result


def same_raster(left, right):
    return compare_rasters(left, right)['equivalent']


def acquire(config, source_plan, log_dir, *, probe_only=False):
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    candidates = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        for region in source_plan['regions']:
            root, index = extract_region(session, config, region)
            for tile in index['tiles']:
                if geometry.Intersection(rectangle(tile['bounds'])).GetArea() > 0:
                    candidates.append((region, root, index, tile))
    if not candidates:
        raise ValueError('No official Hessen source TIFF intersects the AOI.')
    raw = raw_directory(config)
    raw.mkdir(parents=True, exist_ok=True)
    paths, seen, selected, duplicates, validated = [], {}, [], [], []
    for region, root, index, tile in track(candidates, 'Hessen selected tile validation'):
        source = root / tile['name']
        if sha256(source) != tile['sha256']:
            raise ValueError(f'Hessen extracted TIFF differs from its receipt: {source}')
        info = validate_native(source)
        if info['extent'] != tile['bounds']:
            raise ValueError(f'Hessen TIFF bounds differ from filename/index: {source}')
        validated.append((region, root, index, tile, info))
    # Resolve every group before copying, so traversal order cannot choose a
    # different winner. Metadata preference is a tie-break, not an accuracy claim.
    policy = 'Prefer explicit NoData; then lowest district ID; then lexical member path.'
    validated.sort(key=lambda item: (item[4]['nodata'] is None, item[0]['id'], item[3]['name']))
    winners = []
    for region, root, index, tile, info in validated:
        source = root / tile['name']
        key = tuple(info['extent'])
        if key in seen:
            previous = seen[key]
            comparison = compare_rasters(previous, source)
            duplicates.append({'kept': str(previous), 'discarded_from_processing': str(source),
                               'bounds': list(key), 'selection_policy': policy, **comparison})
            LOG.warning('Hessen duplicate tile (%s): keeping %s; excluding %s. %s Differences: %s',
                        'equivalent' if comparison['equivalent'] else 'CONFLICT',
                        previous, source, policy, comparison)
            continue
        seen[key] = source
        winners.append((region, root, index, tile, info))
    write_json(log_dir/'hessen_duplicate_tiles.json', {'selection_policy': policy,
               'duplicate_count': len(duplicates),
               'conflict_count': sum(not d['equivalent'] for d in duplicates), 'duplicates': duplicates})
    for region, root, index, tile, info in track(winners, 'Hessen selected tile caching'):
        source = root / tile['name']
        # Unique flat names also avoid collisions in the unchanged shared cleaner.
        token = hashlib.sha256(tile['name'].encode()).hexdigest()[:12]
        path = raw / f'he_{config["source"]["download_date"]}_{region["id"]}_{token}_{source.name}'
        if not (config.get('reuse_cache', True) and path.is_file() and sha256(path) == tile['sha256']):
            part = download_part(path, config)
            try:
                shutil.copyfile(source, part)
                if sha256(part) != tile['sha256']:
                    raise ValueError(f'Hessen raw copy verification failed: {source}')
                part.replace(path)
            finally:
                part.unlink(missing_ok=True)
        record = {'source': source_identity(config, region), 'archive': index['archive'],
                  'member': tile['name'], 'sha256': tile['sha256'], 'grid': info}
        atomic_json(receipt_path(path, config), record)
        paths.append(path)
        selected.append({'path': str(path), 'district': region['id'], 'member': tile['name'], 'grid': info})
    write_json(log_dir/'hessen_selected_tiles.json', {'regions': source_plan['regions'],
               'download_date': config['source']['download_date'], 'tiles': selected,
               'identical_boundary_duplicates': [d for d in duplicates if d['equivalent']],
               'conflicting_boundary_duplicates': [d for d in duplicates if not d['equivalent']],
               'duplicate_report': str(log_dir/'hessen_duplicate_tiles.json'), 'probe_only': probe_only})
    return paths[:1] if probe_only else paths


def download(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir, probe_only=True)[0]
