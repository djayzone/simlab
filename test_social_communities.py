import tempfile
import unittest

import engine as engine_module
from social_engine import Engine as SocialEngine, ensure_community_schema


def make_agent(agent_id, x, y, age=30.0):
    return {
        'id': agent_id,
        'x': float(x),
        'y': float(y),
        'age': age,
        'alive': True,
        'relations': {},
        'traits': {'conformity': 0.50},
        'community_id': None,
        'community_affinity': 0.0,
        'community_joined_year': None,
        'thirst': 10.0,
        'hunger': 10.0,
        'energy': 90.0,
    }


def link(a, b, trust=0.62, affection=0.52, respect=0.30, encounters=6):
    a['relations'][b['id']] = {
        'trust': trust,
        'affection': affection,
        'respect': respect,
        'encounters': encounters,
    }
    b['relations'][a['id']] = {
        'trust': trust,
        'affection': affection,
        'respect': respect,
        'encounters': encounters,
    }


class SocialHarness(SocialEngine):
    def __init__(self):
        self.year = 20.0
        self.agents = {}
        self.communities = {}
        self.community_relations = {}
        self.next_community_id = 0
        self._next_community_refresh_year = 0.0
        self.events = []

    def living(self):
        return [a for a in self.agents.values() if a['alive']]

    def _log(self, kind, text):
        self.events.append({'kind': kind, 'text': text})


class SocialCommunityTests(unittest.TestCase):
    def test_mutual_repeated_relationship_forms_a_community(self):
        engine = SocialHarness()
        a = make_agent(1, 100, 100)
        b = make_agent(2, 145, 100)
        link(a, b)
        engine.agents = {1: a, 2: b}

        engine._refresh_communities()

        self.assertIsNotNone(a['community_id'])
        self.assertEqual(a['community_id'], b['community_id'])
        self.assertIn(a['community_id'], engine.communities)
        self.assertTrue(any(event['kind'] == 'community' for event in engine.events))

    def test_proximity_without_relationship_never_forms_a_community(self):
        engine = SocialHarness()
        a = make_agent(1, 100, 100)
        b = make_agent(2, 110, 100)
        engine.agents = {1: a, 2: b}

        engine._refresh_communities()

        self.assertIsNone(a['community_id'])
        self.assertIsNone(b['community_id'])
        self.assertEqual({}, engine.communities)

    def test_distant_member_targets_a_peer_not_a_fixed_centroid(self):
        engine = SocialHarness()
        a = make_agent(1, 100, 100)
        b = make_agent(2, 450, 300)
        a['community_id'] = b['community_id'] = 1
        engine.agents = {1: a, 2: b}
        engine.communities = {1: {'id': 1, 'created_year': 10.0, 'last_active_year': 20.0}}

        target = engine._community_companion_target(a)

        self.assertIsNotNone(target)
        self.assertEqual(2, target['_community_peer'])
        self.assertLess(engine._distance(target, b), 80)
        self.assertGreater(engine._distance(target, {'x': 275.0, 'y': 200.0}), 80)

    def test_repeated_cross_group_help_builds_an_alliance(self):
        engine = SocialHarness()
        a = make_agent(1, 100, 100)
        b = make_agent(2, 120, 100)
        a['community_id'], b['community_id'] = 1, 2
        engine.agents = {1: a, 2: b}
        engine.communities = {
            1: {'id': 1, 'created_year': 10.0, 'last_active_year': 20.0},
            2: {'id': 2, 'created_year': 10.0, 'last_active_year': 20.0},
        }

        for _ in range(3):
            engine._record_intercommunity(a, b, 0.14, 'help')

        relation = engine._community_relation(1, 2)
        self.assertEqual('allied', relation['state'])
        self.assertGreaterEqual(relation['score'], 0.36)
        self.assertTrue(any(event['kind'] == 'diplomacy' for event in engine.events))

    def test_repeated_theft_creates_hostility(self):
        engine = SocialHarness()
        a = make_agent(1, 100, 100)
        b = make_agent(2, 120, 100)
        a['community_id'], b['community_id'] = 1, 2
        engine.agents = {1: a, 2: b}
        engine.communities = {
            1: {'id': 1, 'created_year': 10.0, 'last_active_year': 20.0},
            2: {'id': 2, 'created_year': 10.0, 'last_active_year': 20.0},
        }

        for _ in range(3):
            engine._record_intercommunity(a, b, -0.20, 'steal')

        relation = engine._community_relation(1, 2)
        self.assertEqual('hostile', relation['state'])
        self.assertGreater(relation['conflict'], 0.5)

    def test_diplomacy_can_reverse_after_cooperation(self):
        engine = SocialHarness()
        a = make_agent(1, 100, 100)
        b = make_agent(2, 120, 100)
        a['community_id'], b['community_id'] = 1, 2
        engine.agents = {1: a, 2: b}
        engine.communities = {
            1: {'id': 1, 'created_year': 10.0, 'last_active_year': 20.0},
            2: {'id': 2, 'created_year': 10.0, 'last_active_year': 20.0},
        }

        for _ in range(3):
            engine._record_intercommunity(a, b, -0.20, 'steal')
        for _ in range(7):
            engine._record_intercommunity(a, b, 0.14, 'help')

        relation = engine._community_relation(1, 2)
        self.assertIn(relation['state'], {'cooperative', 'allied'})
        self.assertGreater(relation['score'], 0.12)

    def test_internal_subgroups_can_fracture_into_new_communities(self):
        engine = SocialHarness()
        agents = [make_agent(i, 100 + i * 10, 100) for i in range(1, 5)]
        for agent in agents:
            agent['community_id'] = 1
        a, b, c, d = agents
        link(a, b, trust=0.60, affection=0.50, respect=0.30, encounters=8)
        link(c, d, trust=0.60, affection=0.50, respect=0.30, encounters=8)
        for first in (a, b):
            for second in (c, d):
                link(first, second, trust=0.01, affection=0.01, respect=0.01, encounters=8)
        engine.agents = {agent['id']: agent for agent in agents}
        engine.communities = {
            1: {'id': 1, 'created_year': 10.0, 'last_active_year': 20.0}
        }
        engine.next_community_id = 1

        engine._refresh_communities()

        resulting = {agent['community_id'] for agent in agents if agent['community_id'] is not None}
        self.assertGreaterEqual(len(resulting), 2)
        self.assertTrue(any('se fracture' in event['text'] for event in engine.events))

    def test_community_schema_is_additive(self):
        old_path = engine_module.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                engine_module.DB_PATH = f"{tmp}/sim.db"
                engine_module.init_db()
                ensure_community_schema()
                conn = engine_module.connect()
                try:
                    tables = {
                        row['name']
                        for row in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                finally:
                    conn.close()
                self.assertIn('communities', tables)
                self.assertIn('community_memberships', tables)
                self.assertIn('community_relations', tables)
                self.assertIn('agents', tables)
        finally:
            engine_module.DB_PATH = old_path


if __name__ == '__main__':
    unittest.main()
