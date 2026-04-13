"""Tests for dashboard JSON API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pilot_dashboard.app import create_app


@pytest.fixture
def client():
    app = create_app(":memory:")
    with TestClient(app) as c:
        # Seed test data
        db = app.state.db
        db.execute(
            "INSERT INTO cars (id, vin, model, efficiency, usable_battery_capacity_kwh) "
            "VALUES (1, 'VIN001', 'Model Y', 0.149, 57.0)"
        )
        db.execute(
            "INSERT INTO drives (car_id, start_time, end_time, distance_km, "
            "energy_consumed_kwh, efficiency_whkm, efficiency_kmkwh, road_type, "
            "outside_temp_avg, start_battery_level, end_battery_level, "
            "start_rated_range_km, end_rated_range_km, is_complete) "
            "VALUES (1, '2026-04-10T10:00:00', '2026-04-10T10:30:00', 25.5, "
            "3.8, 149.0, 6.71, 'city', 18.5, 80, 72, 200.0, 174.5, 1)"
        )
        db.execute(
            "INSERT INTO drives (car_id, start_time, end_time, distance_km, "
            "energy_consumed_kwh, efficiency_whkm, efficiency_kmkwh, road_type, "
            "outside_temp_avg, is_complete) "
            "VALUES (1, '2026-04-11T14:00:00', '2026-04-11T15:00:00', 80.0, "
            "15.6, 195.0, 5.13, 'highway', 22.0, 1)"
        )
        db.execute(
            "INSERT INTO charging_sessions (car_id, start_time, end_time, "
            "charge_energy_added, max_charger_power, cost_jpy, is_complete) "
            "VALUES (1, '2026-04-10T22:00:00', '2026-04-11T06:00:00', "
            "30.0, 7.4, 840, 1)"
        )
        db.execute(
            "INSERT INTO states (car_id, state, start_time) "
            "VALUES (1, 'idle', '2026-04-12T00:00:00')"
        )
        db.execute(
            "INSERT INTO positions (car_id, timestamp, latitude, longitude, "
            "speed, battery_level, rated_range_km, outside_temp, tpms_fl, tpms_fr, tpms_rl, tpms_rr) "
            "VALUES (1, '2026-04-10T10:00:00', 34.69, 135.50, "
            "60, 80, 200.0, 18.5, 2.9, 2.9, 2.9, 2.9)"
        )
        db.commit()
        yield c


class TestCarAndStatus:
    def test_car(self, client):
        r = client.get("/api/car")
        assert r.status_code == 200
        assert r.json()["car"]["vin"] == "VIN001"

    def test_status(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        assert r.json()["state"]["state"] == "idle"


class TestDrives:
    def test_list(self, client):
        r = client.get("/api/drives")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["drives"]) == 2

    def test_pagination(self, client):
        r = client.get("/api/drives?per_page=1&page=1")
        data = r.json()
        assert len(data["drives"]) == 1
        assert data["pages"] == 2

    def test_detail(self, client):
        r = client.get("/api/drives/1")
        assert r.status_code == 200
        assert r.json()["drive"]["distance_km"] == 25.5

    def test_positions(self, client):
        r = client.get("/api/drives/1/positions")
        assert r.status_code == 200


class TestCharging:
    def test_list(self, client):
        r = client.get("/api/charging")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_detail(self, client):
        r = client.get("/api/charging/1")
        assert r.status_code == 200
        assert r.json()["session"]["charge_energy_added"] == 30.0


class TestEfficiency:
    def test_summary_all(self, client):
        r = client.get("/api/efficiency/summary")
        assert r.status_code == 200
        s = r.json()["summary"]
        assert s["drive_count"] == 2
        assert s["total_distance_km"] == 105.5

    def test_trend(self, client):
        r = client.get("/api/efficiency/trend?interval=daily")
        assert r.status_code == 200

    def test_speed_bands(self, client):
        r = client.get("/api/efficiency/speed-bands")
        assert r.status_code == 200

    def test_temp_scatter(self, client):
        r = client.get("/api/efficiency/temp-scatter")
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_road_type(self, client):
        r = client.get("/api/efficiency/road-type")
        assert r.status_code == 200
        types = {rt["road_type"] for rt in r.json()["road_types"]}
        assert "city" in types
        assert "highway" in types


class TestBattery:
    def test_health(self, client):
        r = client.get("/api/battery/health")
        assert r.status_code == 200

    def test_cycles(self, client):
        r = client.get("/api/battery/cycles")
        assert r.status_code == 200
        data = r.json()
        assert data["total_energy_kwh"] == 19.4  # 3.8 + 15.6
        assert data["capacity_kwh"] == 57.0


class TestVehicle:
    def test_software(self, client):
        r = client.get("/api/vehicle/software")
        assert r.status_code == 200

    def test_tpms(self, client):
        r = client.get("/api/vehicle/tpms")
        assert r.status_code == 200
        assert len(r.json()["tpms"]) == 1


class TestSettings:
    def test_get(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200

    def test_update(self, client):
        r = client.put("/api/settings", json={"locale": "ja", "currency": "JPY"})
        assert r.status_code == 200
        r2 = client.get("/api/settings")
        assert r2.json()["settings"]["locale"] == "ja"


class TestHtmlRoutes:
    def test_home(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_efficiency(self, client):
        r = client.get("/efficiency")
        assert r.status_code == 200

    def test_drives(self, client):
        r = client.get("/drives")
        assert r.status_code == 200

    def test_charging(self, client):
        r = client.get("/charging")
        assert r.status_code == 200

    def test_battery(self, client):
        r = client.get("/battery")
        assert r.status_code == 200

    def test_vehicle(self, client):
        r = client.get("/vehicle")
        assert r.status_code == 200

    def test_settings_page(self, client):
        r = client.get("/settings")
        assert r.status_code == 200

    def test_fragment(self, client):
        r = client.get("/fragment/home")
        assert r.status_code == 200
