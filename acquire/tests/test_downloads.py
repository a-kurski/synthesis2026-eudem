"""Offline concurrent acquisition tests using real TIFFs and simulated HTTP."""
from concurrent.futures import Future
from contextlib import contextmanager
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
import requests

import test_preparation as helpers
from dtm.acquire import cached, download_tile
from dtm.downloads import download_tiles, worker_count


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_download_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'downloads'
        self.output.mkdir()
        self.tiles = []
        self.payloads = {}
        for i in range(4):
            x = 200000 + i * 8
            self.tiles.append({'id': f'tile_{i}', 'bounds': [x, 425000, x + 8, 425008]})
            path = helpers.raster(self.root / f'input_{i}.tif', np.full((16, 16), i),
                                  transform=(x, .5, 0, 425008, 0, -.5))
            self.payloads[f'x({x},{x + 8})'] = path.read_bytes()
        self.config = {'source': {'url': 'https://example.invalid/wcs', 'coverage': 'dtm_05m',
                                  'epsg': 28992, 'resolution': .5},
                       'download_workers': 2, 'download_attempts': 2,
                       'request_pause_seconds': .02, 'timeout_seconds': 2}

    @contextmanager
    def transport(self, fail_first=False, bad_key=None):
        state = {'sessions': [], 'calls': [], 'active': 0, 'peak': 0, 'failed': False}
        lock = threading.Lock()
        payloads = self.payloads

        class Response:
            url = 'https://example.invalid/wcs'
            headers = {'Content-Type': 'image/tiff'}

            def __init__(self, key, failure):
                self.key, self.failure = key, failure

            def __enter__(self):
                return self

            def __exit__(self, *args):
                with lock:
                    state['active'] -= 1

            def raise_for_status(self):
                if self.failure:
                    raise requests.HTTPError('temporary server failure')

            def iter_content(self, size):
                # Hold the first transfer longer to exercise completion ordering.
                time.sleep(.12 if self.key == 'x(200000,200008)' else .05)
                yield b'<Exception>bad response</Exception>' if self.key == bad_key else payloads[self.key]

        class Session:
            def __init__(self):
                self.headers = {}
                self.owner = threading.get_ident()
                self.closed = False
                with lock:
                    state['sessions'].append(self)

            def get(self, url, *, params, stream, timeout):
                if self.owner != threading.get_ident():
                    raise AssertionError('HTTP session shared across worker threads')
                with lock:
                    state['calls'].append((time.perf_counter(), params['SUBSET'][0]))
                    state['active'] += 1
                    state['peak'] = max(state['peak'], state['active'])
                    failure = fail_first and not state['failed']
                    state['failed'] |= failure
                return Response(params['SUBSET'][0], failure)

            def close(self):
                self.closed = True

        with patch('dtm.downloads.requests.Session', Session):
            yield state

    def run_download(self, candidates=()):
        return download_tiles(self.config, self.tiles, self.output, candidates,
                              'Test downloads', download_tile)

    def test_concurrency_order_private_sessions_pacing_and_cache_reuse(self):
        with self.transport() as state:
            paths = self.run_download()
            self.assertEqual([p.stem for p in paths], [t['id'] for t in self.tiles])
            self.assertEqual(state['peak'], 2)
            self.assertEqual(len(state['sessions']), 2)
            self.assertTrue(all(s.closed for s in state['sessions']))
            for (a, _), (b, _) in zip(state['calls'], state['calls'][1:]):
                self.assertGreaterEqual(b - a, .018)
            self.assertTrue(all(cached(p, self.config['source'], tile) for p, tile in zip(paths, self.tiles)))
            # All-cache runs need neither HTTP requests nor worker sessions.
            again = self.run_download([self.output])
            self.assertEqual(again, paths)
            self.assertEqual(len(state['calls']), 4)
            self.assertEqual(len(state['sessions']), 2)
        self.assertFalse(list(self.output.glob('*.part')))

    def test_retry_is_validated_and_also_rate_limited(self):
        with self.transport(fail_first=True) as state:
            paths = self.run_download()
            self.assertEqual(len(state['calls']), 5)
            self.assertTrue(all(cached(p, self.config['source'], t) for p, t in zip(paths, self.tiles)))
            for (a, _), (b, _) in zip(state['calls'], state['calls'][1:]):
                self.assertGreaterEqual(b - a, .018)
        self.assertFalse(list(self.output.glob('*.part')))

    def test_failure_preserves_completed_downloads_and_rerun_recovers(self):
        self.config.update(download_workers=1, download_attempts=1)
        with self.transport(bad_key='x(200008,200016)') as state:
            with self.assertRaisesRegex(RuntimeError, 'tile_1'):
                self.run_download()
            self.assertEqual(len(state['calls']), 2)
            self.assertTrue(all(s.closed for s in state['sessions']))
        self.assertTrue(cached(self.output / 'tile_0.tif', self.config['source'], self.tiles[0]))
        self.assertFalse((self.output / 'tile_1.json').exists())
        self.assertFalse(list(self.output.glob('*.part')))
        with self.transport() as state:
            self.run_download([self.output])
            self.assertEqual(len(state['calls']), 3)

    def test_interrupt_cancels_bounded_queue_and_signals_workers(self):
        futures = [Future(), Future()]
        with patch('dtm.downloads.ThreadPoolExecutor') as constructor, \
             patch('dtm.downloads.wait', side_effect=KeyboardInterrupt):
            pool = constructor.return_value
            pool.submit.side_effect = futures
            with self.assertRaises(KeyboardInterrupt):
                self.run_download()
            self.assertEqual(pool.submit.call_count, 2)
            self.assertTrue(all(f.cancelled() for f in futures))
            # Even an already-dispatched worker must not start a request after stop.
            fetch, tile = pool.submit.call_args.args
            from concurrent.futures import CancelledError
            with self.assertRaises(CancelledError):
                fetch(tile)
            pool.shutdown.assert_called_once_with(wait=True, cancel_futures=True)

    def test_invalid_workers_and_duplicate_ids_are_rejected(self):
        self.assertEqual(worker_count({}), 1)
        for value in (0, -1, True, 2.5, '4', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                worker_count({'download_workers': value})
        self.tiles.append(self.tiles[0])
        with self.transport() as state:
            with self.assertRaisesRegex(ValueError, 'Duplicate tile IDs'):
                self.run_download()
            self.assertFalse(state['calls'])
