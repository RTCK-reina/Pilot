"""Automatic drive/charge session boundary detection.

Listens to state transitions and creates/finalizes session records.
Handles edge cases: short stops at traffic lights, brief charger disconnects.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from pilot_common.constants import VehicleState
from tesla_poller.data_recorder import _miles_to_km, _safe_get
from tesla_poller.efficiency import (
    calc_efficiency_kmkwh,
    calc_efficiency_whkm,
    calc_energy_consumed,
    classify_road_type,
)

logger = logging.getLogger(__name__)

# Minimum drive duration (seconds) to be considered a real drive
# Prevents micro-drives from parking lot maneuvers
MIN_DRIVE_DURATION_S = 60

# Minimum charge duration (seconds) to be considered a real session
MIN_CHARGE_DURATION_S = 120


class SessionDetector:
    """Detects drive and charge session boundaries from state transitions."""

    def __init__(self, conn: sqlite3.Connection, car_id: int, efficiency: float):
        self._conn = conn
        self._car_id = car_id
        self._efficiency = efficiency
        self._current_drive_id: int | None = None
        self._current_charge_id: int | None = None
        self._drive_start_data: dict | None = None
        self._charge_start_data: dict | None = None

    @property
    def current_drive_id(self) -> int | None:
        return self._current_drive_id

    @property
    def current_charge_id(self) -> int | None:
        return self._current_charge_id

    def on_state_change(
        self, old: VehicleState, new: VehicleState, timestamp: float
    ) -> None:
        """Handle state transitions for session detection."""
        if new == VehicleState.DRIVING and old != VehicleState.DRIVING:
            # Don't start new drive if one is already open (handles re-entry)
            if self._current_drive_id is None:
                self._start_drive()

        elif old == VehicleState.DRIVING and new != VehicleState.DRIVING:
            self._end_drive()

        if new == VehicleState.CHARGING and old != VehicleState.CHARGING:
            if self._current_charge_id is None:
                self._start_charge()

        elif old == VehicleState.CHARGING and new != VehicleState.CHARGING:
            self._end_charge()

    def set_current_data(self, data: dict) -> None:
        """Update the latest vehicle data for session start/end calculations."""
        if self._current_drive_id is not None and self._drive_start_data is None:
            self._drive_start_data = data
        if self._current_charge_id is not None and self._charge_start_data is None:
            self._charge_start_data = data
        self._latest_data = data

    def _start_drive(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        data = getattr(self, "_latest_data", {})
        drive = data.get("drive_state", {})
        charge = data.get("charge_state", {})

        cursor = self._conn.execute(
            """INSERT INTO drives (
                car_id, start_time, start_lat, start_lng,
                start_odometer, start_battery_level, start_rated_range_km
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self._car_id,
                now,
                drive.get("latitude"),
                drive.get("longitude"),
                _safe_get(data, "vehicle_state", "odometer"),
                charge.get("battery_level"),
                _miles_to_km(charge.get("battery_range")),
            ),
        )
        self._conn.commit()
        self._current_drive_id = cursor.lastrowid
        self._drive_start_data = data
        logger.info("Drive started: id=%d", self._current_drive_id)

    def _end_drive(self) -> None:
        if self._current_drive_id is None:
            return

        drive_id = self._current_drive_id
        data = getattr(self, "_latest_data", {})
        drive = data.get("drive_state", {})
        charge = data.get("charge_state", {})
        climate = data.get("climate_state", {})

        # Calculate aggregates from positions
        positions = self._conn.execute(
            "SELECT speed, outside_temp FROM positions WHERE drive_id = ?",
            (drive_id,),
        ).fetchall()

        speed_samples = [p[0] for p in positions if p[0] is not None]
        temps = [p[1] for p in positions if p[1] is not None]

        # Get start data
        start = self._conn.execute(
            "SELECT start_odometer, start_rated_range_km, start_battery_level, start_time FROM drives WHERE id = ?",
            (drive_id,),
        ).fetchone()

        end_odometer = _safe_get(data, "vehicle_state", "odometer")
        end_range = _miles_to_km(charge.get("battery_range"))
        now = datetime.now(timezone.utc).isoformat()

        distance = None
        if start["start_odometer"] and end_odometer:
            distance = round(end_odometer - start["start_odometer"], 2)

        energy = None
        if start["start_rated_range_km"] and end_range:
            energy = calc_energy_consumed(
                start["start_rated_range_km"], end_range, self._efficiency
            )

        whkm = calc_efficiency_whkm(energy, distance) if energy and distance else None
        kmkwh = calc_efficiency_kmkwh(distance, energy) if energy and distance else None
        road_type = classify_road_type(speed_samples)

        # Duration in minutes
        duration = None
        if start["start_time"]:
            try:
                st = datetime.fromisoformat(start["start_time"])
                et = datetime.fromisoformat(now)
                duration = round((et - st).total_seconds() / 60, 1)
            except (ValueError, TypeError):
                pass

        self._conn.execute(
            """UPDATE drives SET
                end_time = ?, end_lat = ?, end_lng = ?,
                end_odometer = ?, end_battery_level = ?, end_rated_range_km = ?,
                distance_km = ?, duration_min = ?,
                outside_temp_avg = ?,
                speed_max = ?, speed_avg = ?,
                energy_consumed_kwh = ?,
                efficiency_whkm = ?, efficiency_kmkwh = ?,
                road_type = ?, is_complete = 1
            WHERE id = ?""",
            (
                now,
                drive.get("latitude"),
                drive.get("longitude"),
                end_odometer,
                charge.get("battery_level"),
                end_range,
                distance,
                duration,
                round(sum(temps) / len(temps), 1) if temps else None,
                max(speed_samples) if speed_samples else None,
                round(sum(speed_samples) / len(speed_samples), 1) if speed_samples else None,
                round(energy, 4) if energy else None,
                round(whkm, 1) if whkm else None,
                round(kmkwh, 2) if kmkwh else None,
                road_type,
                drive_id,
            ),
        )
        self._conn.commit()
        self._current_drive_id = None
        self._drive_start_data = None
        logger.info("Drive ended: id=%d distance=%.1fkm", drive_id, distance or 0)

    def _start_charge(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        data = getattr(self, "_latest_data", {})
        drive = data.get("drive_state", {})
        charge = data.get("charge_state", {})

        cursor = self._conn.execute(
            """INSERT INTO charging_sessions (
                car_id, start_time, latitude, longitude,
                start_battery_level
            ) VALUES (?, ?, ?, ?, ?)""",
            (
                self._car_id,
                now,
                drive.get("latitude"),
                drive.get("longitude"),
                charge.get("battery_level"),
            ),
        )
        self._conn.commit()
        self._current_charge_id = cursor.lastrowid
        self._charge_start_data = data
        logger.info("Charge started: id=%d", self._current_charge_id)

    def _end_charge(self) -> None:
        if self._current_charge_id is None:
            return

        session_id = self._current_charge_id
        data = getattr(self, "_latest_data", {})
        charge = data.get("charge_state", {})
        now = datetime.now(timezone.utc).isoformat()

        # Get max charger power from charge records
        row = self._conn.execute(
            "SELECT MAX(charger_power), SUM(1) FROM charges WHERE charging_session_id = ?",
            (session_id,),
        ).fetchone()
        max_power = row[0] if row else None

        start = self._conn.execute(
            "SELECT start_time, start_battery_level FROM charging_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        duration = None
        if start and start["start_time"]:
            try:
                st = datetime.fromisoformat(start["start_time"])
                et = datetime.fromisoformat(now)
                duration = round((et - st).total_seconds() / 60, 1)
            except (ValueError, TypeError):
                pass

        self._conn.execute(
            """UPDATE charging_sessions SET
                end_time = ?, end_battery_level = ?,
                charge_energy_added = ?, max_charger_power = ?,
                duration_min = ?, is_complete = 1
            WHERE id = ?""",
            (
                now,
                charge.get("battery_level"),
                charge.get("charge_energy_added"),
                max_power,
                duration,
                session_id,
            ),
        )
        self._conn.commit()
        self._current_charge_id = None
        self._charge_start_data = None
        logger.info("Charge ended: id=%d", session_id)
