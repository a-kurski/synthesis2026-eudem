"""Verified, atomic archive acquisition shared by German source adapters."""
import hashlib
import logging
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


def archive(config, log_dir, *, filename, label):
    source = config['source']
    root = scoped_root(config, 'cache_root')
    path = root / 'source_archive' / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if config.get('reuse_cache', True) and verify_archive(path, source):
        LOG.info('Reusing Mapterhorn archive with verified size/MD5: %s', path)
        return path
    part = path.with_suffix('.tar.part')
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        for attempt in range(1, config['download_attempts'] + 1):
            try:
                LOG.info('Downloading %s archive, attempt %d: %s', label, attempt, source['url'])
                with session.get(source['url'], stream=True, timeout=(30, config['timeout_seconds'])) as response:
                    response.raise_for_status()
                    digest = hashlib.md5()
                    with part.open('wb') as output, bar(f'{label} archive download', source['size'], 'bytes') as progress:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
                            digest.update(chunk)
                            progress.update(len(chunk))
                if part.stat().st_size != source['size'] or digest.hexdigest() != source['md5']:
                    raise ValueError('Mapterhorn archive size/MD5 mismatch.')
                part.replace(path)
                return path
            except (requests.RequestException, OSError, ValueError) as exc:
                part.unlink(missing_ok=True)
                if attempt == config['download_attempts']:
                    raise RuntimeError(f'Failed to acquire {label} archive: {exc}') from exc
                time.sleep(min(2 ** attempt, 30))

