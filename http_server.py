import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from simulation_runtime import RUNTIME


MAX_BODY = 256 * 1024
PORT = int(os.getenv('PORT', '8081'))


class Handler(BaseHTTPRequestHandler):
    server_version = 'SIMLabEngine/8'

    def log_message(self, fmt, *args):
        return

    def _write(self, status, body, content_type='application/json; charset=utf-8'):
        try:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
        self._write(status, body)

    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0') or '0')
        if length <= 0 or length > MAX_BODY:
            raise ValueError('invalid body size')
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/healthz':
            health = RUNTIME.probe_health()
            self._json(200 if health.get('ok') else 503, health)
            return
        if path == '/api/world':
            try:
                self._write(200, RUNTIME.snapshot_bytes())
            except RuntimeError as exc:
                self._json(503, {'error': 'snapshot_unavailable', 'detail': str(exc)})
            return
        if path.startswith('/api/agents/'):
            try:
                agent_id = int(path.rsplit('/', 1)[1])
            except ValueError:
                self._json(400, {'error': 'bad_agent_id'})
                return
            data = RUNTIME.agent(agent_id)
            self._json(200 if data else 404, data or {'error': 'not_found'})
            return
        self._json(404, {'error': 'not_found'})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self._read_json() if path != '/api/reset' else {}
            if path == '/api/control':
                self._json(200, RUNTIME.control(data)); return
            if path == '/api/settings':
                self._json(200, RUNTIME.update_settings(data.get('settings', {}))); return
            if path == '/api/inject':
                self._json(200, RUNTIME.inject(data.get('type'), data.get('count', 1))); return
            if path == '/api/shock':
                self._json(200, RUNTIME.shock(data.get('type'))); return
            if path == '/api/weather/control':
                self._json(200, RUNTIME.update_weather_control(data)); return
            if path == '/api/reset':
                self._json(200, RUNTIME.reset()); return
            self._json(404, {'error': 'not_found'})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {'error': 'bad_request', 'detail': str(exc)})


def main():
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
