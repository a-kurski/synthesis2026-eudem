"""Exercise the real Requests streaming stack against a deliberately failing HTTP server."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

import requests

from dtm.countries.germany.archive import archive


class ArchiveHTTPTests(unittest.TestCase):
    def run_transfer(self, faults, attempts=4, timeout=2):
        payload = bytes(range(256)) * (4 * 1024 * 1024 // 256)
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                header = self.headers.get('Range')
                start = int(header[6:-1]) if header else 0
                observed.append(start)
                fault = faults[len(observed)-1] if len(observed) <= len(faults) else None
                if fault == 'http503':
                    self.send_error(503)
                    return
                if fault == 'ignore_range':
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    return
                self.send_response(206 if start else 200)
                self.send_header('Content-Length', str(len(payload)-start))
                if start:
                    self.send_header('Content-Range', f'bytes {start}-{len(payload)-1}/{len(payload)}')
                self.end_headers()
                if fault in ('disconnect', 'stall'):
                    # Flush exactly one client chunk, then terminate or stall.
                    self.wfile.write(payload[start:start+1024*1024])
                    self.wfile.flush()
                    if fault == 'stall':
                        shutdown.wait(1)
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                self.wfile.write(payload[start:])

        shutdown = threading.Event()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='archive_http_') as temp:
                config = {'country': 'germany', 'region': 'hessen', 'cache_root': temp,
                          'logs_dir': str(Path(temp) / 'logs'), 'reuse_cache': True,
                          'download_attempts': attempts, 'timeout_seconds': timeout,
                          'source': {'url': f'http://127.0.0.1:{server.server_port}/archive.tar',
                                     'size': len(payload), 'md5': hashlib.md5(payload).hexdigest()}}
                # Keep actual HTTP/Requests behavior; only remove backoff and
                # environment proxy settings from this loopback-only fixture.
                session = requests.Session()
                session.trust_env = False
                with patch('dtm.countries.germany.archive.requests.Session', return_value=session), \
                        patch('dtm.countries.germany.archive.time.sleep'), self.assertLogs('dtm', level='INFO') as logs:
                    path = archive(config, Path(temp), filename='dehessen.tar', label='Hessen')
                self.assertEqual(path.read_bytes(), payload)
                self.assertFalse(path.with_suffix('.tar.part').exists())
                return observed, logs.output
        finally:
            shutdown.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_repeated_real_socket_disconnects_resume_without_byte_loss(self):
        offsets, logs = self.run_transfer(['disconnect', 'disconnect', 'disconnect'])
        self.assertEqual(offsets, [0, 1048576, 2097152, 3145728])
        self.assertTrue(any('ChunkedEncodingError' in line for line in logs))

    def test_read_timeout_preserves_received_prefix(self):
        offsets, logs = self.run_transfer(['stall'], timeout=.1)
        self.assertEqual(offsets, [0, 1048576])
        self.assertTrue(any('timed out' in line for line in logs))

    def test_http_error_during_resume_does_not_erase_prefix(self):
        offsets, logs = self.run_transfer(['disconnect', 'http503'])
        self.assertEqual(offsets, [0, 1048576, 1048576])
        self.assertTrue(any('503' in line for line in logs))

    def test_ignored_range_during_resume_does_not_erase_prefix(self):
        offsets, logs = self.run_transfer(['disconnect', 'ignore_range'])
        self.assertEqual(offsets, [0, 1048576, 1048576])
        self.assertTrue(any('Server ignored Range' in line for line in logs))
