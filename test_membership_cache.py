import threading
import unittest

from membership_cache import LivingMembershipCache


class LivingMembershipCacheTests(unittest.TestCase):
    def test_revision_controls_membership_rebuild(self):
        agents = {
            1: {'id': 1, 'alive': True},
            2: {'id': 2, 'alive': False},
        }
        cache = LivingMembershipCache()

        first = cache.snapshot(agents)
        second = cache.snapshot(agents)
        self.assertIs(first, second)
        self.assertEqual([agent['id'] for agent in second], [1])
        self.assertEqual(cache.status()['hits'], 1)

        agents[2]['alive'] = True
        cache.changed('agent_revived_for_test')
        third = cache.snapshot(agents)
        self.assertEqual([agent['id'] for agent in third], [1, 2])
        self.assertEqual(cache.status()['revision'], 1)

    def test_dictionary_replacement_falls_back_to_safe_rebuild(self):
        cache = LivingMembershipCache()
        original = {1: {'id': 1, 'alive': True}}
        replacement = {2: {'id': 2, 'alive': True}}

        cache.snapshot(original)
        result = cache.snapshot(replacement)

        self.assertEqual([agent['id'] for agent in result], [2])
        self.assertEqual(cache.status()['sourceFallbacks'], 1)

    def test_changed_reason_is_observable(self):
        cache = LivingMembershipCache()
        cache.changed('reset')
        cache.changed('agent_added')
        status = cache.status()
        self.assertEqual(status['revision'], 2)
        self.assertEqual(status['changes'], 2)
        self.assertEqual(status['lastChange'], 'agent_added')

    def test_readers_observe_every_writer_revision_under_engine_lock_contract(self):
        cache = LivingMembershipCache()
        lock = threading.RLock()
        agents = {
            1: {'id': 1, 'alive': True},
            2: {'id': 2, 'alive': False},
        }
        readers = 4
        rounds = 80
        phase = threading.Barrier(readers + 1)
        failures = []

        def reader():
            for turn in range(rounds):
                phase.wait()
                with lock:
                    actual = [agent['id'] for agent in cache.snapshot(agents)]
                    expected = [agent['id'] for agent in agents.values() if agent['alive']]
                    if actual != expected:
                        failures.append((turn, actual, expected))
                phase.wait()

        def writer():
            for turn in range(rounds):
                with lock:
                    agents[2]['alive'] = bool(turn % 2)
                    cache.changed('test_membership_change')
                # Readers cannot advance to the next mutation until every reader
                # has observed this exact revision.
                phase.wait()
                phase.wait()

        threads = [threading.Thread(target=reader) for _ in range(readers)]
        threads.append(threading.Thread(target=writer))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        self.assertEqual(cache.status()['revision'], rounds)
        self.assertGreaterEqual(cache.status()['misses'], rounds)


if __name__ == '__main__':
    unittest.main()
