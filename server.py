import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from engine import DB_LOCK, WORLD_ID, connect, init_db
from weather_control_engine import Engine as WeatherEngine

STATIC_ROOT = Path(os.getenv('SIM_STATIC_ROOT', '/app'))
STATIC_FILES = {'index.html', 'app.js', 'weather.js', 'persistence.js', 'styles.css'}
MAX_BODY = 256 * 1024
PORT = int(os.getenv('PORT', '8080'))


class Engine(WeatherEngine):
    """Runtime guard: ensure every in-memory agent exists before FK-dependent rows are persisted."""

    def _persist(self, full_reset=False):
        if not full_reset and getattr(self, 'agents', None):
            valid_ids = set(self.agents)
            for agent in self.agents.values():
                agent['relations'] = {
                    other_id: relation
                    for other_id, relation in agent.get('relations', {}).items()
                    if other_id in valid_ids
                }
            with DB_LOCK:
                conn = connect()
                try:
                    conn.execute('BEGIN IMMEDIATE')
                    for agent in self.agents.values():
                        conn.execute('''
                            INSERT OR IGNORE INTO agents(
                              id,world_id,sex,x,y,age,health,energy,hunger,thirst,social_need,
                              food_store,mate_cooldown,alive,action,action_detail,target_x,target_y,
                              birth_year,death_year
                            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ''', (
                            agent['id'], WORLD_ID, agent['sex'], agent['x'], agent['y'], agent['age'],
                            agent['health'], agent['energy'], agent['hunger'], agent['thirst'],
                            agent['social_need'], agent.get('food_store', 0), agent.get('mate_cooldown', 0),
                            1 if agent.get('alive', True) else 0, agent.get('action') or 'idle',
                            agent.get('action_detail') or '', agent.get('target_x'), agent.get('target_y'),
                            agent['birth_year'], agent.get('death_year'),
                        ))
                    conn.commit()
                finally:
                    conn.close()
        super()._persist(full_reset=full_reset)


init_db()
ENGINE = Engine()


class Handler(BaseHTTPRequestHandler):
    server_version = 'SIMLab/5'

    def log_message(self, fmt, *args):
        return

    def _security_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('Cache-Control', 'no-cache')

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0') or '0')
        if length <= 0 or length > MAX_BODY:
            raise ValueError('invalid body size')
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/healthz':
            self._json(200, {'ok': True})
            return
        if path == '/api/world':
            self._json(200, ENGINE.world_view())
            return
        if path.startswith('/api/agents/'):
            try:
                agent_id = int(path.rsplit('/', 1)[1])
            except ValueError:
                self._json(400, {'error': 'bad_agent_id'})
                return
            data = ENGINE.agent_view(agent_id)
            self._json(200 if data else 404, data or {'error': 'not_found'})
            return
        self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self._read_json() if path != '/api/reset' else {}
            if path == '/api/control':
                self._json(200, ENGINE.command(data)); return
            if path == '/api/settings':
                self._json(200, {'settings': ENGINE.update_settings(data.get('settings', {}))}); return
            if path == '/api/inject':
                ENGINE.inject(data.get('type'), data.get('count', 1)); self._json(200, {'ok': True}); return
            if path == '/api/shock':
                ENGINE.shock(data.get('type')); self._json(200, {'ok': True}); return
            if path == '/api/weather/control':
                self._json(200, {'control': ENGINE.update_weather_control(data)}); return
            if path == '/api/reset':
                ENGINE.reset(); self._json(200, {'ok': True}); return
            self._json(404, {'error': 'not_found'})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {'error': 'bad_request', 'detail': str(exc)})

    def _serve_static(self, path):
        name = 'index.html' if path in ('', '/') else path.lstrip('/')
        if name not in STATIC_FILES:
            self._json(404, {'error': 'not_found'}); return
        try:
            body = (STATIC_ROOT / name).read_bytes()
        except FileNotFoundError:
            self._json(404, {'error': 'not_found'}); return
        if name == 'index.html':
            body = body.replace(b'</body>', b'<script src="/weather.js"></script></body>')
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', f'{content_type}; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)


def main():
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
