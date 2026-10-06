"""Concurrent tile acquisition with private HTTP sessions and shared pacing."""
from concurrent.futures import CancelledError, FIRST_COMPLETED, ThreadPoolExecutor, wait
import logging
import os
from pathlib import Path
import threading
import time

import requests

from .acquire import cached
from .progress import bar

LOG = logging.getLogger('dtm')


def worker_count(config):
    count = config.get('download_workers', 1)
    if type(count) is not int or count < 1:
        raise ValueError('download_workers must be a positive integer.')
    return count


class RequestGate:
    """Space coverage request starts across all workers, including retries."""
    def __init__(self, interval):
        self.interval = interval
        self.next_start = 0.0
        self.lock = threading.Lock()

    def wait(self, stopped):
        with self.lock:
            while True:
                if stopped.is_set():
                    raise CancelledError('Download acquisition stopped.')
                delay = self.next_start - time.perf_counter()
                if delay <= 0:
                    break
                stopped.wait(delay)
            self.next_start = time.perf_counter() + self.interval


def download_tiles(config, tiles, directory, candidates, description, download_one):
    """Reuse cached files and download missing tiles in original manifest order.

    The caller fetches metadata once before entering this function. Only the
    main thread updates progress. Each HTTP worker owns and reuses its session;
    all sessions are closed after in-flight work has drained.
    """
    workers = worker_count(config)
    tiles = list(tiles)
    identities = [os.path.normcase(str(Path(directory) / f"{tile['id']}.tif")) for tile in tiles]
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate tile IDs would write to the same download file.')
    results = [None] * len(tiles)
    missing = []
    downloaded = reused = 0
    with bar(description, len(tiles)) as progress:
        for index, tile in enumerate(tiles):
            for cache in candidates:
                path = cache / f"{tile['id']}.tif"
                if cached(path, config['source'], tile, config):
                    results[index] = path
                    reused += 1
                    LOG.info('Reusing validated source tile %s', path)
                    progress.set_postfix(downloaded=downloaded, cached=reused, refresh=False)
                    progress.update(1)
                    break
            else:
                missing.append((index, tile))
        if not missing:
            return results

        workers = min(workers, len(missing))
        LOG.info('%s: %d cached, %d to download, %d HTTP workers',
                 description, reused, len(missing), workers)
        gate = RequestGate(config['request_pause_seconds'])
        stopped = threading.Event()
        local = threading.local()
        sessions = []
        sessions_lock = threading.Lock()

        def fetch(tile):
            if stopped.is_set():
                raise CancelledError('Download acquisition stopped.')
            if not hasattr(local, 'session'):
                local.session = requests.Session()
                local.session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
                with sessions_lock:
                    sessions.append(local.session)
            return download_one(local.session, config['source'], tile, directory, config,
                                request_gate=gate, stop_event=stopped)

        jobs = iter(missing)
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='dtm-download')
        pending = {}

        def submit_next():
            job = next(jobs, None)
            if job is not None:
                index, tile = job
                pending[pool.submit(fetch, tile)] = (index, tile)

        try:
            # Bound outstanding work so Ctrl+C does not leave a large queue.
            for _ in range(workers):
                submit_next()
            while pending:
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    index, tile = pending.pop(future)
                    try:
                        results[index] = future.result()
                    except Exception as exc:
                        raise RuntimeError(f'Failed to acquire {tile["id"]}: {exc}') from exc
                    downloaded += 1
                    progress.set_postfix(downloaded=downloaded, cached=reused, refresh=False)
                    progress.update(1)
                for _ in completed:
                    submit_next()
        except BaseException:
            stopped.set()
            for future in pending:
                future.cancel()
            LOG.warning('Stopping acquisition; waiting for active HTTP requests to finish. '
                        'Completed validated tiles remain reusable.')
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
            for session in sessions:
                session.close()
    return results
