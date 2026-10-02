from climate_model import advance_drought
from engine import clamp
from hot_mechanics_engine import Engine as HotMechanicsEngine


class Engine(HotMechanicsEngine):
    """Climate correction layer with a bounded, recoverable soil-drought model."""

    def _advance_weather(self):
        previous_drought = clamp(float(self.weather.get('drought', 0.0)), 0.0, 1.0)

        # The legacy model fed the full drought value back into humidity_target.
        # That made high drought suppress its own future rain and created an
        # irreversible drift toward 1.0. Keep only a weak atmospheric feedback;
        # soil drought itself is recalculated below from a bounded water balance.
        self.weather['drought'] = previous_drought * 0.22
        super()._advance_weather()

        control = getattr(self, 'weather_control', {})
        manual_values = control.get('values', {}) if control.get('mode') == 'manual' else {}

        # An explicitly forced drought value is authoritative. Partial manual
        # controls (temperature/rain/wind only) still let soil drought evolve from
        # the imposed environmental conditions.
        if 'drought' in manual_values:
            return

        w = self.weather
        w['drought'] = advance_drought(
            previous_drought,
            w.get('season', 'printemps'),
            w.get('temperature', 14.0),
            w.get('humidity', 0.58),
            w.get('precipitation', 0.0),
            w.get('wind', 0.0),
        )
        # The base weather layer already built cells before the corrected soil
        # deficit was applied. Refresh the 6x4 weather grid with the final value.
        self._rebuild_weather_cells()
