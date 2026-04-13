"""Individual health-check functions for PiLot services.

Each check returns a :class:`CheckResult` indicating pass, warn, or critical
status together with a human-readable message.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from urllib.error import URLError

from pilot_common.config import get_setting
from pilot_common.constants import DB_PATH_DEFAULT

logger = logging.getLogger(__name__)

POLLER_SERVICE = "tesla-poller"
DASHBOARD_URL = "http://localhost:80"
STORAGE_PATH = Path("/var/lib/pilot")
STORAGE_WARN_PCT = 10
STORAGE_CRITICAL_PCT = 5
POLLER_STALE_SECONDS = 5 * 60  # 5 minutes
TOKEN_EXPIRY_WARN_DAYS = 7


class Status(str, Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class CheckResult:
    name: str
    status: Status
    message: str


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_poller(conn: sqlite3.Connection) -> CheckResult:
    """Verify the tesla-poller service is active and writing to the DB.

    Checks:
        1. ``systemctl is-active tesla-poller`` returns ``active``.
        2. The most recent ``positions`` row was written within 5 minutes.
    """
    name = "poller"

    # Service active?
    try:
        result = subprocess.run(
            ["systemctl", "is-active", POLLER_SERVICE],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip() != "active":
            return CheckResult(name, Status.CRITICAL, f"{POLLER_SERVICE} is not active")
    except (subprocess.SubprocessError, FileNotFoundError):
        return CheckResult(name, Status.CRITICAL, f"Cannot query {POLLER_SERVICE} status")

    # Recent DB write?
    row = conn.execute(
        "SELECT (julianday('now') - julianday(MAX(timestamp))) * 86400 AS age_seconds "
        "FROM positions"
    ).fetchone()

    if row is None or row[0] is None:
        return CheckResult(name, Status.WARN, "No position data in DB yet")

    age = row[0]
    if age > POLLER_STALE_SECONDS:
        return CheckResult(
            name,
            Status.CRITICAL,
            f"Last DB write {age:.0f}s ago (threshold {POLLER_STALE_SECONDS}s)",
        )

    return CheckResult(name, Status.OK, "Poller active and writing")


def check_dashboard() -> CheckResult:
    """HTTP GET localhost:80 and expect a 200 response."""
    name = "dashboard"
    try:
        resp = urlopen(DASHBOARD_URL, timeout=10)  # noqa: S310
        if resp.status == 200:
            return CheckResult(name, Status.OK, "Dashboard responding")
        return CheckResult(name, Status.WARN, f"Dashboard returned HTTP {resp.status}")
    except (URLError, OSError) as exc:
        return CheckResult(name, Status.CRITICAL, f"Dashboard unreachable: {exc}")


def check_db_integrity(conn: sqlite3.Connection) -> CheckResult:
    """Run ``PRAGMA integrity_check`` (intended for daily execution only).

    This is expensive on large databases; the caller should gate invocation
    to once per day.
    """
    name = "db_integrity"
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row and row[0] == "ok":
            return CheckResult(name, Status.OK, "Database integrity OK")
        detail = row[0] if row else "unknown"
        return CheckResult(name, Status.CRITICAL, f"Integrity check failed: {detail}")
    except sqlite3.DatabaseError as exc:
        return CheckResult(name, Status.CRITICAL, f"Integrity check error: {exc}")


def check_storage(path: Path = STORAGE_PATH) -> CheckResult:
    """Check free disk space on the partition containing *path*.

    Warns if free space drops below 10 %, critical below 5 %.
    """
    name = "storage"
    try:
        usage = shutil.disk_usage(str(path))
    except OSError as exc:
        return CheckResult(name, Status.CRITICAL, f"Cannot stat {path}: {exc}")

    free_pct = (usage.free / usage.total) * 100

    if free_pct < STORAGE_CRITICAL_PCT:
        return CheckResult(
            name,
            Status.CRITICAL,
            f"Disk free {free_pct:.1f}% (critical threshold {STORAGE_CRITICAL_PCT}%)",
        )
    if free_pct < STORAGE_WARN_PCT:
        return CheckResult(
            name,
            Status.WARN,
            f"Disk free {free_pct:.1f}% (warn threshold {STORAGE_WARN_PCT}%)",
        )
    return CheckResult(name, Status.OK, f"Disk free {free_pct:.1f}%")


def check_token_expiry(conn: sqlite3.Connection) -> CheckResult:
    """Warn if the Tesla refresh token expires within 7 days.

    Reads ``tesla_token_expires_at`` from settings (epoch timestamp).
    """
    name = "token_expiry"

    expires_str = get_setting(conn, "tesla_token_expires_at")
    if expires_str is None:
        return CheckResult(name, Status.WARN, "Token expiry metadata not found")

    try:
        expires_at = float(expires_str)
    except (ValueError, TypeError):
        return CheckResult(name, Status.WARN, "Invalid token expiry value")

    remaining = expires_at - time.time()
    remaining_days = remaining / 86400

    if remaining_days <= 0:
        return CheckResult(name, Status.CRITICAL, "Refresh token has expired")
    if remaining_days < TOKEN_EXPIRY_WARN_DAYS:
        return CheckResult(
            name,
            Status.WARN,
            f"Refresh token expires in {remaining_days:.1f} days",
        )
    return CheckResult(name, Status.OK, f"Token valid for {remaining_days:.0f} days")
