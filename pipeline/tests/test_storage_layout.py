"""Regional TIFF-only caches and writer locking."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from test_preparation import raster
from dtm.acquire import cached, download_tile, params, sha256, write_json
from dtm.countries.germany.nrw.acquisition import download
from dtm.paths import raw_directory, receipt_path, region_lock, scoped_root


class StorageLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_layout_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {'country': 'germany', 'region': 'nrw', 'cache_root': str(self.root / 'data'),
                       'output_root': str(self.root / 'data'), 'old_runs_root': str(self.root / 'data/old_runs'),
                       'logs_dir': str(self.root / 'logs'), 'download_attempts': 1, 'timeout_seconds': 1,
                       'request_pause_seconds': 0, 'reuse_cache': True,
                       'source': {'url': 'https://example.invalid', 'coverage': 'dgm', 'epsg': 25832,
                                  'resolution': 1}}
        self.tile = {'id': 'tile', 'bounds': [310000, 5740000, 310010, 5740010]}
        self.source = raster(self.root / 'source.tif', np.full((10, 10), 7), epsg=25832,
                             transform=(310000, 1, 0, 5740010, 0, -1))
        self.raw = raw_directory(self.config)
        self.raw.mkdir(parents=True)

    def session(self, payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_content.return_value = [payload]
        response.headers = {}
        response.url = self.config['source']['url']
        session = MagicMock()
        session.get.return_value = response
        return session

    def test_raw_contains_only_tiffs_with_external_receipts_and_failed_refresh_is_safe(self):
        config = self.config
        path = download_tile(self.session(self.source.read_bytes()), config['source'], self.tile, self.raw, config)
        receipt = receipt_path(path, config)
        self.assertTrue(receipt.is_file())
        self.assertFalse(path.with_suffix('.json').exists())
        self.assertTrue(cached(path, config['source'], self.tile, config))
        original = sha256(path)
        saved_receipt = receipt.read_bytes()
        config['reuse_cache'] = False
        with self.assertRaises(RuntimeError):
            download_tile(self.session(b'<Exception>failure</Exception>'), config['source'], self.tile, self.raw, config)
        self.assertEqual(sha256(path), original)
        self.assertEqual(receipt.read_bytes(), saved_receipt)
        self.assertEqual(list(self.raw.iterdir()), [path])
        self.assertFalse(any((scoped_root(config, 'logs_dir') / 'download_work').iterdir()))

    def test_runtime_never_searches_old_runs_or_other_regions(self):
        for directory in (scoped_root(self.config, 'old_runs_root') / 'old/raw_nrw_tiles',
                          self.root / 'data/germany/rlp/raw_tiles'):
            directory.mkdir(parents=True)
            path = directory / 'tile.tif'
            path.write_bytes(self.source.read_bytes())
            write_json(path.with_suffix('.json'), {'source': self.config['source'],
                       'request': params(self.config['source'], self.tile), 'sha256': sha256(path)})
        with patch('dtm.countries.germany.nrw.acquisition.metadata'), \
             patch('dtm.countries.germany.nrw.acquisition.download_tile') as fetch:
            download(self.config, {'tiles': [self.tile]}, self.root / 'run')
            fetch.assert_called_once()
            self.assertEqual(fetch.call_args.args[3], self.raw)

    def test_lock_is_region_scoped_and_released_after_errors(self):
        with region_lock(self.config):
            with self.assertRaisesRegex(RuntimeError, 'already in use'):
                with region_lock(self.config):
                    pass
            with region_lock({**self.config, 'region': 'rlp'}):
                pass
        with self.assertRaises(ValueError):
            with region_lock(self.config):
                raise ValueError('failed run')
        self.assertFalse((scoped_root(self.config, 'logs_dir') / 'active.lock').exists())
