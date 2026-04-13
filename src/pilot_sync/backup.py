"""Local SQLite backup with rotation.

Uses sqlite3.Connection.backup() for a consistent snapshot while the DB may
be under active WAL writes. Keeps a maximum of 7 daily backups; the oldest
file beyond that limit is deleted automatically.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pilot_common.constants import DB_PATH_DEFAULT

logger = logging.getLogger(__name__)

MAX_BACKUPS = 7
BACKUP_SUFFIX = ".bak"


def _backup_dir(db_path: str | Path) -> Path:
    """Return the backup directory next to the database file."""
    return Path(db_path).parent / "backups"


def create_backup(
    conn: sqlite3.Connection,
    db_path: str | Path = DB_PATH_DEFAULT,
    *,
    backup_dir: Path | None = None,
) -> Path:
    """Create a timestamped .bak snapshot of the database.

    Args:
        conn: Open connection to the source database.
        db_path: Path of the source database (used to derive backup dir).
        backup_dir: Override the default backup directory.

    Returns:
        Path to the newly created backup file.
    """
    dest_dir = backup_dir or _backup_dir(db_path)
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    db_name = Path(db_path).stem
    backup_path = dest_dir / f"{db_name}_{timestamp}{BACKUP_SUFFIX}"

    dst = sqlite3.connect(str(backup_path))
    try:
        conn.backup(dst)
        logger.info("Backup created: %s", backup_path)
    finally:
        dst.close()

    return backup_path


def rotate_backups(
    db_path: str | Path = DB_PATH_DEFAULT,
    *,
    backup_dir: Path | None = None,
    max_backups: int = MAX_BACKUPS,
) -> list[Path]:
    """Delete the oldest backups beyond *max_backups*.

    Returns:
        List of deleted file paths.
    """
    dest_dir = backup_dir or _backup_dir(db_path)
    if not dest_dir.exists():
        return []

    backups = sorted(
        dest_dir.glob(f"*{BACKUP_SUFFIX}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    deleted: list[Path] = []
    for old in backups[max_backups:]:
        old.unlink()
        logger.info("Rotated out old backup: %s", old.name)
        deleted.append(old)

    return deleted
