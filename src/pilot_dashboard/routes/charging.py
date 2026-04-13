"""Charging sessions route."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _fetch_charging_data(db: sqlite3.Connection) -> dict:
    """Query charging stats and paginated session list from SQLite."""
    # Summary stats
    stats = db.execute(
        """
        SELECT
            COUNT(*)                                AS session_count,
            COALESCE(SUM(charge_energy_added), 0)   AS total_kwh,
            COALESCE(SUM(cost_jpy), 0)              AS total_cost
        FROM charging_sessions
        WHERE is_complete = 1
        """
    ).fetchone()

    # Paginated session list (most recent 20)
    rows = db.execute(
        """
        SELECT
            id, start_time, end_time, charger_type, charger_brand,
            start_battery_level, end_battery_level,
            charge_energy_added, max_charger_power, duration_min,
            cost_jpy, cost_per_kwh, address
        FROM charging_sessions
        WHERE is_complete = 1
        ORDER BY start_time DESC
        LIMIT 20
        """
    ).fetchall()

    sessions = []
    for r in rows:
        sessions.append(dict(r))

    # Chart: energy added over time (monthly)
    energy_trend = db.execute("""
        SELECT strftime('%Y-%m', start_time) AS month,
               SUM(charge_energy_added) AS kwh
        FROM charging_sessions WHERE is_complete = 1
        GROUP BY month ORDER BY month
    """).fetchall()

    # Chart: cost breakdown by charger type
    cost_breakdown = db.execute("""
        SELECT charger_type,
               SUM(cost_jpy) AS cost,
               SUM(charge_energy_added) AS kwh
        FROM charging_sessions WHERE is_complete = 1
        GROUP BY charger_type
    """).fetchall()

    return {
        "session_count": stats["session_count"] or 0,
        "total_kwh": stats["total_kwh"] or 0,
        "total_cost": stats["total_cost"] or 0,
        "sessions": sessions,
        "energy_trend": [dict(r) for r in energy_trend],
        "cost_breakdown": [dict(r) for r in cost_breakdown],
    }


@router.get("/charging")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page charging dashboard."""
    templates = request.app.state.templates
    data = _fetch_charging_data(db)
    return templates.TemplateResponse(
        request=request,
        name="charging.html",
        context={"active": "charging", **data},
    )


@router.get("/fragment/charging")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for charging content."""
    templates = request.app.state.templates
    data = _fetch_charging_data(db)
    return templates.TemplateResponse(
        request=request,
        name="charging.html",
        context={"active": "charging", "fragment": True, **data},
    )
