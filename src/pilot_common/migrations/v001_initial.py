"""v001: Initial schema — all 9 tables + indices."""

from __future__ import annotations

import sqlite3

VERSION = 1

_SCHEMA = """
-- settings (must exist first — migration runner uses it)
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- cars
CREATE TABLE IF NOT EXISTS cars (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vin           TEXT NOT NULL UNIQUE,
    model         TEXT,
    trim          TEXT,
    battery_type  TEXT,
    exterior_color TEXT,
    car_version   TEXT,
    efficiency    REAL DEFAULT 0.149,
    usable_battery_capacity_kwh REAL DEFAULT 57.0,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

-- drives
CREATE TABLE IF NOT EXISTS drives (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id                INTEGER NOT NULL REFERENCES cars(id),
    start_time            TEXT NOT NULL,
    end_time              TEXT,
    start_lat             REAL,
    start_lng             REAL,
    end_lat               REAL,
    end_lng               REAL,
    start_address         TEXT,
    end_address           TEXT,
    distance_km           REAL,
    duration_min          REAL,
    start_odometer        REAL,
    end_odometer          REAL,
    start_battery_level   INTEGER,
    end_battery_level     INTEGER,
    start_rated_range_km  REAL,
    end_rated_range_km    REAL,
    outside_temp_avg      REAL,
    speed_max             INTEGER,
    speed_avg             REAL,
    power_max             REAL,
    power_min             REAL,
    total_ascent_m        INTEGER,
    total_descent_m       INTEGER,
    energy_consumed_kwh   REAL,
    energy_regen_kwh      REAL,
    efficiency_whkm       REAL,
    efficiency_kmkwh      REAL,
    road_type             TEXT,
    is_complete           INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_drives_time ON drives(car_id, start_time);

-- positions
CREATE TABLE IF NOT EXISTS positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id          INTEGER NOT NULL REFERENCES cars(id),
    drive_id        INTEGER REFERENCES drives(id),
    timestamp       TEXT NOT NULL,
    latitude        REAL,
    longitude       REAL,
    speed           INTEGER,
    power           REAL,
    odometer        REAL,
    battery_level   INTEGER,
    usable_battery_level INTEGER,
    rated_range_km  REAL,
    est_range_km    REAL,
    elevation       INTEGER,
    heading         INTEGER,
    inside_temp     REAL,
    outside_temp    REAL,
    is_climate_on   INTEGER DEFAULT 0,
    battery_heater  INTEGER DEFAULT 0,
    tpms_fl         REAL,
    tpms_fr         REAL,
    tpms_rl         REAL,
    tpms_rr         REAL,
    fan_status      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_positions_drive ON positions(drive_id);
CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON positions(car_id, timestamp);

-- charging_sessions
CREATE TABLE IF NOT EXISTS charging_sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id                INTEGER NOT NULL REFERENCES cars(id),
    start_time            TEXT NOT NULL,
    end_time              TEXT,
    latitude              REAL,
    longitude             REAL,
    address               TEXT,
    charger_type          TEXT,
    charger_brand         TEXT,
    start_battery_level   INTEGER,
    end_battery_level     INTEGER,
    charge_energy_added   REAL,
    charge_energy_used    REAL,
    max_charger_power     REAL,
    duration_min          REAL,
    outside_temp_avg      REAL,
    cost_jpy              REAL,
    cost_per_kwh          REAL,
    is_complete           INTEGER DEFAULT 0
);

-- charges
CREATE TABLE IF NOT EXISTS charges (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    charging_session_id   INTEGER NOT NULL REFERENCES charging_sessions(id),
    timestamp             TEXT NOT NULL,
    battery_level         INTEGER,
    usable_battery_level  INTEGER,
    charge_energy_added   REAL,
    charger_power         REAL,
    charger_voltage       INTEGER,
    charger_current       INTEGER,
    charger_phases        INTEGER,
    outside_temp          REAL,
    battery_heater        INTEGER DEFAULT 0,
    conn_charge_cable     TEXT,
    fast_charger_type     TEXT
);
CREATE INDEX IF NOT EXISTS idx_charges_session ON charges(charging_session_id);

-- states
CREATE TABLE IF NOT EXISTS states (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id     INTEGER NOT NULL REFERENCES cars(id),
    state      TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT
);

-- software_updates
CREATE TABLE IF NOT EXISTS software_updates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id     INTEGER NOT NULL REFERENCES cars(id),
    version    TEXT NOT NULL,
    timestamp  TEXT NOT NULL
);

-- telemetry_extra (future: Fleet Telemetry fields)
CREATE TABLE IF NOT EXISTS telemetry_extra (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id          INTEGER NOT NULL REFERENCES cars(id),
    timestamp       TEXT NOT NULL,
    field_name      TEXT NOT NULL,
    field_value     REAL
);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_extra(car_id, timestamp, field_name);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
