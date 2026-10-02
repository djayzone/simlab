import json
import os
import threading
import time

from engine import DB_LOCK, WORLD_ID, connect, init_db
from hot_mechanics_engine import Engine as HotMechanicsEngine
from membership_cache import LivingMembershipCache
from spatial_index import LivingSpatialIndex, SpatialCollectionCache
from runtime_api import SimulationRuntime
import runtime_profiler


SNAPSHOT_INTERVAL = max(0.5, min(5.0, float(os.getenv('SIM_WORLD_SNAPSHOT_INTERVAL', '1.5'))))
PERSIST_INTERVAL = max(1.0, min(30.0, float(os.getenv('SIM_PERSIST_INTERVAL', '5.0'))))


class Engine(HotMechanicsEngine):
    """Durable simulation runtime with runtime-only optimisations."""

    def __init__(self):
        # The base constructor may call _load() or reset(), so membership state
        # must exist before delegating to it.
        self._living_membership = LivingMembershipCache()
        self._living_spatial = LivingSpatialIndex(cell_size=100.0)
        self._living_spatial_revision = -1
        self._resource_spatial = SpatialCollectionCache(cell_size=100.0)
        self._artifact_spatial = SpatialCollectionCache(cell_size=100.0)
        super().__init__()

    def _load(self):
        loaded = super()._load()
        if loaded:
            self._living_membership.changed('load')
            self._living_spatial_revision = -1
        return loaded

    def reset(self):
        # Core reset replaces the agents dictionary. Mark that boundary before
        # delegating; _new_agent() will then advance the revision for founders.
        with self.lock:
            self._living_membership.changed('reset')
            self._living_spatial_revision = -1
            return super().reset()

    def _new_agent(self, parents):
        agent = super()._new_agent(parents)
        self._living_membership.changed('agent_added')
        self._living_spatial_revision = -1
        return agent

    def _die(self, agent, reason):
        was_alive = bool(agent.get('alive'))
        result = super()._die(agent, reason)
        if was_alive and not agent.get('alive'):
            self._living_membership.changed('agent_died')
            self._living_spatial_revision = -1
        return result

    def living(self):
        """Return immutable living membership keyed by explicit revision."""
        return self._living_membership.snapshot(self.agents)

    def living_cache_status(self):
        with self.lock:
            return {
                **self._living_membership.status(),
                'immutable': True,
            }

    def _resource_items(self, resource_type):
        signature = (
            id(self.resources),
            len(self.resources),
            self.next_resource_id,
        )
        self._resource_spatial.refresh(
            signature,
            {
                'food': (
                    resource
                    for resource in self.resources.values()
                    if resource['type'] == 'food'
                ),
                'water': (
                    resource
                    for resource in self.resources.values()
                    if resource['type'] == 'water'
                ),
            },
        )
        return self._resource_spatial.view(resource_type)

    def _artifact_items(self):
        signature = (
            id(self.artifacts),
            len(self.artifacts),
            self.next_artifact_id,
        )
        self._artifact_spatial.refresh(
            signature,
            {'all': self.artifacts.values()},
        )
        return self._artifact_spatial.view('all')

    def _ensure_living_spatial(self, living):
        revision = self._living_membership.revision
        if self._living_spatial_revision != revision:
            self._living_spatial.rebuild(living)
            self._living_spatial_revision = revision

    def spatial_index_status(self):
        with self.lock:
            return {
                **self._living_spatial.status(),
                'membershipRevision': self._living_membership.revision,
                'indexedRevision': self._living_spatial_revision,
            }

    def _nearest(self, origin, items, max_distance, predicate=None):
        """Preserve exact nearest semantics while avoiding repeated full scans."""
        if self._resource_spatial.owns('food', items):
            return self._resource_spatial.nearest('food', origin, max_distance, predicate)
        if self._resource_spatial.owns('water', items):
            return self._resource_spatial.nearest('water', origin, max_distance, predicate)
        if self._artifact_spatial.owns('all', items):
            return self._artifact_spatial.nearest('all', origin, max_distance, predicate)
        if (
            isinstance(items, tuple)
            and items is self._living_membership.cached
            and self._living_membership.cached_revision == self._living_membership.revision
        ):
            self._ensure_living_spatial(items)
            return self._living_spatial.nearest(origin, max_distance, predicate)

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

    def _move_toward(self, agent, target, dt, multiplier=1.0):
        super()._move_toward(agent, target, dt, multiplier)
        if self._living_spatial_revision == self._living_membership.revision:
            self._living_spatial.update(agent)

    def persist_now(self):
        """Force a durable flush for callers using the explicit runtime API."""
        previous = getattr(self, '_runtime_last_persist_at', 0.0)
        self._runtime_last_persist_at = 0.0
        try:
            self._persist()
        except Exception:
            self._runtime_last_persist_at = previous
            raise

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


class WorldSnapshotCache:
    """Demand-driven stale-while-revalidate cache for serialized world snapshots."""

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


init_db()
ENGINE = Engine()
WORLD_CACHE = WorldSnapshotCache(ENGINE, SNAPSHOT_INTERVAL)

runtime_profiler.SIM_FILES.update({'simulation_runtime.py', 'membership_cache.py', 'spatial_index.py'})
PERF = runtime_profiler.RuntimeSampler(thread_names={'sim-engine'})
PERF.start()

RUNTIME = SimulationRuntime(ENGINE, WORLD_CACHE, PERF, PERSIST_INTERVAL)
