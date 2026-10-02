import math

from climate_engine import Engine as ClimateEngine
from engine import DB_LOCK, WORLD_ID, clamp, connect


COMMUNITY_REFRESH_YEARS = 0.50
FORMATION_DISTANCE = 105.0
JOIN_DISTANCE = 135.0
COHESION_DISTANCE = 180.0
FORMATION_RELATION = 0.22
JOIN_RELATION = 0.24
LEAVE_RELATION = 0.12
DIPLOMACY_MIN_ENCOUNTERS = 3
DIPLOMACY_COOPERATIVE = 0.12
DIPLOMACY_ALLIED = 0.36
DIPLOMACY_RIVAL = -0.24
DIPLOMACY_HOSTILE = -0.50
FRACTURE_INTERNAL_RELATION = 0.30
FRACTURE_CROSS_RELATION = 0.08
FRACTURE_MIN_CROSS_ENCOUNTERS = 5


def ensure_community_schema():
    """Additive community persistence; existing worlds are never reset."""
    with DB_LOCK:
        conn = connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS communities (
                  id INTEGER PRIMARY KEY,
                  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                  created_year REAL NOT NULL,
                  last_active_year REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_communities_world
                  ON communities(world_id);

                CREATE TABLE IF NOT EXISTS community_memberships (
                  agent_id INTEGER PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
                  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                  community_id INTEGER NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
                  joined_year REAL NOT NULL,
                  affinity REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_community_memberships_world_group
                  ON community_memberships(world_id, community_id);

                CREATE TABLE IF NOT EXISTS community_relations (
                  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                  community_a INTEGER NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
                  community_b INTEGER NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
                  score REAL NOT NULL DEFAULT 0,
                  encounters INTEGER NOT NULL DEFAULT 0,
                  cooperation REAL NOT NULL DEFAULT 0,
                  conflict REAL NOT NULL DEFAULT 0,
                  state TEXT NOT NULL DEFAULT 'neutral',
                  updated_year REAL NOT NULL,
                  PRIMARY KEY (world_id, community_a, community_b),
                  CHECK (community_a < community_b)
                );
                CREATE INDEX IF NOT EXISTS idx_community_relations_world
                  ON community_relations(world_id);
                """
            )
            conn.commit()
        finally:
            conn.close()


class Engine(ClimateEngine):
    """Leaderless social layer: communities emerge from repeated relationships."""

    def __init__(self):
        ensure_community_schema()
        self.communities = {}
        self.community_relations = {}
        self.next_community_id = 0
        self._next_community_refresh_year = 0.0
        super().__init__()

    def reset(self):
        self.communities = {}
        self.community_relations = {}
        self.next_community_id = 0
        self._next_community_refresh_year = 0.0
        return super().reset()

    def _load(self):
        loaded = super()._load()
        if not loaded:
            return False

        for agent in self.agents.values():
            agent['community_id'] = None
            agent['community_affinity'] = 0.0
            agent['community_joined_year'] = None

        with DB_LOCK:
            conn = connect()
            try:
                self.communities = {
                    int(row['id']): {
                        'id': int(row['id']),
                        'created_year': float(row['created_year']),
                        'last_active_year': float(row['last_active_year']),
                    }
                    for row in conn.execute(
                        'SELECT id,created_year,last_active_year FROM communities WHERE world_id=?',
                        (WORLD_ID,),
                    )
                }
                for row in conn.execute(
                    'SELECT agent_id,community_id,joined_year,affinity '
                    'FROM community_memberships WHERE world_id=?',
                    (WORLD_ID,),
                ):
                    agent = self.agents.get(int(row['agent_id']))
                    cid = int(row['community_id'])
                    if agent and cid in self.communities:
                        agent['community_id'] = cid
                        agent['community_affinity'] = float(row['affinity'])
                        agent['community_joined_year'] = float(row['joined_year'])
                self.community_relations = {}
                for row in conn.execute(
                    'SELECT community_a,community_b,score,encounters,cooperation,conflict,state,updated_year '
                    'FROM community_relations WHERE world_id=?',
                    (WORLD_ID,),
                ):
                    a, b = int(row['community_a']), int(row['community_b'])
                    if a not in self.communities or b not in self.communities:
                        continue
                    self.community_relations[(a, b)] = {
                        'communityA': a,
                        'communityB': b,
                        'score': float(row['score']),
                        'encounters': int(row['encounters']),
                        'cooperation': float(row['cooperation']),
                        'conflict': float(row['conflict']),
                        'state': str(row['state']),
                        'updatedYear': float(row['updated_year']),
                    }
                self.next_community_id = max(self.communities, default=0)
                self._next_community_refresh_year = self.year
                return True
            finally:
                conn.close()

    def _new_agent(self, parents):
        agent = super()._new_agent(parents)
        inherited = None
        if parents:
            parent_groups = {p.get('community_id') for p in parents if p.get('community_id') is not None}
            if len(parent_groups) == 1:
                inherited = next(iter(parent_groups))
        agent['community_id'] = inherited
        agent['community_affinity'] = 0.45 if inherited is not None else 0.0
        agent['community_joined_year'] = self.year if inherited is not None else None
        return agent

    def _persist(self, full_reset=False):
        super()._persist(full_reset=full_reset)
        with DB_LOCK:
            conn = connect()
            try:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('DELETE FROM community_relations WHERE world_id=?', (WORLD_ID,))
                conn.execute('DELETE FROM community_memberships WHERE world_id=?', (WORLD_ID,))
                conn.execute('DELETE FROM communities WHERE world_id=?', (WORLD_ID,))
                for community in self.communities.values():
                    conn.execute(
                        'INSERT INTO communities(id,world_id,created_year,last_active_year) VALUES(?,?,?,?)',
                        (
                            community['id'],
                            WORLD_ID,
                            community['created_year'],
                            community['last_active_year'],
                        ),
                    )
                for agent in self.agents.values():
                    cid = agent.get('community_id')
                    if not agent.get('alive') or cid is None or cid not in self.communities:
                        continue
                    conn.execute(
                        'INSERT INTO community_memberships('
                        'agent_id,world_id,community_id,joined_year,affinity'
                        ') VALUES(?,?,?,?,?)',
                        (
                            agent['id'],
                            WORLD_ID,
                            cid,
                            agent.get('community_joined_year') or self.year,
                            float(agent.get('community_affinity', 0.0)),
                        ),
                    )
                for relation in self.community_relations.values():
                    a, b = relation['communityA'], relation['communityB']
                    if a not in self.communities or b not in self.communities:
                        continue
                    conn.execute(
                        'INSERT INTO community_relations('
                        'world_id,community_a,community_b,score,encounters,cooperation,conflict,state,updated_year'
                        ') VALUES(?,?,?,?,?,?,?,?,?)',
                        (
                            WORLD_ID,
                            a,
                            b,
                            float(relation['score']),
                            int(relation['encounters']),
                            float(relation['cooperation']),
                            float(relation['conflict']),
                            relation['state'],
                            float(relation['updatedYear']),
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _relation_strength(self, agent, other):
        forward = agent.get('relations', {}).get(other['id'])
        backward = other.get('relations', {}).get(agent['id'])
        if not forward or not backward:
            return 0.0
        encounters = min(int(forward.get('encounters', 0)), int(backward.get('encounters', 0)))
        if encounters < 2:
            return 0.0
        trust = (float(forward.get('trust', 0)) + float(backward.get('trust', 0))) / 2
        affection = (float(forward.get('affection', 0)) + float(backward.get('affection', 0))) / 2
        respect = (float(forward.get('respect', 0)) + float(backward.get('respect', 0))) / 2
        return clamp(trust * 0.45 + affection * 0.35 + respect * 0.20, 0, 1)

    def _community_relation_key(self, first_id, second_id):
        if first_id == second_id:
            return None
        return tuple(sorted((int(first_id), int(second_id))))

    def _diplomatic_state(self, score, encounters):
        if encounters < DIPLOMACY_MIN_ENCOUNTERS:
            return 'neutral'
        if score >= DIPLOMACY_ALLIED:
            return 'allied'
        if score >= DIPLOMACY_COOPERATIVE:
            return 'cooperative'
        if score <= DIPLOMACY_HOSTILE:
            return 'hostile'
        if score <= DIPLOMACY_RIVAL:
            return 'rival'
        return 'neutral'

    def _community_relation(self, first_id, second_id, create=False):
        key = self._community_relation_key(first_id, second_id)
        if key is None:
            return None
        relation = self.community_relations.get(key)
        if relation is None and create:
            relation = {
                'communityA': key[0],
                'communityB': key[1],
                'score': 0.0,
                'encounters': 0,
                'cooperation': 0.0,
                'conflict': 0.0,
                'state': 'neutral',
                'updatedYear': self.year,
            }
            self.community_relations[key] = relation
        return relation

    def _record_intercommunity(self, agent, other, delta, kind):
        first_id = agent.get('community_id')
        second_id = other.get('community_id')
        if first_id is None or second_id is None or first_id == second_id:
            return None
        if first_id not in self.communities or second_id not in self.communities:
            return None

        relation = self._community_relation(first_id, second_id, create=True)
        old_state = relation['state']
        relation['score'] = clamp(float(relation['score']) + delta, -1.0, 1.0)
        relation['encounters'] += 1
        if delta > 0:
            relation['cooperation'] += delta
        elif delta < 0:
            relation['conflict'] += abs(delta)
        relation['updatedYear'] = self.year
        relation['state'] = self._diplomatic_state(relation['score'], relation['encounters'])

        if relation['state'] != old_state:
            a, b = relation['communityA'], relation['communityB']
            labels = {
                'allied': 'forment une alliance',
                'cooperative': 'entrent dans une phase de coopération',
                'neutral': 'reviennent à une relation neutre',
                'rival': 'deviennent rivales',
                'hostile': 'entrent dans une hostilité ouverte',
            }
            self._log(
                'diplomacy',
                f"Les communautés #{a} et #{b} {labels[relation['state']]} après leurs interactions.",
            )
        return relation

    def _refresh_intercommunity_relations(self):
        valid = set(self.communities)
        for key in list(self.community_relations):
            if key[0] not in valid or key[1] not in valid:
                self.community_relations.pop(key, None)
                continue
            relation = self.community_relations[key]
            # Inactive diplomacy slowly drifts back toward neutrality. Fresh actions
            # always dominate this tiny decay, so alliances and rivalries can reverse.
            if self.year - float(relation['updatedYear']) > 1.0:
                old_state = relation['state']
                relation['score'] *= 0.995
                relation['state'] = self._diplomatic_state(
                    relation['score'], relation['encounters']
                )
                if relation['state'] != old_state:
                    a, b = key
                    self._log(
                        'diplomacy',
                        f"Les communautés #{a} et #{b} voient leur ancienne relation s’atténuer.",
                    )

    def _pair_encounters(self, first, second):
        forward = first.get('relations', {}).get(second['id'], {})
        backward = second.get('relations', {}).get(first['id'], {})
        return min(
            int(forward.get('encounters', 0)),
            int(backward.get('encounters', 0)),
        )

    def _maybe_polarized_fracture(self, source_id, members):
        """Split a community only when two cohesive camps have repeatedly diverged."""
        if len(members) < 4:
            return False

        strongest = None
        for index, first in enumerate(members):
            for second in members[index + 1:]:
                strength = self._relation_strength(first, second)
                if strength < FRACTURE_INTERNAL_RELATION:
                    continue
                if strongest is None or strength > strongest[0]:
                    strongest = (strength, first, second)
        if strongest is None:
            return False

        _, first_a, first_b = strongest
        group_a = [first_a, first_b]
        remaining = [
            member for member in members
            if member['id'] not in {first_a['id'], first_b['id']}
        ]

        second_pair = None
        for index, first in enumerate(remaining):
            for second in remaining[index + 1:]:
                strength = self._relation_strength(first, second)
                if strength < FRACTURE_INTERNAL_RELATION:
                    continue
                if second_pair is None or strength > second_pair[0]:
                    second_pair = (strength, first, second)
        if second_pair is None:
            return False

        _, second_a, second_b = second_pair
        group_b = [second_a, second_b]

        cross = []
        for left in group_a:
            for right in group_b:
                encounters = self._pair_encounters(left, right)
                if encounters < FRACTURE_MIN_CROSS_ENCOUNTERS:
                    return False
                cross.append(self._relation_strength(left, right))
        if not cross or sum(cross) / len(cross) > FRACTURE_CROSS_RELATION:
            return False

        assigned = {agent['id'] for agent in group_a + group_b}
        leftovers = [agent for agent in members if agent['id'] not in assigned]
        for agent in leftovers:
            affinity_a = sum(self._relation_strength(agent, other) for other in group_a) / len(group_a)
            affinity_b = sum(self._relation_strength(agent, other) for other in group_b) / len(group_b)
            if max(affinity_a, affinity_b) >= FORMATION_RELATION:
                (group_a if affinity_a >= affinity_b else group_b).append(agent)

        for member in members:
            member['community_id'] = None
            member['community_affinity'] = 0.0
            member['community_joined_year'] = None
        self.communities.pop(source_id, None)

        new_a = self._create_community(group_a[0], group_a[1])
        for member in group_a[2:]:
            member['community_id'] = new_a
            member['community_joined_year'] = self.year
            member['community_affinity'] = self._community_affinity(member, group_a)

        new_b = self._create_community(group_b[0], group_b[1])
        for member in group_b[2:]:
            member['community_id'] = new_b
            member['community_joined_year'] = self.year
            member['community_affinity'] = self._community_affinity(member, group_b)

        self._log(
            'community',
            f"La communauté #{source_id} se fracture en #{new_a} et #{new_b} après une polarisation durable.",
        )
        return True

    def _form_splinters(self, source_id, departing):
        remaining = list(departing)
        created = []
        while len(remaining) >= 2:
            best = None
            for index, first in enumerate(remaining):
                for second in remaining[index + 1:]:
                    strength = self._relation_strength(first, second)
                    if strength < FORMATION_RELATION:
                        continue
                    if best is None or strength > best[0]:
                        best = (strength, first, second)
            if best is None:
                break
            _, first, second = best
            new_id = self._create_community(first, second)
            created.append(new_id)
            remaining = [
                agent for agent in remaining
                if agent['id'] not in {first['id'], second['id']}
            ]
            self._log(
                'community',
                f"La communauté #{source_id} se fracture : #{first['id']} et #{second['id']} fondent la communauté #{new_id}.",
            )
        return remaining, created

    def _community_members(self, community_id, living=None):
        living = living if living is not None else self.living()
        return [a for a in living if a.get('community_id') == community_id]

    def _community_affinity(self, agent, members):
        strengths = [
            self._relation_strength(agent, other)
            for other in members
            if other['id'] != agent['id'] and self._relation_strength(agent, other) > 0
        ]
        if not strengths:
            return float(agent.get('community_affinity', 0.0)) * 0.96
        return sum(strengths) / len(strengths)

    def _create_community(self, first, second):
        self.next_community_id += 1
        cid = self.next_community_id
        self.communities[cid] = {
            'id': cid,
            'created_year': self.year,
            'last_active_year': self.year,
        }
        for member in (first, second):
            member['community_id'] = cid
            member['community_joined_year'] = self.year
            member['community_affinity'] = self._relation_strength(first, second)
        self._log(
            'community',
            f"Une communauté émerge autour de #{first['id']} et #{second['id']}, après des liens répétés.",
        )
        return cid

    def _dissolve_community(self, community_id, members):
        if community_id not in self.communities:
            return
        for member in members:
            if member.get('community_id') == community_id:
                member['community_id'] = None
                member['community_affinity'] = 0.0
                member['community_joined_year'] = None
        self.communities.pop(community_id, None)
        self._log('community', f"La communauté #{community_id} se dissout faute de liens suffisants.")

    def _refresh_communities(self):
        living = self.living()
        living_ids = {a['id'] for a in living}

        for agent in self.agents.values():
            if agent['id'] not in living_ids:
                agent['community_id'] = None
                agent['community_affinity'] = 0.0
                agent['community_joined_year'] = None
            elif agent.get('community_id') not in self.communities:
                agent['community_id'] = None
                agent['community_affinity'] = 0.0
                agent['community_joined_year'] = None

        # Existing groups can weaken and fracture. A pair only leaves after a clearly
        # hostile/eroded bilateral relationship; larger groups use mean affinity.
        for cid in list(self.communities):
            members = self._community_members(cid, living)
            if len(members) < 2:
                self._dissolve_community(cid, members)
                continue
            if self._maybe_polarized_fracture(cid, members):
                continue
            departing = []
            for agent in members:
                affinity = self._community_affinity(agent, members)
                agent['community_affinity'] = affinity
                linked = [
                    other for other in members
                    if other['id'] != agent['id'] and self._relation_strength(agent, other) > 0
                ]
                if (
                    agent['age'] >= 10
                    and linked
                    and affinity < LEAVE_RELATION
                    and max(
                        min(
                            int(agent.get('relations', {}).get(other['id'], {}).get('encounters', 0)),
                            int(other.get('relations', {}).get(agent['id'], {}).get('encounters', 0)),
                        )
                        for other in linked
                    ) >= 5
                ):
                    departing.append(agent)
            for agent in departing:
                agent['community_id'] = None
                agent['community_affinity'] = 0.0
                agent['community_joined_year'] = None
            if len(departing) >= 2:
                remaining_departing, _ = self._form_splinters(cid, departing)
                for agent in remaining_departing:
                    agent['community_id'] = None

            members = self._community_members(cid, living)
            if len(members) < 2:
                self._dissolve_community(cid, members)
            else:
                self.communities[cid]['last_active_year'] = self.year

        # Ungrouped lives can join a nearby group only through an actual relationship
        # with one of its members. Proximity alone is never enough.
        for agent in [a for a in living if a.get('community_id') is None and a['age'] >= 7]:
            best = None
            for cid in self.communities:
                members = self._community_members(cid, living)
                for member in members:
                    distance = self._distance(agent, member)
                    strength = self._relation_strength(agent, member)
                    if distance <= JOIN_DISTANCE and strength >= JOIN_RELATION:
                        candidate = (strength - distance / 1000, cid, strength)
                        if best is None or candidate[0] > best[0]:
                            best = candidate
            if best:
                _, cid, strength = best
                agent['community_id'] = cid
                agent['community_joined_year'] = self.year
                agent['community_affinity'] = strength
                self.communities[cid]['last_active_year'] = self.year

        # New groups emerge only from mutually reinforced relationships.
        ungrouped = [a for a in living if a.get('community_id') is None and a['age'] >= 10]
        claimed = set()
        for agent in ungrouped:
            if agent['id'] in claimed or agent.get('community_id') is not None:
                continue
            best = None
            for other in ungrouped:
                if other['id'] == agent['id'] or other['id'] in claimed or other.get('community_id') is not None:
                    continue
                distance = self._distance(agent, other)
                if distance > FORMATION_DISTANCE:
                    continue
                strength = self._relation_strength(agent, other)
                if strength < FORMATION_RELATION:
                    continue
                score = strength - distance / 1200
                if best is None or score > best[0]:
                    best = (score, other)
            if best:
                other = best[1]
                self._create_community(agent, other)
                claimed.add(agent['id'])
                claimed.add(other['id'])

        self._refresh_intercommunity_relations()

    def _community_companion_target(self, agent):
        cid = agent.get('community_id')
        if cid is None or cid not in self.communities:
            return None
        members = [
            other for other in self._community_members(cid)
            if other['id'] != agent['id']
        ]
        if not members:
            return None
        nearest = min(members, key=lambda other: self._distance(agent, other))
        if self._distance(agent, nearest) <= COHESION_DISTANCE:
            return None

        # Follow a moving peer, not a fixed group centroid. The deterministic offset
        # spreads members around the companion instead of stacking them on one point.
        angle = (agent['id'] * 2.3999632297 + nearest['id'] * 0.6180339887) % math.tau
        radius = 38 + 26 * agent['traits'].get('conformity', 0.5)
        return {
            'x': clamp(nearest['x'] + math.cos(angle) * radius, 20, 1180),
            'y': clamp(nearest['y'] + math.sin(angle) * radius, 20, 740),
            '_community_peer': nearest['id'],
        }

    def _socialize(self, agent, other):
        super()._socialize(agent, other)
        self._record_intercommunity(agent, other, 0.025, 'socialize')

    def _help(self, agent, other):
        giver_before = int(agent.get('food_store', 0))
        receiver_before = int(other.get('food_store', 0))
        super()._help(agent, other)
        if int(agent.get('food_store', 0)) < giver_before or int(other.get('food_store', 0)) > receiver_before:
            self._record_intercommunity(agent, other, 0.14, 'help')

    def _steal(self, agent, other):
        thief_before = int(agent.get('food_store', 0))
        victim_before = int(other.get('food_store', 0))
        super()._steal(agent, other)
        if int(agent.get('food_store', 0)) > thief_before or int(other.get('food_store', 0)) < victim_before:
            self._record_intercommunity(agent, other, -0.20, 'steal')

    def _choose_action(self, agent):
        choice = super()._choose_action(agent)
        nearby = self._nearest(
            agent,
            self.living(),
            80,
            lambda other: other['id'] != agent['id'],
        )
        if not nearby:
            return choice

        first_id = agent.get('community_id')
        second_id = nearby.get('community_id')
        relation = self._community_relation(first_id, second_id) if first_id is not None and second_id is not None else None
        if not relation:
            return choice

        scores = dict(agent.get('last_decision', {}))
        state = relation['state']
        if state == 'allied':
            scores['socialize'] = scores.get('socialize', 0) * 1.30
            scores['help'] = scores.get('help', 0) * 1.45
            scores['steal'] = scores.get('steal', 0) * 0.08
        elif state == 'cooperative':
            scores['socialize'] = scores.get('socialize', 0) * 1.16
            scores['help'] = scores.get('help', 0) * 1.20
            scores['steal'] = scores.get('steal', 0) * 0.55
        elif state == 'rival':
            scores['socialize'] = scores.get('socialize', 0) * 0.62
            scores['help'] = scores.get('help', 0) * 0.40
            scores['steal'] = scores.get('steal', 0) * 1.20
            if agent.get('hunger', 0) < 60:
                scores['explore'] = scores.get('explore', 0) + 0.08
        elif state == 'hostile':
            scores['socialize'] = scores.get('socialize', 0) * 0.25
            scores['help'] = scores.get('help', 0) * 0.10
            scores['steal'] = scores.get('steal', 0) * 1.38
            if agent.get('hunger', 0) < 70:
                scores['explore'] = scores.get('explore', 0) + 0.18

        agent['last_decision'] = dict(
            sorted(scores.items(), key=lambda item: item[1], reverse=True)
        )
        return max(scores, key=scores.get)

    def _explore(self, agent, dt):
        safe_for_social_cohesion = (
            agent['thirst'] < 58
            and agent['hunger'] < 68
            and agent['energy'] > 38
            and not agent.get('_water_departure_target')
        )
        ttl = int(agent.get('_exploration_ttl', 0))
        if safe_for_social_cohesion and (not agent.get('_exploration_target') or ttl <= 0):
            target = self._community_companion_target(agent)
            if target:
                agent['_exploration_target'] = target
                agent['_exploration_ttl'] = 90
                agent['_community_route_peer'] = target['_community_peer']

        super()._explore(agent, dt)

        peer = agent.pop('_community_route_peer', None)
        if peer is not None and agent.get('action_detail', '').startswith('suit une direction'):
            agent['action_detail'] = f"reste à portée de sa communauté en suivant #{peer}"

    def _tick(self):
        super()._tick()
        if self.year >= self._next_community_refresh_year:
            self._refresh_communities()
            self._next_community_refresh_year = self.year + COMMUNITY_REFRESH_YEARS

    def world_view(self):
        data = super().world_view()
        living = self.living()
        by_id = {a['id']: a for a in living}
        for row in data.get('agents', []):
            agent = by_id.get(row['id'])
            row['communityId'] = agent.get('community_id') if agent else None

        communities = []
        for cid, community in sorted(self.communities.items()):
            members = self._community_members(cid, living)
            if len(members) < 2:
                continue
            x = sum(a['x'] for a in members) / len(members)
            y = sum(a['y'] for a in members) / len(members)
            cohesion = sum(float(a.get('community_affinity', 0)) for a in members) / len(members)
            communities.append({
                'id': cid,
                'size': len(members),
                'x': round(x, 2),
                'y': round(y, 2),
                'cohesion': round(cohesion, 3),
                'createdYear': community['created_year'],
            })
        data['communities'] = communities
        data['communityRelations'] = [
            {
                'communityA': relation['communityA'],
                'communityB': relation['communityB'],
                'score': round(float(relation['score']), 3),
                'encounters': int(relation['encounters']),
                'cooperation': round(float(relation['cooperation']), 3),
                'conflict': round(float(relation['conflict']), 3),
                'state': relation['state'],
                'updatedYear': relation['updatedYear'],
            }
            for _, relation in sorted(self.community_relations.items())
            if relation['communityA'] in self.communities
            and relation['communityB'] in self.communities
        ]
        return data

    def agent_view(self, agent_id):
        data = super().agent_view(agent_id)
        if not data:
            return None
        agent = self.agents.get(agent_id)
        cid = agent.get('community_id') if agent else None
        if cid is None or cid not in self.communities:
            data['community'] = None
            return data
        members = self._community_members(cid)
        data['community'] = {
            'id': cid,
            'size': len(members),
            'affinity': round(float(agent.get('community_affinity', 0)), 3),
            'joinedYear': agent.get('community_joined_year'),
            'relations': [
                {
                    'communityId': relation['communityB'] if relation['communityA'] == cid else relation['communityA'],
                    'state': relation['state'],
                    'score': round(float(relation['score']), 3),
                }
                for relation in self.community_relations.values()
                if cid in (relation['communityA'], relation['communityB'])
            ],
        }
        return data
