"""Battery health route."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _fetch_battery_data(db: sqlite3.Connection) -> dict:
    """Query battery health data from SQLite."""
    # Latest battery level and range from positions
    latest = db.execute(
        """
        SELECT battery_level, rated_range_km, est_range_km, odometer
        FROM positions
        ORDER BY timestamp DESC
        LIMIT 1
        """
    ).fetchone()

    current_soc = latest["battery_level"] if latest else None
    current_range = latest["rated_range_km"] if latest else None
    if current_range is None and latest:
        current_range = latest["est_range_km"]

    # Car capacity info
    car = db.execute(
        """
        SELECT model, trim, battery_type, usable_battery_capacity_kwh
        FROM cars
        LIMIT 1
        """
    ).fetchone()

    capacity_kwh = car["usable_battery_capacity_kwh"] if car else 57.0
    battery_type = car["battery_type"] if car else None
    is_lfp = battery_type and "lfp" in battery_type.lower() if battery_type else False

    # Estimated cycles: total energy consumed / capacity
    energy_row = db.execute(
        """
        SELECT COALESCE(SUM(energy_consumed_kwh), 0) AS total_energy
        FROM drives
        WHERE is_complete = 1
        """
    ).fetchone()

    total_energy = energy_row["total_energy"] or 0
    est_cycles = total_energy / capacity_kwh if capacity_kwh > 0 else 0

    # Full-charge range estimate (100% range = current_range / (soc/100))
    full_range = None
    if current_soc and current_soc > 0 and current_range:
        full_range = current_range / (current_soc / 100.0)

    # Degradation over time: max range when SOC >= 95%
    degradation = db.execute("""
        SELECT date(timestamp) AS date, MAX(rated_range_km) AS max_range
        FROM positions
        WHERE battery_level >= 95 AND rated_range_km IS NOT NULL
        GROUP BY date ORDER BY date LIMIT 365
    """).fetchall()

    # SOC distribution: how often at each SOC band
    soc_dist = db.execute("""
        SELECT (battery_level / 10) * 10 AS soc_band, COUNT(*) AS count
        FROM positions WHERE battery_level IS NOT NULL
        GROUP BY soc_band ORDER BY soc_band
    """).fetchall()

    return {
        "current_soc": current_soc,
        "current_range": current_range,
        "full_range": full_range,
        "est_cycles": est_cycles,
        "capacity_kwh": capacity_kwh,
        "battery_type": battery_type,
        "is_lfp": is_lfp,
        "total_energy": total_energy,
        "degradation": [dict(r) for r in degradation],
        "soc_distribution": [dict(r) for r in soc_dist],
    }


@router.get("/battery")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page battery health dashboard."""
    templates = request.app.state.templates
    data = _fetch_battery_data(db)
    return templates.TemplateResponse(
        request=request,
        name="battery.html",
        context={"active": "battery", **data},
    )


@router.get("/fragment/battery")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for battery content."""
    templates = request.app.state.templates
    data = _fetch_battery_data(db)
    return templates.TemplateResponse(
        request=request,
        name="battery.html",
        context={"active": "battery", "fragment": True, **data},
    )
