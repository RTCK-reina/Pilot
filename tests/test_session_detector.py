"""Tests for drive/charge session detection."""

from __future__ import annotations

import json
from pathlib import Path

from pilot_common.constants import VehicleState
from tesla_poller.data_recorder import ensure_car
from tesla_poller.session_detector import SessionDetector

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestDriveSession:
    def test_drive_start(self, db):
        data = _load("vehicle_data_driving.json")
        car_id = ensure_car(db, "VIN001", data)
        sd = SessionDetector(db, car_id, 0.149)
        sd.set_current_data(data)
        sd.on_state_change(VehicleState.IDLE, VehicleState.DRIVING, 0)

        assert sd.current_drive_id is not None
        row = db.execute("SELECT * FROM drives WHERE id = ?", (sd.current_drive_id,)).fetchone()
        assert row["car_id"] == car_id
        assert row["is_complete"] == 0

    def test_drive_end(self, db):
        data_start = _load("vehicle_data_driving.json")
        data_end = _load("vehicle_data_idle.json")
        car_id = ensure_car(db, "VIN001", data_start)
        sd = SessionDetector(db, car_id, 0.149)

        sd.set_current_data(data_start)
        sd.on_state_change(VehicleState.IDLE, VehicleState.DRIVING, 0)
        drive_id = sd.current_drive_id

        sd.set_current_data(data_end)
        sd.on_state_change(VehicleState.DRIVING, VehicleState.IDLE, 100)

        assert sd.current_drive_id is None
        row = db.execute("SELECT * FROM drives WHERE id = ?", (drive_id,)).fetchone()
        assert row["is_complete"] == 1
        assert row["end_time"] is not None

    def test_no_duplicate_drive_on_reentry(self, db):
        data = _load("vehicle_data_driving.json")
        car_id = ensure_car(db, "VIN001", data)
        sd = SessionDetector(db, car_id, 0.149)
        sd.set_current_data(data)

        sd.on_state_change(VehicleState.IDLE, VehicleState.DRIVING, 0)
        first_id = sd.current_drive_id

        # Another driving event while already driving — should NOT create new drive
        sd.on_state_change(VehicleState.DRIVING, VehicleState.DRIVING, 10)
        assert sd.current_drive_id == first_id


class TestChargeSession:
    def test_charge_start(self, db):
        data = _load("vehicle_data_charging.json")
        car_id = ensure_car(db, "VIN001", data)
        sd = SessionDetector(db, car_id, 0.149)
        sd.set_current_data(data)
        sd.on_state_change(VehicleState.IDLE, VehicleState.CHARGING, 0)

        assert sd.current_charge_id is not None

    def test_charge_end(self, db):
        data_start = _load("vehicle_data_charging.json")
        data_end = _load("vehicle_data_idle.json")
        car_id = ensure_car(db, "VIN001", data_start)
        sd = SessionDetector(db, car_id, 0.149)

        sd.set_current_data(data_start)
        sd.on_state_change(VehicleState.IDLE, VehicleState.CHARGING, 0)
        session_id = sd.current_charge_id

        sd.set_current_data(data_end)
        sd.on_state_change(VehicleState.CHARGING, VehicleState.IDLE, 100)

        assert sd.current_charge_id is None
        row = db.execute(
            "SELECT * FROM charging_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        assert row["is_complete"] == 1
