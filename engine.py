import math
import os
import random
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv('SIM_DB_PATH', '/data/sim.db')
WORLD_ID = 1
WORLD_W = 1200
WORLD_H = 760
DB_LOCK = threading.RLock()

ACTIONS = ['inspect', 'manipulate', 'strike', 'feed', 'bury', 'roll', 'consume']
ARTIFACT_TYPES = {
    'stick': {
        'label': 'Bâton', 'best': 'manipulate', 'discovery': 'cueillette assistée', 'bonus': 'forage', 'reward': 1.0,
        'properties': ['long', 'rigid', 'light', 'wooden'],
    },
    'stone': {
        'label': 'Pierre', 'best': 'strike', 'discovery': 'outil de taille', 'bonus': 'harvest', 'reward': 1.1,
        'properties': ['hard', 'heavy', 'mineral', 'rigid'],
    },
    'ember': {
        'label': 'Braise', 'best': 'feed', 'discovery': 'feu entretenu', 'bonus': 'warmth', 'reward': 1.25, 'hazard': 0.18,
        'properties': ['hot', 'bright', 'dangerous', 'fragile'],
    },
    'seed': {
        'label': 'Graine', 'best': 'bury', 'discovery': 'culture rudimentaire', 'bonus': 'farming', 'reward': 1.35,
        'properties': ['small', 'organic', 'light', 'edible_candidate'],
    },
    'wheel': {
        'label': 'Roue', 'best': 'roll', 'discovery': 'transport roulant', 'bonus': 'mobility', 'reward': 1.2,
        'properties': ['round', 'rigid', 'rolling', 'portable'],
    },
    'herb': {
        'label': 'Plante', 'best': 'consume', 'discovery': 'soin végétal', 'bonus': 'medicine', 'reward': 0.9, 'hazard': 0.08,
        'properties': ['organic', 'soft', 'edible_candidate', 'scented'],
    },
}
DEFAULT_SETTINGS = {
    'initialPopulation': 90.0,
    'maxPopulation': 700.0,
    'mutation': 0.08,
    'fertility': 0.24,
    'lifespan': 82.0,
    'foodAbundance': 0.58,
    'resourceRespawn': 0.28,
    'learningRate': 0.24,
    'socialLearning': 0.58,
    'meanCuriosity': 0.58,
    'meanAggression': 0.24,
    'meanEmpathy': 0.62,
    'scarcityPressure': 0.35,
}
BASE_SKILLS = ['observation', 'locomotion', 'manipulation', 'communication', 'reasoning', 'experimentation', 'imitation', 'care', 'teaching', 'gathering', 'tool_use']

SCHEMA = r'''
CREATE TABLE IF NOT EXISTS worlds (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  year REAL NOT NULL DEFAULT 0,
  running INTEGER NOT NULL DEFAULT 1 CHECK(running IN (0,1)),
  speed REAL NOT NULL DEFAULT 4,
  births INTEGER NOT NULL DEFAULT 0,
  deaths INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS world_settings (
  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  value REAL NOT NULL,
  PRIMARY KEY(world_id, key)
);
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY,
  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
  sex TEXT NOT NULL CHECK(sex IN ('F','M')),
  x REAL NOT NULL, y REAL NOT NULL,
  age REAL NOT NULL,
  health REAL NOT NULL, energy REAL NOT NULL, hunger REAL NOT NULL, thirst REAL NOT NULL,
  social_need REAL NOT NULL, food_store INTEGER NOT NULL DEFAULT 0, mate_cooldown REAL NOT NULL DEFAULT 0,
  alive INTEGER NOT NULL CHECK(alive IN (0,1)),
  action TEXT NOT NULL DEFAULT 'naissance', action_detail TEXT NOT NULL DEFAULT '',
  target_x REAL, target_y REAL,
  birth_year REAL NOT NULL,
  death_year REAL
);
CREATE INDEX IF NOT EXISTS idx_agents_world_alive ON agents(world_id, alive);
CREATE TABLE IF NOT EXISTS agent_traits (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  trait TEXT NOT NULL,
  value REAL NOT NULL,
  PRIMARY KEY(agent_id, trait)
);
CREATE TABLE IF NOT EXISTS agent_rules (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  rule TEXT NOT NULL,
  value REAL NOT NULL,
  PRIMARY KEY(agent_id, rule)
);
CREATE TABLE IF NOT EXISTS agent_parents (
  child_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  parent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  PRIMARY KEY(child_id, parent_id)
);
CREATE TABLE IF NOT EXISTS relations (
  source_agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  target_agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  trust REAL NOT NULL, affection REAL NOT NULL, respect REAL NOT NULL, encounters INTEGER NOT NULL,
  PRIMARY KEY(source_agent_id, target_agent_id)
);
CREATE TABLE IF NOT EXISTS beliefs (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  artifact_type TEXT NOT NULL,
  confidence REAL NOT NULL, utility REAL NOT NULL, attempts INTEGER NOT NULL,
  action TEXT, source TEXT NOT NULL,
  PRIMARY KEY(agent_id, artifact_type)
);
CREATE TABLE IF NOT EXISTS discoveries (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  artifact_type TEXT NOT NULL,
  discovered_year REAL NOT NULL,
  PRIMARY KEY(agent_id, artifact_type)
);
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  year REAL NOT NULL,
  text TEXT NOT NULL,
  weight REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_agent_year ON memories(agent_id, year DESC);
CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY,
  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
  resource_type TEXT NOT NULL CHECK(resource_type IN ('food','water')),
  x REAL NOT NULL, y REAL NOT NULL, value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_resources_world_type ON resources(world_id, resource_type);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY,
  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
  artifact_type TEXT NOT NULL,
  x REAL NOT NULL, y REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_world_type ON artifacts(world_id, artifact_type);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
  year REAL NOT NULL,
  kind TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_world_id ON events(world_id, id DESC);

-- Learning model v2: additive migration. Newborns start nearly blank.
CREATE TABLE IF NOT EXISTS agent_skills (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  skill TEXT NOT NULL,
  level REAL NOT NULL DEFAULT 0,
  practice REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(agent_id, skill)
);
CREATE TABLE IF NOT EXISTS hypotheses (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  action TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  evidence_for REAL NOT NULL DEFAULT 0,
  evidence_against REAL NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'unknown',
  updated_year REAL NOT NULL,
  PRIMARY KEY(agent_id, subject, action)
);
CREATE INDEX IF NOT EXISTS idx_hypotheses_agent ON hypotheses(agent_id);
CREATE TABLE IF NOT EXISTS agent_concepts (
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  concept TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  evidence REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(agent_id, concept)
);
CREATE TABLE IF NOT EXISTS experiments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  year REAL NOT NULL,
  artifact_type TEXT NOT NULL,
  action TEXT NOT NULL,
  reward REAL NOT NULL,
  success INTEGER NOT NULL CHECK(success IN (0,1)),
  confidence_before REAL NOT NULL,
  confidence_after REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'direct'
);
CREATE INDEX IF NOT EXISTS idx_experiments_agent_year ON experiments(agent_id, year DESC);
'''


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        conn = connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


