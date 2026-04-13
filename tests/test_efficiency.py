"""Tests for energy efficiency calculations."""

from __future__ import annotations

from tesla_poller.efficiency import (
    calc_efficiency_kmkwh,
    calc_efficiency_whkm,
    calc_energy_consumed,
    calc_gasoline_equivalent,
    classify_road_type,
)


class TestEnergyConsumed:
    def test_basic_consumption(self):
        # 200km rated range -> 180km = 20km range consumed
        # With efficiency 0.149 kWh/km: 20 * 0.149 = 2.98 kWh
        result = calc_energy_consumed(200.0, 180.0, 0.149)
        assert abs(result - 2.98) < 0.001

    def test_zero_change(self):
        result = calc_energy_consumed(200.0, 200.0, 0.149)
        assert result == 0.0

    def test_regen_gain(self):
        # Range increased (downhill regen) -> negative consumption
        result = calc_energy_consumed(180.0, 185.0, 0.149)
        assert result < 0


class TestEfficiencyWhkm:
    def test_normal(self):
        # 5 kWh over 30 km = 166.7 Wh/km
        result = calc_efficiency_whkm(5.0, 30.0)
        assert abs(result - 166.7) < 0.1

    def test_zero_distance(self):
        assert calc_efficiency_whkm(5.0, 0.0) is None

    def test_negative_distance(self):
        assert calc_efficiency_whkm(5.0, -1.0) is None


class TestEfficiencyKmkwh:
    def test_normal(self):
        # 30 km on 5 kWh = 6.0 km/kWh
        result = calc_efficiency_kmkwh(30.0, 5.0)
        assert result == 6.0

    def test_zero_energy(self):
        assert calc_efficiency_kmkwh(30.0, 0.0) is None

    def test_model_y_benchmark_city_summer(self):
        # Appendix B: city summer 113-130 Wh/km -> ~7.7-8.8 km/kWh
        # 50km drive at 120 Wh/km = 6 kWh consumed
        energy = 6.0
        distance = 50.0
        result = calc_efficiency_kmkwh(distance, energy)
        assert 8.0 < result < 8.5

    def test_model_y_benchmark_highway_120(self):
        # Appendix B: highway 120km/h -> 195 Wh/km -> ~5.1 km/kWh
        energy = 19.5  # 100km at 195 Wh/km
        distance = 100.0
        result = calc_efficiency_kmkwh(distance, energy)
        assert abs(result - 5.13) < 0.1


class TestGasolineEquivalent:
    def test_conversion(self):
        # 6.5 km/kWh * 8.9 = 57.85 km/L
        result = calc_gasoline_equivalent(6.5)
        assert abs(result - 57.85) < 0.01


class TestClassifyRoadType:
    def test_highway(self):
        # 70% samples above 80 km/h
        speeds = [90, 100, 110, 95, 85, 105, 60, 40, 30, 50]
        # 6 out of 10 >= 80 = 60% -> highway
        assert classify_road_type(speeds) == "highway"

    def test_city(self):
        # 50% samples below 30 km/h
        speeds = [10, 20, 25, 15, 28, 40, 35, 50, 60, 45]
        # 5 out of 10 < 30 = 50% > 40% -> city
        assert classify_road_type(speeds) == "city"

    def test_mixed(self):
        speeds = [40, 50, 60, 70, 80, 45, 55, 65, 75, 85]
        assert classify_road_type(speeds) == "mixed"

    def test_empty(self):
        assert classify_road_type([]) == "mixed"
