"""Tests for pilot_watchdog health checks and recovery rate limiting."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from pilot_watchdog.checks import (
    CheckResult,
    Status,
    check_db_integrity,
    check_poller,
    check_storage,
    check_token_expiry,
)
from pilot_watchdog.recovery import (
    MAX_RESTARTS_PER_HOUR,
    _restart_history,
    is_rate_limited,
    reset_rate_limits,
    restart_service,
)


# ---------------------------------------------------------------------------
# check_poller
# ---------------------------------------------------------------------------


class TestCheckPoller:
    def _insert_position(self, db: sqlite3.Connection, iso_timestamp: str) -> None:
        """Helper: insert a car and a position row at the given ISO timestamp."""
        db.execute("INSERT OR IGNORE INTO cars (id, vin) VALUES (1, 'TESTVIN')")
        db.execute(
            "INSERT INTO positions (car_id, timestamp, latitude, longitude) "
            "VALUES (1, ?, 0.0, 0.0)",
            (iso_timestamp,),
        )
        db.commit()

    @patch("pilot_watchdog.checks.subprocess.run")
    def test_poller_ok(self, mock_run, db: sqlite3.Connection):
        """Active service + recent DB write -> OK."""
        mock_run.return_value = type(
            "Result", (), {"stdout": "active\n", "returncode": 0}
        )()
        from datetime import datetime, timezone
        self._insert_position(db, datetime.now(timezone.utc).isoformat())
        result = check_poller(db)
        assert result.status == Status.OK

    @patch("pilot_watchdog.checks.subprocess.run")
    def test_poller_service_inactive(self, mock_run, db: sqlite3.Connection):
        """Inactive service -> CRITICAL."""
        mock_run.return_value = type(
            "Result", (), {"stdout": "inactive\n", "returncode": 3}
        )()
        result = check_poller(db)
        assert result.status == Status.CRITICAL

    @patch("pilot_watchdog.checks.subprocess.run")
    def test_poller_stale_data(self, mock_run, db: sqlite3.Connection):
        """Active service but stale DB write -> CRITICAL."""
        mock_run.return_value = type(
            "Result", (), {"stdout": "active\n", "returncode": 0}
        )()
        # Position from 10 minutes ago (exceeds 5-minute threshold)
        self._insert_position(db, "2020-01-01T00:00:00+00:00")
        result = check_poller(db)
        assert result.status == Status.CRITICAL

    @patch("pilot_watchdog.checks.subprocess.run")
    def test_poller_no_data(self, mock_run, db: sqlite3.Connection):
        """Active service but no data at all -> WARN."""
        mock_run.return_value = type(
            "Result", (), {"stdout": "active\n", "returncode": 0}
        )()
        result = check_poller(db)
        assert result.status == Status.WARN


# ---------------------------------------------------------------------------
# check_storage
# ---------------------------------------------------------------------------


class TestCheckStorage:
    def test_storage_ok(self, tmp_path: Path):
        """A freshly created tmp dir should have plenty of free space."""
        result = check_storage(path=tmp_path)
        assert result.status == Status.OK

    def test_storage_nonexistent_path(self):
        """Non-existent path -> CRITICAL."""
        result = check_storage(path=Path("/nonexistent/pilot/data"))
        assert result.status == Status.CRITICAL


# ---------------------------------------------------------------------------
# check_db_integrity
# ---------------------------------------------------------------------------


class TestCheckDbIntegrity:
    def test_integrity_ok(self, db: sqlite3.Connection):
        result = check_db_integrity(db)
        assert result.status == Status.OK


# ---------------------------------------------------------------------------
# check_token_expiry
# ---------------------------------------------------------------------------


class TestCheckTokenExpiry:
    def setup_method(self):
        from pilot_common.config import invalidate_cache
        invalidate_cache()

    def test_missing_metadata(self, db: sqlite3.Connection):
        """No expiry metadata -> WARN."""
        result = check_token_expiry(db)
        assert result.status == Status.WARN

    def test_token_valid(self, db: sqlite3.Connection):
        """Token with plenty of time remaining -> OK."""
        from pilot_common.config import invalidate_cache, set_setting
        set_setting(db, "tesla_token_expires_at", str(time.time() + 86400 * 30))
        invalidate_cache()
        result = check_token_expiry(db)
        assert result.status == Status.OK

    def test_token_expiring_soon(self, db: sqlite3.Connection):
        """Token expiring within 7 days -> WARN."""
        from pilot_common.config import invalidate_cache, set_setting
        set_setting(db, "tesla_token_expires_at", str(time.time() + 86400 * 3))
        invalidate_cache()
        result = check_token_expiry(db)
        assert result.status == Status.WARN

    def test_token_expired(self, db: sqlite3.Connection):
        """Already-expired token -> CRITICAL."""
        from pilot_common.config import invalidate_cache, set_setting
        set_setting(db, "tesla_token_expires_at", str(time.time() - 86400))
        invalidate_cache()
        result = check_token_expiry(db)
        assert result.status == Status.CRITICAL


# ---------------------------------------------------------------------------
# Recovery rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def setup_method(self):
        reset_rate_limits()

    def test_not_rate_limited_initially(self):
        assert is_rate_limited("tesla-poller") is False

    def test_rate_limited_after_max(self):
        now = time.monotonic()
        for _ in range(MAX_RESTARTS_PER_HOUR):
            _restart_history["tesla-poller"].append(now)
        assert is_rate_limited("tesla-poller", now=now) is True

    def test_rate_limit_per_service(self):
        """Rate limits are tracked independently per service."""
        now = time.monotonic()
        for _ in range(MAX_RESTARTS_PER_HOUR):
            _restart_history["tesla-poller"].append(now)
        assert is_rate_limited("tesla-poller", now=now) is True
        assert is_rate_limited("pilot-dashboard", now=now) is False

    def test_rate_limit_expires(self):
        """Entries older than 1 hour are pruned, allowing new restarts."""
        old_time = time.monotonic() - 7200  # 2 hours ago
        for _ in range(MAX_RESTARTS_PER_HOUR):
            _restart_history["tesla-poller"].append(old_time)

        now = time.monotonic()
        assert is_rate_limited("tesla-poller", now=now) is False

    @patch("pilot_watchdog.recovery.subprocess.run")
    def test_restart_service_records_history(self, mock_run):
        mock_run.return_value = type("Result", (), {"returncode": 0})()
        result = restart_service("tesla-poller")
        assert result is True
        assert len(_restart_history["tesla-poller"]) == 1

    @patch("pilot_watchdog.recovery.subprocess.run")
    def test_restart_blocked_when_rate_limited(self, mock_run):
        """restart_service returns False when rate-limited."""
        now = time.monotonic()
        for _ in range(MAX_RESTARTS_PER_HOUR):
            _restart_history["tesla-poller"].append(now)
        result = restart_service("tesla-poller")
        assert result is False
        mock_run.assert_not_called()
