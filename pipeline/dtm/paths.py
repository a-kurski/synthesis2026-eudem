"""Country/region namespaces shared by logging, acquisition and publication."""
from pathlib import Path
from contextlib import contextmanager
import os


def scoped_root(config, key):
    root = Path(config[key]) / config['country']
    if config.get('region'):
        root /= config['region']
    return root


def cache_scope(config):
    # Both countries use the same swissALTI3D assets, receipts and writer lock.
    if config['country'] in ('switzerland', 'liechtenstein'):
        return {**config, 'country': 'switzerland', 'region': None}
    return config


def raw_directory(config):
    return scoped_root(cache_scope(config), 'cache_root') / 'raw_tiles'


def receipt_path(path, config=None):
    path = Path(path)
    if config and 'country' in config and path.parent.resolve() == raw_directory(config).resolve():
        return scoped_root(cache_scope(config), 'logs_dir') / 'raw_receipts' / path.with_suffix('.json').name
    return path.with_suffix('.json')


def download_part(path, config):
    path = Path(path)
    if 'country' in config and path.parent.resolve() == raw_directory(config).resolve():
        part = scoped_root(cache_scope(config), 'logs_dir') / 'download_work' / (path.name + '.part')
        part.parent.mkdir(parents=True, exist_ok=True)
        return part
    return path.with_suffix('.tif.part')


@contextmanager
def region_lock(config):
    """Shared regional raw caches permit one writer at a time."""
    path = scoped_root(cache_scope(config), 'logs_dir') / 'active.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        stream = path.open('x', encoding='utf-8')
    except FileExistsError as exc:
        raise RuntimeError(f'Region is already in use. If the previous process stopped, remove its lock: {path}') from exc
    try:
        with stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink()
