"""Settings read/write backed by the `settings` SQLite table.

Includes a simple in-memory cache with TTL to avoid repeated queries for
hot paths (e.g., efficiency unit on every page render).
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

_CACHE_TTL_SECONDS = 30.0
_cache: dict[str, tuple[str, float]] = {}  # key -> (value, expiry)


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    """Read a setting value. Returns *default* if not found."""
    now = time.monotonic()
    if key in _cache:
        value, expiry = _cache[key]
        if now < expiry:
            return value

    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    _cache[key] = (row[0], now + _CACHE_TTL_SECONDS)
    return row[0]


def get_setting_json(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    """Read a JSON-encoded setting value."""
    raw = get_setting(conn, key)
    if raw is None:
        return default
    return json.loads(raw)


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Write a setting value (insert or update)."""
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    _cache[key] = (value, time.monotonic() + _CACHE_TTL_SECONDS)


def set_setting_json(conn: sqlite3.Connection, key: str, value: Any) -> None:
    """Write a JSON-encoded setting value."""
    set_setting(conn, key, json.dumps(value, ensure_ascii=False))


def delete_setting(conn: sqlite3.Connection, key: str) -> None:
    """Remove a setting."""
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    _cache.pop(key, None)


def invalidate_cache(key: str | None = None) -> None:
    """Clear the in-memory cache. If key is None, clear all."""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(key, None)


def get_all_settings(conn: sqlite3.Connection) -> dict[str, str]:
    """Return all settings as a dict."""
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r[0]: r[1] for r in rows}
