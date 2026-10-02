class LivingMembershipCache:
    """Cache the ordered living population behind an explicit membership revision.

    The simulation engine owns synchronization. Callers mutate membership and call
    ``changed()`` while holding ``engine.lock``; reads happen under that same lock.
    A source-identity fallback protects reset/load dictionary replacement if a
    future mutation path forgets to bump the revision, and exposes that drift in
    health telemetry instead of silently serving the previous tuple.
    """

    def __init__(self):
        self.revision = 0
        self.cached_revision = -1
        self.cached_source_id = None
        self.cached = ()
        self.hits = 0
        self.misses = 0
        self.changes = 0
        self.source_fallbacks = 0
        self.last_change = None

    def changed(self, reason):
        self.revision += 1
        self.changes += 1
        self.last_change = str(reason)
        return self.revision

    def snapshot(self, agents):
        source_id = id(agents)
        if self.cached_revision == self.revision and self.cached_source_id == source_id:
            self.hits += 1
            return self.cached

        if self.cached_revision == self.revision and self.cached_source_id not in (None, source_id):
            self.source_fallbacks += 1

        self.cached = tuple(agent for agent in agents.values() if agent['alive'])
        self.cached_revision = self.revision
        self.cached_source_id = source_id
        self.misses += 1
        return self.cached

    def status(self):
        return {
            'revision': self.revision,
            'cachedRevision': self.cached_revision,
            'hits': self.hits,
            'misses': self.misses,
            'changes': self.changes,
            'size': len(self.cached),
            'sourceFallbacks': self.source_fallbacks,
            'lastChange': self.last_change,
        }
