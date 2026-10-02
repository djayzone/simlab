import threading
import unittest

from runtime_api import SimulationRuntime


class FakeEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.year = 2.0
        self.ticks = 0
        self.resets = 0
        self.persists = 0

    def _tick(self):
        self.ticks += 1
        self.year += 0.01

    def reset(self):
        self.resets += 1

    def world_view(self):
        return {'year': self.year, 'agents': []}

    def persist_now(self):
        self.persists += 1

    def agent_view(self, agent_id):
        return {'id': agent_id} if agent_id == 7 else None

    def command(self, payload):
        return {'command': payload}

    def update_settings(self, settings):
        return settings

    def inject(self, kind, count):
        self.injected = (kind, count)

    def shock(self, kind):
        self.shocked = kind

    def update_weather_control(self, payload):
        return payload

    def living_cache_status(self):
        return {'hits': 3, 'misses': 1, 'size': 2, 'immutable': True}


class FakeCache:
    def get(self):
        return b'{"year":2}'

    def status(self):
        return {'generation': 4, 'ageMs': 10.0}


class FakeProfiler:
    def status(self):
        return {'generation': 2}


class SimulationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.engine = FakeEngine()
        self.runtime = SimulationRuntime(self.engine, FakeCache(), FakeProfiler(), 5.0)

    def test_tick_is_bounded_and_serialized_by_engine_lock(self):
        result = self.runtime.tick(3)
        self.assertEqual(self.engine.ticks, 3)
        self.assertEqual(result['steps'], 3)
        self.assertAlmostEqual(result['simulationYear'], 2.03)
        with self.assertRaises(ValueError):
            self.runtime.tick(121)

    def test_snapshot_contract_does_not_expose_engine_object(self):
        self.assertEqual(self.runtime.snapshot(), {'year': 2.0, 'agents': []})
        self.assertEqual(self.runtime.snapshot_bytes(), b'{"year":2}')

    def test_reset_and_explicit_persist_delegate_through_runtime_contract(self):
        self.assertEqual(self.runtime.reset(), {'ok': True})
        self.assertEqual(self.runtime.persist(), {'ok': True})
        self.assertEqual(self.engine.resets, 1)
        self.assertEqual(self.engine.persists, 1)

    def test_http_facing_operations_are_explicit(self):
        self.assertEqual(self.runtime.agent(7), {'id': 7})
        self.assertIsNone(self.runtime.agent(8))
        self.assertEqual(self.runtime.update_settings({'x': 1}), {'settings': {'x': 1}})
        self.assertEqual(self.runtime.inject('food', 2), {'ok': True})
        self.assertEqual(self.engine.injected, ('food', 2))
        self.assertEqual(self.runtime.shock('storm'), {'ok': True})
        self.assertEqual(self.engine.shocked, 'storm')

    def test_health_reports_runtime_contract(self):
        health = self.runtime.health()
        self.assertTrue(health['ok'])
        self.assertEqual(health['runtimeApi']['version'], 1)
        self.assertEqual(health['persistence']['intervalMs'], 5000)
        self.assertTrue(health['livingCache']['immutable'])


if __name__ == '__main__':
    unittest.main()
