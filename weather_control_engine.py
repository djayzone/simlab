from engine import clamp
from weather_engine import Engine as WeatherEngine, SEASONS


PRESETS = {
    'clear': {
        'precipitation': 0.02,
        'cloud': 0.08,
        'wind': 0.12,
        'humidity': 0.35,
        'storm_intensity': 0.05,
    },
    'rain': {
        'precipitation': 0.78,
        'cloud': 0.92,
        'wind': 0.28,
        'humidity': 0.88,
        'storm_intensity': 0.35,
    },
    'storm': {
        'precipitation': 0.96,
        'cloud': 1.0,
        'wind': 0.82,
        'humidity': 0.94,
        'storm_intensity': 1.0,
    },
    'heatwave': {
        'temperature': 39.0,
        'precipitation': 0.01,
        'cloud': 0.05,
        'wind': 0.18,
        'humidity': 0.18,
        'drought': 0.72,
        'storm_intensity': 0.05,
    },
    'cold_snap': {
        'temperature': -8.0,
        'precipitation': 0.12,
        'cloud': 0.62,
        'wind': 0.42,
        'humidity': 0.60,
        'storm_intensity': 0.18,
    },
    'drought': {
        'temperature': 33.0,
        'precipitation': 0.0,
        'cloud': 0.03,
        'wind': 0.24,
        'humidity': 0.12,
        'drought': 0.96,
        'storm_intensity': 0.02,
    },
}

SEASON_BY_NAME = {name: (name, temp, rain_bias) for name, temp, rain_bias in SEASONS}


class Engine(WeatherEngine):
    """Operator-facing live weather controls layered over the natural climate engine."""

    def __init__(self):
        self.weather_control = {
            'mode': 'auto',
            'preset': None,
            'season': None,
            'values': {},
            'changed_at_year': None,
        }
        super().__init__()

    def _season_definition(self):
        forced = self.weather_control.get('season')
        if self.weather_control.get('mode') == 'manual' and forced in SEASON_BY_NAME:
            return SEASON_BY_NAME[forced]
        return super()._season_definition()

    def _apply_manual_weather(self):
        if self.weather_control.get('mode') != 'manual':
            return
        values = self.weather_control.get('values', {})
        for key, value in values.items():
            if key in ('temperature', 'storm_x', 'storm_y'):
                self.weather[key] = float(value)
            elif key in ('humidity', 'precipitation', 'cloud', 'wind', 'drought', 'storm_intensity'):
                self.weather[key] = clamp(float(value), 0, 1)
        forced = self.weather_control.get('season')
        if forced in SEASON_BY_NAME:
            self.weather['season'] = forced
        self._rebuild_weather_cells()

    def _advance_weather(self):
        super()._advance_weather()
        self._apply_manual_weather()

    def update_weather_control(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('weather control payload must be an object')

        action = payload.get('action')
        if action == 'auto':
            self.weather_control = {
                'mode': 'auto', 'preset': None, 'season': None,
                'values': {}, 'changed_at_year': self.year,
            }
            self._log('weather', 'Contrôle météo relâché : le climat naturel reprend.')
            return self.weather_control_view()

        preset = payload.get('preset')
        if preset is not None and preset not in PRESETS:
            raise ValueError('unknown weather preset')

        season_provided = 'season' in payload
        season = payload.get('season')
        if season == '':
            season = None
        if season is not None and season not in SEASON_BY_NAME:
            raise ValueError('unknown season')

        values = dict(self.weather_control.get('values', {})) if self.weather_control.get('mode') == 'manual' else {}
        if preset:
            values.update(PRESETS[preset])

        allowed = {
            'temperature': (-25.0, 50.0),
            'humidity': (0.0, 1.0),
            'precipitation': (0.0, 1.0),
            'cloud': (0.0, 1.0),
            'wind': (0.0, 1.0),
            'drought': (0.0, 1.0),
            'storm_intensity': (0.0, 1.0),
        }
        for key, (minimum, maximum) in allowed.items():
            if key in payload and payload[key] is not None:
                value = float(payload[key])
                if value < minimum or value > maximum:
                    raise ValueError(f'{key} out of range')
                values[key] = value

        forced_season = season if season_provided else self.weather_control.get('season')
        self.weather_control = {
            'mode': 'manual',
            'preset': preset,
            'season': forced_season,
            'values': values,
            'changed_at_year': self.year,
        }
        self._apply_manual_weather()
        label = preset or 'réglage manuel'
        if forced_season:
            label += f' / {forced_season}'
        self._log('weather', f'Contrôle météo opérateur activé : {label}.')
        return self.weather_control_view()

    def weather_control_view(self):
        return {
            'mode': self.weather_control.get('mode', 'auto'),
            'preset': self.weather_control.get('preset'),
            'season': self.weather_control.get('season'),
            'values': dict(self.weather_control.get('values', {})),
            'changedAtYear': self.weather_control.get('changed_at_year'),
            'presets': list(PRESETS),
        }

    def world_view(self):
        data = super().world_view()
        data.setdefault('weather', {})['control'] = self.weather_control_view()
        return data
