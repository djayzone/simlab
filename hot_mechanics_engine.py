import copy
import hashlib
import json
import os
import random
import time
from pathlib import Path

from engine import ARTIFACT_TYPES, DB_LOCK, WORLD_ID, clamp, connect
from weather_control_engine import Engine as WeatherControlEngine

MECHANICS_DIR = Path(os.getenv('SIM_MECHANICS_DIR', '/mechanics'))
RELOAD_INTERVAL_SECONDS = 2.0


def ensure_mechanics_schema():
    with DB_LOCK:
        conn = connect()
        try:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS mechanic_activations (
                  world_id INTEGER NOT NULL,
                  mechanic_id TEXT NOT NULL,
                  version TEXT NOT NULL,
                  activated_year REAL NOT NULL,
                  activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY(world_id, mechanic_id, version)
                );
            ''')
            conn.commit()
        finally:
            conn.close()


class Engine(WeatherControlEngine):
    """Gameplay extension layer whose JSON packs can change without restarting the simulation."""

    def __init__(self):
        ensure_mechanics_schema()
        self._base_artifact_types = copy.deepcopy(ARTIFACT_TYPES)
        self._dynamic_artifact_types = set()
        self.mechanics = {}
        self.mechanics_generation = 0
        self.mechanics_digest = None
        self.mechanics_error = None
        self.mechanics_last_reload = None
        self._next_mechanics_scan = 0.0
        super().__init__()
        with self.lock:
            self._reload_mechanics(force=True)

    def _mechanic_files(self):
        if not MECHANICS_DIR.exists():
            return []
        return sorted(MECHANICS_DIR.glob('*.json'))

    def _read_mechanic_packs(self):
        raw_files, packs = [], []
        for path in self._mechanic_files():
            raw = path.read_bytes()
            raw_files.append(path.name.encode() + b'\0' + raw)
            payload = json.loads(raw.decode('utf-8'))
            if payload.get('schema') != 1:
                raise ValueError(f'{path.name}: unsupported schema')
            mechanic_id = str(payload.get('id') or '').strip()
            version = str(payload.get('version') or '').strip()
            if not mechanic_id or not version:
                raise ValueError(f'{path.name}: id/version required')
            if not isinstance(payload.get('artifacts', {}), dict):
                raise ValueError(f'{path.name}: artifacts must be an object')
            packs.append(payload)
        return hashlib.sha256(b'\n'.join(raw_files)).hexdigest(), packs

    def _validate_artifact(self, mechanic_id, artifact_type, definition):
        required = ('label', 'best', 'discovery', 'bonus', 'reward', 'properties')
        missing = [key for key in required if key not in definition]
        if missing:
            raise ValueError(f'{mechanic_id}/{artifact_type}: missing {missing}')
        if definition['best'] not in {'inspect', 'manipulate', 'strike', 'feed', 'bury', 'roll', 'consume'}:
            raise ValueError(f'{mechanic_id}/{artifact_type}: unsupported action {definition["best"]}')
        if not isinstance(definition['properties'], list):
            raise ValueError(f'{mechanic_id}/{artifact_type}: properties must be a list')
        definition['reward'] = float(definition['reward'])
        if 'hazard' in definition:
            definition['hazard'] = clamp(float(definition['hazard']), 0, 1)

    def _activation_seen(self, mechanic_id, version):
        with DB_LOCK:
            conn = connect()
            try:
                return bool(conn.execute(
                    'SELECT 1 FROM mechanic_activations WHERE world_id=? AND mechanic_id=? AND version=?',
                    (WORLD_ID, mechanic_id, version),
                ).fetchone())
            finally:
                conn.close()

    def _introduce_pack(self, pack):
        mechanic_id, version = pack['id'], pack['version']
        if self._activation_seen(mechanic_id, version):
            return

        created = []
        next_id = self.next_artifact_id
        for introduction in pack.get('introduce', []):
            artifact_type = introduction.get('artifact')
            if artifact_type not in ARTIFACT_TYPES:
                continue
            count = int(clamp(int(introduction.get('count', 1)), 0, 100))
            for _ in range(count):
                next_id += 1
                created.append({
                    'id': next_id,
                    'type': artifact_type,
                    'x': random.uniform(30, 1170),
                    'y': random.uniform(30, 730),
                })

        with DB_LOCK:
            conn = connect()
            try:
                conn.execute('BEGIN IMMEDIATE')
                for artifact in created:
                    conn.execute(
                        'INSERT INTO artifacts(id,world_id,artifact_type,x,y) VALUES(?,?,?,?,?)',
                        (artifact['id'], WORLD_ID, artifact['type'], artifact['x'], artifact['y']),
                    )
                conn.execute(
                    'INSERT INTO mechanic_activations(world_id,mechanic_id,version,activated_year) VALUES(?,?,?,?)',
                    (WORLD_ID, mechanic_id, version, self.year),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        for artifact in created:
            self.artifacts[artifact['id']] = artifact
        self.next_artifact_id = next_id
        self._log('mechanic', f"Mécanique « {pack.get('name', mechanic_id)} » v{version} disponible dans le monde. Aucun agent ne la connaît automatiquement.")

    def _reload_mechanics(self, force=False):
        try:
            digest, packs = self._read_mechanic_packs()
            if not force and digest == self.mechanics_digest:
                return False

            definitions, registry = {}, {}
            for pack in packs:
                if not pack.get('enabled', True):
                    continue
                mechanic_id = pack['id']
                for artifact_type, definition in pack.get('artifacts', {}).items():
                    definition = copy.deepcopy(definition)
                    self._validate_artifact(mechanic_id, artifact_type, definition)
                    definition['_mechanic'] = mechanic_id
                    definition['_effects'] = copy.deepcopy(definition.pop('effects', []))
                    definitions[artifact_type] = definition
                registry[mechanic_id] = {
                    'id': mechanic_id,
                    'name': pack.get('name', mechanic_id),
                    'version': pack['version'],
                    'enabled': True,
                    'artifacts': sorted(pack.get('artifacts', {}).keys()),
                }

            previous_dynamic = {
                artifact_type: copy.deepcopy(ARTIFACT_TYPES[artifact_type])
                for artifact_type in self._dynamic_artifact_types
                if artifact_type in ARTIFACT_TYPES
            }
            persistent_types = {artifact['type'] for artifact in self.artifacts.values()}
            for artifact_type, old_definition in previous_dynamic.items():
                if artifact_type not in definitions and artifact_type in persistent_types:
                    old_definition['_retired'] = True
                    definitions[artifact_type] = old_definition

            for artifact_type in self._dynamic_artifact_types:
                if artifact_type not in self._base_artifact_types:
                    ARTIFACT_TYPES.pop(artifact_type, None)
            for artifact_type, definition in self._base_artifact_types.items():
                ARTIFACT_TYPES[artifact_type] = copy.deepcopy(definition)
            ARTIFACT_TYPES.update(definitions)

            self._dynamic_artifact_types = set(definitions)
            self.mechanics = registry
            self.mechanics_digest = digest
            self.mechanics_generation += 1
            self.mechanics_last_reload = time.time()
            self.mechanics_error = None

            for pack in packs:
                if pack.get('enabled', True):
                    self._introduce_pack(pack)
            return True
        except Exception as exc:
            self.mechanics_error = str(exc)
            self._log('mechanic_error', f'Échec du rechargement des mécaniques : {exc}')
            return False

    def _apply_hot_effects(self, agent, artifact_type):
        definition = ARTIFACT_TYPES.get(artifact_type, {})
        if definition.get('_retired'):
            return
        for effect in definition.get('_effects', []):
            chance = clamp(float(effect.get('chance', 1.0)), 0, 1)
            if random.random() > chance:
                continue
            kind = effect.get('type')
            if kind == 'practice':
                self._practice(agent, str(effect.get('skill', 'experimentation')), float(effect.get('amount', 0.01)))
            elif kind == 'food_store':
                agent['food_store'] = max(0, min(8, agent.get('food_store', 0) + int(effect.get('amount', 1))))
            elif kind == 'energy':
                agent['energy'] = clamp(agent['energy'] + float(effect.get('amount', 0)), 0, 100)
            elif kind == 'spawn_resource':
                self.next_resource_id += 1
                self.resources[self.next_resource_id] = {
                    'id': self.next_resource_id,
                    'type': str(effect.get('resource', 'food')),
                    'x': clamp(agent['x'] + random.uniform(-20, 20), 10, 1190),
                    'y': clamp(agent['y'] + random.uniform(-20, 20), 10, 750),
                    'value': float(effect.get('value', 1.0)),
                }
            elif kind == 'spawn_artifact':
                target = str(effect.get('artifact', ''))
                if target in ARTIFACT_TYPES and not ARTIFACT_TYPES[target].get('_retired'):
                    self.next_artifact_id += 1
                    self.artifacts[self.next_artifact_id] = {
                        'id': self.next_artifact_id,
                        'type': target,
                        'x': clamp(agent['x'] + random.uniform(-12, 12), 20, 1180),
                        'y': clamp(agent['y'] + random.uniform(-12, 12), 20, 740),
                    }

    def _update_hypothesis(self, agent, artifact_type, action, reward, source='direct'):
        before, after = super()._update_hypothesis(agent, artifact_type, action, reward, source)
        definition = ARTIFACT_TYPES.get(artifact_type)
        if definition and definition.get('_mechanic') and not definition.get('_retired') and action == definition['best'] and reward > 0.55:
            self._apply_hot_effects(agent, artifact_type)
        return before, after

    def _tick(self):
        now = time.monotonic()
        if now >= self._next_mechanics_scan:
            self._next_mechanics_scan = now + RELOAD_INTERVAL_SECONDS
            self._reload_mechanics()
        super()._tick()

    def world_view(self):
        data = super().world_view()
        data['artifactCatalog'] = {
            artifact_type: {
                'label': definition.get('label', artifact_type),
                'discovery': definition.get('discovery', ''),
                'bonus': definition.get('bonus', ''),
                'mechanic': definition.get('_mechanic'),
                'retired': bool(definition.get('_retired')),
            }
            for artifact_type, definition in ARTIFACT_TYPES.items()
        }
        data['mechanics'] = {
            'generation': self.mechanics_generation,
            'digest': self.mechanics_digest,
            'lastReload': self.mechanics_last_reload,
            'error': self.mechanics_error,
            'active': list(self.mechanics.values()),
            'retiredArtifacts': sorted(
                artifact_type for artifact_type in self._dynamic_artifact_types
                if ARTIFACT_TYPES.get(artifact_type, {}).get('_retired')
            ),
        }
        return data
