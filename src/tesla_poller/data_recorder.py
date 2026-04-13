"""Parse Tesla API responses and write to SQLite.

Handles positions, charges, states, and car info. Sends IPC notify after writes.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pilot_common.notify import send_notify

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def ensure_car(conn: sqlite3.Connection, vin: str, vehicle_data: dict) -> int:
    """Ensure car exists in DB. Returns car_id."""
    row = conn.execute("SELECT id FROM cars WHERE vin = ?", (vin,)).fetchone()
    if row:
        return row[0]

    config = vehicle_data.get("vehicle_config", {})
    car_type = config.get("car_type", "")
    model = "Model Y" if "modely" in car_type else "Model 3" if "model3" in car_type else car_type

    conn.execute(
        """INSERT INTO cars (vin, model, trim, exterior_color, car_version)
           VALUES (?, ?, ?, ?, ?)""",
        (
            vin,
            model,
            config.get("trim_badging"),
            config.get("exterior_color"),
            _safe_get(vehicle_data, "vehicle_state", "car_version"),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM cars WHERE vin = ?", (vin,)).fetchone()
    logger.info("Created car record: vin=%s model=%s id=%d", vin, model, row[0])
    return row[0]


def record_position(
    conn: sqlite3.Connection,
    car_id: int,
    drive_id: int | None,
    data: dict,
) -> int | None:
    """Insert a position record from vehicle_data. Returns position id."""
    drive = data.get("drive_state", {})
    charge = data.get("charge_state", {})
    climate = data.get("climate_state", {})
    vehicle = data.get("vehicle_state", {})

    ts = drive.get("timestamp")
    if ts:
        timestamp = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    else:
        timestamp = _iso_now()

    cursor = conn.execute(
        """INSERT INTO positions (
            car_id, drive_id, timestamp, latitude, longitude, speed, power,
            odometer, battery_level, usable_battery_level, rated_range_km,
            est_range_km, elevation, heading, inside_temp, outside_temp,
            is_climate_on, battery_heater,
            tpms_fl, tpms_fr, tpms_rl, tpms_rr, fan_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            car_id,
            drive_id,
            timestamp,
            drive.get("latitude"),
            drive.get("longitude"),
            drive.get("speed"),
            drive.get("power"),
            vehicle.get("odometer"),
            charge.get("battery_level"),
            charge.get("usable_battery_level"),
            _miles_to_km(charge.get("battery_range")),
            _miles_to_km(charge.get("est_battery_range")),
            None,  # elevation — to be filled by SRTM later
            drive.get("heading"),
            climate.get("inside_temp"),
            climate.get("outside_temp"),
            1 if climate.get("is_climate_on") else 0,
            1 if climate.get("battery_heater") else 0,
            vehicle.get("tpms_pressure_fl"),
            vehicle.get("tpms_pressure_fr"),
            vehicle.get("tpms_pressure_rl"),
            vehicle.get("tpms_pressure_rr"),
            climate.get("fan_status"),
        ),
    )
    conn.commit()
    send_notify()
    return cursor.lastrowid


def record_charge(
    conn: sqlite3.Connection,
    session_id: int,
    data: dict,
) -> int | None:
    """Insert a charge data point. Returns charge id."""
    charge = data.get("charge_state", {})
    climate = data.get("climate_state", {})

    ts_raw = charge.get("timestamp") or _safe_get(data, "drive_state", "timestamp")
    if ts_raw:
        timestamp = datetime.fromtimestamp(ts_raw / 1000, tz=timezone.utc).isoformat()
    else:
        timestamp = _iso_now()

    cursor = conn.execute(
        """INSERT INTO charges (
            charging_session_id, timestamp, battery_level, usable_battery_level,
            charge_energy_added, charger_power, charger_voltage, charger_current,
            charger_phases, outside_temp, battery_heater,
            conn_charge_cable, fast_charger_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            timestamp,
            charge.get("battery_level"),
            charge.get("usable_battery_level"),
            charge.get("charge_energy_added"),
            charge.get("charger_power"),
            charge.get("charger_voltage"),
            charge.get("charger_actual_current"),
            charge.get("charger_phases"),
            climate.get("outside_temp"),
            1 if climate.get("battery_heater") else 0,
            charge.get("conn_charge_cable"),
            charge.get("fast_charger_type"),
        ),
    )
    conn.commit()
    send_notify()
    return cursor.lastrowid


def record_state(
    conn: sqlite3.Connection,
    car_id: int,
    state: str,
) -> None:
    """Record a state transition. Closes previous open state."""
    now = _iso_now()
    conn.execute(
        "UPDATE states SET end_time = ? WHERE car_id = ? AND end_time IS NULL",
        (now, car_id),
    )
    conn.execute(
        "INSERT INTO states (car_id, state, start_time) VALUES (?, ?, ?)",
        (car_id, state, now),
    )
    conn.commit()


def _miles_to_km(miles: float | None) -> float | None:
    """Convert miles to km. Tesla API returns range in miles."""
    if miles is None:
        return None
    return round(miles * 1.60934, 2)
