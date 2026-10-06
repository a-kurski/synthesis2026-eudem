"""Extract the complete verified source once; index before selecting raster inputs."""
import hashlib
import json
import logging
from pathlib import Path, PurePosixPath
import re
import tarfile

from osgeo import ogr

from ....acquire import sha256, write_json
from ....geo import rectangle
from ....paths import scoped_root, raw_directory, receipt_path, download_part
from ....progress import track
from ..archive import archive as acquire_archive
from .processing import validate_native

LOG = logging.getLogger('dtm')
SUPPORT_FILES = {'metadata.json', 'LICENSE.pdf', 'bounds.csv', 'coverage.gpkg'}
TILE_NAME = re.compile(r'DGM1_32_(\d{3})_(\d{4})_1_he\.tiff?', re.IGNORECASE)


def archive(config, log_dir):
    return acquire_archive(config, log_dir, filename='dehessen.tar', label='Hessen')


def filename_bounds(name):
    match = TILE_NAME.fullmatch(name)
    if not match:
        return None
    x, y = (int(value) * 1000 for value in match.groups())
    return [x, y, x + 1000, y + 1000]


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix('.json.part')
    try:
        write_json(part, value)
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def members(package):
    """Preflight every path before extracting; flatten only regular known files."""
    result, names = [], set()
    for member in package.getmembers():
        name = PurePosixPath(member.name)
        if (name.is_absolute() or '..' in name.parts or '\\' in member.name or ':' in member.name
                or not (member.isfile() or member.isdir())):
            raise ValueError(f'Unsafe or non-regular archive member: {member.name}')
        if member.isdir():
            continue
        if name.suffix.lower() not in ('.tif', '.tiff') and name.name not in SUPPORT_FILES:
            continue
        key = name.name.lower()
        if key in names:
            raise ValueError(f'Duplicate archive basename: {name.name}')
        names.add(key)
        result.append(member)
    if not {'metadata.json', 'license.pdf'} <= names:
        raise ValueError('Hessen archive must include metadata.json and LICENSE.pdf.')
    if not any(PurePosixPath(m.name).suffix.lower() in ('.tif', '.tiff') for m in result):
        raise ValueError('Hessen archive contains no GeoTIFFs.')
    return result


def complete_index(config):
    index = read_json(scoped_root(config, 'logs_dir') / 'hessen_source_index.json')
    if not index or index.get('source') != config['source'] or not index.get('complete'):
        return None
    raw = raw_directory(config)
    support = scoped_root(config, 'cache_root') / 'source_archive'
    try:
        if not index['tiles'] or not {'metadata.json', 'LICENSE.pdf'} <= set(index['support']):
            return None
        for tile in index['tiles']:
            path = raw / tile['name']
            if path.stat().st_size != tile['size'] or not receipt_path(path, config).is_file():
                return None
        for name, digest in index['support'].items():
            if sha256(support / name) != digest:
                return None
    except (OSError, KeyError, TypeError):
        return None
    return index


def extract(config, log_dir):
    """Completion is recorded only after all files exist, including non-AOI tiles."""
    archive_path = archive(config, log_dir)
    raw = raw_directory(config)
    raw.mkdir(parents=True, exist_ok=True)
    support = archive_path.parent
    index_path = scoped_root(config, 'logs_dir') / 'hessen_source_index.json'
    # Invalidate the previous completion marker before any replacement. A failed
    # refresh cannot leave a mixed collection claiming to be fully extracted.
    atomic_json(index_path, {'source': config['source'], 'complete': False})
    tiles, support_hashes = [], {}
    with tarfile.open(archive_path, 'r:') as package:
        for member in track(members(package), 'Hessen extraction'):
            name = PurePosixPath(member.name).name
            is_tile = Path(name).suffix.lower() in ('.tif', '.tiff')
            path = (raw if is_tile else support) / name
            receipt = read_json(receipt_path(path, config)) if is_tile else None
            reusable = (config.get('reuse_cache', True) and receipt
                        and receipt.get('source') == config['source']
                        and receipt.get('member') == member.name
                        and receipt.get('archive_verified') is True
                        and path.is_file() and path.stat().st_size == member.size
                        and receipt.get('sha256') == sha256(path))
            if reusable:
                digest = receipt['sha256']
            else:
                part = download_part(path, config)
                try:
                    digest_builder = hashlib.sha256()
                    with package.extractfile(member) as src, part.open('wb') as dst:
                        while chunk := src.read(1024 * 1024):
                            dst.write(chunk)
                            digest_builder.update(chunk)
                    if part.stat().st_size != member.size:
                        raise ValueError(f'Incomplete Hessen extraction: {name}')
                    digest = digest_builder.hexdigest()
                    # Selected raster metadata is checked below, before processing.
                    part.replace(path)
                finally:
                    part.unlink(missing_ok=True)
                if is_tile:
                    atomic_json(receipt_path(path, config), {
                        'source': config['source'], 'member': member.name, 'size': member.size,
                        'sha256': digest, 'archive_verified': True})
            if is_tile:
                extent = filename_bounds(name)
                # Nonstandard names require a header read once, then use the index.
                if extent is None:
                    extent = validate_native(path)['extent']
                tiles.append({'name': name, 'size': member.size, 'bounds': extent, 'sha256': digest})
            else:
                support_hashes[name] = digest
    index = {'source': config['source'], 'complete': True, 'tiles': tiles, 'support': support_hashes}
    atomic_json(index_path, index)
    return index


def acquire(config, source_plan, log_dir, *, probe_only=False):
    index = complete_index(config) if config.get('reuse_cache', True) else None
    if index is None:
        index = extract(config, log_dir)
    else:
        LOG.info('Reusing complete Hessen extraction and tile index (%d tiles)', len(index['tiles']))
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    selected = [tile for tile in index['tiles']
                if geometry.Intersection(rectangle(tile['bounds'])).GetArea() > 0]
    selected.sort(key=lambda tile: tile['name'])
    if not selected:
        raise ValueError('AOI does not intersect any Hessen source tiles.')
    if probe_only:
        selected = selected[:1]
    paths = []
    for tile in track(selected, 'Hessen selected tile validation'):
        path = raw_directory(config) / tile['name']
        receipt = read_json(receipt_path(path, config))
        if (not receipt or receipt.get('source') != config['source']
                or receipt.get('sha256') != tile['sha256'] or sha256(path) != tile['sha256']):
            raise ValueError(f'Hessen cached tile differs from its receipt: {path}; use --fresh-download to replace it.')
        info = validate_native(path)
        if info['extent'] != tile['bounds']:
            raise ValueError(f'Hessen raster bounds differ from the tile index/filename: {path}')
        receipt['grid'] = info
        atomic_json(receipt_path(path, config), receipt)
        paths.append(path)
    write_json(log_dir / 'hessen_selected_tiles.json', {
        'source_index': str(scoped_root(config, 'logs_dir') / 'hessen_source_index.json'),
        'available_tile_count': len(index['tiles']), 'probe_only': probe_only, 'tiles': selected,
        'package_metadata': str(scoped_root(config, 'cache_root') / 'source_archive')})
    return paths


def download(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir, probe_only=True)[0]
