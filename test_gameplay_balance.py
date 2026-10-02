import random
import unittest
from unittest.mock import patch

from engine import ARTIFACT_TYPES
from learning_engine import Engine
from test_runtime_profiler import RuntimeProfilerTests
from test_spatial_index import LivingSpatialIndexTests, SpatialCollectionCacheTests


class BalanceHarness(Engine):
    def __init__(self):
        self.settings = {
            'learningRate': 0.24,
            'socialLearning': 0.58,
            'fertility': 0.24,
        }
        self.year = 12.0
        self.events = []
        self.unsaved_events = []
        self.unsaved_experiments = []
        self._living = []

    def living(self):
        return self._living

    def _generalize(self, agent, artifact_type, action, reward):
        return None

    def _remember(self, agent, text, weight=1.0):
        agent.setdefault('memory', []).append({'text': text, 'weight': weight})

    def _log(self, kind, text):
        self.events.append({'kind': kind, 'text': text})


def make_agent(agent_id=1, x=100, y=100):
    return {
        'id': agent_id,
        'sex': 'M' if agent_id % 2 else 'F',
        'x': x,
        'y': y,
        'age': 30.0,
        'health': 100.0,
        'energy': 90.0,
        'hunger': 10.0,
        'thirst': 10.0,
        'social_need': 35.0,
        'food_store': 0,
        'mate_cooldown': 10.0,
        'alive': True,
        'action': 'explore',
        'action_detail': '',
        'traits': {
            'curiosity': 0.58,
            'creativity': 0.50,
            'risk': 0.45,
            'trust': 0.52,
            'sociability': 0.55,
            'aggression': 0.24,
            'empathy': 0.62,
            'conformity': 0.50,
        },
        'rules': {
            'experimentBias': 0.55,
            'exploreBias': 0.55,
            'helpBias': 0.50,
            'mateBias': 0.50,
        },
        'relations': {},
        'hypotheses': {},
        'discoveries': {},
        'beliefs': {},
        'skills': {
            'reasoning': {'level': 0.30, 'practice': 0.0},
            'manipulation': {'level': 0.30, 'practice': 0.0},
            'experimentation': {'level': 0.22, 'practice': 0.0},
            'tool_use': {'level': 0.10, 'practice': 0.0},
            'observation': {'level': 0.28, 'practice': 0.0},
            'imitation': {'level': 0.20, 'practice': 0.0},
            'communication': {'level': 0.25, 'practice': 0.0},
            'teaching': {'level': 0.18, 'practice': 0.0},
        },
        'concepts': {},
        'memory': [],
        'parents': [],
        'last_decision': {},
    }


