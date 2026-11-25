"""Verified, atomic archive acquisition shared by German source adapters."""
import hashlib
import json
import logging
import re
import time

import requests

from ...paths import scoped_root
from ...progress import bar

LOG = logging.getLogger('dtm')


def verify_archive(path, source):
    if not path.is_file() or path.stat().st_size != source['size']:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'md5').hexdigest() == source['md5']


def prepare_partial(part, config, filename):
    """Bind resumable bytes to the configured source, outside the raw tile cache.

    Legacy .part files have no record. Adopt their prefix, but still require the
    pinned full-file MD5 before publication, just as for a new download.
    """
    record_path = scoped_root(config, 'logs_dir') / (filename + '.resume.json')
    identity = {key: config['source'][key] for key in ('url', 'size', 'md5')}
    try:
        record = json.loads(record_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        record = None
    if part.exists():
        if (not config.get('reuse_cache', True) or part.stat().st_size > identity['size']
                or (record is not None and record != identity)):
            LOG.warning('Discarding partial archive for a fresh request or changed source: %s', part)
            part.unlink()
        elif record is None:
            LOG.info('Adopting existing partial archive; full MD5 verification is required: %s', part)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = record_path.with_suffix('.json.part')
    temporary.write_text(json.dumps(identity, indent=2), encoding='utf-8')
    temporary.replace(record_path)
    return record_path


def response_window(response, offset, size):
    """Validate response offsets before opening the partial file for writing."""
    response.raise_for_status()
    encoding = response.headers.get('Content-Encoding', 'identity')
    if encoding.lower() != 'identity':
        raise ValueError(f'Cannot resume an encoded archive response: {encoding}')
    if response.status_code == 206:
        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
        if not match:
            raise ValueError('Archive response has missing or invalid Content-Range.')
        start, end, total = map(int, match.groups())
        if start != offset or total != size or not start <= end < total:
            raise ValueError(f'Archive Content-Range does not match requested offset/size: {match.group()}')
        length = end - start + 1
    elif response.status_code == 200:
        if offset:
            raise ValueError('Server ignored Range (HTTP 200); retaining the partial archive and retrying the same offset.')
        start, length = 0, size
    else:
        raise ValueError(f'Unexpected archive HTTP status: {response.status_code}')
    declared = response.headers.get('Content-Length')
    if declared is not None and (not declared.isdecimal() or int(declared) != length):
        raise ValueError('Archive Content-Length differs from expected response size.')
    return start, length


def archive(config, log_dir, *, filename, label):
    source = config['source']
    root = scoped_root(config, 'cache_root')
    path = root / 'source_archive' / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if config.get('reuse_cache', True) and verify_archive(path, source):
        LOG.info('Reusing Mapterhorn archive with verified size/MD5: %s', path)
        return path
    part = path.with_suffix('.tar.part')
    record_path = prepare_partial(part, config, filename)
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        session.headers['Accept-Encoding'] = 'identity'
        for attempt in range(1, config['download_attempts'] + 1):
            try:
                offset = part.stat().st_size if part.exists() else 0
                if offset < source['size']:
                    LOG.info('%s %s archive, attempt %d, byte %d/%d: %s',
                             'Resuming' if offset else 'Downloading', label, attempt, offset, source['size'], source['url'])
                    headers = {'Range': f'bytes={offset}-'} if offset else {}
                    with session.get(source['url'], headers=headers, stream=True,
                                     timeout=(30, config['timeout_seconds'])) as response:
                        start, length = response_window(response, offset, source['size'])
                        received = 0
                        with part.open('ab' if start else 'wb') as output, bar(
                                f'{label} archive download', source['size'], 'bytes', initial=start) as progress:
                            for chunk in response.iter_content(1024 * 1024):
                                if received + len(chunk) > length:
                                    raise ValueError('Archive response exceeds its expected byte range.')
                                output.write(chunk)
                                received += len(chunk)
                                progress.update(len(chunk))
                if part.stat().st_size < source['size']:
                    raise ValueError(f'Incomplete archive size: {part.stat().st_size}/{source["size"]} bytes; retaining partial download.')
                # Hash the completed file once, including any prefix from earlier
                # attempts/processes. Never trust a suffix-only checksum.
                LOG.info('Verifying %s archive size/MD5 (%d bytes): %s', label, source['size'], part)
                if not verify_archive(part, source):
                    part.unlink(missing_ok=True)
                    raise ValueError('Mapterhorn archive size/MD5 mismatch.')
                part.replace(path)
                record_path.unlink(missing_ok=True)
                return path
            except (requests.RequestException, OSError, ValueError) as exc:
                LOG.warning('%s archive attempt %d/%d failed (%s): %s. Partial file retained when valid: %s',
                            label, attempt, config['download_attempts'], type(exc).__name__, exc, part)
                if attempt == config['download_attempts']:
                    raise RuntimeError(f'Failed to acquire {label} archive: {exc}. Rerun with --reuse-cache to resume {part}') from exc
                time.sleep(min(2 ** attempt, 30))

