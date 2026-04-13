"""Drive history route."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _fetch_drives_data(db: sqlite3.Connection) -> dict:
    """Query drive stats and paginated drive list from SQLite."""
    # Summary stats
    stats = db.execute(
        """
        SELECT
            COUNT(*)                          AS drive_count,
            COALESCE(SUM(distance_km), 0)     AS total_km,
            COALESCE(AVG(distance_km), 0)     AS avg_km,
            COALESCE(SUM(duration_min), 0)     AS total_min
        FROM drives
        WHERE is_complete = 1
        """
    ).fetchone()

    # Paginated drive list (most recent 20)
    rows = db.execute(
        """
        SELECT
            id, start_time, end_time, distance_km, duration_min,
            efficiency_kmkwh, start_battery_level, end_battery_level,
            speed_max, road_type, start_address, end_address,
            energy_consumed_kwh, energy_regen_kwh, speed_avg
        FROM drives
        WHERE is_complete = 1
        ORDER BY start_time DESC
        LIMIT 20
        """
    ).fetchall()

    drives = []
    for r in rows:
        drives.append(dict(r))

    # Format total time as Xh Ym
    total_min = stats["total_min"] or 0
    hours = int(total_min // 60)
    mins = int(total_min % 60)
    total_time_str = f"{hours}h {mins}m" if hours else f"{mins}m"

    return {
        "drive_count": stats["drive_count"] or 0,
        "total_km": stats["total_km"] or 0,
        "avg_km": stats["avg_km"] or 0,
        "total_time": total_time_str,
        "drives": drives,
    }


@router.get("/drives")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page drives list."""
    templates = request.app.state.templates
    data = _fetch_drives_data(db)
    return templates.TemplateResponse(
        request=request,
        name="drives.html",
        context={"active": "drives", **data},
    )


@router.get("/fragment/drives")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for drives content."""
    templates = request.app.state.templates
    data = _fetch_drives_data(db)
    return templates.TemplateResponse(
        request=request,
        name="drives.html",
        context={"active": "drives", "fragment": True, **data},
    )
