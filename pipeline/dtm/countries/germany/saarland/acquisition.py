"""Use local native TIFFs first; acquire a verified Mapterhorn archive if needed."""
import json
import logging
from pathlib import Path, PurePosixPath
import shutil
import tarfile

from osgeo import ogr

from ....acquire import sha256, write_json
from ....geo import rectangle
from ....paths import raw_directory, receipt_path, download_part
from ..archive import archive as acquire_archive, verify_archive
from ....progress import track
from .processing import validate_native

LOG = logging.getLogger('dtm')
SUPPORT_FILES = {'metadata.json', 'bounds.csv', 'coverage.gpkg', 'saarland_coverage.gpkg', 'LICENSE.pdf'}


def archive(config, log_dir):
    return acquire_archive(config, log_dir, filename='desaarland.tar', label='Saarland')


def select_tiles(package, archive_path, source_plan):
    """Read native raster extents; the package's bounds.csv uses another CRS."""
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    selected, names = [], set()
    for member in track(sorted(package.getmembers(), key=lambda m: m.name), 'Saarland tile discovery'):
        if not member.name.lower().endswith(('.tif', '.tiff')):
            continue
        name = PurePosixPath(member.name)
        if not member.isfile() or name.is_absolute() or '..' in name.parts or '\\' in member.name:
            raise ValueError(f'Unsafe or non-regular archive tile: {member.name}')
        if name.name in names:
            raise ValueError(f'Duplicate archive TIFF basename: {name.name}')
        names.add(name.name)
        path = f'/vsitar/{archive_path.resolve().as_posix()}/{member.name}'
        info = validate_native(path)
        if geometry.Intersection(rectangle(info['extent'])).GetArea() > 0:
            selected.append({'member': member.name, 'name': name.name, 'size': member.size,
                             'bounds': info['extent'], 'grid': info})
    if not selected:
        raise ValueError('AOI does not intersect any Saarland source tiles.')
    return selected


def reusable(path, tile, config):
    try:
        receipt = json.loads(receipt_path(path, config).read_text(encoding='utf-8'))
        return (receipt['source'] == config['source'] and receipt['member'] == tile['member']
                and path.stat().st_size == tile['size'] and receipt['sha256'] == sha256(path)
                and validate_native(path) == tile['grid'])
    except (OSError, ValueError, RuntimeError, KeyError):
        return False


def local_tiles(config, source_plan, log_dir, probe_only):
    """Treat manually supplied TIFFs as the local source collection, without a TAR."""
    files = sorted(p for p in raw_directory(config).iterdir()
                   if p.is_file() and p.suffix.lower() in ('.tif', '.tiff'))
    if not files:
        return None
    geometry = ogr.CreateGeometryFromWkt(source_plan['selection_wkt'])
    selected = []
    for path in track(files, 'Saarland local tile discovery'):
        info = validate_native(path)
        if geometry.Intersection(rectangle(info['extent'])).GetArea() <= 0:
            continue
        record_path = receipt_path(path, config)
        digest = sha256(path)
        if record_path.exists():
            record = json.loads(record_path.read_text(encoding='utf-8'))
            if record.get('source') != config['source'] or record.get('sha256') != digest:
                raise ValueError(f'Saarland cached tile differs from its receipt: {path}')
        else:
            # This records local validation, not verification against the source archive.
            record = {'source': config['source'], 'sha256': digest, 'grid': info,
                      'validation': 'local_native_tiff', 'archive_verified': False}
            record_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(record_path, record)
        selected.append({'path': str(path), 'name': path.name, 'grid': info})
    if not selected:
        raise ValueError('No local Saarland TIFF intersects the AOI; supply the missing tiles or use --fresh-download.')
    if probe_only:
        selected = selected[:1]
    write_json(log_dir / 'saarland_selected_tiles.json', {
        'mode': 'local_tiffs', 'directory': str(raw_directory(config)),
        'available_tile_count': len(files), 'probe_only': probe_only, 'tiles': selected})
    LOG.info('Using local Saarland TIFFs without an archive: %s selected of %s', len(selected), len(files))
    return [Path(tile['path']) for tile in selected]


def acquire(config, source_plan, log_dir, *, probe_only=False):
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)
    if config.get('reuse_cache', True):
        local = local_tiles(config, source_plan, log_dir, probe_only)
        if local is not None:
            return local
    archive_path = archive(config, log_dir)
    candidates = [directory] if config.get('reuse_cache', True) else []
    with tarfile.open(archive_path, 'r:') as package:
        # Fixed basenames only: never extract archive paths or links to disk.
        for member in package.getmembers():
            if member.name in SUPPORT_FILES and member.isfile():
                with package.extractfile(member) as src, (log_dir / member.name).open('wb') as dst:
                    shutil.copyfileobj(src, dst)
        selected = select_tiles(package, archive_path, source_plan)
        if probe_only:
            selected = selected[:1]
        write_json(log_dir / 'saarland_selected_tiles.json', {
            'archive': str(archive_path), 'url': config['source']['url'],
            'md5': config['source']['md5'], 'probe_only': probe_only, 'tiles': selected})
        paths = []
        for tile in track(selected, 'Saarland extraction'):
            reused = next((p / tile['name'] for p in candidates
                           if reusable(p / tile['name'], tile, config)), None)
            if reused:
                paths.append(reused)
                continue
            path = directory / tile['name']
            part = download_part(path, config)
            try:
                with package.extractfile(tile['member']) as src, part.open('wb') as dst:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                info = validate_native(part)
                if part.stat().st_size != tile['size'] or info != tile['grid']:
                    raise ValueError(f'Extracted tile differs from archive: {tile["name"]}')
                receipt = {'source': config['source'], 'archive': str(archive_path),
                           'member': tile['member'], 'sha256': sha256(part), 'grid': info}
                part.replace(path)
                record_path = receipt_path(path, config)
                record_path.parent.mkdir(parents=True, exist_ok=True)
                write_json(record_path, receipt)
                paths.append(path)
            finally:
                part.unlink(missing_ok=True)
    return paths


def download(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    return acquire(config, source_plan, log_dir, probe_only=True)[0]
