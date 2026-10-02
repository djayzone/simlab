class SimulationRuntime:
    """Small, testable contract between SIM.lab state and transports.

    The HTTP layer only speaks to this facade. The engine remains authoritative
    for locking and state semantics; the facade prevents transports from reaching
    into mutable engine internals directly.
    """

    MAX_MANUAL_TICKS = 120

    def __init__(self, engine, snapshot_cache, profiler, persist_interval):
        self.engine = engine
        self.snapshot_cache = snapshot_cache
        self.profiler = profiler
        self.persist_interval = persist_interval

    def tick(self, steps=1):
        steps = int(steps)
        if steps < 1 or steps > self.MAX_MANUAL_TICKS:
            raise ValueError(f'steps must be between 1 and {self.MAX_MANUAL_TICKS}')
        with self.engine.lock:
            for _ in range(steps):
                self.engine._tick()
            return {'steps': steps, 'simulationYear': self.engine.year}

    def reset(self):
        self.engine.reset()
        return {'ok': True}

    def snapshot(self):
        return self.engine.world_view()

    def snapshot_bytes(self):
        return self.snapshot_cache.get()

    def persist(self):
        with self.engine.lock:
            self.engine.persist_now()
        return {'ok': True}

    def agent(self, agent_id):
        return self.engine.agent_view(agent_id)

    def control(self, payload):
        return self.engine.command(payload)

    def update_settings(self, settings):
        return {'settings': self.engine.update_settings(settings)}

    def inject(self, kind, count=1):
        self.engine.inject(kind, count)
        return {'ok': True}

    def shock(self, kind):
        self.engine.shock(kind)
        return {'ok': True}

    def update_weather_control(self, payload):
        return {'control': self.engine.update_weather_control(payload)}

    def probe_health(self):
        """Constant-time Kubernetes probe contract.

        Do not call cache/profiler/engine diagnostic helpers here: some of them
        contend with the simulation loop and can exceed the kubelet probe timeout
        while the engine is healthy and CPU-bound.
        """
        engine_thread = getattr(self.engine, 'thread', None)
        engine_loop_alive = bool(engine_thread and engine_thread.is_alive())
        return {
            'ok': engine_loop_alive,
            'component': 'engine',
            'engineLoop': {
                'alive': engine_loop_alive,
                'thread': getattr(engine_thread, 'name', 'sim-engine') if engine_thread else None,
            },
            'runtimeApi': {'version': 1},
        }

    def health(self):
        health = self.probe_health()
        health.update({
            'snapshot': self.snapshot_cache.status(),
            'perf': self.profiler.status(),
            'persistence': {'intervalMs': round(self.persist_interval * 1000)},
            'livingCache': self.engine.living_cache_status(),
        })
        return health
