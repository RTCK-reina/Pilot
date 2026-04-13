"""Home / overview dashboard route."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _query_home_data(db: sqlite3.Connection) -> dict:
    """Gather all data needed for the home dashboard."""

    # Latest car info
    car_row = db.execute("SELECT model, vin FROM cars LIMIT 1").fetchone()
    car_model = car_row["model"] if car_row else None
    car_vin = car_row["vin"] if car_row else None

    # Latest vehicle state
    state_row = db.execute(
        "SELECT state, start_time FROM states ORDER BY id DESC LIMIT 1"
    ).fetchone()
    vehicle_state = state_row["state"] if state_row else "Offline"

    # Latest position (battery, range, location, temps, odometer)
    pos_row = db.execute(
        "SELECT battery_level, rated_range_km, latitude, longitude, "
        "outside_temp, inside_temp, odometer, timestamp "
        "FROM positions ORDER BY id DESC LIMIT 1"
    ).fetchone()

    battery_level = pos_row["battery_level"] if pos_row else None
    rated_range_km = round(pos_row["rated_range_km"], 1) if pos_row and pos_row["rated_range_km"] else None
    latitude = round(pos_row["latitude"], 5) if pos_row and pos_row["latitude"] else None
    longitude = round(pos_row["longitude"], 5) if pos_row and pos_row["longitude"] else None
    outside_temp = round(pos_row["outside_temp"], 1) if pos_row and pos_row["outside_temp"] is not None else None
    inside_temp = round(pos_row["inside_temp"], 1) if pos_row and pos_row["inside_temp"] is not None else None
    odometer = round(pos_row["odometer"], 1) if pos_row and pos_row["odometer"] else None
    last_updated = pos_row["timestamp"] if pos_row else None

    # Today's driving stats
    today_row = db.execute("""
        SELECT
            COUNT(*) as drive_count,
            COALESCE(SUM(distance_km), 0) as total_distance,
            COALESCE(AVG(efficiency_kmkwh), 0) as avg_efficiency,
            COALESCE(SUM(energy_consumed_kwh), 0) as total_energy
        FROM drives
        WHERE is_complete = 1 AND date(start_time) = date('now')
    """).fetchone()

    today_drives = today_row["drive_count"] if today_row else 0
    today_distance = round(today_row["total_distance"], 1) if today_row else 0.0
    today_efficiency = round(today_row["avg_efficiency"], 2) if today_row and today_row["avg_efficiency"] else 0.0
    today_energy = round(today_row["total_energy"], 1) if today_row else 0.0

    # Latest charging info
    charge_row = db.execute("""
        SELECT charge_energy_added, cost_jpy, end_time
        FROM charging_sessions
        WHERE is_complete = 1
        ORDER BY end_time DESC LIMIT 1
    """).fetchone()

    charge_energy_added = round(charge_row["charge_energy_added"], 1) if charge_row and charge_row["charge_energy_added"] else None
    charge_cost = int(charge_row["cost_jpy"]) if charge_row and charge_row["cost_jpy"] else None

    # Recent 5 drives
    drive_rows = db.execute("""
        SELECT id, start_time, end_time, distance_km, efficiency_kmkwh,
               start_address, end_address, energy_consumed_kwh
        FROM drives
        WHERE is_complete = 1
        ORDER BY start_time DESC LIMIT 5
    """).fetchall()

    recent_drives = []
    for r in drive_rows:
        recent_drives.append({
            "id": r["id"],
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "distance_km": round(r["distance_km"], 1) if r["distance_km"] else 0,
            "efficiency_kmkwh": round(r["efficiency_kmkwh"], 2) if r["efficiency_kmkwh"] else 0,
            "start_address": r["start_address"] or "",
            "end_address": r["end_address"] or "",
            "energy_kwh": round(r["energy_consumed_kwh"], 1) if r["energy_consumed_kwh"] else 0,
        })

    # 7-day efficiency trend for the mini chart
    trend_rows = db.execute("""
        SELECT
            date(start_time) as day,
            AVG(efficiency_kmkwh) as avg_eff
        FROM drives
        WHERE is_complete = 1
          AND start_time >= datetime('now', '-7 days')
        GROUP BY day
        ORDER BY day
    """).fetchall()

    trend_labels = [r["day"] for r in trend_rows]
    trend_values = [round(r["avg_eff"], 2) if r["avg_eff"] else 0 for r in trend_rows]

    return {
        "car_model": car_model,
        "car_vin": car_vin,
        "vehicle_state": vehicle_state,
        "battery_level": battery_level,
        "rated_range_km": rated_range_km,
        "latitude": latitude,
        "longitude": longitude,
        "outside_temp": outside_temp,
        "inside_temp": inside_temp,
        "odometer": odometer,
        "last_updated": last_updated,
        "today_drives": today_drives,
        "today_distance": today_distance,
        "today_efficiency": today_efficiency,
        "today_energy": today_energy,
        "charge_energy_added": charge_energy_added,
        "charge_cost": charge_cost,
        "recent_drives": recent_drives,
        "trend_labels_json": json.dumps(trend_labels),
        "trend_values_json": json.dumps(trend_values),
    }


@router.get("/")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page home dashboard."""
    templates = request.app.state.templates
    data = _query_home_data(db)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"active": "home", **data},
    )


@router.get("/fragment/home")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for home content."""
    templates = request.app.state.templates
    data = _query_home_data(db)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"active": "home", "fragment": True, **data},
    )
