"""Tests for database connection, PRAGMA settings, and schema migration."""

from __future__ import annotations

import sqlite3

import pytest

from pilot_common.db import get_connection, open_db


class TestConnection:
    def test_in_memory_connection(self):
        conn = get_connection(":memory:")
        assert conn is not None
        conn.close()

    def test_row_factory_is_row(self):
        conn = get_connection(":memory:")
        row = conn.execute("SELECT 1 AS val").fetchone()
        assert row["val"] == 1
        conn.close()

    def test_file_connection(self, tmp_db_path):
        conn = get_connection(tmp_db_path)
        assert tmp_db_path.exists()
        conn.close()

    def test_context_manager(self):
        with open_db(":memory:") as conn:
            row = conn.execute("SELECT 1 AS val").fetchone()
            assert row["val"] == 1


class TestPragmas:
    def test_wal_mode(self, tmp_db_path):
        """WAL mode only applies to file-backed databases (not :memory:)."""
        conn = get_connection(tmp_db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_synchronous_normal(self, db):
        val = db.execute("PRAGMA synchronous").fetchone()[0]
        assert val == 1  # NORMAL = 1

    def test_foreign_keys_enabled(self, db):
        val = db.execute("PRAGMA foreign_keys").fetchone()[0]
        assert val == 1

    def test_busy_timeout(self, db):
        val = db.execute("PRAGMA busy_timeout").fetchone()[0]
        assert val == 5000

    def test_custom_cache_size(self):
        conn = get_connection(":memory:", cache_size=-2000)
        val = conn.execute("PRAGMA cache_size").fetchone()[0]
        assert val == -2000
        conn.close()


class TestMigrations:
    def test_schema_version_set(self, db):
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == 1

    def test_all_tables_created(self, db):
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected = {
            "settings",
            "cars",
            "positions",
            "drives",
            "charging_sessions",
            "charges",
            "states",
            "software_updates",
            "telemetry_extra",
        }
        assert expected.issubset(tables)

    def test_indices_created(self, db):
        indices = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        expected = {
            "idx_positions_drive",
            "idx_positions_timestamp",
            "idx_drives_time",
            "idx_charges_session",
            "idx_telemetry_ts",
        }
        assert expected.issubset(indices)

    def test_migration_idempotent(self, db):
        """Running migrations again should not fail or duplicate."""
        from pilot_common.migrations import run_migrations

        v = run_migrations(db)
        assert v == 1

    def test_cars_insert(self, db):
        db.execute(
            "INSERT INTO cars (vin, model, efficiency) VALUES (?, ?, ?)",
            ("5YJ3E1EA0PF000001", "Model Y", 0.149),
        )
        db.commit()
        row = db.execute("SELECT vin FROM cars").fetchone()
        assert row["vin"] == "5YJ3E1EA0PF000001"

    def test_foreign_key_constraint(self, db):
        """positions.car_id must reference a valid cars.id."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO positions (car_id, timestamp) VALUES (999, '2026-01-01T00:00:00')"
            )
            db.commit()
