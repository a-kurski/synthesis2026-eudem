"""WCS acquisition with atomic, validated, checksummed source-tile caching."""
import hashlib
import json
import logging
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import requests

from .geo import validate_tile

LOG = logging.getLogger('dtm')


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def params(source, tile):
    x0, y0, x1, y1 = tile['bounds']
    # Both deployed MapServer services use these subset limits as raster edges.
    # Verified with tiny live requests: centre-inset limits lose a pixel and
    # create gaps between adjacent tiles, so use the exact snapped edges.
    result = {'SERVICE': 'WCS', 'VERSION': '2.0.1', 'REQUEST': 'GetCoverage',
              'COVERAGEID': source['coverage'], 'FORMAT': 'image/tiff',
              'SUBSET': [f'x({x0},{x1})', f'y({y0},{y1})']}
    return result


def exception_text(content):
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    exceptions = [node for node in root.iter() if node.tag.split('}')[-1] in ('Exception', 'ServiceException')]
    return '; '.join(f"{node.get('exceptionCode', node.get('code', ''))}: {' '.join(node.itertext()).strip()}" for node in exceptions) or 'Unexpected XML response'


def cached(path, source, tile):
    sidecar = path.with_suffix('.json')
    if not path.exists() or not sidecar.exists():
        return False
    try:
        record = json.loads(sidecar.read_text(encoding='utf-8'))
        if record['request'] != params(source, tile) or record['source'] != source or record['sha256'] != sha256(path):
            return False
        validate_tile(path, source, tile)
        return True
    except (ValueError, RuntimeError, KeyError, OSError):
        return False


def download_tile(session, source, tile, directory, config):
    path = directory / f"{tile['id']}.tif"
    if cached(path, source, tile):
        LOG.info('Reusing validated source tile %s', path)
        return path
    # An unindexed valid tile can be recovered only with a matching acquisition
    # receipt; an arbitrary same-named TIFF must never be silently reused.
    request = params(source, tile)
    prepared = requests.Request('GET', source['url'], params=request).prepare()
    part = path.with_suffix('.tif.part')
    for attempt in range(1, config['download_attempts'] + 1):
        try:
            LOG.info('HTTP GET attempt=%s %s', attempt, prepared.url)
            with session.get(source['url'], params=request, stream=True, timeout=(30, config['timeout_seconds'])) as response:
                response.raise_for_status()
                with part.open('wb') as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        stream.write(chunk)
                with part.open('rb') as stream:
                    head = stream.read(65536)
                if head.lstrip().startswith(b'<'):
                    # Never treat arbitrary server/XML failures as missing terrain.
                    raise ValueError(f'WCS service exception: {exception_text(head)}')
                info = validate_tile(part, source, tile)
                record = {'source': source, 'request': request, 'url': response.url,
                          'downloaded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                          'headers': {k: v for k, v in response.headers.items() if k.lower() in ('last-modified', 'etag', 'content-type')},
                          'sha256': sha256(part), **info}
            part.replace(path)
            write_json(path.with_suffix('.json'), record)
            LOG.info('Downloaded %s: %s', path, json.dumps(info))
            time.sleep(config['request_pause_seconds'])
            return path
        except (requests.RequestException, RuntimeError, ValueError, OSError) as exc:
            LOG.warning('Tile %s attempt %d failed: %s', tile['id'], attempt, exc)
            if part.exists():
                part.unlink()
            if attempt == config['download_attempts']:
                raise RuntimeError(f'Failed to acquire {tile["id"]}: {exc}. Completed tiles are preserved.') from exc
            time.sleep(min(2 ** attempt, 30))


def metadata(session, source, directory, name, config):
    for operation in ('GetCapabilities', 'DescribeCoverage'):
        request = {'SERVICE': 'WCS', 'VERSION': '2.0.1', 'REQUEST': operation}
        if operation == 'DescribeCoverage':
            request['COVERAGEID'] = source['coverage']
        LOG.info('HTTP GET %s', requests.Request('GET', source['url'], params=request).prepare().url)
        response = session.get(source['url'], params=request, timeout=(30, config['timeout_seconds']))
        response.raise_for_status()
        root = ET.fromstring(response.content)
        if any(node.tag.split('}')[-1] == 'Exception' for node in root.iter()):
            raise ValueError(exception_text(response.content))
        (directory / f'{name}_{operation}.xml').write_bytes(response.content)
        if operation == 'DescribeCoverage':
            ids = [n.text for n in root.iter() if n.tag.split('}')[-1] == 'CoverageId']
            if source['coverage'] not in ids:
                raise ValueError(f'Coverage {source["coverage"]} missing from service metadata.')


def acquire(config, plan, root, run_dir):
    sources = {}
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        for name, source in config['sources'].items():
            metadata(session, source, run_dir, name, config)
            directory = root / f'{name}_tiles'
            sources[name] = []
            for index, tile in enumerate(plan['sources'][name]['tiles'], 1):
                LOG.info('%s tile %d/%d', name, index, plan['sources'][name]['chunks'])
                sources[name].append(download_tile(session, source, tile, directory, config))
    return sources