def development(age):
    """Innate developmental envelope. Knowledge is not inherited here."""
    return {
        'perception': clamp(0.08 + age / 4.0, 0.08, 1.0),
        'locomotion': 0.0 if age < 0.7 else clamp((age - 0.7) / 3.0, 0.0, 1.0),
        'manipulation': clamp(0.02 + age / 6.0, 0.02, 1.0),
        'communication': clamp(age / 7.0, 0.0, 1.0),
        'imitation': clamp(0.04 + age / 5.0, 0.04, 1.0),
        'reasoning': 0.0 if age < 1.5 else clamp((age - 1.5) / 14.0, 0.0, 1.0),
        'autonomy': 0.0 if age < 1.2 else clamp((age - 1.2) / 6.0, 0.0, 1.0),
    }


class Engine:
    def __init__(self):
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.settings = dict(DEFAULT_SETTINGS)
        self.year = 0.0
        self.running = True
        self.speed = 4.0
        self.births = 0
        self.deaths = 0
        self.agents = {}
        self.resources = {}
        self.artifacts = {}
        self.events = []
        self.next_agent_id = 0
        self.next_resource_id = 0
        self.next_artifact_id = 0
        self.unsaved_memories = []
        self.unsaved_events = []
        self.unsaved_experiments = []
        self.last_persist = 0.0
        self.tick_carry = 0.0
        if not self._load():
            self.reset()
        self.thread = threading.Thread(target=self._loop, name='sim-engine', daemon=True)
        self.thread.start()

    def living(self):
        return [a for a in self.agents.values() if a['alive']]

    def _load(self):
        with DB_LOCK:
            conn = connect()
            try:
                world = conn.execute('SELECT * FROM worlds WHERE id=?', (WORLD_ID,)).fetchone()
                if not world:
                    return False
                self.year = float(world['year'])
                self.running = bool(world['running'])
                self.speed = float(world['speed'])
                self.births = int(world['births'])
                self.deaths = int(world['deaths'])
                self.settings.update({r['key']: float(r['value']) for r in conn.execute('SELECT key,value FROM world_settings WHERE world_id=?', (WORLD_ID,))})

                trait_map, rule_map, parent_map = {}, {}, {}
                relation_map, belief_map, discovery_map, memory_map = {}, {}, {}, {}
                skill_map, hypothesis_map, concept_map = {}, {}, {}
                for r in conn.execute('SELECT agent_id,trait,value FROM agent_traits'):
                    trait_map.setdefault(r['agent_id'], {})[r['trait']] = float(r['value'])
                for r in conn.execute('SELECT agent_id,rule,value FROM agent_rules'):
                    rule_map.setdefault(r['agent_id'], {})[r['rule']] = float(r['value'])
                for r in conn.execute('SELECT child_id,parent_id FROM agent_parents'):
                    parent_map.setdefault(r['child_id'], []).append(r['parent_id'])
                for r in conn.execute('SELECT * FROM relations'):
                    relation_map.setdefault(r['source_agent_id'], {})[r['target_agent_id']] = {
                        'trust': float(r['trust']), 'affection': float(r['affection']), 'respect': float(r['respect']), 'encounters': int(r['encounters'])
                    }
                for r in conn.execute('SELECT * FROM beliefs'):
                    belief_map.setdefault(r['agent_id'], {})[r['artifact_type']] = {
                        'confidence': float(r['confidence']), 'utility': float(r['utility']), 'attempts': int(r['attempts']), 'action': r['action'], 'source': r['source']
                    }
                for r in conn.execute('SELECT agent_id,artifact_type,discovered_year FROM discoveries'):
                    discovery_map.setdefault(r['agent_id'], {})[r['artifact_type']] = float(r['discovered_year'])
                for r in conn.execute('SELECT agent_id,year,text,weight FROM memories ORDER BY id DESC'):
                    arr = memory_map.setdefault(r['agent_id'], [])
                    if len(arr) < 12:
                        arr.append({'year': float(r['year']), 'text': r['text'], 'weight': float(r['weight'])})
                for r in conn.execute('SELECT agent_id,skill,level,practice FROM agent_skills'):
                    skill_map.setdefault(r['agent_id'], {})[r['skill']] = {'level': float(r['level']), 'practice': float(r['practice'])}
                for r in conn.execute('SELECT * FROM hypotheses'):
                    hypothesis_map.setdefault(r['agent_id'], {})[(r['subject'], r['action'])] = {
                        'confidence': float(r['confidence']), 'evidence_for': float(r['evidence_for']), 'evidence_against': float(r['evidence_against']),
                        'source': r['source'], 'updated_year': float(r['updated_year'])
                    }
                for r in conn.execute('SELECT agent_id,concept,confidence,evidence FROM agent_concepts'):
                    concept_map.setdefault(r['agent_id'], {})[r['concept']] = {'confidence': float(r['confidence']), 'evidence': float(r['evidence'])}

                for r in conn.execute('SELECT * FROM agents WHERE world_id=?', (WORLD_ID,)):
                    aid = r['id']
                    skills = skill_map.get(aid) or self._bootstrap_skills(float(r['age']), founder=True)
                    self.agents[aid] = {
                        'id': aid, 'sex': r['sex'], 'x': float(r['x']), 'y': float(r['y']), 'age': float(r['age']),
                        'health': float(r['health']), 'energy': float(r['energy']), 'hunger': float(r['hunger']), 'thirst': float(r['thirst']),
                        'social_need': float(r['social_need']), 'food_store': int(r['food_store']), 'mate_cooldown': float(r['mate_cooldown']),
                        'alive': bool(r['alive']), 'action': r['action'], 'action_detail': r['action_detail'],
                        'target': None if r['target_x'] is None else {'x': float(r['target_x']), 'y': float(r['target_y'])},
                        'birth_year': float(r['birth_year']), 'death_year': None if r['death_year'] is None else float(r['death_year']),
                        'traits': trait_map.get(aid, {}), 'rules': rule_map.get(aid, {}), 'parents': parent_map.get(aid, []),
                        'relations': relation_map.get(aid, {}), 'beliefs': belief_map.get(aid, {}), 'discoveries': discovery_map.get(aid, {}),
                        'memory': memory_map.get(aid, []), 'skills': skills, 'hypotheses': hypothesis_map.get(aid, {}),
                        'concepts': concept_map.get(aid, {}), 'last_decision': {},
                    }
                self.resources = {r['id']: {'id': r['id'], 'type': r['resource_type'], 'x': float(r['x']), 'y': float(r['y']), 'value': float(r['value'])} for r in conn.execute('SELECT * FROM resources WHERE world_id=?', (WORLD_ID,))}
                self.artifacts = {r['id']: {'id': r['id'], 'type': r['artifact_type'], 'x': float(r['x']), 'y': float(r['y'])} for r in conn.execute('SELECT * FROM artifacts WHERE world_id=?', (WORLD_ID,))}
                self.events = [{'id': r['id'], 'year': float(r['year']), 'kind': r['kind'], 'text': r['text']} for r in conn.execute('SELECT id,year,kind,text FROM events WHERE world_id=? ORDER BY id DESC LIMIT 80', (WORLD_ID,))]
                self.next_agent_id = max(self.agents.keys(), default=0)
                self.next_resource_id = max(self.resources.keys(), default=0)
                self.next_artifact_id = max(self.artifacts.keys(), default=0)
                return True
            finally:
                conn.close()

    def _bootstrap_skills(self, age, founder=False):
        dev = development(age)
        if not founder and age < 0.1:
            return {skill: {'level': 0.0, 'practice': 0.0} for skill in BASE_SKILLS}
        maturity = dev['autonomy']
        levels = {
            'observation': dev['perception'] * (0.30 + 0.25 * maturity),
            'locomotion': dev['locomotion'] * (0.30 + 0.30 * maturity),
            'manipulation': dev['manipulation'] * (0.25 + 0.28 * maturity),
            'communication': dev['communication'] * (0.20 + 0.30 * maturity),
            'reasoning': dev['reasoning'] * (0.15 + 0.32 * maturity),
            'experimentation': dev['reasoning'] * (0.12 + 0.28 * maturity),
            'imitation': dev['imitation'] * (0.24 + 0.25 * maturity),
            'care': (0.08 + 0.22 * maturity) if age >= 8 else 0.02 * maturity,
            'teaching': (0.05 + 0.18 * maturity) if age >= 12 else 0.0,
            'gathering': 0.08 + 0.25 * maturity,
            'tool_use': 0.03 + 0.18 * maturity,
        }
        return {k: {'level': clamp(v + (random.uniform(-0.05, 0.05) if founder else 0), 0, 0.75), 'practice': 0.0} for k, v in levels.items()}

    def reset(self):
        with self.lock:
            previous_speed = getattr(self, 'speed', 4.0)
            self.year, self.births, self.deaths = 0.0, 0, 0
            self.running, self.speed = True, previous_speed
            self.agents, self.resources, self.artifacts, self.events = {}, {}, {}, []
            self.next_agent_id = self.next_resource_id = self.next_artifact_id = 0
            self.unsaved_memories, self.unsaved_events, self.unsaved_experiments = [], [], []
            for _ in range(int(self.settings['initialPopulation'])):
                self._new_agent(None)
            for _ in range(int(140 * self.settings['foodAbundance'])):
                self._spawn_resource('food')
            for _ in range(7):
                self._spawn_resource('water', random.uniform(18, 34))
            self._log('system', f"Monde initialisé avec {len(self.living())} vies. Les nouveaux-nés ne possèdent aucune connaissance technique.")
            self._persist(full_reset=True)

    def _new_agent(self, parents):
        self.next_agent_id += 1
        aid = self.next_agent_id
        newborn = parents is not None
        if newborn:
            x = sum(p['x'] for p in parents) / 2 + random.uniform(-8, 8)
            y = sum(p['y'] for p in parents) / 2 + random.uniform(-8, 8)
            age = 0.0
        else:
            x, y, age = random.uniform(30, 1170), random.uniform(30, 730), random.uniform(8, 45)

        def inherit_trait(key, fallback):
            if not parents:
                return clamp(fallback + random.uniform(-0.18, 0.18), 0, 1)
            base = sum(p['traits'][key] for p in parents) / len(parents)
            return clamp(base + random.uniform(-self.settings['mutation'], self.settings['mutation']), 0, 1)

        def inherit_rule(key, low, high):
            if not parents:
                return random.uniform(low, high)
            base = sum(p['rules'][key] for p in parents) / len(parents)
            return clamp(base + random.uniform(-0.08, 0.08), 0.05, 0.95)

        traits = {
            'curiosity': inherit_trait('curiosity', self.settings['meanCuriosity']), 'sociability': inherit_trait('sociability', 0.55),
            'aggression': inherit_trait('aggression', self.settings['meanAggression']), 'empathy': inherit_trait('empathy', self.settings['meanEmpathy']),
            'risk': inherit_trait('risk', 0.45), 'conformity': inherit_trait('conformity', 0.5),
            'creativity': inherit_trait('creativity', 0.5), 'trust': inherit_trait('trust', 0.52),
        }
        rules = {
            'hungerThreshold': inherit_rule('hungerThreshold', 0.55, 0.82), 'thirstThreshold': inherit_rule('thirstThreshold', 0.50, 0.78),
            'restThreshold': inherit_rule('restThreshold', 0.18, 0.42), 'experimentBias': inherit_rule('experimentBias', 0.25, 0.85),
            'socialBias': inherit_rule('socialBias', 0.20, 0.80), 'helpBias': inherit_rule('helpBias', 0.15, 0.85),
            'mateBias': inherit_rule('mateBias', 0.20, 0.80), 'exploreBias': inherit_rule('exploreBias', 0.25, 0.90),
        }
        agent = {
            'id': aid, 'sex': 'F' if random.random() < 0.5 else 'M', 'x': clamp(x, 8, 1192), 'y': clamp(y, 8, 752), 'age': age,
            'health': random.uniform(86, 100) if newborn else random.uniform(78, 100), 'energy': random.uniform(65, 100),
            'hunger': random.uniform(0, 20) if newborn else random.uniform(0, 45), 'thirst': random.uniform(0, 18) if newborn else random.uniform(0, 35),
            'social_need': random.uniform(25, 55), 'food_store': 0 if newborn else (1 if random.random() < 0.3 else 0),
            'mate_cooldown': random.uniform(0, 180), 'alive': True, 'action': 'naissance' if newborn else 'explore', 'action_detail': '',
            'target': None, 'birth_year': self.year - age, 'death_year': None, 'traits': traits, 'rules': rules,
            'parents': [p['id'] for p in parents] if parents else [], 'relations': {}, 'beliefs': {}, 'discoveries': {}, 'memory': [],
            'skills': self._bootstrap_skills(age, founder=not newborn), 'hypotheses': {}, 'concepts': {}, 'last_decision': {},
        }
        self.agents[aid] = agent
        # No technical knowledge or discoveries are copied at birth. Culture must be observed/taught later.
        return agent

    def _spawn_resource(self, resource_type, value=None):
        self.next_resource_id += 1
        self.resources[self.next_resource_id] = {
            'id': self.next_resource_id, 'type': resource_type, 'x': random.uniform(10, 1190), 'y': random.uniform(10, 750),
            'value': value if value is not None else random.uniform(0.6, 1.3),
        }

    def _distance(self, a, b):
        return math.hypot(a['x'] - b['x'], a['y'] - b['y'])

    def _nearest(self, origin, items, max_distance, predicate=None):
        best, best_d = None, max_distance
        for item in items:
            if predicate and not predicate(item):
                continue
            d = self._distance(origin, item)
            if d < best_d:
                best, best_d = item, d
        return best

    def _skill(self, agent, name):
        return agent['skills'].get(name, {'level': 0.0, 'practice': 0.0})['level']

    def _practice(self, agent, name, amount=0.02):
        item = agent['skills'].setdefault(name, {'level': 0.0, 'practice': 0.0})
        item['practice'] += amount
        aptitude = 0.55 + agent['traits']['curiosity'] * 0.15 + agent['traits']['creativity'] * 0.10
        item['level'] = clamp(item['level'] + amount * aptitude * (1 - item['level']) * 0.45, 0, 1)

    def _relation(self, agent, other):
        if other['id'] not in agent['relations']:
            base = 0.38 if other['id'] in agent['parents'] or agent['id'] in other['parents'] else agent['traits']['trust'] * 0.32
            agent['relations'][other['id']] = {'trust': base, 'affection': 0.28 if base > 0.3 else 0.10, 'respect': 0.10, 'encounters': 0}
        return agent['relations'][other['id']]

    def _remember(self, agent, text, weight=1.0):
        mem = {'year': self.year, 'text': text, 'weight': weight}
        agent['memory'].insert(0, mem)
        agent['memory'] = agent['memory'][:12]
        self.unsaved_memories.append((agent['id'], mem))

    def _hypothesis(self, agent, subject, action, source='self'):
        key = (subject, action)
        if key not in agent['hypotheses']:
            agent['hypotheses'][key] = {
                'confidence': 0.08, 'evidence_for': 0.0, 'evidence_against': 0.0, 'source': source, 'updated_year': self.year,
            }
        return agent['hypotheses'][key]

    def _concept(self, agent, concept):
        return agent['concepts'].setdefault(concept, {'confidence': 0.0, 'evidence': 0.0})

    def _perceive_artifact(self, agent, artifact):
        dev = development(agent['age'])
        if dev['perception'] < 0.12:
            return
        self._practice(agent, 'observation', 0.003 * dev['perception'])
        subject = f"artifact:{artifact['type']}"
        # Perception creates possibilities, never knowledge. Young children get fewer candidate actions.
        possible = ['inspect']
        if dev['manipulation'] > 0.18:
            possible += ['manipulate', 'consume']
        if dev['manipulation'] > 0.35:
            possible += ['strike', 'roll']
        if dev['reasoning'] > 0.20:
            possible += ['feed', 'bury']
        for action in set(possible):
            self._hypothesis(agent, subject, action, 'perception')

    def _generalize(self, agent, artifact_type, action, reward):
        definition = ARTIFACT_TYPES[artifact_type]
        success = reward > 0.55
        factor = self._skill(agent, 'reasoning') * development(agent['age'])['reasoning']
        if factor <= 0.03:
            return
        for prop in definition['properties']:
            concept = self._concept(agent, f"property:{prop}|action:{action}")
            delta = (0.08 if success else -0.025) * (0.4 + factor)
            concept['confidence'] = clamp(concept['confidence'] + delta, 0, 1)
            concept['evidence'] += 1
        self._practice(agent, 'reasoning', 0.012 if success else 0.005)

    def _concept_prior(self, agent, artifact_type, action):
        vals = []
        for prop in ARTIFACT_TYPES[artifact_type]['properties']:
            concept = agent['concepts'].get(f"property:{prop}|action:{action}")
            if concept:
                vals.append(concept['confidence'])
        return sum(vals) / len(vals) if vals else 0.0

    def _update_hypothesis(self, agent, artifact_type, action, reward, source='direct'):
        subject = f'artifact:{artifact_type}'
        h = self._hypothesis(agent, subject, action, source)
        before = h['confidence']
        lr = self.settings['learningRate'] * (0.25 + self._skill(agent, 'reasoning') * 0.45 + agent['traits']['curiosity'] * 0.25)
        if reward > 0.55:
            h['evidence_for'] += 1
            h['confidence'] = clamp(h['confidence'] + lr * (1 - h['confidence']), 0, 1)
        else:
            h['evidence_against'] += 1
            h['confidence'] = clamp(h['confidence'] - lr * 0.45 * max(h['confidence'], 0.15), 0, 1)
        h['source'], h['updated_year'] = source, self.year
        self._generalize(agent, artifact_type, action, reward)
        return before, h['confidence']

    def _learn_from_observation(self, observer, actor, artifact_type, action, reward):
        dev = development(observer['age'])
        if dev['imitation'] < 0.08 or self._distance(observer, actor) > 90:
            return
        rel = self._relation(observer, actor)
        reliability = 0.15 + rel['trust'] * 0.45 + self._skill(observer, 'observation') * 0.30
        factor = self.settings['socialLearning'] * dev['imitation'] * reliability
        if random.random() > factor:
            return
        h = self._hypothesis(observer, f'artifact:{artifact_type}', action, f'observation #{actor["id"]}')
        delta = (0.12 if reward > 0.55 else -0.035) * factor
        h['confidence'] = clamp(h['confidence'] + delta, 0, 1)
        if reward > 0.55:
            h['evidence_for'] += 0.35
        else:
            h['evidence_against'] += 0.2
        h['source'], h['updated_year'] = f'observation #{actor["id"]}', self.year
        self._practice(observer, 'observation', 0.008)
        self._practice(observer, 'imitation', 0.006)

    def _teach(self, teacher, student):
        dev = development(student['age'])
        if dev['communication'] < 0.12 or not teacher['hypotheses']:
            return False
        rel = self._relation(student, teacher)
        candidates = sorted(teacher['hypotheses'].items(), key=lambda kv: kv[1]['confidence'], reverse=True)
        if not candidates:
            return False
        (subject, action), source_h = candidates[0]
        transmission = self.settings['socialLearning'] * (0.2 + self._skill(teacher, 'teaching') * 0.45) * (0.25 + rel['trust'] * 0.55) * dev['communication']
        if random.random() > transmission:
            return False
        target = self._hypothesis(student, subject, action, f'enseignement #{teacher["id"]}')
        target['confidence'] = clamp(max(target['confidence'], source_h['confidence'] * transmission * 0.55), 0, 0.78)
        target['evidence_for'] += 0.15 * transmission
        target['source'], target['updated_year'] = f'enseignement #{teacher["id"]}', self.year
        self._practice(teacher, 'teaching', 0.012)
        self._practice(student, 'communication', 0.006)
        return True

    def _maybe_discover(self, agent, artifact_type, action):
        definition = ARTIFACT_TYPES[artifact_type]
        h = agent['hypotheses'].get((f'artifact:{artifact_type}', action))
        if not h or action != definition['best'] or artifact_type in agent['discoveries']:
            return
        skill_gate = 0.10 + self._skill(agent, 'tool_use') * 0.20
        if h['confidence'] >= 0.72 and h['evidence_for'] >= 2.0 and self._skill(agent, f'action:{action}') >= skill_gate:
            agent['discoveries'][artifact_type] = self.year
            agent['beliefs'][artifact_type] = {'confidence': h['confidence'], 'utility': definition['reward'], 'attempts': int(h['evidence_for'] + h['evidence_against']), 'action': action, 'source': h['source']}
            self._remember(agent, f"J'ai compris : {definition['label']} → {definition['discovery']}.", 2.0)
            self._log('discovery', f"#{agent['id']} comprend « {definition['discovery']} » avec {definition['label']}.")

    def _has_capability(self, agent, bonus):
        return any(ARTIFACT_TYPES[t]['bonus'] == bonus for t in agent['discoveries'] if t in ARTIFACT_TYPES)

    def _move_toward(self, agent, target, dt, multiplier=1.0):
        dev = development(agent['age'])
        if not target or dev['locomotion'] <= 0.02:
            return
        dx, dy = target['x'] - agent['x'], target['y'] - agent['y']
        d = math.hypot(dx, dy) or 1.0
        mobility = 1.35 if self._has_capability(agent, 'mobility') else 1.0
        competence = 0.35 + self._skill(agent, 'locomotion') * 0.65
        step = (0.7 + agent['energy'] / 140) * mobility * multiplier * dt * dev['locomotion'] * competence
        agent['x'] = clamp(agent['x'] + dx / d * step, 8, 1192)
        agent['y'] = clamp(agent['y'] + dy / d * step, 8, 752)
        self._practice(agent, 'locomotion', 0.002)

    def _wander(self, agent, dt):
        if development(agent['age'])['locomotion'] < 0.1:
            agent['action_detail'] = 'reste près de ses proches'
            return
        if not agent['target'] or random.random() < 0.015 or self._distance(agent, agent['target']) < 10:
            agent['target'] = {'x': random.uniform(20, 1180), 'y': random.uniform(20, 740)}
        self._move_toward(agent, agent['target'], dt, 0.65 + agent['traits']['risk'] * 0.5)

    def _find_caregiver(self, child):
        adults = [a for a in self.living() if a['age'] >= 14 and a['id'] != child['id']]
        def score(a):
            kin = 1.0 if a['id'] in child['parents'] else 0.0
            return kin * 1000 + a['traits']['empathy'] * 100 - self._distance(child, a)
        nearby = [a for a in adults if self._distance(child, a) <= 120]
        return max(nearby, key=score) if nearby else None

    def _care(self, caregiver, child, dt):
        self._move_toward(caregiver, child, dt, 0.9)
        if self._distance(caregiver, child) > 25:
            return
        amount = (0.8 + self._skill(caregiver, 'care')) * dt
        child['hunger'] = clamp(child['hunger'] - 5.0 * amount, 0, 100)
        child['thirst'] = clamp(child['thirst'] - 6.0 * amount, 0, 100)
        child['energy'] = clamp(child['energy'] + 2.2 * amount, 0, 100)
        child['health'] = clamp(child['health'] + 0.12 * amount, 0, 100)
        child['social_need'] = clamp(child['social_need'] - 5.0 * amount, 0, 100)
        self._relation(child, caregiver)['trust'] = clamp(self._relation(child, caregiver)['trust'] + 0.006 * dt, 0, 1)
        self._relation(child, caregiver)['affection'] = clamp(self._relation(child, caregiver)['affection'] + 0.007 * dt, 0, 1)
        self._practice(caregiver, 'care', 0.004 * dt)
        self._practice(child, 'observation', 0.002 * development(child['age'])['perception'])
        caregiver['action_detail'] = f"prend soin de #{child['id']}"

    def _choose_action(self, agent):
        dev = development(agent['age'])
        living = self.living()
        foods = [r for r in self.resources.values() if r['type'] == 'food']
        waters = [r for r in self.resources.values() if r['type'] == 'water']
        nearby_food = self._nearest(agent, foods, 170)
        nearby_water = self._nearest(agent, waters, 200)
        nearby_artifact = self._nearest(agent, list(self.artifacts.values()), 150)
        nearby_agent = self._nearest(agent, living, 80, lambda a: a['id'] != agent['id'])
        child = self._nearest(agent, living, 90, lambda a: a['age'] < 7 and a['id'] != agent['id'])

        scores = {
            'drink': agent['thirst'] / 100 * 1.45 * dev['autonomy'],
            'eat': agent['hunger'] / 100 * 1.35 * dev['autonomy'],
            'rest': (1 - agent['energy'] / 100) * 1.05,
            'explore': agent['rules']['exploreBias'] * (0.2 + agent['traits']['curiosity'] * 0.65) * dev['locomotion'],
            'socialize': (agent['social_need'] / 100) * (0.35 + agent['traits']['sociability']) * dev['communication'] if nearby_agent else 0,
            'observe': (0.25 + agent['traits']['curiosity'] * 0.45 + self._skill(agent, 'observation') * 0.25) * dev['perception'] if nearby_agent or nearby_artifact else 0,
            'experiment': 0,
            'care': (0.5 + agent['traits']['empathy'] * 0.8 + self._skill(agent, 'care') * 0.3) if child and agent['age'] >= 12 else 0,
            'mate': 0,
            'help': 0,
            'steal': 0,
        }
        if agent['age'] < 2:
            caregiver = self._find_caregiver(agent)
            scores['observe'] += 0.35 * dev['perception']
            scores['rest'] += 0.35
            if caregiver:
                scores['socialize'] += 0.15
        if nearby_artifact and dev['manipulation'] > 0.12 and dev['reasoning'] > 0.03:
            self._perceive_artifact(agent, nearby_artifact)
            subject = f"artifact:{nearby_artifact['type']}"
            uncertainty = 1 - max((h['confidence'] for (s, _), h in agent['hypotheses'].items() if s == subject), default=0)
            scores['experiment'] = uncertainty * (0.35 + agent['traits']['curiosity'] + agent['traits']['creativity'] * 0.3) * agent['rules']['experimentBias'] * dev['manipulation'] * (0.25 + dev['reasoning'])
        if nearby_agent and agent['age'] >= 7:
            scores['help'] = agent['traits']['empathy'] * agent['rules']['helpBias'] if nearby_agent['hunger'] > 70 else 0
            scores['steal'] = agent['traits']['aggression'] * (0.5 + agent['hunger'] / 100) if agent['age'] >= 11 and agent['hunger'] > 65 and nearby_agent['food_store'] > 0 else 0
        if nearby_agent and agent['age'] >= 17 and nearby_agent['age'] >= 17 and nearby_agent['sex'] != agent['sex'] and agent['mate_cooldown'] <= 0:
            scores['mate'] = agent['rules']['mateBias'] * self.settings['fertility'] * 1.5
        agent['last_decision'] = dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))
        return max(scores, key=scores.get)

    def _experiment(self, agent, artifact):
        dev = development(agent['age'])
        if dev['manipulation'] < 0.12:
            return
        self._perceive_artifact(agent, artifact)
        subject = f"artifact:{artifact['type']}"
        allowed = ['inspect']
        if dev['manipulation'] > 0.18:
            allowed += ['manipulate', 'consume']
        if dev['manipulation'] > 0.35:
            allowed += ['strike', 'roll']
        if dev['reasoning'] > 0.20:
            allowed += ['feed', 'bury']

        def action_score(action):
            h = self._hypothesis(agent, subject, action, 'self')
            concept = self._concept_prior(agent, artifact['type'], action)
            unknown = 1 - h['confidence']
            return h['confidence'] * 0.65 + concept * 0.45 + unknown * agent['traits']['curiosity'] * 0.35 + random.random() * agent['traits']['creativity'] * 0.18

        action = max(allowed, key=action_score)
        definition = ARTIFACT_TYPES[artifact['type']]
        relevant = (self._skill(agent, f'action:{action}') + self._skill(agent, 'manipulation') + self._skill(agent, 'experimentation')) / 3
        if action == definition['best']:
            success_chance = clamp(0.30 + relevant * 0.50 + dev['manipulation'] * 0.20, 0.15, 0.95)
            success = random.random() < success_chance
            reward = definition['reward'] if success else random.uniform(-0.08, 0.18)
        else:
            # Rare coincidences can create false beliefs; repetition should later correct them.
            success = random.random() < 0.035
            reward = random.uniform(0.58, 0.78) if success else random.uniform(-0.22, 0.18)
        if definition.get('hazard') and action != definition['best'] and random.random() < definition['hazard'] * (1 - agent['traits']['risk'] * 0.4):
            agent['health'] = clamp(agent['health'] - random.uniform(2, 9), 0, 100)
            reward -= 0.35
            self._remember(agent, f"{definition['label']} m'a blessé pendant un essai.", 1.2)
        before, after = self._update_hypothesis(agent, artifact['type'], action, reward, 'expérience')
        self._practice(agent, 'experimentation', 0.014)
        self._practice(agent, 'manipulation', 0.010)
        self._practice(agent, f'action:{action}', 0.018 if success else 0.010)
        if action != 'inspect':
            self._practice(agent, 'tool_use', 0.008 if success else 0.003)
        self.unsaved_experiments.append((agent['id'], artifact['type'], action, reward, success, before, after, 'direct'))
        agent['energy'] = clamp(agent['energy'] - 1.0, 0, 100)
        agent['action_detail'] = f"teste {action} sur {definition['label'].lower()} ({'succès' if success else 'échec'})"
        self._maybe_discover(agent, artifact['type'], action)
        for observer in self.living():
            if observer['id'] != agent['id']:
                self._learn_from_observation(observer, agent, artifact['type'], action, reward)
        if random.random() < 0.07:
            self._log('experiment', f"#{agent['id']} teste {action} sur {definition['label']} : {'succès' if success else 'échec'}.")

    def _socialize(self, agent, other):
        a, b = self._relation(agent, other), self._relation(other, agent)
        compatibility = 1 - abs(agent['traits']['empathy'] - other['traits']['empathy']) * 0.35 - abs(agent['traits']['aggression'] - other['traits']['aggression']) * 0.25
        gain = 0.008 + compatibility * 0.010
        a['trust'] = clamp(a['trust'] + gain, 0, 1)
        a['affection'] = clamp(a['affection'] + gain * 0.8, 0, 1)
        a['encounters'] += 1
        b['trust'] = clamp(b['trust'] + gain * agent['traits']['trust'], 0, 1)
        b['affection'] = clamp(b['affection'] + gain * 0.65, 0, 1)
        b['encounters'] += 1
        agent['social_need'] = clamp(agent['social_need'] - 16, 0, 100)
        other['social_need'] = clamp(other['social_need'] - 7, 0, 100)
        self._practice(agent, 'communication', 0.006)
        self._practice(other, 'communication', 0.003)
        # Teaching is a social act, not inheritance. Parent-child gets a natural trust advantage.
        if agent['age'] >= 10 and random.random() < 0.25 + agent['traits']['sociability'] * 0.25:
            self._teach(agent, other)
        agent['action_detail'] = f"échange avec #{other['id']}"

    def _observe(self, agent, other, artifact):
        if artifact:
            self._perceive_artifact(agent, artifact)
            agent['action_detail'] = f"observe {ARTIFACT_TYPES[artifact['type']]['label'].lower()}"
        elif other:
            self._practice(agent, 'observation', 0.008 * development(agent['age'])['perception'])
            if other['action'] == 'experiment' and other['action_detail']:
                agent['action_detail'] = f"observe #{other['id']} expérimenter"
            else:
                agent['action_detail'] = f"observe #{other['id']}"

    def _help(self, agent, other):
        if agent['food_store'] > 0 and agent['traits']['empathy'] * agent['rules']['helpBias'] > 0.28:
            agent['food_store'] -= 1
            other['hunger'] = clamp(other['hunger'] - 28, 0, 100)
            other['food_store'] = min(4, other['food_store'] + 1)
            self._relation(other, agent)['trust'] = clamp(self._relation(other, agent)['trust'] + 0.10, 0, 1)
            self._remember(other, f"#{agent['id']} m'a aidé.", 1.2)
            self._log('social', f"#{agent['id']} partage de la nourriture avec #{other['id']}.")
        agent['action_detail'] = f"aide #{other['id']}"

    def _steal(self, agent, other):
        success = agent['traits']['aggression'] + agent['traits']['risk'] * 0.25 > other['traits']['aggression'] * 0.7 + random.random() * 0.65
        if success and other['food_store'] > 0:
            other['food_store'] -= 1
            agent['food_store'] += 1
            self._relation(other, agent)['trust'] = clamp(self._relation(other, agent)['trust'] - 0.28, 0, 1)
            self._remember(other, f"#{agent['id']} m'a volé.", 2.0)
            self._log('conflict', f"#{agent['id']} vole une réserve à #{other['id']}.")
        agent['action_detail'] = f"tente de voler #{other['id']}"

    def _mate(self, agent, other):
        if agent['mate_cooldown'] > 0 or other['mate_cooldown'] > 0 or len(self.living()) >= int(self.settings['maxPopulation']):
            return
        r1, r2 = self._relation(agent, other), self._relation(other, agent)
        compatibility = 0.35 + (r1['affection'] + r2['affection'] + r1['trust'] + r2['trust']) / 5
        consent = other['rules']['mateBias'] * self.settings['fertility'] * (0.55 + other['health'] / 200)
        if random.random() < compatibility * consent * 0.18:
            child = self._new_agent([agent, other])
            self.births += 1
            agent['mate_cooldown'] = other['mate_cooldown'] = 310
            self._log('birth', f"Naissance de #{child['id']}, enfant de #{agent['id']} et #{other['id']}. Il ne possède encore aucune connaissance technique.")
        agent['action_detail'] = f"se rapproche de #{other['id']}"

    def _die(self, agent, reason):
        agent['alive'] = False
        agent['death_year'] = self.year
        self.deaths += 1
        self._log('death', f"#{agent['id']} meurt ({reason}) à {agent['age']:.1f} ans.")

    def _act(self, agent, dt):
        if not agent['alive']:
            return
        dev = development(agent['age'])
        agent['age'] += dt / 255
        dependency = 1 - dev['autonomy']
        agent['hunger'] = clamp(agent['hunger'] + dt * (0.055 + self.settings['scarcityPressure'] * 0.022), 0, 100)
        agent['thirst'] = clamp(agent['thirst'] + dt * 0.075, 0, 100)
        agent['energy'] = clamp(agent['energy'] - dt * 0.035, 0, 100)
        agent['social_need'] = clamp(agent['social_need'] + dt * (0.03 + dependency * 0.03), 0, 100)
        agent['mate_cooldown'] -= dt
        if agent['hunger'] > 94 or agent['thirst'] > 94:
            agent['health'] -= dt * (0.16 + self.settings['scarcityPressure'] * 0.16)
        if agent['energy'] < 4:
            agent['health'] -= dt * 0.05
        if self._has_capability(agent, 'warmth'):
            agent['health'] = clamp(agent['health'] + dt * 0.005, 0, 100)
        if self._has_capability(agent, 'medicine') and agent['health'] < 70:
            agent['health'] = clamp(agent['health'] + dt * 0.015, 0, 100)
        lifespan = self.settings['lifespan'] * (0.78 + agent['health'] / 250)
        if agent['health'] <= 0 or (agent['age'] > lifespan and random.random() < 0.004 * dt):
            self._die(agent, 'épuisement' if agent['health'] <= 0 else 'vieillesse')
            return

        choice = self._choose_action(agent)
        agent['action'], agent['action_detail'] = choice, ''
        living = self.living()
        foods = [r for r in self.resources.values() if r['type'] == 'food']
        waters = [r for r in self.resources.values() if r['type'] == 'water']
        nearby_agent = self._nearest(agent, living, 90, lambda a: a['id'] != agent['id'])
        artifact = self._nearest(agent, list(self.artifacts.values()), 175)

        if choice == 'care':
            child = self._nearest(agent, living, 95, lambda a: a['age'] < 7 and a['id'] != agent['id'])
            if child:
                self._care(agent, child, dt)
        elif agent['age'] < 1.2:
            caregiver = self._find_caregiver(agent)
            if caregiver:
                agent['action_detail'] = f"dépend de #{caregiver['id']}"
            return
        elif choice == 'drink':
            water = self._nearest(agent, waters, 220)
            if water:
                self._move_toward(agent, water, dt, 1.1)
                if self._distance(agent, water) < 15:
                    agent['thirst'] = clamp(agent['thirst'] - 3.2 * dt, 0, 100)
            else:
                self._wander(agent, dt)
        elif choice == 'eat':
            if agent['food_store'] > 0 and agent['hunger'] > 52:
                agent['hunger'] = clamp(agent['hunger'] - 22 * dt, 0, 100)
                if random.random() < 0.08 * dt:
                    agent['food_store'] -= 1
            else:
                food = self._nearest(agent, foods, 240 if self._has_capability(agent, 'forage') else 175)
                if food:
                    self._move_toward(agent, food, dt, 1.0)
                    if self._distance(agent, food) < 12:
                        agent['hunger'] = clamp(agent['hunger'] - (34 if self._has_capability(agent, 'harvest') else 24), 0, 100)
                        if random.random() < (0.8 if self._has_capability(agent, 'farming') else 0.42):
                            agent['food_store'] = min(4, agent['food_store'] + 1)
                        self.resources.pop(food['id'], None)
                        self._practice(agent, 'gathering', 0.010)
                else:
                    self._wander(agent, dt)
        elif choice == 'rest':
            agent['energy'] = clamp(agent['energy'] + 0.72 * dt, 0, 100)
        elif choice == 'experiment' and artifact:
            self._move_toward(agent, artifact, dt, 0.8)
            if self._distance(agent, artifact) < 18:
                self._experiment(agent, artifact)
        elif choice == 'observe':
            self._observe(agent, nearby_agent, artifact)
        elif choice in ('socialize', 'help', 'steal', 'mate') and nearby_agent:
            self._move_toward(agent, nearby_agent, dt, 0.8)
            if self._distance(agent, nearby_agent) < 22:
                if choice == 'socialize': self._socialize(agent, nearby_agent)
                elif choice == 'help': self._help(agent, nearby_agent)
                elif choice == 'steal': self._steal(agent, nearby_agent)
                elif choice == 'mate': self._mate(agent, nearby_agent)
        else:
            self._wander(agent, dt)

    def _tick(self):
        self.year += 1 / 255
        for agent in list(self.living()):
            self._act(agent, 1.0)
        respawn = self.settings['resourceRespawn'] * self.settings['foodAbundance'] * (len(self.living()) / 80 + 0.35)
        food_count = sum(1 for r in self.resources.values() if r['type'] == 'food')
        if random.random() < respawn * 0.18 and food_count < 360:
            self._spawn_resource('food')
        if food_count < max(20, len(self.living()) * 0.22) and random.random() < 0.04:
            self._spawn_resource('food')

    def _loop(self):
        last = time.monotonic()
        base_ticks_per_second = 2.0
        while not self.stop_event.is_set():
            start = time.monotonic()
            elapsed = min(0.5, start - last)
            last = start
            with self.lock:
                if self.running:
                    self.tick_carry += elapsed * base_ticks_per_second * self.speed
                    steps = min(120, int(self.tick_carry))
                    self.tick_carry -= steps
                    for _ in range(steps):
                        self._tick()
                if start - self.last_persist >= 1.0:
                    self._persist()
                    self.last_persist = start
            time.sleep(max(0.01, 0.05 - (time.monotonic() - start)))

    def _log(self, kind, text):
        event = {'id': None, 'year': self.year, 'kind': kind, 'text': text}
        self.events.insert(0, event)
        self.events = self.events[:80]
        self.unsaved_events.append(event)

    def _persist(self, full_reset=False):
        timestamp = now_iso()
        with DB_LOCK:
            conn = connect()
            try:
                conn.execute('BEGIN IMMEDIATE')
                if full_reset:
                    conn.execute('DELETE FROM worlds WHERE id=?', (WORLD_ID,))
                conn.execute('''INSERT INTO worlds(id,year,running,speed,births,deaths,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET year=excluded.year,running=excluded.running,speed=excluded.speed,births=excluded.births,deaths=excluded.deaths,updated_at=excluded.updated_at''',
                    (WORLD_ID, self.year, int(self.running), self.speed, self.births, self.deaths, timestamp, timestamp))
                for key, value in self.settings.items():
                    conn.execute('INSERT INTO world_settings(world_id,key,value) VALUES(?,?,?) ON CONFLICT(world_id,key) DO UPDATE SET value=excluded.value', (WORLD_ID, key, float(value)))
                for a in self.agents.values():
                    tx = a['target']['x'] if a['target'] else None
                    ty = a['target']['y'] if a['target'] else None
                    conn.execute('''INSERT INTO agents(id,world_id,sex,x,y,age,health,energy,hunger,thirst,social_need,food_store,mate_cooldown,alive,action,action_detail,target_x,target_y,birth_year,death_year)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET x=excluded.x,y=excluded.y,age=excluded.age,health=excluded.health,energy=excluded.energy,hunger=excluded.hunger,thirst=excluded.thirst,social_need=excluded.social_need,food_store=excluded.food_store,mate_cooldown=excluded.mate_cooldown,alive=excluded.alive,action=excluded.action,action_detail=excluded.action_detail,target_x=excluded.target_x,target_y=excluded.target_y,death_year=excluded.death_year''',
                        (a['id'], WORLD_ID, a['sex'], a['x'], a['y'], a['age'], a['health'], a['energy'], a['hunger'], a['thirst'], a['social_need'], a['food_store'], a['mate_cooldown'], int(a['alive']), a['action'], a['action_detail'], tx, ty, a['birth_year'], a['death_year']))
                    for key, value in a['traits'].items():
                        conn.execute('INSERT INTO agent_traits(agent_id,trait,value) VALUES(?,?,?) ON CONFLICT(agent_id,trait) DO UPDATE SET value=excluded.value', (a['id'], key, value))
                    for key, value in a['rules'].items():
                        conn.execute('INSERT INTO agent_rules(agent_id,rule,value) VALUES(?,?,?) ON CONFLICT(agent_id,rule) DO UPDATE SET value=excluded.value', (a['id'], key, value))
                    for parent_id in a['parents']:
                        conn.execute('INSERT OR IGNORE INTO agent_parents(child_id,parent_id) VALUES(?,?)', (a['id'], parent_id))
                    for other_id, rel in a['relations'].items():
                        conn.execute('INSERT INTO relations(source_agent_id,target_agent_id,trust,affection,respect,encounters) VALUES(?,?,?,?,?,?) ON CONFLICT(source_agent_id,target_agent_id) DO UPDATE SET trust=excluded.trust,affection=excluded.affection,respect=excluded.respect,encounters=excluded.encounters', (a['id'], other_id, rel['trust'], rel['affection'], rel['respect'], rel['encounters']))
                    for artifact_type, belief in a['beliefs'].items():
                        conn.execute('INSERT INTO beliefs(agent_id,artifact_type,confidence,utility,attempts,action,source) VALUES(?,?,?,?,?,?,?) ON CONFLICT(agent_id,artifact_type) DO UPDATE SET confidence=excluded.confidence,utility=excluded.utility,attempts=excluded.attempts,action=excluded.action,source=excluded.source', (a['id'], artifact_type, belief['confidence'], belief['utility'], belief['attempts'], belief['action'], belief['source']))
                    for artifact_type, year in a['discoveries'].items():
                        conn.execute('INSERT OR IGNORE INTO discoveries(agent_id,artifact_type,discovered_year) VALUES(?,?,?)', (a['id'], artifact_type, year))
                    for skill, data in a['skills'].items():
                        conn.execute('INSERT INTO agent_skills(agent_id,skill,level,practice) VALUES(?,?,?,?) ON CONFLICT(agent_id,skill) DO UPDATE SET level=excluded.level,practice=excluded.practice', (a['id'], skill, data['level'], data['practice']))
                    for (subject, action), h in a['hypotheses'].items():
                        conn.execute('INSERT INTO hypotheses(agent_id,subject,action,confidence,evidence_for,evidence_against,source,updated_year) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(agent_id,subject,action) DO UPDATE SET confidence=excluded.confidence,evidence_for=excluded.evidence_for,evidence_against=excluded.evidence_against,source=excluded.source,updated_year=excluded.updated_year', (a['id'], subject, action, h['confidence'], h['evidence_for'], h['evidence_against'], h['source'], h['updated_year']))
                    for concept, data in a['concepts'].items():
                        conn.execute('INSERT INTO agent_concepts(agent_id,concept,confidence,evidence) VALUES(?,?,?,?) ON CONFLICT(agent_id,concept) DO UPDATE SET confidence=excluded.confidence,evidence=excluded.evidence', (a['id'], concept, data['confidence'], data['evidence']))
                conn.execute('DELETE FROM resources WHERE world_id=?', (WORLD_ID,))
                conn.executemany('INSERT INTO resources(id,world_id,resource_type,x,y,value) VALUES(?,?,?,?,?,?)', [(r['id'], WORLD_ID, r['type'], r['x'], r['y'], r['value']) for r in self.resources.values()])
                conn.execute('DELETE FROM artifacts WHERE world_id=?', (WORLD_ID,))
                conn.executemany('INSERT INTO artifacts(id,world_id,artifact_type,x,y) VALUES(?,?,?,?,?)', [(a['id'], WORLD_ID, a['type'], a['x'], a['y']) for a in self.artifacts.values()])
                for agent_id, m in self.unsaved_memories:
                    conn.execute('INSERT INTO memories(agent_id,year,text,weight) VALUES(?,?,?,?)', (agent_id, m['year'], m['text'], m['weight']))
                for event in self.unsaved_events:
                    cur = conn.execute('INSERT INTO events(world_id,year,kind,text,created_at) VALUES(?,?,?,?,?)', (WORLD_ID, event['year'], event['kind'], event['text'], timestamp))
                    event['id'] = cur.lastrowid
                for row in self.unsaved_experiments:
                    conn.execute('INSERT INTO experiments(agent_id,year,artifact_type,action,reward,success,confidence_before,confidence_after,source) VALUES(?,?,?,?,?,?,?,?,?)', (row[0], self.year, row[1], row[2], row[3], int(row[4]), row[5], row[6], row[7]))
                conn.commit()
                self.unsaved_memories.clear(); self.unsaved_events.clear(); self.unsaved_experiments.clear()
            finally:
                conn.close()

    def command(self, data):
        with self.lock:
            if 'running' in data:
                self.running = bool(data['running'])
            if 'speed' in data:
                self.speed = clamp(float(data['speed']), 0.25, 100.0)
            self._persist()
            return {'running': self.running, 'speed': self.speed}

    def update_settings(self, values):
        with self.lock:
            for key, value in values.items():
                if key in DEFAULT_SETTINGS:
                    self.settings[key] = float(value)
            self._persist()
            return dict(self.settings)

    def inject(self, artifact_type, count):
        if artifact_type not in ARTIFACT_TYPES:
            raise ValueError('unknown artifact type')
        count = int(clamp(int(count), 1, 100))
        with self.lock:
            for _ in range(count):
                self.next_artifact_id += 1
                self.artifacts[self.next_artifact_id] = {'id': self.next_artifact_id, 'type': artifact_type, 'x': random.uniform(30, 1170), 'y': random.uniform(30, 730)}
            self._log('inject', f"{count} × {ARTIFACT_TYPES[artifact_type]['label']} introduits. Aucun agent n'en reçoit la connaissance automatiquement.")
            self._persist()

    def shock(self, kind):
        with self.lock:
            if kind == 'drought':
                food_ids = [rid for rid, r in self.resources.items() if r['type'] == 'food']
                random.shuffle(food_ids)
                for rid in food_ids[:int(len(food_ids) * 0.62)]: self.resources.pop(rid, None)
                self._log('shock', 'Sécheresse : les ressources chutent brutalement.')
            elif kind == 'abundance':
                for _ in range(120): self._spawn_resource('food')
                self._log('shock', 'Abondance : arrivée massive de nourriture.')
            elif kind == 'disease':
                for a in self.living():
                    if random.random() < 0.28: a['health'] = clamp(a['health'] - random.uniform(8, 28), 1, 100)
                self._log('shock', 'Épidémie : une partie de la population perd de la santé.')
            else:
                raise ValueError('unknown shock')
            self._persist()

    def world_view(self):
        with self.lock:
            living = self.living()
            avg_age = sum(a['age'] for a in living) / len(living) if living else 0
            knowledge = {}
            for artifact_type in ARTIFACT_TYPES:
                known = sum(1 for a in living if artifact_type in a['discoveries'])
                hypotheses = sum(1 for a in living if any(s == f'artifact:{artifact_type}' and h['confidence'] >= 0.25 for (s, _), h in a['hypotheses'].items()))
                knowledge[artifact_type] = {'known': known, 'hypothesizing': hypotheses, 'percent': known / len(living) if living else 0}
            return {
                'year': self.year, 'running': self.running, 'speed': self.speed, 'births': self.births, 'deaths': self.deaths,
                'population': len(living), 'avgAge': avg_age, 'settings': dict(self.settings),
                'agents': [{'id': a['id'], 'sex': a['sex'], 'x': a['x'], 'y': a['y'], 'age': a['age'], 'health': a['health'], 'action': a['action']} for a in living],
                'food': [{'id': r['id'], 'x': r['x'], 'y': r['y']} for r in self.resources.values() if r['type'] == 'food'],
                'water': [{'id': r['id'], 'x': r['x'], 'y': r['y'], 'r': r['value']} for r in self.resources.values() if r['type'] == 'water'],
                'artifacts': list(self.artifacts.values()), 'events': self.events[:40], 'knowledge': knowledge,
            }

    def agent_view(self, agent_id):
        with self.lock:
            a = self.agents.get(agent_id)
            if not a:
                return None
            children = [o['id'] for o in self.agents.values() if agent_id in o['parents']]
            dev = development(a['age'])
            hypotheses = [
                {'subject': s, 'action': action, **h}
                for (s, action), h in sorted(a['hypotheses'].items(), key=lambda kv: kv[1]['confidence'], reverse=True)[:20]
            ]
            concepts = [{'concept': k, **v} for k, v in sorted(a['concepts'].items(), key=lambda kv: kv[1]['confidence'], reverse=True)[:12]]
            return {
                'id': a['id'], 'sex': a['sex'], 'age': a['age'], 'alive': a['alive'], 'health': a['health'], 'energy': a['energy'],
                'hunger': a['hunger'], 'thirst': a['thirst'], 'socialNeed': a['social_need'], 'foodStore': a['food_store'],
                'action': a['action'], 'actionDetail': a['action_detail'], 'traits': a['traits'], 'rules': a['rules'],
                'lastDecision': a['last_decision'], 'beliefs': a['beliefs'], 'discoveries': a['discoveries'], 'memory': a['memory'],
                'relations': a['relations'], 'parents': a['parents'], 'children': children, 'birthYear': a['birth_year'], 'deathYear': a['death_year'],
                'development': dev, 'skills': a['skills'], 'hypotheses': hypotheses, 'concepts': concepts,
            }
