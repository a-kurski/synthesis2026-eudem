"""Download the national COG once, then validate and reuse the local source."""
import logging
import time

import requests

from ...acquire import write_json
from ...paths import raw_directory, receipt_path
from ...progress import bar
from .processing import SOURCE_BYTES, validate_native

LOG = logging.getLogger('dtm')


def source_path(config):
    # A relative path follows the existing country raw cache, not the run folder.
    return (raw_directory(config) / config['source'].get('path', 'MNT_Lidar2024.tif')).resolve()


def download(config, source_plan, log_dir):
    if source_plan.get('skip_reason'):
        return []
    path = source_path(config)
    if not path.is_file():
        acquire_source(path, config)
    info = validate_native(path)
    receipt = receipt_path(path, config)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    write_json(receipt, {'source': config['source'], 'path': str(path), 'grid': info,
                        'size_bytes': path.stat().st_size,
                        'validation': 'local_cog_size_and_metadata', 'checksum_verified': False})
    LOG.info('Reusing Luxembourg national COG: %s', path)
    return [path]


def acquire_source(path, config):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep partial transfers on the same filesystem for atomic publication.
    part = path.with_suffix(path.suffix + '.part')
    url = config['source']['url']
    # A completed transfer may have failed validation with an older validator.
    # Revalidate it before any HTTP request; never overwrite a complete file.
    if part.is_file() and part.stat().st_size == SOURCE_BYTES:
        validate_native(part)
        part.replace(path)
        return
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        for attempt in range(1, config['download_attempts'] + 1):
            try:
                LOG.info('Downloading Luxembourg national COG, attempt %d: %s', attempt, url)
                with session.get(url, stream=True, timeout=(30, config['timeout_seconds'])) as response:
                    response.raise_for_status()
                    with part.open('wb') as output, bar('Luxembourg COG download', SOURCE_BYTES, 'bytes') as progress:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
                            progress.update(len(chunk))
                if part.stat().st_size != SOURCE_BYTES:
                    raise requests.RequestException(
                        f'Incomplete transfer: expected {SOURCE_BYTES} bytes, received {part.stat().st_size}')
            except requests.RequestException as exc:
                LOG.warning('Luxembourg download attempt %d failed: %s', attempt, exc)
                if part.is_file() and part.stat().st_size == SOURCE_BYTES:
                    raise RuntimeError(f'Transfer error after receiving the full file; preserved at {part}. '
                                       'Rerun to validate it without downloading again.') from exc
                if attempt == config['download_attempts']:
                    raise RuntimeError(f'Failed to download Luxembourg national COG from {url}: {exc}. '
                                       f'Any partial file is preserved at {part}.') from exc
                time.sleep(min(2 ** attempt, 30))
                continue
            # Validation and filesystem errors cannot be fixed by repeating a
            # 40 GB HTTP transfer. Leave the file intact and stop immediately.
            validate_native(part)
            part.replace(path)
            return


def probe(config, source_plan, log_dir):
    return download(config, source_plan, log_dir)[0]
