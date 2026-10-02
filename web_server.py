import json
import mimetypes
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

STATIC_ROOT = Path(os.getenv('SIM_STATIC_ROOT', '/app'))
ENGINE_URL = os.getenv('SIM_ENGINE_URL', 'http://sim-lab-engine:8081').rstrip('/')
ENGINE_TIMEOUT = max(1.0, min(30.0, float(os.getenv('SIM_ENGINE_TIMEOUT', '8'))))
PORT = int(os.getenv('PORT', '8080'))
MAX_BODY = 256 * 1024
STATIC_FILES = {'index.html', 'app.js', 'weather.js', 'persistence.js', 'styles.css', 'mobile_ux.css', 'mobile_ux.js'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'SIMLabWeb/3'

    def log_message(self, fmt, *args):
        return

    def _security_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Cache-Control', 'no-cache')

    def _write(self, status, body, content_type='application/json; charset=utf-8'):
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _json(self, status, payload):
        self._write(status, json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode())

    def _proxy(self, method):
        parsed = urlparse(self.path)
        target = f'{ENGINE_URL}{parsed.path}' + (f'?{parsed.query}' if parsed.query else '')
        body = None
        if method == 'POST':
            length = int(self.headers.get('Content-Length', '0') or '0')
            if length > MAX_BODY:
                self._json(413, {'error': 'body_too_large'}); return
            body = self.rfile.read(length) if length else b''
        headers = {'Accept': 'application/json'}
        if body is not None:
            headers['Content-Type'] = self.headers.get('Content-Type', 'application/json')
        request = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=ENGINE_TIMEOUT) as response:
                payload = response.read()
                self._write(response.status, payload, response.headers.get('Content-Type', 'application/json; charset=utf-8'))
        except urllib.error.HTTPError as exc:
            self._write(exc.code, exc.read(), exc.headers.get('Content-Type', 'application/json; charset=utf-8'))
        except (urllib.error.URLError, TimeoutError, OSError):
            self._json(503, {'error': 'engine_unavailable', 'detail': 'Le moteur de simulation redémarre, se resynchronise ou est momentanément saturé. L’interface reste disponible.'})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/healthz':
            self._json(200, {'ok': True, 'component': 'web'}); return
        if path == '/engine-healthz':
            self.path = '/healthz'; self._proxy('GET'); return
        if path.startswith('/api/'):
            self._proxy('GET'); return
        self._serve_static(path)

    def do_POST(self):
        if urlparse(self.path).path.startswith('/api/'):
            self._proxy('POST'); return
        self._json(404, {'error': 'not_found'})

    def _serve_static(self, path):
        name = 'index.html' if path in ('', '/') else path.lstrip('/')
        if name not in STATIC_FILES:
            self._json(404, {'error': 'not_found'}); return
        try:
            body = (STATIC_ROOT / name).read_bytes()
        except FileNotFoundError:
            self._json(404, {'error': 'not_found'}); return
        if name == 'index.html':
            body = body.replace(b'</head>', b'<link rel="stylesheet" href="/mobile_ux.css"></head>')
            body = body.replace(b'</body>', b'<script src="/weather.js"></script><script src="/mobile_ux.js"></script></body>')
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self._write(200, body, f'{content_type}; charset=utf-8')


def main():
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
