import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from engine import DB_LOCK, WORLD_ID, connect, init_db
from hot_mechanics_engine import Engine as HotMechanicsEngine
from runtime_profiler import RuntimeSampler

MAX_BODY = 256 * 1024
PORT = int(os.getenv('PORT', '8081'))
SNAPSHOT_INTERVAL = max(0.5, min(5.0, float(os.getenv('SIM_WORLD_SNAPSHOT_INTERVAL', '1.5'))))
PERSIST_INTERVAL = max(1.0, min(30.0, float(os.getenv('SIM_PERSIST_INTERVAL', '5.0'))))


class Engine(HotMechanicsEngine):
    """Durable simulation runtime with FK-safe persistence ordering."""

    def living(self):
        """Return immutable living membership without rebuilding it on every call.

        The cached tuple contains live agent dictionaries, so positions, needs and
        knowledge continue changing normally. Only membership is immutable. It is
        rebuilt as soon as births, deaths, agent-count changes or a reset replaces
        the agents dictionary.
        """
        agents = getattr(self, 'agents', {})
        signature = (
            id(agents),
            len(agents),
            getattr(self, 'births', 0),
            getattr(self, 'deaths', 0),
        )
        if getattr(self, '_runtime_living_signature', None) == signature:
            self._runtime_living_cache_hits = getattr(self, '_runtime_living_cache_hits', 0) + 1
            return self._runtime_living_cache

        living = tuple(super().living())
        self._runtime_living_cache = living
        self._runtime_living_signature = signature
        self._runtime_living_cache_misses = getattr(self, '_runtime_living_cache_misses', 0) + 1
        return living

    def living_cache_status(self):
        return {
            'hits': getattr(self, '_runtime_living_cache_hits', 0),
            'misses': getattr(self, '_runtime_living_cache_misses', 0),
            'size': len(getattr(self, '_runtime_living_cache', ())),
            'immutable': True,
        }

    def _nearest(self, origin, items, max_distance, predicate=None):
        """Find the same nearest candidate as the core implementation without sqrt.

        The original hot path calls math.hypot() for every candidate. Since this
        method only compares distances, squared Euclidean distance is equivalent
        and avoids the square root entirely. The strict max-distance boundary is
        preserved (`distance < max_distance`).
        """
        best = None
        best_d2 = max_distance * max_distance
        ox = origin['x']
        oy = origin['y']
        for item in items:
            if predicate and not predicate(item):
                continue
            dx = ox - item['x']
            dy = oy - item['y']
            d2 = dx * dx + dy * dy
            if d2 < best_d2:
                best = item
                best_d2 = d2
        return best

    def _persist(self, full_reset=False):
        now = time.monotonic()
        previous = getattr(self, '_runtime_last_persist_at', 0.0)
        if not full_reset and previous and now - previous < PERSIST_INTERVAL:
            return

        if not full_reset:
            self._runtime_last_persist_at = now

        try:
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
                                agent['id'], WORLD_ID, agent['sex'], agent['x'], agent['y'], agent['age'], agent['health'], agent['energy'],
                                agent['hunger'], agent['thirst'], agent['social_need'], agent.get('food_store', 0), agent.get('mate_cooldown', 0),
                                1 if agent.get('alive', True) else 0, agent.get('action') or 'idle', agent.get('action_detail') or '',
                                agent.get('target_x'), agent.get('target_y'), agent['birth_year'], agent.get('death_year'),
                            ))
                        conn.commit()
                    finally:
                        conn.close()
            super()._persist(full_reset=full_reset)
        except Exception:
            if not full_reset:
                self._runtime_last_persist_at = previous
            raise


init_db()
ENGINE = Engine()


class WorldSnapshotCache:
    """Serve stale snapshots immediately and refresh only when clients need them.

    The previous periodic refresher rebuilt the full world even with no UI client.
    This stale-while-revalidate cache keeps request latency low while eliminating
    idle snapshot CPU. At most one refresh can run at a time.
    """

    def __init__(self, engine, interval):
        self.engine = engine
        self.interval = interval
        self.lock = threading.Lock()
        self.body = None
        self.generated_at = 0.0
        self.duration_ms = 0.0
        self.generation = 0
        self.error = None
        self.request_count = 0
        self.refresh_count = 0
        self.refreshing = False
        self._refresh_event = threading.Event()
        self._ready_event = threading.Event()
        threading.Thread(target=self._worker, name='simlab-world-snapshot', daemon=True).start()

    def _refresh(self):
        with self.lock:
            if self.refreshing:
                return False
            self.refreshing = True
        started = time.monotonic()
        try:
            payload = self.engine.world_view()
            body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
            duration_ms = (time.monotonic() - started) * 1000
            with self.lock:
                self.body = body
                self.generated_at = time.time()
                self.duration_ms = duration_ms
                self.generation += 1
                self.refresh_count += 1
                self.error = None
                self._ready_event.set()
            return True
        except Exception as exc:
            with self.lock:
                self.error = f'{type(exc).__name__}: {exc}'
            return False
        finally:
            with self.lock:
                self.refreshing = False

    def _worker(self):
        while True:
            self._refresh_event.wait()
            self._refresh_event.clear()
            with self.lock:
                age = time.time() - self.generated_at if self.generated_at else None
                needs_refresh = self.body is None or age is None or age >= self.interval
            if needs_refresh:
                self._refresh()

    def _request_async_refresh(self):
        self._refresh_event.set()

    def get(self):
        with self.lock:
            self.request_count += 1
            body = self.body
            age = time.time() - self.generated_at if self.generated_at else None
        if body is None:
            built_here = self._refresh()
            if not built_here:
                self._ready_event.wait(timeout=10.0)
            with self.lock:
                body = self.body
                error = self.error
            if body is None:
                raise RuntimeError(error or 'initial world snapshot unavailable')
            return body
        if age is None or age >= self.interval:
            self._request_async_refresh()
        return body

    def status(self):
        with self.lock:
            return {
                'generation': self.generation,
                'ageMs': round(max(0.0, time.time() - self.generated_at) * 1000, 1) if self.generated_at else None,
                'buildMs': round(self.duration_ms, 1),
                'intervalMs': round(self.interval * 1000),
                'requestCount': self.request_count,
                'refreshCount': self.refresh_count,
                'refreshing': self.refreshing,
                'mode': 'stale-while-revalidate',
                'error': self.error,
            }


WORLD_CACHE = WorldSnapshotCache(ENGINE, SNAPSHOT_INTERVAL)
PERF = RuntimeSampler()
PERF.start()


class Handler(BaseHTTPRequestHandler):
    server_version = 'SIMLabEngine/7'

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
            self._json(200, {
                'ok': True,
                'component': 'engine',
                'snapshot': WORLD_CACHE.status(),
                'perf': PERF.status(),
                'persistence': {'intervalMs': round(PERSIST_INTERVAL * 1000)},
                'livingCache': ENGINE.living_cache_status(),
            })
            return
        if path == '/api/world':
            try:
                self._write(200, WORLD_CACHE.get())
            except RuntimeError as exc:
                self._json(503, {'error': 'snapshot_unavailable', 'detail': str(exc)})
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
        self._json(404, {'error': 'not_found'})

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


def main():
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
