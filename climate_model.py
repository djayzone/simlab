SEASONAL_DROUGHT_BASELINE = {
    'printemps': 0.18,
    'été': 0.38,
    'automne': 0.22,
    'hiver': 0.16,
}


def clamp01(value):
    return max(0.0, min(1.0, float(value)))


def drought_target(season, temperature, humidity, precipitation, wind):
    """Return a bounded soil-water deficit target from current climate.

    Drought is modelled as a slow state converging toward environmental
    conditions, not as an accumulator that can only drift upward.
    """
    baseline = SEASONAL_DROUGHT_BASELINE.get(season, 0.24)
    humidity = clamp01(humidity)
    precipitation = clamp01(precipitation)
    wind = clamp01(wind)

    heat_pressure = clamp01((float(temperature) - 20.0) / 22.0)
    dry_air_pressure = clamp01((0.52 - humidity) / 0.52)
    wind_pressure = clamp01((wind - 0.25) / 0.75)
    rain_relief = clamp01(precipitation / 0.70)

    return max(0.08, min(0.96,
        baseline
        + heat_pressure * 0.30
        + dry_air_pressure * 0.22
        + wind_pressure * 0.08
        - rain_relief * 0.25
    ))


def advance_drought(previous, season, temperature, humidity, precipitation, wind):
    """Advance drought with soil memory and rain-sensitive recovery speed."""
    previous = clamp01(previous)
    precipitation = clamp01(precipitation)
    target = drought_target(season, temperature, humidity, precipitation, wind)

    response = 0.030
    if precipitation >= 0.55:
        response = 0.070
    elif precipitation >= 0.30:
        response = 0.048
    elif target > previous:
        response = 0.036

    return max(0.0, min(0.98, previous + (target - previous) * response))
