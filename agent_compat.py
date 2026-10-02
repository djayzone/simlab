from engine import DB_LOCK, WORLD_ID, connect, init_db


# Neutral/additive defaults for agents persisted by older SIM.lab versions.
# Values mirror the midpoint/defaults used by Engine._new_agent(). Existing
# persisted values are never overwritten.
LEGACY_RULE_DEFAULTS = {
    'hungerThreshold': 0.685,
    'thirstThreshold': 0.64,
    'restThreshold': 0.30,
    'experimentBias': 0.55,
    'socialBias': 0.50,
    'helpBias': 0.50,
    'mateBias': 0.50,
    'exploreBias': 0.575,
}

LEGACY_TRAIT_DEFAULTS = {
    'curiosity': 0.58,
    'sociability': 0.55,
    'aggression': 0.24,
    'empathy': 0.62,
    'risk': 0.45,
    'conformity': 0.50,
    'creativity': 0.50,
    'trust': 0.52,
}


def _backfill_defaults(conn, table, key_column, defaults, world_id):
    repaired = 0
    for key, default in defaults.items():
        cursor = conn.execute(
            f'''
            INSERT OR IGNORE INTO {table}(agent_id, {key_column}, value)
            SELECT id, ?, ?
            FROM agents
            WHERE world_id = ?
            ''',
            (key, default, world_id),
        )
        if cursor.rowcount and cursor.rowcount > 0:
            repaired += cursor.rowcount
    return repaired


def backfill_legacy_agent_schema(conn, world_id=WORLD_ID):
    """Fill every currently-required trait/rule missing from legacy agents.

    The migration is additive and idempotent. It intentionally preserves every
    value that is already persisted and only creates absent rows.
    """
    return {
        'rules': _backfill_defaults(
            conn, 'agent_rules', 'rule', LEGACY_RULE_DEFAULTS, world_id
        ),
        'traits': _backfill_defaults(
            conn, 'agent_traits', 'trait', LEGACY_TRAIT_DEFAULTS, world_id
        ),
    }


def backfill_legacy_agent_rules(conn, world_id=WORLD_ID):
    """Compatibility wrapper kept for the focused tests introduced by #707."""
    return _backfill_defaults(
        conn, 'agent_rules', 'rule', LEGACY_RULE_DEFAULTS, world_id
    )


def ensure_persisted_agent_rule_defaults():
    """Normalize persisted agents before Engine construction and startup catch-up."""
    init_db()
    with DB_LOCK:
        conn = connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            repaired = backfill_legacy_agent_schema(conn)
            conn.commit()
            return repaired
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
