import threading
import unittest
from unittest.mock import patch

from runtime_profiler import RuntimeSampler


class FakeThread:
    def __init__(self, ident, name):
        self.ident = ident
        self.name = name


class RuntimeProfilerTests(unittest.TestCase):
    def test_target_thread_names_are_exposed_in_status(self):
        sampler = RuntimeSampler(thread_names={'sim-engine'})
        self.assertEqual(['sim-engine'], sampler.status()['threadNames'])

    def test_target_filter_does_not_include_snapshot_worker(self):
        sampler = RuntimeSampler(thread_names={'sim-engine'})
        threads = [
            FakeThread(11, 'sim-engine'),
            FakeThread(12, 'simlab-world-snapshot'),
        ]
        with patch('runtime_profiler.threading.enumerate', return_value=threads):
            self.assertEqual({11}, sampler._target_idents())

    def test_empty_target_filter_keeps_legacy_all_threads_mode(self):
        sampler = RuntimeSampler()
        self.assertIsNone(sampler._target_idents())


if __name__ == '__main__':
    unittest.main()
