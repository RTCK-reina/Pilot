"""Database migration runner.

Tracks schema version in the `settings` table and applies migrations in order.
"""

from __future__ import annotations

import importlib
import sqlite3
from typing import Protocol


class Migration(Protocol):
    VERSION: int

    def up(self, conn: sqlite3.Connection) -> None: ...


_MIGRATION_MODULES = [
    "pilot_common.migrations.v001_initial",
]


def get_current_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'schema_version'"
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending migrations. Returns the final schema version."""
    current = get_current_version(conn)

    for module_path in _MIGRATION_MODULES:
        mod = importlib.import_module(module_path)
        if mod.VERSION <= current:
            continue
        mod.up(conn)
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
            (str(mod.VERSION),),
        )
        conn.commit()
        current = mod.VERSION

    return current
