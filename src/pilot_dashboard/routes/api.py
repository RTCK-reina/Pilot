"""JSON API endpoints for the dashboard frontend."""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from pilot_common.config import get_all_settings, get_setting, set_setting
from pilot_dashboard.app import get_db

router = APIRouter(prefix="/api")


@router.get("/car")
def api_car(request: Request, db=Depends(get_db)) -> dict:
    row = db.execute("SELECT * FROM cars LIMIT 1").fetchone()
    if not row:
        return {"car": None}
    return {"car": dict(row)}


@router.get("/status")
def api_status(request: Request, db=Depends(get_db)) -> dict:
    state = db.execute(
        "SELECT * FROM states ORDER BY id DESC LIMIT 1"
    ).fetchone()
    pos = db.execute(
        "SELECT * FROM positions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return {
        "state": dict(state) if state else None,
        "last_position": dict(pos) if pos else None,
    }


@router.get("/drives")
def api_drives(
    request: Request,
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    offset = (page - 1) * per_page
    total = db.execute("SELECT COUNT(*) FROM drives WHERE is_complete = 1").fetchone()[0]
    rows = db.execute(
        "SELECT * FROM drives WHERE is_complete = 1 ORDER BY start_time DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()
    return {
        "drives": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total else 0,
    }


@router.get("/drives/{drive_id}")
def api_drive_detail(drive_id: int, request: Request, db=Depends(get_db)) -> dict:
    row = db.execute("SELECT * FROM drives WHERE id = ?", (drive_id,)).fetchone()
    if not row:
        return {"drive": None}
    return {"drive": dict(row)}


@router.get("/drives/{drive_id}/positions")
def api_drive_positions(
    drive_id: int,
    request: Request,
    db=Depends(get_db),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    rows = db.execute(
        "SELECT * FROM positions WHERE drive_id = ? ORDER BY timestamp LIMIT ?",
        (drive_id, limit),
    ).fetchall()
    return {"positions": [dict(r) for r in rows]}


@router.get("/charging")
def api_charging(
    request: Request,
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    offset = (page - 1) * per_page
    total = db.execute("SELECT COUNT(*) FROM charging_sessions WHERE is_complete = 1").fetchone()[0]
    rows = db.execute(
        "SELECT * FROM charging_sessions WHERE is_complete = 1 ORDER BY start_time DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()
    return {
        "sessions": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if total else 0,
    }


@router.get("/charging/{session_id}")
def api_charging_detail(session_id: int, request: Request, db=Depends(get_db)) -> dict:
    session = db.execute(
        "SELECT * FROM charging_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    charges = db.execute(
        "SELECT * FROM charges WHERE charging_session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return {
        "session": dict(session) if session else None,
        "charges": [dict(r) for r in charges],
    }


@router.get("/efficiency/summary")
def api_efficiency_summary(
    request: Request,
    db=Depends(get_db),
    period: str = Query("all", pattern="^(today|week|month|all)$"),
) -> dict:
    conditions = {
        "today": "AND date(start_time) = date('now')",
        "week": "AND start_time >= datetime('now', '-7 days')",
        "month": "AND start_time >= datetime('now', '-30 days')",
        "all": "",
    }
    where = conditions.get(period, "")
    row = db.execute(f"""
        SELECT
            COUNT(*) as drive_count,
            COALESCE(SUM(distance_km), 0) as total_distance_km,
            COALESCE(SUM(energy_consumed_kwh), 0) as total_energy_kwh,
            COALESCE(AVG(efficiency_kmkwh), 0) as avg_kmkwh,
            COALESCE(AVG(efficiency_whkm), 0) as avg_whkm
        FROM drives
        WHERE is_complete = 1 {where}
    """).fetchone()
    return {"summary": dict(row)}


@router.get("/efficiency/trend")
def api_efficiency_trend(
    request: Request,
    db=Depends(get_db),
    interval: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    limit: int = Query(500, ge=1, le=1000),
) -> dict:
    fmt = {"daily": "%Y-%m-%d", "weekly": "%Y-W%W", "monthly": "%Y-%m"}
    strftime = fmt[interval]
    rows = db.execute(f"""
        SELECT
            strftime('{strftime}', start_time) as period,
            AVG(efficiency_kmkwh) as avg_kmkwh,
            AVG(efficiency_whkm) as avg_whkm,
            AVG(outside_temp_avg) as avg_temp,
            SUM(distance_km) as distance_km,
            COUNT(*) as drive_count
        FROM drives
        WHERE is_complete = 1
        GROUP BY period
        ORDER BY period DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return {"trend": [dict(r) for r in reversed(rows)]}


@router.get("/efficiency/speed-bands")
def api_speed_bands(request: Request, db=Depends(get_db)) -> dict:
    rows = db.execute("""
        SELECT
            (speed / 10) * 10 as speed_band,
            AVG(power) as avg_power_kw,
            COUNT(*) as sample_count
        FROM positions
        WHERE speed IS NOT NULL AND speed > 0 AND power IS NOT NULL
        GROUP BY speed_band
        ORDER BY speed_band
    """).fetchall()
    return {"speed_bands": [dict(r) for r in rows]}


@router.get("/efficiency/temp-scatter")
def api_temp_scatter(
    request: Request,
    db=Depends(get_db),
    limit: int = Query(500, ge=1, le=1000),
) -> dict:
    rows = db.execute("""
        SELECT outside_temp_avg as temp, efficiency_whkm as whkm
        FROM drives
        WHERE is_complete = 1 AND outside_temp_avg IS NOT NULL AND efficiency_whkm IS NOT NULL
        ORDER BY start_time DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return {"data": [dict(r) for r in rows]}


@router.get("/efficiency/road-type")
def api_road_type(request: Request, db=Depends(get_db)) -> dict:
    rows = db.execute("""
        SELECT
            road_type,
            AVG(efficiency_whkm) as avg_whkm,
            AVG(efficiency_kmkwh) as avg_kmkwh,
            COUNT(*) as drive_count,
            SUM(distance_km) as total_km
        FROM drives
        WHERE is_complete = 1 AND road_type IS NOT NULL
        GROUP BY road_type
    """).fetchall()
    return {"road_types": [dict(r) for r in rows]}


@router.get("/efficiency/cost")
def api_cost(
    request: Request,
    db=Depends(get_db),
    interval: str = Query("monthly", pattern="^(daily|weekly|monthly)$"),
) -> dict:
    fmt = {"daily": "%Y-%m-%d", "weekly": "%Y-W%W", "monthly": "%Y-%m"}
    strftime = fmt[interval]
    rows = db.execute(f"""
        SELECT
            strftime('{strftime}', start_time) as period,
            COALESCE(SUM(cost_jpy), 0) as total_cost_jpy,
            COALESCE(SUM(charge_energy_added), 0) as total_kwh,
            COUNT(*) as session_count
        FROM charging_sessions
        WHERE is_complete = 1
        GROUP BY period
        ORDER BY period DESC
        LIMIT 24
    """).fetchall()
    return {"cost": [dict(r) for r in reversed(rows)]}


@router.get("/battery/health")
def api_battery_health(request: Request, db=Depends(get_db)) -> dict:
    rows = db.execute("""
        SELECT date(timestamp) as date, MAX(rated_range_km) as max_range_km
        FROM positions
        WHERE battery_level >= 95 AND rated_range_km IS NOT NULL
        GROUP BY date
        ORDER BY date
        LIMIT 365
    """).fetchall()
    return {"health": [dict(r) for r in rows]}


@router.get("/battery/cycles")
def api_battery_cycles(request: Request, db=Depends(get_db)) -> dict:
    row = db.execute("""
        SELECT COALESCE(SUM(energy_consumed_kwh), 0) as total_energy_kwh
        FROM drives WHERE is_complete = 1
    """).fetchone()
    car = db.execute("SELECT usable_battery_capacity_kwh FROM cars LIMIT 1").fetchone()
    capacity = car["usable_battery_capacity_kwh"] if car else 57.0
    total = row["total_energy_kwh"]
    return {
        "total_energy_kwh": round(total, 1),
        "estimated_cycles": round(total / capacity, 1) if capacity else 0,
        "capacity_kwh": capacity,
    }


@router.get("/vehicle/software")
def api_software(request: Request, db=Depends(get_db)) -> dict:
    rows = db.execute(
        "SELECT * FROM software_updates ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()
    return {"updates": [dict(r) for r in rows]}


@router.get("/vehicle/tpms")
def api_tpms(request: Request, db=Depends(get_db)) -> dict:
    rows = db.execute("""
        SELECT timestamp, tpms_fl, tpms_fr, tpms_rl, tpms_rr
        FROM positions
        WHERE tpms_fl IS NOT NULL
        ORDER BY timestamp DESC LIMIT 100
    """).fetchall()
    return {"tpms": [dict(r) for r in reversed(rows)]}


@router.get("/settings")
def api_get_settings(request: Request, db=Depends(get_db)) -> dict:
    return {"settings": get_all_settings(db)}


@router.put("/settings")
def api_update_settings(request: Request, updates: dict, db=Depends(get_db)) -> dict:
    for key, value in updates.items():
        set_setting(db, key, str(value))
    return {"ok": True}
