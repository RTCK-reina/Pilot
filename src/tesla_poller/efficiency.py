"""Energy efficiency calculations and road type classification.

Based on the rated range change method (TeslaMate approach):
  energy_consumed_kwh = (start_range - end_range) * efficiency_constant
"""

from __future__ import annotations

from pilot_common.constants import (
    CITY_RATIO_THRESHOLD,
    CITY_SPEED_THRESHOLD_KMH,
    GASOLINE_ENERGY_DENSITY_KWH_PER_L,
    HIGHWAY_RATIO_THRESHOLD,
    HIGHWAY_SPEED_THRESHOLD_KMH,
)


def calc_energy_consumed(
    start_rated_range_km: float,
    end_rated_range_km: float,
    efficiency_constant: float,
) -> float:
    """Calculate energy consumed (kWh) from rated range change.

    Args:
        start_rated_range_km: Rated range at start of drive (km).
        end_rated_range_km: Rated range at end of drive (km).
        efficiency_constant: Vehicle efficiency (kWh/km), e.g. 0.149 for Model Y LFP.

    Returns:
        Energy consumed in kWh (positive = consumption, negative = net regen gain).
    """
    return (start_rated_range_km - end_rated_range_km) * efficiency_constant


def calc_efficiency_whkm(energy_kwh: float, distance_km: float) -> float | None:
    """Calculate Wh/km. Returns None if distance is zero."""
    if distance_km <= 0:
        return None
    return energy_kwh * 1000 / distance_km


def calc_efficiency_kmkwh(distance_km: float, energy_kwh: float) -> float | None:
    """Calculate km/kWh. Returns None if energy is zero."""
    if energy_kwh <= 0:
        return None
    return distance_km / energy_kwh


def calc_gasoline_equivalent(kmkwh: float) -> float:
    """Convert km/kWh to gasoline-equivalent km/L.

    Uses 8.9 kWh per liter of gasoline as energy density.
    Example: 6.5 km/kWh * 8.9 = 57.9 km/L equivalent.
    """
    return kmkwh * GASOLINE_ENERGY_DENSITY_KWH_PER_L


def classify_road_type(speed_samples: list[int | float]) -> str:
    """Classify road type from speed distribution.

    Args:
        speed_samples: List of speed values (km/h) during the drive.

    Returns:
        'highway', 'city', or 'mixed'.
    """
    if not speed_samples:
        return "mixed"

    total = len(speed_samples)
    highway_count = sum(1 for s in speed_samples if s > HIGHWAY_SPEED_THRESHOLD_KMH)
    city_count = sum(1 for s in speed_samples if s < CITY_SPEED_THRESHOLD_KMH)

    if highway_count / total >= HIGHWAY_RATIO_THRESHOLD:
        return "highway"
    if city_count / total >= CITY_RATIO_THRESHOLD:
        return "city"
    return "mixed"
