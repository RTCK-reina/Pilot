"""Settings route."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _fetch_settings(db: sqlite3.Connection) -> dict:
    """Query all settings from SQLite."""
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    settings = {}
    for r in rows:
        settings[r["key"]] = r["value"]
    return settings


@router.get("/settings")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page settings."""
    templates = request.app.state.templates
    settings = _fetch_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"active": "settings", "settings": settings},
    )


@router.get("/fragment/settings")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for settings content."""
    templates = request.app.state.templates
    settings = _fetch_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"active": "settings", "fragment": True, "settings": settings},
    )
