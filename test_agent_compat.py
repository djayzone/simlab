import sqlite3
import unittest

from agent_compat import (
    LEGACY_RULE_DEFAULTS,
    LEGACY_TRAIT_DEFAULTS,
    backfill_legacy_agent_rules,
    backfill_legacy_agent_schema,
)


class AgentCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE agents (id INTEGER PRIMARY KEY, world_id INTEGER NOT NULL)')
        self.conn.execute('''
            CREATE TABLE agent_rules (
                agent_id INTEGER NOT NULL,
                rule TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY(agent_id, rule)
            )
        ''')
        self.conn.execute('''
            CREATE TABLE agent_traits (
                agent_id INTEGER NOT NULL,
                trait TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY(agent_id, trait)
            )
        ''')
        self.conn.executemany(
            'INSERT INTO agents(id, world_id) VALUES(?, ?)',
            [(1, 1), (2, 1), (3, 2)],
        )

    def tearDown(self):
        self.conn.close()

    def test_backfills_complete_current_schema_for_current_world(self):
        repaired = backfill_legacy_agent_schema(self.conn, world_id=1)
        self.assertEqual(repaired['rules'], 2 * len(LEGACY_RULE_DEFAULTS))
        self.assertEqual(repaired['traits'], 2 * len(LEGACY_TRAIT_DEFAULTS))

        for trait, default in LEGACY_TRAIT_DEFAULTS.items():
            rows = self.conn.execute(
                'SELECT agent_id, value FROM agent_traits WHERE trait=? ORDER BY agent_id',
                (trait,),
            ).fetchall()
            self.assertEqual(rows, [(1, default), (2, default)])

        rows = self.conn.execute(
            "SELECT agent_id, value FROM agent_rules WHERE rule='exploreBias' ORDER BY agent_id"
        ).fetchall()
        self.assertEqual(rows, [(1, 0.575), (2, 0.575)])

    def test_preserves_existing_values(self):
        self.conn.execute(
            "INSERT INTO agent_rules(agent_id, rule, value) VALUES(1, 'exploreBias', 0.83)"
        )
        self.conn.execute(
            "INSERT INTO agent_traits(agent_id, trait, value) VALUES(1, 'curiosity', 0.91)"
        )
        backfill_legacy_agent_schema(self.conn, world_id=1)
        self.assertEqual(
            self.conn.execute(
                "SELECT value FROM agent_rules WHERE agent_id=1 AND rule='exploreBias'"
            ).fetchone()[0],
            0.83,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT value FROM agent_traits WHERE agent_id=1 AND trait='curiosity'"
            ).fetchone()[0],
            0.91,
        )

    def test_is_idempotent(self):
        first = backfill_legacy_agent_schema(self.conn, world_id=1)
        second = backfill_legacy_agent_schema(self.conn, world_id=1)
        self.assertGreater(first['rules'] + first['traits'], 0)
        self.assertEqual(second, {'rules': 0, 'traits': 0})

    def test_previous_rule_only_wrapper_remains_compatible(self):
        self.assertEqual(backfill_legacy_agent_rules(self.conn, world_id=1), 2)
        self.assertEqual(backfill_legacy_agent_rules(self.conn, world_id=1), 0)


if __name__ == '__main__':
    unittest.main()
