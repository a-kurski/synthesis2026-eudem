"""Resumable archive transport, with no live downloads."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

from dtm.countries.germany.archive import archive
from dtm.paths import scoped_root


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dtm_archive_')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.payload = b'0123456789abcdefghij'
        self.config = {'country': 'germany', 'region': 'hessen', 'cache_root': str(root / 'data'),
                       'logs_dir': str(root / 'logs'), 'reuse_cache': True,
                       'download_attempts': 2, 'timeout_seconds': 1,
                       'source': {'url': 'https://example.invalid/dehessen.tar',
                                  'size': len(self.payload), 'md5': hashlib.md5(self.payload).hexdigest()}}
        self.path = scoped_root(self.config, 'cache_root') / 'source_archive/dehessen.tar'
        self.path.parent.mkdir(parents=True)
        self.part = self.path.with_suffix('.tar.part')
        self.log = scoped_root(self.config, 'logs_dir')
        sleeper = patch('dtm.countries.germany.archive.time.sleep')
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def download(self):
        return archive(self.config, self.log, filename='dehessen.tar', label='Hessen')

    def response(self, data, *, start=0, status=200, headers=None):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = status
        response.headers = {'Content-Length': str(len(self.payload) - start)}
        if status == 206:
            response.headers['Content-Range'] = f'bytes {start}-{len(self.payload)-1}/{len(self.payload)}'
        if headers:
            response.headers.update(headers)
        response.iter_content.return_value = data
        return response

    def assert_result(self):
        self.assertEqual(self.path.read_bytes(), self.payload)
        self.assertFalse(self.part.exists())
        self.assertFalse((self.log / 'dehessen.tar.resume.json').exists())

    def test_connection_failure_retries_at_saved_offset_and_logs_reason(self):
        def interrupted():
            yield self.payload[:15]
            raise requests.ConnectionError('connection reset by peer')
        responses = [self.response(interrupted()), self.response([self.payload[15:]], start=15, status=206)]
        with patch('requests.Session.get', side_effect=responses) as get, self.assertLogs('dtm', level='INFO') as logs:
            self.download()
        self.assertEqual(get.call_args_list[1].kwargs['headers']['Range'], 'bytes=15-')
        self.assertTrue(any('connection reset by peer' in item for item in logs.output))
        self.assert_result()

    def test_exhausted_retries_and_next_invocation_resume(self):
        self.config['download_attempts'] = 1
        with patch('requests.Session.get', return_value=self.response([self.payload[:7]])):
            with self.assertRaisesRegex(RuntimeError, '--reuse-cache'):
                self.download()
        self.assertEqual(self.part.read_bytes(), self.payload[:7])
        with patch('requests.Session.get', return_value=self.response([self.payload[7:]], start=7, status=206)) as get:
            self.download()
            self.assertEqual(get.call_args.kwargs['headers'], {'Range': 'bytes=7-'})
        self.assert_result()

    def test_keyboard_interrupt_preserves_partial_for_next_invocation(self):
        def interrupted():
            yield self.payload[:8]
            raise KeyboardInterrupt()
        with patch('requests.Session.get', return_value=self.response(interrupted())), self.assertRaises(KeyboardInterrupt):
            self.download()
        self.assertEqual(self.part.read_bytes(), self.payload[:8])
        with patch('requests.Session.get', return_value=self.response([self.payload[8:]], start=8, status=206)):
            self.download()
        self.assert_result()

    def test_legacy_partial_without_receipt_resumes_and_checks_whole_file(self):
        self.part.write_bytes(self.payload[:10])
        with patch('requests.Session.get', return_value=self.response([self.payload[10:]], start=10, status=206)) as get:
            self.download()
            self.assertEqual(get.call_args.kwargs['headers'], {'Range': 'bytes=10-'})
        self.assert_result()

    def test_server_ignoring_range_preserves_prefix_and_retries_same_offset(self):
        self.part.write_bytes(self.payload[:12])
        ignored = self.response([self.payload])
        resumed = self.response([self.payload[12:]], start=12, status=206)
        with patch('requests.Session.get', side_effect=[ignored, resumed]) as get:
            self.download()
        ignored.iter_content.assert_not_called()
        self.assertEqual([call.kwargs['headers'] for call in get.call_args_list],
                         [{'Range': 'bytes=12-'}, {'Range': 'bytes=12-'}])
        self.assert_result()

    def test_persistently_ignored_range_fails_without_discarding_prefix(self):
        self.part.write_bytes(self.payload[:12])
        with patch('requests.Session.get', return_value=self.response([self.payload])):
            with self.assertRaisesRegex(RuntimeError, 'Server ignored Range'):
                self.download()
        self.assertEqual(self.part.read_bytes(), self.payload[:12])

    def test_bad_response_headers_never_modify_existing_partial(self):
        self.config['download_attempts'] = 1
        for headers in ({'Content-Range': 'bytes 9-19/20'}, {'Content-Range': 'bytes 10-19/21'},
                        {'Content-Range': 'garbage'}, {'Content-Length': '11'}, {'Content-Encoding': 'gzip'}):
            with self.subTest(headers=headers):
                self.part.write_bytes(self.payload[:10])
                response = self.response([self.payload[10:]], start=10, status=206, headers=headers)
                with patch('requests.Session.get', return_value=response), self.assertRaises(RuntimeError):
                    self.download()
                self.assertEqual(self.part.read_bytes(), self.payload[:10])
                response.iter_content.assert_not_called()

    def test_full_partial_is_verified_and_published_without_http(self):
        self.part.write_bytes(self.payload)
        with patch('requests.Session.get') as get:
            self.download()
            get.assert_not_called()
        self.assert_result()

    def test_checksum_failure_preserves_completed_archive_and_restarts_from_zero(self):
        self.config['reuse_cache'] = False
        old = b'previous completed archive'
        self.path.write_bytes(old)
        self.config['download_attempts'] = 1
        with patch('requests.Session.get', return_value=self.response([b'x' * len(self.payload)])):
            with self.assertRaisesRegex(RuntimeError, 'MD5 mismatch'):
                self.download()
        self.assertEqual(self.path.read_bytes(), old)
        self.assertFalse(self.part.exists())
        self.config['reuse_cache'] = True
        with patch('requests.Session.get', return_value=self.response([self.payload])) as get:
            self.download()
            self.assertEqual(get.call_args.kwargs['headers'], {})
        self.assert_result()

    def test_corrupt_prefix_cannot_pass_suffix_only_checksum(self):
        self.part.write_bytes(b'x' * 10)
        responses = [self.response([self.payload[10:]], start=10, status=206), self.response([self.payload])]
        with patch('requests.Session.get', side_effect=responses) as get:
            self.download()
        self.assertEqual(get.call_args_list[0].kwargs['headers'], {'Range': 'bytes=10-'})
        self.assertEqual(get.call_args_list[1].kwargs['headers'], {})
        self.assert_result()

    def test_source_change_or_explicit_fresh_download_does_not_resume_stale_bytes(self):
        for fresh in (False, True):
            with self.subTest(fresh=fresh):
                self.path.unlink(missing_ok=True)
                self.part.write_bytes(self.payload[:10])
                self.log.mkdir(parents=True, exist_ok=True)
                (self.log / 'dehessen.tar.resume.json').write_text(json.dumps({'url': 'old source'}))
                self.config['reuse_cache'] = not fresh
                with patch('requests.Session.get', return_value=self.response([self.payload])) as get:
                    self.download()
                    self.assertEqual(get.call_args.kwargs['headers'], {})
                self.assert_result()

    def test_oversized_response_is_rejected_before_writing_excess(self):
        self.config['download_attempts'] = 1
        with patch('requests.Session.get', return_value=self.response([self.payload + b'excess'])):
            with self.assertRaisesRegex(RuntimeError, 'exceeds'):
                self.download()
        self.assertEqual(self.part.read_bytes(), b'')
        self.assertFalse(self.path.exists())
