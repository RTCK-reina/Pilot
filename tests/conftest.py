"""Shared pytest fixtures for PiLot tests."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from pilot_common.db import get_connection


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory SQLite database with schema applied."""
    conn = get_connection(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def tmp_secrets_dir(tmp_path: Path) -> Path:
    """Temporary directory for crypto secrets."""
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    return secrets


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Temporary file path for a SQLite database."""
    return tmp_path / "test.db"
