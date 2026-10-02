import threading
import unittest

from runtime_api import SimulationRuntime


class FakeThread:
    name = 'sim-engine'

    def __init__(self, alive):
        self.alive = alive

    def is_alive(self):
        return self.alive


class FakeEngine:
    def __init__(self, alive):
        self.lock = threading.RLock()
        self.thread = FakeThread(alive)
        self.rich_health_calls = 0

    def living_cache_status(self):
        self.rich_health_calls += 1
        return {'immutable': True}


class FakeCache:
    def __init__(self):
        self.calls = 0

    def status(self):
        self.calls += 1
        return {'generation': 1}


class FakeProfiler:
    def __init__(self):
        self.calls = 0

    def status(self):
        self.calls += 1
        return {'generation': 1}


class RuntimeHealthTests(unittest.TestCase):
    def runtime(self, alive):
        return SimulationRuntime(FakeEngine(alive), FakeCache(), FakeProfiler(), 5.0)

    def test_probe_health_is_ok_when_engine_loop_is_alive(self):
        runtime = self.runtime(True)
        health = runtime.probe_health()
        self.assertTrue(health['ok'])
        self.assertTrue(health['engineLoop']['alive'])
        self.assertEqual(health['engineLoop']['thread'], 'sim-engine')
        self.assertEqual(runtime.snapshot_cache.calls, 0)
        self.assertEqual(runtime.profiler.calls, 0)
        self.assertEqual(runtime.engine.rich_health_calls, 0)

    def test_probe_health_fails_when_engine_loop_has_died(self):
        health = self.runtime(False).probe_health()
        self.assertFalse(health['ok'])
        self.assertFalse(health['engineLoop']['alive'])

    def test_rich_health_keeps_diagnostics_outside_probe_path(self):
        runtime = self.runtime(True)
        health = runtime.health()
        self.assertTrue(health['ok'])
        self.assertEqual(health['snapshot']['generation'], 1)
        self.assertEqual(health['perf']['generation'], 1)
        self.assertEqual(health['livingCache'], {'immutable': True})
        self.assertEqual(runtime.snapshot_cache.calls, 1)
        self.assertEqual(runtime.profiler.calls, 1)
        self.assertEqual(runtime.engine.rich_health_calls, 1)


if __name__ == '__main__':
    unittest.main()
