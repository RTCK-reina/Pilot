"""Tests for pilot_sync backup creation, rotation, and file integrity."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from pilot_sync.backup import MAX_BACKUPS, create_backup, rotate_backups


class TestCreateBackup:
    def test_creates_backup_file(self, db: sqlite3.Connection, tmp_path: Path):
        backup = create_backup(db, db_path=":memory:", backup_dir=tmp_path)
        assert backup.exists()
        assert backup.suffix == ".bak"

    def test_backup_is_valid_sqlite(self, db: sqlite3.Connection, tmp_path: Path):
        """The backup file must be a readable SQLite database."""
        backup = create_backup(db, db_path=":memory:", backup_dir=tmp_path)

        conn = sqlite3.connect(str(backup))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            assert row[0] == "ok"
        finally:
            conn.close()

    def test_backup_contains_data(self, db: sqlite3.Connection, tmp_path: Path):
        """Data written before backup should be present in the snapshot."""
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("test_key", "test_value"),
        )
        db.commit()

        backup = create_backup(db, db_path=":memory:", backup_dir=tmp_path)

        conn = sqlite3.connect(str(backup))
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", ("test_key",)
            ).fetchone()
            assert row is not None
            assert row[0] == "test_value"
        finally:
            conn.close()

    def test_multiple_backups_have_distinct_names(
        self, db: sqlite3.Connection, tmp_path: Path
    ):
        b1 = create_backup(db, db_path=":memory:", backup_dir=tmp_path)
        # Ensure different timestamp (subsecond resolution in filename)
        time.sleep(1.1)
        b2 = create_backup(db, db_path=":memory:", backup_dir=tmp_path)
        assert b1.name != b2.name


class TestRotateBackups:
    def _make_fake_backups(self, directory: Path, count: int) -> list[Path]:
        """Create *count* fake .bak files with incrementing mtimes."""
        files: list[Path] = []
        for i in range(count):
            p = directory / f"pilot_2025010{i}T000000Z.bak"
            p.write_bytes(b"fake")
            files.append(p)
        return files

    def test_no_rotation_under_limit(self, tmp_path: Path):
        self._make_fake_backups(tmp_path, MAX_BACKUPS)
        deleted = rotate_backups(db_path="/dummy/pilot.db", backup_dir=tmp_path)
        assert deleted == []
        assert len(list(tmp_path.glob("*.bak"))) == MAX_BACKUPS

    def test_rotation_removes_oldest(self, tmp_path: Path):
        files = self._make_fake_backups(tmp_path, MAX_BACKUPS + 3)
        deleted = rotate_backups(db_path="/dummy/pilot.db", backup_dir=tmp_path)
        assert len(deleted) == 3
        remaining = list(tmp_path.glob("*.bak"))
        assert len(remaining) == MAX_BACKUPS

    def test_rotation_with_empty_dir(self, tmp_path: Path):
        deleted = rotate_backups(db_path="/dummy/pilot.db", backup_dir=tmp_path)
        assert deleted == []

    def test_rotation_with_nonexistent_dir(self, tmp_path: Path):
        deleted = rotate_backups(
            db_path="/dummy/pilot.db",
            backup_dir=tmp_path / "nonexistent",
        )
        assert deleted == []

    def test_keeps_exactly_max(self, tmp_path: Path):
        """After rotation, exactly MAX_BACKUPS files should remain."""
        self._make_fake_backups(tmp_path, 15)
        rotate_backups(db_path="/dummy/pilot.db", backup_dir=tmp_path)
        remaining = list(tmp_path.glob("*.bak"))
        assert len(remaining) == MAX_BACKUPS
