import math
import random
from datetime import datetime, timezone

from engine import (
    Engine as BaseEngine,
    ARTIFACT_TYPES,
    DB_LOCK,
    WORLD_ID,
    clamp,
    connect,
    development,
    now_iso,
)

BASE_TICKS_PER_SECOND = 2.0
MAX_DEPLOY_CATCHUP_SECONDS = 60.0


def ensure_survival_schema():
    """Additive/idempotent schema extension for continuity and spatial memory."""
    with DB_LOCK:
        conn = connect()
        try:
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(worlds)')}
            if 'last_tick_at' not in columns:
                conn.execute('ALTER TABLE worlds ADD COLUMN last_tick_at TEXT')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS resource_memories (
                  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                  resource_type TEXT NOT NULL CHECK(resource_type IN ('food','water')),
                  x REAL NOT NULL,
                  y REAL NOT NULL,
                  confidence REAL NOT NULL DEFAULT 0,
                  last_seen_year REAL NOT NULL,
                  successful_uses INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(agent_id, resource_type)
                )
            ''')
            conn.commit()
        finally:
            conn.close()


class Engine(BaseEngine):
    """Playable calibration layer with developmental learning and durable survival memory."""

    def __init__(self):
        ensure_survival_schema()
        self._persisted_last_tick_at = None
        self._startup_last_tick_at = None
        super().__init__()
        # BaseEngine starts its loop at the end of __init__. The startup timestamp is kept
        # separately so an immediate flush by that thread cannot erase the downtime origin.
        with self.lock:
            self._catch_up_short_downtime()

    def _load(self):
        loaded = super()._load()
        if not loaded:
            return False
        with DB_LOCK:
            conn = connect()
            try:
                world = conn.execute('SELECT last_tick_at,updated_at FROM worlds WHERE id=?', (WORLD_ID,)).fetchone()
                # `updated_at` is the bridge for the first deployment of this migration:
                # the previous engine already flushed it every second before last_tick_at existed.
                timestamp = (world['last_tick_at'] or world['updated_at']) if world else None
                self._persisted_last_tick_at = timestamp
                self._startup_last_tick_at = timestamp
                memories = {}
                for row in conn.execute('SELECT * FROM resource_memories'):
                    memories.setdefault(row['agent_id'], {})[row['resource_type']] = {
                        'x': float(row['x']),
                        'y': float(row['y']),
                        'confidence': float(row['confidence']),
                        'last_seen_year': float(row['last_seen_year']),
                        'successful_uses': int(row['successful_uses']),
                    }
                for agent in self.agents.values():
                    agent['resource_memory'] = memories.get(agent['id'], {})
                return True
            finally:
                conn.close()

    def _new_agent(self, parents):
        agent = super()._new_agent(parents)
        agent['resource_memory'] = {}
        return agent

    def _persist(self, full_reset=False):
        super()._persist(full_reset=full_reset)
        timestamp = now_iso()
        with DB_LOCK:
            conn = connect()
            try:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('UPDATE worlds SET last_tick_at=? WHERE id=?', (timestamp, WORLD_ID))
                for agent in self.agents.values():
                    for resource_type, memory in agent.get('resource_memory', {}).items():
                        conn.execute('''
                            INSERT INTO resource_memories(
                              agent_id,resource_type,x,y,confidence,last_seen_year,successful_uses
                            ) VALUES(?,?,?,?,?,?,?)
                            ON CONFLICT(agent_id,resource_type) DO UPDATE SET
                              x=excluded.x,
                              y=excluded.y,
                              confidence=excluded.confidence,
                              last_seen_year=excluded.last_seen_year,
                              successful_uses=excluded.successful_uses
                        ''', (
                            agent['id'], resource_type, memory['x'], memory['y'],
                            memory['confidence'], memory['last_seen_year'], memory['successful_uses'],
                        ))
                conn.commit()
                self._persisted_last_tick_at = timestamp
            finally:
                conn.close()

    def _catch_up_short_downtime(self):
        if not self.running or not self._startup_last_tick_at:
            return
        try:
            last = datetime.fromisoformat(self._startup_last_tick_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except ValueError:
            return
        downtime = max(0.0, (datetime.now(timezone.utc) - last).total_seconds())
        replay_seconds = min(downtime, MAX_DEPLOY_CATCHUP_SECONDS)
        steps = int(replay_seconds * BASE_TICKS_PER_SECOND * self.speed)
        if steps <= 0:
            return
        for _ in range(steps):
            self._tick()
        if downtime > MAX_DEPLOY_CATCHUP_SECONDS:
            self._log('system', f"Reprise après interruption longue : {MAX_DEPLOY_CATCHUP_SECONDS:.0f}s de temps réel rattrapées sur {downtime:.0f}s.")
        else:
            self._log('system', f"Continuité moteur : {downtime:.1f}s d'interruption rattrapées au redémarrage.")
        self._persist()
        self._startup_last_tick_at = None

    def _remember_resource(self, agent, resource_type, resource, success=False):
        if not resource:
            return
        memories = agent.setdefault('resource_memory', {})
        old = memories.get(resource_type)
        seen_gain = 0.22 + self._skill(agent, 'observation') * 0.18
        confidence = clamp((old['confidence'] if old else 0.0) + seen_gain + (0.18 if success else 0), 0, 1)
        memory = {
            'x': float(resource['x']),
            'y': float(resource['y']),
            'confidence': confidence,
            'last_seen_year': self.year,
            'successful_uses': (old['successful_uses'] if old else 0) + (1 if success else 0),
        }
        if resource_type == 'water':
            memory['radius'] = self._water_radius(resource)
        memories[resource_type] = memory

    def _resource_items(self, resource_type):
        """Return a stable view for one resource type.

        The base gameplay engine keeps the simple semantics. The composed
        runtime overrides this hook with a signature-aware cache so hot-path
        callers do not rebuild the same lists for every agent.
        """
        return tuple(
            resource
            for resource in self.resources.values()
            if resource['type'] == resource_type
        )

    def _artifact_items(self):
        """Return the current artifact membership as an immutable view."""
        return tuple(self.artifacts.values())

    def _known_resource_target(self, agent, resource_type):
        memory = agent.get('resource_memory', {}).get(resource_type)
        if not memory or memory['confidence'] < 0.12:
            return None
        target = {'x': memory['x'], 'y': memory['y'], '_memory': True, 'type': resource_type}
        if resource_type == 'water':
            target['radius'] = float(memory.get('radius', 24.0))
        return target

    def _water_radius(self, water):
        if not water:
            return 0.0
        return max(6.0, float(water.get('radius', water.get('r', water.get('value', 24.0)))))

    def _distance_to_water_edge(self, agent, water):
        """Distance to drinkable shoreline, not to the visual centre of the pond."""
        if not water:
            return float('inf')
        return max(0.0, self._distance(agent, water) - self._water_radius(water))

    def _nearest_water_by_edge(self, agent, waters, max_edge_distance):
        best, best_distance = None, max_edge_distance
        for water in waters:
            distance = self._distance_to_water_edge(agent, water)
            if distance < best_distance:
                best, best_distance = water, distance
        return best

    def _water_shore_target(self, agent, water, margin=4.0):
        """Pick a stable point just outside the pond instead of its centre."""
        radius = self._water_radius(water)
        dx, dy = agent['x'] - water['x'], agent['y'] - water['y']
        distance = math.hypot(dx, dy)
        if distance > 0.5:
            angle = math.atan2(dy, dx)
        else:
            angle = (agent['id'] * 2.3999632297 + float(water.get('id', 0)) * 0.6180339887) % math.tau

        target_distance = radius + margin
        for candidate_angle in (angle, angle + math.pi, angle + math.pi / 2, angle - math.pi / 2):
            x = clamp(water['x'] + math.cos(candidate_angle) * target_distance, 8, 1192)
            y = clamp(water['y'] + math.sin(candidate_angle) * target_distance, 8, 752)
            if math.hypot(x - water['x'], y - water['y']) >= radius + 1.0:
                return {'x': x, 'y': y, '_shore': True}
        return {'x': agent['x'], 'y': agent['y'], '_shore': True}

    def _set_water_departure(self, agent, water):
        """After drinking, create a short outward excursion so the shoreline is a stop, not a home."""
        radius = self._water_radius(water)
        dx, dy = agent['x'] - water['x'], agent['y'] - water['y']
        if math.hypot(dx, dy) > 0.5:
            angle = math.atan2(dy, dx)
        else:
            angle = (agent['id'] * 2.3999632297 + float(water.get('id', 0)) * 0.6180339887) % math.tau
        angle += (agent['traits']['risk'] - 0.5) * 0.7
        excursion = radius + 90 + agent['traits']['curiosity'] * 70
        x = clamp(water['x'] + math.cos(angle) * excursion, 20, 1180)
        y = clamp(water['y'] + math.sin(angle) * excursion, 20, 740)
        if math.hypot(x - water['x'], y - water['y']) <= radius + 20:
            angle += math.pi
            x = clamp(water['x'] + math.cos(angle) * excursion, 20, 1180)
            y = clamp(water['y'] + math.sin(angle) * excursion, 20, 740)
        agent['_water_departure_target'] = {'x': x, 'y': y}
        agent['_water_departure_ttl'] = 110

    def _degrade_resource_memory(self, agent, resource_type, amount=0.30):
        memory = agent.get('resource_memory', {}).get(resource_type)
        if not memory:
            return
        memory['confidence'] = clamp(memory['confidence'] - amount, 0, 1)
        if memory['confidence'] <= 0.05:
            agent['resource_memory'].pop(resource_type, None)

    def _safe_excursion_radius(self, agent):
        """Distance an agent can reasonably explore while retaining a safe water return margin."""
        dev = development(agent['age'])
        travel = clamp(self._skill(agent, 'travel'), 0, 1)
        observation = clamp(self._skill(agent, 'observation'), 0, 1)
        radius = (
            150
            + 210 * dev['autonomy']
            + 105 * agent['traits']['curiosity']
            + 220 * travel
            + 70 * observation
        )
        return clamp(radius, 120, 650)

    def _water_return_urgency(self, agent, known_water):
        if not known_water:
            return 0.0
        distance = self._distance_to_water_edge(agent, known_water)
        safe_radius = self._safe_excursion_radius(agent)
        # Farther travellers turn back sooner. Close to water they can comfortably wait
        # until they are actually thirsty, which prevents permanent clustering.
        ratio = clamp(distance / max(safe_radius, 1), 0, 1.4)
        return_threshold = 62 - min(27, ratio * 27)
        urgency = clamp((agent['thirst'] - return_threshold) / 24, 0, 1) * 1.85
        if distance > safe_radius:
            urgency = max(urgency, 2.25 + min(0.5, (distance - safe_radius) / 220))
        return urgency

    def _explore(self, agent, dt):
        """Persistent directional excursion instead of a local random walk."""
        dev = development(agent['age'])
        known_water = self._known_resource_target(agent, 'water')
        safe_radius = self._safe_excursion_radius(agent)

        departure_target = agent.get('_water_departure_target')
        departure_ttl = int(agent.get('_water_departure_ttl', 0))
        if departure_target and departure_ttl > 0:
            if self._distance(agent, departure_target) < 18:
                agent.pop('_water_departure_target', None)
                agent.pop('_water_departure_ttl', None)
            else:
                self._move_toward(agent, departure_target, dt, 1.30 + dev['locomotion'] * 0.20)
                agent['_water_departure_ttl'] = departure_ttl - 1
                self._practice(agent, 'travel', 0.0024 * max(dev['locomotion'], 0.2))
                agent['action_detail'] = "s’éloigne de la berge après s’être hydraté"
                return

        if known_water and self._distance_to_water_edge(agent, known_water) > safe_radius:
            agent.pop('_exploration_target', None)
            agent.pop('_exploration_ttl', None)
            shore = self._water_shore_target(agent, known_water)
            self._move_toward(agent, shore, dt, 1.25 + dev['locomotion'] * 0.25)
            agent['action_detail'] = "fait demi-tour vers la berge connue avant d’être en danger"
            return

        target = agent.get('_exploration_target')
        ttl = int(agent.get('_exploration_ttl', 0))
        if not target or ttl <= 0 or self._distance(agent, target) < 24:
            angle = random.random() * math.tau
            leg = random.uniform(max(95, safe_radius * 0.38), max(145, safe_radius * 0.72))
            target = {
                'x': clamp(agent['x'] + math.cos(angle) * leg, 20, 980),
                'y': clamp(agent['y'] + math.sin(angle) * leg, 20, 680),
            }
            agent['_exploration_target'] = target
            agent['_exploration_ttl'] = int(80 + leg * 0.35)

        travel_skill = clamp(self._skill(agent, 'travel'), 0, 1)
        speed = 1.18 + dev['locomotion'] * 0.28 + travel_skill * 0.22
        self._move_toward(agent, target, dt, speed)
        agent['_exploration_ttl'] = max(0, int(agent.get('_exploration_ttl', 1)) - 1)
        self._practice(agent, 'travel', 0.0024 * max(dev['locomotion'], 0.2))
        agent['action_detail'] = 'suit une direction d’exploration sur plusieurs étapes'

    def _death_reason(self, agent):
        thirst = agent['thirst']
        hunger = agent['hunger']
        energy = agent['energy']
        if thirst >= 96 and thirst >= hunger:
            return 'déshydratation'
        if hunger >= 96:
            return 'famine'
        if energy < 4:
            return 'épuisement'
        return agent.get('_last_damage_cause', 'blessure ou affaiblissement')

    def _artifact_uncertainty(self, agent, artifact_type):
        """Keep curiosity alive until the action space is actually explored.

        A single confident (and potentially false) hypothesis must not make the
        whole artefact look solved. Use mean uncertainty across the hypotheses
        the agent can currently imagine instead of the previous max-confidence
        shortcut.
        """
        subject = f'artifact:{artifact_type}'
        hypotheses = [
            h for (seen_subject, _), h in agent['hypotheses'].items()
            if seen_subject == subject
        ]
        if not hypotheses:
            return 1.0
        return sum(1.0 - clamp(h['confidence'], 0, 1) for h in hypotheses) / len(hypotheses)

    def _update_hypothesis(self, agent, artifact_type, action, reward, source='direct'):
        before, after = super()._update_hypothesis(agent, artifact_type, action, reward, source)
        h = agent['hypotheses'][(f'artifact:{artifact_type}', action)]

        # Direct successful experience must converge within a handful of
        # coherent trials. The base Bayesian-ish update remains authoritative;
        # this momentum term only prevents useful evidence from taking dozens
        # of repetitions at the default learning rate.
        if reward > 0.55:
            momentum = (
                0.09 + self.settings['learningRate'] * 0.18
            ) * (0.65 + agent['traits']['curiosity'] * 0.35)
            h['confidence'] = clamp(
                h['confidence'] + momentum * (1 - h['confidence']), 0, 1
            )
            after = h['confidence']

        definition = ARTIFACT_TYPES.get(artifact_type, {})
        label = definition.get('label', artifact_type)
        if before < 0.30 <= after:
            self._log('learning', f"#{agent['id']} commence à soupçonner un usage de {label.lower()} ({action}).")
        elif before < 0.50 <= after:
            self._log('learning', f"#{agent['id']} consolide son hypothèse sur {label.lower()} ({action}).")
        return before, after

    def _learn_from_observation(self, observer, actor, artifact_type, action, reward):
        dev = development(observer['age'])
        if dev['imitation'] < 0.08 or self._distance(observer, actor) > 90:
            return False

        rel = self._relation(observer, actor)
        reliability = 0.15 + rel['trust'] * 0.45 + self._skill(observer, 'observation') * 0.30
        factor = self.settings['socialLearning'] * dev['imitation'] * reliability
        learn_chance = clamp(0.12 + factor * 1.40, 0.12, 0.72)
        if random.random() > learn_chance:
            return False

        subject = f'artifact:{artifact_type}'
        h = self._hypothesis(observer, subject, action, f'observation #{actor["id"]}')
        before = h['confidence']
        if reward > 0.55:
            delta = (0.08 + factor * 0.18) * (1 - h['confidence'])
            h['confidence'] = clamp(h['confidence'] + delta, 0, 1)
            h['evidence_for'] += 0.55 + factor * 0.25
            self._practice(observer, f'action:{action}', 0.003)
        else:
            h['confidence'] = clamp(h['confidence'] - (0.025 + factor * 0.04), 0, 1)
            h['evidence_against'] += 0.30
        h['source'], h['updated_year'] = f'observation #{actor["id"]}', self.year
        self._practice(observer, 'observation', 0.010)
        self._practice(observer, 'imitation', 0.009)

        if before < 0.30 <= h['confidence']:
            label = ARTIFACT_TYPES.get(artifact_type, {}).get('label', artifact_type)
            self._log('learning', f"#{observer['id']} apprend en observant #{actor['id']} utiliser {label.lower()}.")
        self._maybe_discover(observer, artifact_type, action)
        return True

    def _teach(self, teacher, student):
        dev = development(student['age'])
        if dev['communication'] < 0.12 or not teacher['hypotheses']:
            return False

        rel = self._relation(student, teacher)
        candidates = []

        # A mastered discovery is what a teacher should preferentially transmit.
        # Fall back to hypotheses so cultures can still carry incomplete or even
        # mistaken ideas instead of receiving hidden canonical knowledge.
        for artifact_type in teacher.get('discoveries', {}):
            definition = ARTIFACT_TYPES.get(artifact_type)
            if not definition:
                continue
            key = (f'artifact:{artifact_type}', definition['best'])
            source_h = teacher['hypotheses'].get(key)
            if source_h:
                candidates.append((key, source_h, 1))
        for key, source_h in teacher['hypotheses'].items():
            if not any(existing[0] == key for existing in candidates):
                candidates.append((key, source_h, 0))
        candidates.sort(key=lambda item: (item[2], item[1]['confidence']), reverse=True)
        if not candidates:
            return False

        (subject, action), source_h, _ = candidates[0]
        transmission = self.settings['socialLearning'] * (
            0.35 + self._skill(teacher, 'teaching') * 0.45
        ) * (0.40 + rel['trust'] * 0.50) * (0.50 + dev['communication'] * 0.50)
        teach_chance = clamp(0.10 + transmission, 0.10, 0.70)
        if random.random() > teach_chance:
            return False

        target = self._hypothesis(student, subject, action, f'enseignement #{teacher["id"]}')
        before = target['confidence']
        ceiling = clamp(source_h['confidence'] * 0.95 + 0.08, 0.25, 0.88)
        step = 0.10 + transmission * 0.18
        target['confidence'] = min(ceiling, target['confidence'] + step)
        target['evidence_for'] += 0.60 + transmission * 0.30
        target['source'], target['updated_year'] = f'enseignement #{teacher["id"]}', self.year
        self._practice(teacher, 'teaching', 0.014)
        self._practice(student, 'communication', 0.008)

        if subject.startswith('artifact:'):
            artifact_type = subject.split(':', 1)[1]
            self._practice(student, f'action:{action}', 0.002)
            if before < 0.30 <= target['confidence']:
                label = ARTIFACT_TYPES.get(artifact_type, {}).get('label', artifact_type)
                self._log('learning', f"#{teacher['id']} transmet à #{student['id']} une piste sur {label.lower()}.")
            self._maybe_discover(student, artifact_type, action)
        return True

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
            attempts = h['evidence_for'] + h['evidence_against']
            novelty = 1 / (1 + attempts)
            # Prefer untested possibilities, then let accumulated evidence and
            # learned concepts take over. This prevents one lucky false positive
            # from trapping an agent on the same bad action forever.
            return (
                novelty * (0.45 + agent['traits']['curiosity'] * 0.30)
                + h['confidence'] * 0.28
                + concept * 0.38
                + random.random() * agent['traits']['creativity'] * 0.12
            )

        action = max(allowed, key=action_score)
        h_before = self._hypothesis(agent, subject, action, 'self')
        first_attempt = (h_before['evidence_for'] + h_before['evidence_against']) < 0.01

        definition = ARTIFACT_TYPES[artifact['type']]
        relevant = (
            self._skill(agent, f'action:{action}')
            + self._skill(agent, 'manipulation')
            + self._skill(agent, 'experimentation')
        ) / 3
        if action == definition['best']:
            success_chance = clamp(
                0.38 + relevant * 0.42 + dev['manipulation'] * 0.18,
                0.22,
                0.96,
            )
            success = random.random() < success_chance
            reward = definition['reward'] if success else random.uniform(-0.08, 0.18)
        else:
            success = random.random() < 0.035
            reward = random.uniform(0.58, 0.78) if success else random.uniform(-0.22, 0.18)

        if definition.get('hazard') and action != definition['best'] and random.random() < definition['hazard'] * (1 - agent['traits']['risk'] * 0.4):
            agent['health'] = clamp(agent['health'] - random.uniform(2, 9), 0, 100)
            reward -= 0.35
            self._remember(agent, f"{definition['label']} m'a blessé pendant un essai.", 1.2)

        before, after = self._update_hypothesis(agent, artifact['type'], action, reward, 'expérience')
        self._practice(agent, 'experimentation', 0.018)
        self._practice(agent, 'manipulation', 0.012)
        self._practice(agent, f'action:{action}', 0.020 if success else 0.011)
        if action != 'inspect':
            self._practice(agent, 'tool_use', 0.010 if success else 0.004)

        self.unsaved_experiments.append((
            agent['id'], artifact['type'], action, reward, success, before, after, 'direct'
        ))
        agent['energy'] = clamp(agent['energy'] - 0.8, 0, 100)
        agent['action_detail'] = f"teste {action} sur {definition['label'].lower()} ({'succès' if success else 'échec'})"
        self._maybe_discover(agent, artifact['type'], action)

        for observer in self.living():
            if observer['id'] != agent['id']:
                self._learn_from_observation(observer, agent, artifact['type'], action, reward)

        # First encounters and useful successes are game events. Routine failed
        # repetitions stay quiet so the journal remains readable.
        if first_attempt or (action == definition['best'] and success):
            self._log(
                'experiment',
                f"#{agent['id']} teste {action} sur {definition['label']} : {'succès' if success else 'échec'}.",
            )

    def _maybe_discover(self, agent, artifact_type, action):
        definition = ARTIFACT_TYPES[artifact_type]
        h = agent['hypotheses'].get((f'artifact:{artifact_type}', action))
        if not h or action != definition['best'] or artifact_type in agent['discoveries']:
            return

        direct_ready = self._skill(agent, f'action:{action}') >= 0.012
        socially_grounded = (
            h.get('source', '').startswith('observation #')
            or h.get('source', '').startswith('enseignement #')
        ) and (
            self._skill(agent, 'imitation') >= 0.08
            or self._skill(agent, 'communication') >= 0.08
        )
        if h['confidence'] >= 0.54 and h['evidence_for'] >= 3.0 and (direct_ready or socially_grounded):
            agent['discoveries'][artifact_type] = self.year
            agent['beliefs'][artifact_type] = {
                'confidence': h['confidence'],
                'utility': definition['reward'],
                'attempts': int(h['evidence_for'] + h['evidence_against']),
                'action': action,
                'source': h['source'],
            }
            self._remember(agent, f"J'ai compris : {definition['label']} → {definition['discovery']}.", 2.0)
            self._log('discovery', f"#{agent['id']} comprend « {definition['discovery']} » avec {definition['label']}.")

    def _choose_action(self, agent):
        dev = development(agent['age'])
        living = self.living()
        waters = self._resource_items('water')
        nearby_artifact = self._nearest(agent, self._artifact_items(), 175)
        nearby_agent = self._nearest(agent, living, 80, lambda a: a['id'] != agent['id'])
        child = self._nearest(agent, living, 90, lambda a: a['age'] < 7 and a['id'] != agent['id'])
        known_water = self._known_resource_target(agent, 'water')
        known_food = self._known_resource_target(agent, 'food')

        # Proximity to water must not manufacture thirst. Agents drink because they need
        # water, then leave; the pond itself is no longer a positive action-score bonus.
        hydration_floor = 45
        hydration_need = clamp((agent['thirst'] - hydration_floor) / max(1, 100 - hydration_floor), 0, 1)
        return_urgency = self._water_return_urgency(agent, known_water)
        food_need = clamp((agent['hunger'] - 35) / 65, 0, 1)
        rest_need = clamp((55 - agent['energy']) / 55, 0, 1)

        scores = {
            'drink': hydration_need * 1.55 * dev['autonomy'] + return_urgency,
            'eat': food_need * 1.4 * dev['autonomy'] + (0.14 if known_food and agent['hunger'] > 58 else 0),
            'rest': rest_need * 1.28,
            'explore': agent['rules']['exploreBias'] * (0.35 + agent['traits']['curiosity'] * 0.78) * dev['locomotion'] * (0.72 + agent['energy'] / 280),
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
            uncertainty = self._artifact_uncertainty(agent, nearby_artifact['type'])
            survival_pressure = max(
                hydration_need,
                food_need,
                rest_need,
                clamp(return_urgency / 2.5, 0, 1),
            )
            experiment_drive = (
                (0.30 + uncertainty * 0.70)
                * (0.55 + agent['traits']['curiosity'] * 0.45 + agent['traits']['creativity'] * 0.18)
                * (0.65 + agent['rules']['experimentBias'] * 0.45)
                * dev['manipulation']
                * (0.45 + dev['reasoning'] * 0.55)
            )
            if nearby_artifact['type'] in agent['discoveries']:
                experiment_drive *= 0.16
            scores['experiment'] = experiment_drive * (1 - survival_pressure * 0.55)

        if nearby_agent and agent['age'] >= 7:
            scores['help'] = agent['traits']['empathy'] * agent['rules']['helpBias'] if nearby_agent['hunger'] > 70 else 0
            scores['steal'] = agent['traits']['aggression'] * (0.5 + agent['hunger'] / 100) if agent['age'] >= 11 and agent['hunger'] > 65 and nearby_agent['food_store'] > 0 else 0
        if nearby_agent and agent['age'] >= 17 and nearby_agent['age'] >= 17 and nearby_agent['sex'] != agent['sex'] and agent['mate_cooldown'] <= 0:
            scores['mate'] = 0.32 + agent['rules']['mateBias'] * 0.42 + self.settings['fertility'] * 0.48 + agent['social_need'] / 100 * 0.15

        departure_ttl = int(agent.get('_water_departure_ttl', 0))
        if departure_ttl > 0 and hydration_need < 0.30:
            scores['explore'] += 0.55 + min(0.25, departure_ttl / 440)
            scores['socialize'] *= 0.62
            scores['observe'] *= 0.72
            scores['mate'] *= 0.55

        agent['last_decision'] = dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))
        return max(scores, key=scores.get)

    def _mate(self, agent, other):
        if agent['mate_cooldown'] > 0 or other['mate_cooldown'] > 0 or len(self.living()) >= int(self.settings['maxPopulation']):
            return
        r1, r2 = self._relation(agent, other), self._relation(other, agent)
        compatibility = 0.35 + (r1['affection'] + r2['affection'] + r1['trust'] + r2['trust']) / 5
        consent = 0.32 + other['rules']['mateBias'] * self.settings['fertility'] * (0.55 + other['health'] / 200)
        if random.random() < compatibility * consent * 0.65:
            child = self._new_agent([agent, other])
            self.births += 1
            agent['mate_cooldown'] = other['mate_cooldown'] = 310
            self._log('birth', f"Naissance de #{child['id']}, enfant de #{agent['id']} et #{other['id']}. Il ne possède encore aucune connaissance technique.")
        agent['action_detail'] = f"se rapproche de #{other['id']}"

    def _act(self, agent, dt):
        if not agent['alive']:
            return
        dev = development(agent['age'])
        agent['age'] += dt / 255
        dependency = 1 - dev['autonomy']
        travel_skill = clamp(self._skill(agent, 'travel'), 0, 1)
        agent['hunger'] = clamp(agent['hunger'] + dt * (0.050 + self.settings['scarcityPressure'] * 0.020), 0, 100)
        agent['thirst'] = clamp(agent['thirst'] + dt * (0.044 - travel_skill * 0.008), 0, 100)
        agent['energy'] = clamp(agent['energy'] - dt * (0.020 - travel_skill * 0.004), 0, 100)
        agent['social_need'] = clamp(agent['social_need'] + dt * (0.03 + dependency * 0.03), 0, 100)
        agent['mate_cooldown'] -= dt

        foods = self._resource_items('food')
        waters = self._resource_items('water')
        if dev['perception'] >= 0.12:
            visible_water = self._nearest(agent, waters, 115)
            visible_food = self._nearest(agent, foods, 85)
            if visible_water:
                self._remember_resource(agent, 'water', visible_water)
            if visible_food:
                self._remember_resource(agent, 'food', visible_food)

        if agent['hunger'] > 96 or agent['thirst'] > 96:
            if agent['thirst'] >= agent['hunger']:
                agent['_last_damage_cause'] = 'déshydratation'
            else:
                agent['_last_damage_cause'] = 'famine'
            agent['health'] -= dt * (0.12 + self.settings['scarcityPressure'] * 0.12)
        if agent['energy'] < 4:
            agent['_last_damage_cause'] = 'épuisement'
            agent['health'] -= dt * 0.04
        if self._has_capability(agent, 'warmth'):
            agent['health'] = clamp(agent['health'] + dt * 0.005, 0, 100)
        if self._has_capability(agent, 'medicine') and agent['health'] < 70:
            agent['health'] = clamp(agent['health'] + dt * 0.015, 0, 100)

        lifespan = self.settings['lifespan'] * (0.78 + agent['health'] / 250)
        if agent['health'] <= 0:
            self._die(agent, self._death_reason(agent))
            return
        if agent['age'] > lifespan and random.random() < 0.004 * dt:
            self._die(agent, 'vieillesse')
            return

        choice = self._choose_action(agent)
        agent['action'], agent['action_detail'] = choice, ''
        living = self.living()
        nearby_agent = self._nearest(agent, living, 90, lambda a: a['id'] != agent['id'])
        artifact = self._nearest(agent, self._artifact_items(), 175)

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
            agent.pop('_exploration_target', None)
            agent.pop('_exploration_ttl', None)
            agent.pop('_water_departure_target', None)
            agent.pop('_water_departure_ttl', None)
            water = self._nearest_water_by_edge(agent, waters, 220)
            target = water or self._known_resource_target(agent, 'water')
            if target:
                shore = self._water_shore_target(agent, target)
                edge_distance = self._distance_to_water_edge(agent, target)
                if edge_distance > 6:
                    self._move_toward(agent, shore, dt, 1.35)
                    agent['action_detail'] = 'rejoint la berge pour boire'
                elif water:
                    # An agent already inside the visual pond drinks while moving outward.
                    # This prevents every drink cycle from converging on the exact centre.
                    self._move_toward(agent, shore, dt, 1.12)
                    agent['thirst'] = clamp(agent['thirst'] - 6.2 * dt, 0, 100)
                    agent['energy'] = clamp(agent['energy'] + 0.08 * dt, 0, 100)
                    self._remember_resource(agent, 'water', water, success=True)
                    agent['action_detail'] = 'boit sur la berge'
                    if agent['thirst'] <= 26:
                        self._set_water_departure(agent, water)
                        agent['action_detail'] = 'boit puis quitte la berge'
                elif target.get('_memory'):
                    found = self._nearest_water_by_edge(agent, waters, 80)
                    if found:
                        self._remember_resource(agent, 'water', found, success=True)
                    else:
                        self._degrade_resource_memory(agent, 'water', 0.38)
                        agent['action_detail'] = 'cherche un ancien point d’eau'
            else:
                self._wander(agent, dt)
        elif choice == 'eat':
            if agent['food_store'] > 0 and agent['hunger'] > 52:
                agent['hunger'] = clamp(agent['hunger'] - 22 * dt, 0, 100)
                if random.random() < 0.08 * dt:
                    agent['food_store'] -= 1
                agent['action_detail'] = 'mange sa réserve'
            else:
                local_range = 250 if self._has_capability(agent, 'forage') else 185
                food = self._nearest(agent, foods, local_range)
                target = food or self._known_resource_target(agent, 'food')
                if target:
                    self._move_toward(agent, target, dt, 1.12)
                    if food and self._distance(agent, food) < 12:
                        agent['hunger'] = clamp(agent['hunger'] - (34 if self._has_capability(agent, 'harvest') else 24), 0, 100)
                        if random.random() < (0.8 if self._has_capability(agent, 'farming') else 0.42):
                            agent['food_store'] = min(4, agent['food_store'] + 1)
                        self._remember_resource(agent, 'food', food, success=True)
                        self.resources.pop(food['id'], None)
                        self._practice(agent, 'gathering', 0.010)
                        agent['action_detail'] = 'récolte sur une zone connue'
                    elif target.get('_memory') and self._distance(agent, target) < 25:
                        found = self._nearest(agent, foods, 90)
                        if found:
                            self._remember_resource(agent, 'food', found)
                        else:
                            self._degrade_resource_memory(agent, 'food', 0.28)
                            agent['action_detail'] = 'recherche une ancienne zone de nourriture'
                else:
                    self._explore(agent, dt)
        elif choice == 'rest':
            agent['energy'] = clamp(agent['energy'] + 0.92 * dt, 0, 100)
            agent['action_detail'] = 'se repose sur place avant de poursuivre'
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
        elif choice == 'explore':
            self._explore(agent, dt)
        else:
            self._wander(agent, dt)

    def agent_view(self, agent_id):
        data = super().agent_view(agent_id)
        if not data:
            return None
        agent = self.agents.get(agent_id)
        data['knownResources'] = dict(agent.get('resource_memory', {})) if agent else {}
        if agent:
            data['mobility'] = {
                'safeExcursionRadius': round(self._safe_excursion_radius(agent), 1),
                'travelSkill': round(self._skill(agent, 'travel'), 4),
                'hasExplorationTarget': bool(agent.get('_exploration_target')),
            }
        return data