class GameplayBalanceTests(unittest.TestCase):
    def setUp(self):
        self.engine = BalanceHarness()

    def test_false_confident_hypothesis_does_not_kill_artifact_curiosity(self):
        agent = make_agent()
        subject = 'artifact:stick'
        agent['hypotheses'] = {
            (subject, 'inspect'): {
                'confidence': 0.92, 'evidence_for': 1.0, 'evidence_against': 0.0,
                'source': 'self', 'updated_year': 1.0,
            },
            (subject, 'manipulate'): {
                'confidence': 0.08, 'evidence_for': 0.0, 'evidence_against': 0.0,
                'source': 'self', 'updated_year': 1.0,
            },
            (subject, 'consume'): {
                'confidence': 0.08, 'evidence_for': 0.0, 'evidence_against': 0.0,
                'source': 'self', 'updated_year': 1.0,
            },
        }
        self.assertGreater(self.engine._artifact_uncertainty(agent, 'stick'), 0.60)

    def test_safe_adult_prefers_experimenting_with_a_novel_nearby_artifact(self):
        agent = make_agent()
        self.engine._living = [agent]
        self.engine.resources = {}
        self.engine.artifacts = {
            1: {'id': 1, 'type': 'stick', 'x': 105.0, 'y': 100.0},
        }
        self.engine._known_resource_target = lambda _agent, _kind: None
        self.engine._water_return_urgency = lambda _agent, _target: 0.0

        choice = self.engine._choose_action(agent)

        self.assertEqual('experiment', choice)
        self.assertGreater(
            agent['last_decision']['experiment'],
            agent['last_decision']['observe'],
        )


    def test_water_target_is_on_shore_not_at_pond_centre(self):
        agent = make_agent(x=100, y=100)
        water = {'id': 7, 'type': 'water', 'x': 100.0, 'y': 100.0, 'value': 30.0}

        target = self.engine._water_shore_target(agent, water)

        distance = self.engine._distance(water, target)
        self.assertGreaterEqual(distance, 31.0)
        self.assertLess(distance, 40.0)

    def test_low_thirst_agent_next_to_water_prefers_leaving_over_drinking(self):
        agent = make_agent(x=134, y=100)
        agent['thirst'] = 35.0
        self.engine._living = [agent]
        self.engine.resources = {
            1: {'id': 1, 'type': 'water', 'x': 100.0, 'y': 100.0, 'value': 30.0},
        }
        self.engine.artifacts = {}

        choice = self.engine._choose_action(agent)

        self.assertEqual('explore', choice)
        self.assertEqual(0.0, agent['last_decision']['drink'])

    def test_recently_hydrated_agent_prefers_departure_over_shore_socializing(self):
        agent = make_agent(1, 134, 100)
        other = make_agent(2, 136, 100)
        agent['thirst'] = 20.0
        agent['social_need'] = 80.0
        agent['_water_departure_target'] = {'x': 240.0, 'y': 100.0}
        agent['_water_departure_ttl'] = 100
        self.engine._living = [agent, other]
        self.engine.resources = {
            1: {'id': 1, 'type': 'water', 'x': 100.0, 'y': 100.0, 'value': 30.0},
        }
        self.engine.artifacts = {}

        choice = self.engine._choose_action(agent)

        self.assertEqual('explore', choice)
        self.assertGreater(agent['last_decision']['explore'], agent['last_decision']['socialize'])

    def test_three_coherent_successes_can_produce_a_direct_discovery(self):
        agent = make_agent()
        for _ in range(3):
            self.engine._update_hypothesis(agent, 'stick', 'manipulate', 1.0, 'expérience')
            self.engine._practice(agent, 'action:manipulate', 0.020)
            self.engine._maybe_discover(agent, 'stick', 'manipulate')
        self.assertIn('stick', agent['discoveries'])
        self.assertGreaterEqual(
            agent['hypotheses'][('artifact:stick', 'manipulate')]['confidence'],
            0.54,
        )

    def test_observation_is_progressive_but_can_eventually_create_culture(self):
        actor = make_agent(1, 100, 100)
        observer = make_agent(2, 105, 100)
        self.engine._living = [actor, observer]

        with patch('learning_engine.random.random', return_value=0.0):
            self.engine._learn_from_observation(observer, actor, 'stick', 'manipulate', 1.0)
        self.assertNotIn('stick', observer['discoveries'])

        with patch('learning_engine.random.random', return_value=0.0):
            for _ in range(8):
                self.engine._learn_from_observation(observer, actor, 'stick', 'manipulate', 1.0)
        self.assertIn('stick', observer['discoveries'])

    def test_teaching_prefers_a_mastered_discovery(self):
        teacher = make_agent(1)
        student = make_agent(2)
        teacher['discoveries']['stick'] = 4.0
        teacher['hypotheses'][('artifact:stick', 'manipulate')] = {
            'confidence': 0.80, 'evidence_for': 5.0, 'evidence_against': 0.0,
            'source': 'expérience', 'updated_year': 4.0,
        }
        teacher['hypotheses'][('artifact:stone', 'inspect')] = {
            'confidence': 0.99, 'evidence_for': 1.0, 'evidence_against': 0.0,
            'source': 'self', 'updated_year': 4.0,
        }

        with patch('learning_engine.random.random', return_value=0.0):
            self.assertTrue(self.engine._teach(teacher, student))
        self.assertIn(('artifact:stick', 'manipulate'), student['hypotheses'])
        self.assertNotIn(('artifact:stone', 'inspect'), student['hypotheses'])


if __name__ == '__main__':
    unittest.main()
