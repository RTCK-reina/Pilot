"""SQLite connection management with PRAGMA tuning and migration support."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from pilot_common.constants import (
    CACHE_SIZE_LOW,
    CACHE_SIZE_NORMAL,
    DB_PATH_DEFAULT,
    LOW_MEMORY_THRESHOLD_BYTES,
)
from pilot_common.migrations import run_migrations


def _detect_cache_size() -> int:
    """Return SQLite cache_size based on available system memory."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    if kb * 1024 < LOW_MEMORY_THRESHOLD_BYTES:
                        return CACHE_SIZE_LOW
                    return CACHE_SIZE_NORMAL
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return CACHE_SIZE_NORMAL


def _apply_pragmas(conn: sqlite3.Connection, cache_size: int | None = None) -> None:
    """Apply performance and safety PRAGMAs."""
    cs = cache_size if cache_size is not None else _detect_cache_size()
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(f"PRAGMA cache_size = {cs}")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL")


def get_connection(
    db_path: str | Path = DB_PATH_DEFAULT,
    *,
    cache_size: int | None = None,
    run_migrations_on_connect: bool = True,
) -> sqlite3.Connection:
    """Open a SQLite connection with PiLot PRAGMAs applied.

    Args:
        db_path: Path to the database file. Use ":memory:" for testing.
        cache_size: Override auto-detected cache size. Negative = KiB.
        run_migrations_on_connect: Apply pending schema migrations.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn, cache_size)

    if run_migrations_on_connect:
        run_migrations(conn)

    return conn


@contextmanager
def open_db(
    db_path: str | Path = DB_PATH_DEFAULT,
    *,
    cache_size: int | None = None,
    run_migrations_on_connect: bool = True,
) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for a PiLot SQLite connection."""
    conn = get_connection(
        db_path,
        cache_size=cache_size,
        run_migrations_on_connect=run_migrations_on_connect,
    )
    try:
        yield conn
    finally:
        conn.close()
