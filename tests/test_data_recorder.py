"""Tests for data recorder — API response parsing and DB writes."""

from __future__ import annotations

import json
from pathlib import Path

from tesla_poller.data_recorder import ensure_car, record_charge, record_position, record_state

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestEnsureCar:
    def test_creates_car(self, db):
        data = _load("vehicle_data_driving.json")
        car_id = ensure_car(db, "5YJ3E1EAXPF000001", data)
        assert car_id > 0

        row = db.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        assert row["vin"] == "5YJ3E1EAXPF000001"
        assert row["model"] == "Model Y"

    def test_returns_existing(self, db):
        data = _load("vehicle_data_driving.json")
        id1 = ensure_car(db, "5YJ3E1EAXPF000001", data)
        id2 = ensure_car(db, "5YJ3E1EAXPF000001", data)
        assert id1 == id2


class TestRecordPosition:
    def test_inserts_position(self, db):
        data = _load("vehicle_data_driving.json")
        car_id = ensure_car(db, "VIN001", data)
        pos_id = record_position(db, car_id, None, data)
        assert pos_id is not None

        row = db.execute("SELECT * FROM positions WHERE id = ?", (pos_id,)).fetchone()
        assert row["car_id"] == car_id
        assert row["speed"] == 65
        assert row["latitude"] is not None

    def test_with_drive_id(self, db):
        data = _load("vehicle_data_driving.json")
        car_id = ensure_car(db, "VIN001", data)

        db.execute(
            "INSERT INTO drives (car_id, start_time) VALUES (?, '2026-01-01T00:00:00')",
            (car_id,),
        )
        db.commit()
        drive_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        pos_id = record_position(db, car_id, drive_id, data)
        row = db.execute("SELECT drive_id FROM positions WHERE id = ?", (pos_id,)).fetchone()
        assert row["drive_id"] == drive_id

    def test_handles_null_fields(self, db):
        data = _load("vehicle_data_idle.json")
        car_id = ensure_car(db, "VIN001", data)
        pos_id = record_position(db, car_id, None, data)
        row = db.execute("SELECT speed, power FROM positions WHERE id = ?", (pos_id,)).fetchone()
        assert row["speed"] is None
        assert row["power"] is None


class TestRecordCharge:
    def test_inserts_charge(self, db):
        data = _load("vehicle_data_charging.json")
        car_id = ensure_car(db, "VIN001", data)

        db.execute(
            "INSERT INTO charging_sessions (car_id, start_time) VALUES (?, '2026-01-01T00:00:00')",
            (car_id,),
        )
        db.commit()
        session_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        charge_id = record_charge(db, session_id, data)
        assert charge_id is not None

        row = db.execute("SELECT * FROM charges WHERE id = ?", (charge_id,)).fetchone()
        assert row["charger_power"] == 48
        assert row["battery_level"] == 45


class TestRecordState:
    def test_records_transition(self, db):
        car_id = 1
        db.execute("INSERT INTO cars (id, vin) VALUES (1, 'VIN001')")
        db.commit()

        record_state(db, car_id, "driving")
        rows = db.execute("SELECT * FROM states WHERE car_id = ?", (car_id,)).fetchall()
        assert len(rows) == 1
        assert rows[0]["state"] == "driving"
        assert rows[0]["end_time"] is None

    def test_closes_previous_state(self, db):
        car_id = 1
        db.execute("INSERT INTO cars (id, vin) VALUES (1, 'VIN001')")
        db.commit()

        record_state(db, car_id, "driving")
        record_state(db, car_id, "idle")

        rows = db.execute(
            "SELECT * FROM states WHERE car_id = ? ORDER BY id", (car_id,)
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["end_time"] is not None  # previous state closed
        assert rows[1]["end_time"] is None       # new state open
