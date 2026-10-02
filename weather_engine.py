import math
import random

from engine import DB_LOCK, WORLD_H, WORLD_ID, WORLD_W, clamp, connect
from learning_engine import Engine as LearningEngine

WEATHER_COLS = 6
WEATHER_ROWS = 4
SEASONS = (
    ('printemps', 14.0, 0.58),
    ('été', 25.0, 0.34),
    ('automne', 13.0, 0.56),
    ('hiver', 4.0, 0.38),
)


def ensure_weather_schema():
    with DB_LOCK:
        conn = connect()
        try:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS weather_state (
                  world_id INTEGER PRIMARY KEY REFERENCES worlds(id) ON DELETE CASCADE,
                  season TEXT NOT NULL,
                  temperature REAL NOT NULL,
                  humidity REAL NOT NULL,
                  precipitation REAL NOT NULL,
                  cloud REAL NOT NULL,
                  wind REAL NOT NULL,
                  drought REAL NOT NULL,
                  storm_x REAL NOT NULL,
                  storm_y REAL NOT NULL,
                  storm_intensity REAL NOT NULL,
                  weather_tick INTEGER NOT NULL DEFAULT 0,
                  updated_year REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS weather_cells (
                  world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                  cell_x INTEGER NOT NULL,
                  cell_y INTEGER NOT NULL,
                  temperature REAL NOT NULL,
                  humidity REAL NOT NULL,
                  precipitation REAL NOT NULL,
                  cloud REAL NOT NULL,
                  wind REAL NOT NULL,
                  drought REAL NOT NULL,
                  PRIMARY KEY(world_id, cell_x, cell_y)
                );
                CREATE TABLE IF NOT EXISTS weather_spawned_water (
                  world_id INTEGER NOT NULL,
                  resource_id INTEGER NOT NULL,
                  expires_year REAL NOT NULL,
                  PRIMARY KEY(world_id, resource_id)
                );
            ''')
            conn.commit()
        finally:
            conn.close()


class Engine(LearningEngine):
    """Dynamic environment layer: seasons, local weather and water cycle."""

    def __init__(self):
        ensure_weather_schema()
        self.weather = self._default_weather()
        self.weather_cells = {}
        self.ephemeral_water = {}
        self._last_season = self.weather['season']
        super().__init__()

    def _default_weather(self):
        return {
            'season': 'printemps',
            'temperature': 14.0,
            'humidity': 0.58,
            'precipitation': 0.18,
            'cloud': 0.42,
            'wind': 0.22,
            'drought': 0.10,
            'storm_x': WORLD_W * 0.5,
            'storm_y': WORLD_H * 0.5,
            'storm_intensity': 0.25,
            'weather_tick': 0,
        }

    def _load(self):
        loaded = super()._load()
        if not loaded:
            return False
        with DB_LOCK:
            conn = connect()
            try:
                row = conn.execute('SELECT * FROM weather_state WHERE world_id=?', (WORLD_ID,)).fetchone()
                if row:
                    self.weather = {
                        'season': row['season'],
                        'temperature': float(row['temperature']),
                        'humidity': float(row['humidity']),
                        'precipitation': float(row['precipitation']),
                        'cloud': float(row['cloud']),
                        'wind': float(row['wind']),
                        'drought': float(row['drought']),
                        'storm_x': float(row['storm_x']),
                        'storm_y': float(row['storm_y']),
                        'storm_intensity': float(row['storm_intensity']),
                        'weather_tick': int(row['weather_tick']),
                    }
                self.weather_cells = {
                    (int(r['cell_x']), int(r['cell_y'])): {
                        'x': int(r['cell_x']), 'y': int(r['cell_y']),
                        'temperature': float(r['temperature']), 'humidity': float(r['humidity']),
                        'precipitation': float(r['precipitation']), 'cloud': float(r['cloud']),
                        'wind': float(r['wind']), 'drought': float(r['drought']),
                    }
                    for r in conn.execute('SELECT * FROM weather_cells WHERE world_id=?', (WORLD_ID,))
                }
                existing_water = set(self.resources)
                self.ephemeral_water = {
                    int(r['resource_id']): float(r['expires_year'])
                    for r in conn.execute('SELECT resource_id,expires_year FROM weather_spawned_water WHERE world_id=?', (WORLD_ID,))
                    if int(r['resource_id']) in existing_water
                }
                self._last_season = self.weather['season']
                if not self.weather_cells:
                    self._rebuild_weather_cells()
                return True
            finally:
                conn.close()

    def _persist(self, full_reset=False):
        super()._persist(full_reset=full_reset)
        with DB_LOCK:
            conn = connect()
            try:
                conn.execute('BEGIN IMMEDIATE')
                if full_reset:
                    conn.execute('DELETE FROM weather_spawned_water WHERE world_id=?', (WORLD_ID,))
                w = self.weather
                conn.execute('''
                    INSERT INTO weather_state(
                      world_id,season,temperature,humidity,precipitation,cloud,wind,drought,
                      storm_x,storm_y,storm_intensity,weather_tick,updated_year
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(world_id) DO UPDATE SET
                      season=excluded.season,temperature=excluded.temperature,humidity=excluded.humidity,
                      precipitation=excluded.precipitation,cloud=excluded.cloud,wind=excluded.wind,
                      drought=excluded.drought,storm_x=excluded.storm_x,storm_y=excluded.storm_y,
                      storm_intensity=excluded.storm_intensity,weather_tick=excluded.weather_tick,
                      updated_year=excluded.updated_year
                ''', (
                    WORLD_ID, w['season'], w['temperature'], w['humidity'], w['precipitation'],
                    w['cloud'], w['wind'], w['drought'], w['storm_x'], w['storm_y'],
                    w['storm_intensity'], w['weather_tick'], self.year,
                ))
                for (cx, cy), cell in self.weather_cells.items():
                    conn.execute('''
                        INSERT INTO weather_cells(
                          world_id,cell_x,cell_y,temperature,humidity,precipitation,cloud,wind,drought
                        ) VALUES(?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(world_id,cell_x,cell_y) DO UPDATE SET
                          temperature=excluded.temperature,humidity=excluded.humidity,
                          precipitation=excluded.precipitation,cloud=excluded.cloud,
                          wind=excluded.wind,drought=excluded.drought
                    ''', (
                        WORLD_ID, cx, cy, cell['temperature'], cell['humidity'], cell['precipitation'],
                        cell['cloud'], cell['wind'], cell['drought'],
                    ))
                conn.execute('DELETE FROM weather_spawned_water WHERE world_id=?', (WORLD_ID,))
                conn.executemany(
                    'INSERT INTO weather_spawned_water(world_id,resource_id,expires_year) VALUES(?,?,?)',
                    [(WORLD_ID, rid, expiry) for rid, expiry in self.ephemeral_water.items()],
                )
                conn.commit()
            finally:
                conn.close()

    def reset(self):
        self.weather = self._default_weather()
        self.weather_cells = {}
        self.ephemeral_water = {}
        self._last_season = 'printemps'
        super().reset()
        self._rebuild_weather_cells()
        self._persist()

    def _season_definition(self):
        fraction = self.year % 1.0
        idx = min(3, int(fraction * 4))
        return SEASONS[idx]

    def _advance_weather(self):
        season, base_temp, rain_bias = self._season_definition()
        w = self.weather
        w['weather_tick'] += 1
        phase = (self.year % 1.0) * math.tau
        seasonal_wave = math.sin(phase - math.pi / 2) * 3.5

        if w['weather_tick'] % 9 == 0:
            w['storm_intensity'] = clamp(w['storm_intensity'] + random.uniform(-0.22, 0.25), 0.05, 1.0)
        w['storm_x'] = clamp(w['storm_x'] + random.uniform(-25, 25) + w['wind'] * 8, 0, WORLD_W)
        w['storm_y'] = clamp(w['storm_y'] + random.uniform(-17, 17), 0, WORLD_H)

        humidity_target = clamp(rain_bias + random.uniform(-0.10, 0.10) - w['drought'] * 0.18, 0.12, 0.96)
        w['humidity'] += (humidity_target - w['humidity']) * 0.08
        storm_trigger = max(0.0, w['humidity'] - 0.48) * (0.6 + w['storm_intensity'])
        rain_target = clamp(storm_trigger + random.uniform(-0.12, 0.10), 0, 1)
        w['precipitation'] += (rain_target - w['precipitation']) * 0.12
        w['cloud'] += (clamp(w['humidity'] * 0.72 + w['precipitation'] * 0.42, 0, 1) - w['cloud']) * 0.10
        w['wind'] = clamp(w['wind'] + random.uniform(-0.035, 0.035) + w['storm_intensity'] * 0.006 - 0.004, 0.02, 0.95)
        temp_target = base_temp + seasonal_wave + random.uniform(-1.5, 1.5) - w['cloud'] * 1.2
        w['temperature'] += (temp_target - w['temperature']) * 0.07

        drying = max(0.0, (w['temperature'] - 22) / 28) * 0.010 + max(0, 0.30 - w['precipitation']) * 0.005
        wetting = w['precipitation'] * 0.018
        w['drought'] = clamp(w['drought'] + drying - wetting, 0, 1)
        w['season'] = season
        self._rebuild_weather_cells()

        if season != self._last_season:
            self._last_season = season
            self._log('weather', f"La saison devient {season}. Température moyenne {w['temperature']:.0f}°C.")
        if w['weather_tick'] % 64 == 0:
            if w['drought'] > 0.72:
                self._log('weather', 'Une sécheresse durable réduit l’eau et la croissance végétale.')
            elif w['precipitation'] > 0.72:
                self._log('weather', 'De fortes pluies remplissent les points d’eau et créent des mares temporaires.')
            elif w['temperature'] < -2:
                self._log('weather', 'Un épisode de froid intense augmente les besoins énergétiques.')
            elif w['temperature'] > 34:
                self._log('weather', 'Une forte chaleur augmente le besoin d’eau pendant les déplacements.')

    def _rebuild_weather_cells(self):
        w = self.weather
        cells = {}
        cell_w = WORLD_W / WEATHER_COLS
        cell_h = WORLD_H / WEATHER_ROWS
        diagonal = math.hypot(WORLD_W, WORLD_H)
        for cy in range(WEATHER_ROWS):
            for cx in range(WEATHER_COLS):
                px = (cx + 0.5) * cell_w
                py = (cy + 0.5) * cell_h
                distance = math.hypot(px - w['storm_x'], py - w['storm_y']) / diagonal
                storm = clamp(1 - distance * 2.7, 0, 1) * w['storm_intensity']
                rain = clamp(w['precipitation'] * 0.55 + storm * 0.75 + random.uniform(-0.035, 0.035), 0, 1)
                humidity = clamp(w['humidity'] + storm * 0.25 + rain * 0.12, 0, 1)
                cells[(cx, cy)] = {
                    'x': cx,
                    'y': cy,
                    'temperature': w['temperature'] - storm * 2.2 + random.uniform(-0.7, 0.7),
                    'humidity': humidity,
                    'precipitation': rain,
                    'cloud': clamp(w['cloud'] + storm * 0.34, 0, 1),
                    'wind': clamp(w['wind'] + storm * 0.25, 0, 1),
                    'drought': clamp(w['drought'] - rain * 0.20, 0, 1),
                }
        self.weather_cells = cells

    def _cell_at(self, x, y):
        cx = min(WEATHER_COLS - 1, max(0, int(x / WORLD_W * WEATHER_COLS)))
        cy = min(WEATHER_ROWS - 1, max(0, int(y / WORLD_H * WEATHER_ROWS)))
        return self.weather_cells.get((cx, cy), self.weather)

    def _apply_weather_ecology(self):
        if self.weather['weather_tick'] % 4 != 0:
            return
        avg_rain = sum(c['precipitation'] for c in self.weather_cells.values()) / max(1, len(self.weather_cells))
        avg_temp = sum(c['temperature'] for c in self.weather_cells.values()) / max(1, len(self.weather_cells))

        for resource in list(self.resources.values()):
            if resource['type'] != 'water':
                continue
            cell = self._cell_at(resource['x'], resource['y'])
            if resource['id'] in self.ephemeral_water:
                if self.year >= self.ephemeral_water[resource['id']]:
                    self.resources.pop(resource['id'], None)
                    self.ephemeral_water.pop(resource['id'], None)
                    continue
                resource['value'] = clamp(resource['value'] + cell['precipitation'] * 0.5 - (0.12 + cell['drought'] * 0.22), 4, 22)
            else:
                resource['value'] = clamp(resource['value'] + cell['precipitation'] * 0.48 - cell['drought'] * 0.20, 10, 55)

        if avg_rain > 0.68 and random.random() < 0.12 and len(self.ephemeral_water) < 10:
            self._spawn_resource('water', random.uniform(7, 13))
            rid = self.next_resource_id
            self.ephemeral_water[rid] = self.year + random.uniform(0.035, 0.085)

        growth = avg_rain * 0.55 + clamp((avg_temp - 4) / 24, 0, 1) * 0.25 - self.weather['drought'] * 0.55
        if growth > 0.25 and random.random() < growth * 0.22:
            self._spawn_resource('food')
        if self.weather['drought'] > 0.74 and random.random() < 0.12:
            food_ids = [rid for rid, r in self.resources.items() if r['type'] == 'food']
            random.shuffle(food_ids)
            for rid in food_ids[:max(1, len(food_ids) // 80)]:
                self.resources.pop(rid, None)

    def _learn_weather_pattern(self, agent, cell):
        if agent['age'] < 4 or random.random() > 0.018 + self._skill(agent, 'observation') * 0.025:
            return
        if cell['precipitation'] > 0.58:
            concept = self._concept(agent, 'weather:pluie→eau')
            concept['evidence'] += 1
            concept['confidence'] = clamp(concept['confidence'] + 0.018 * (1 - concept['confidence']), 0, 1)
        if cell['drought'] > 0.68:
            concept = self._concept(agent, 'weather:sécheresse→rareté')
            concept['evidence'] += 1
            concept['confidence'] = clamp(concept['confidence'] + 0.014 * (1 - concept['confidence']), 0, 1)
        concept = self._concept(agent, f"season:{self.weather['season']}")
        concept['evidence'] += 0.25
        concept['confidence'] = clamp(concept['confidence'] + 0.004 * (1 - concept['confidence']), 0, 1)

    def _act(self, agent, dt):
        cell = self._cell_at(agent['x'], agent['y']) if self.weather_cells else self.weather
        if cell['temperature'] > 30:
            agent['thirst'] = clamp(agent['thirst'] + dt * ((cell['temperature'] - 30) * 0.0025), 0, 100)
            agent['energy'] = clamp(agent['energy'] - dt * 0.003, 0, 100)
        elif cell['temperature'] < 3:
            cold = (3 - cell['temperature']) * 0.0018
            if self._has_capability(agent, 'warmth'):
                cold *= 0.25
            agent['energy'] = clamp(agent['energy'] - dt * cold, 0, 100)
            if cell['temperature'] < -5 and agent['energy'] < 12:
                agent['health'] -= dt * 0.008
                agent['_last_damage_cause'] = 'froid'
        self._learn_weather_pattern(agent, cell)
        super()._act(agent, dt)

    def _move_toward(self, agent, target, dt, multiplier=1.0):
        cell = self._cell_at(agent['x'], agent['y']) if self.weather_cells else self.weather
        penalty = 1.0
        if cell['precipitation'] > 0.65:
            penalty *= 0.86
        if cell['wind'] > 0.72:
            penalty *= 0.91
        super()._move_toward(agent, target, dt, multiplier * penalty)

    def _tick(self):
        self._advance_weather()
        super()._tick()
        self._apply_weather_ecology()

    def world_view(self):
        data = super().world_view()
        w = self.weather
        data['weather'] = {
            'season': w['season'],
            'temperature': round(w['temperature'], 1),
            'humidity': round(w['humidity'], 3),
            'precipitation': round(w['precipitation'], 3),
            'cloud': round(w['cloud'], 3),
            'wind': round(w['wind'], 3),
            'drought': round(w['drought'], 3),
            'cells': [
                {
                    'x': c['x'], 'y': c['y'],
                    'temperature': round(c['temperature'], 1),
                    'humidity': round(c['humidity'], 3),
                    'precipitation': round(c['precipitation'], 3),
                    'cloud': round(c['cloud'], 3),
                    'wind': round(c['wind'], 3),
                    'drought': round(c['drought'], 3),
                }
                for c in self.weather_cells.values()
            ],
        }
        return data

    def agent_view(self, agent_id):
        data = super().agent_view(agent_id)
        if not data:
            return None
        agent = self.agents.get(agent_id)
        if agent:
            cell = self._cell_at(agent['x'], agent['y'])
            data['localWeather'] = {
                'season': self.weather['season'],
                'temperature': round(cell['temperature'], 1),
                'humidity': round(cell['humidity'], 3),
                'precipitation': round(cell['precipitation'], 3),
                'wind': round(cell['wind'], 3),
                'drought': round(cell['drought'], 3),
            }
        return data
