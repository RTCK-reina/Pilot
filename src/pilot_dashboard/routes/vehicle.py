"""Vehicle info route."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _fetch_vehicle_data(db: sqlite3.Connection) -> dict:
    """Query vehicle info from SQLite."""
    # Car info
    car = db.execute(
        """
        SELECT
            id, vin, model, trim, battery_type,
            exterior_color, car_version,
            usable_battery_capacity_kwh
        FROM cars
        LIMIT 1
        """
    ).fetchone()

    car_info = dict(car) if car else {}

    # Latest position for TPMS and odometer
    latest_pos = db.execute(
        """
        SELECT
            odometer, tpms_fl, tpms_fr, tpms_rl, tpms_rr,
            inside_temp, outside_temp, is_climate_on
        FROM positions
        ORDER BY timestamp DESC
        LIMIT 1
        """
    ).fetchone()

    tpms = {}
    odometer = None
    inside_temp = None
    outside_temp = None
    is_climate_on = None
    if latest_pos:
        tpms = {
            "fl": latest_pos["tpms_fl"],
            "fr": latest_pos["tpms_fr"],
            "rl": latest_pos["tpms_rl"],
            "rr": latest_pos["tpms_rr"],
        }
        odometer = latest_pos["odometer"]
        inside_temp = latest_pos["inside_temp"]
        outside_temp = latest_pos["outside_temp"]
        is_climate_on = latest_pos["is_climate_on"]

    # Latest software version
    sw = db.execute(
        """
        SELECT version, timestamp
        FROM software_updates
        ORDER BY timestamp DESC
        LIMIT 1
        """
    ).fetchone()

    sw_version = sw["version"] if sw else None
    sw_date = sw["timestamp"] if sw else None

    # Lifetime stats
    drive_stats = db.execute(
        """
        SELECT
            COUNT(*) AS total_drives,
            COALESCE(SUM(distance_km), 0) AS total_km,
            COALESCE(SUM(energy_consumed_kwh), 0) AS total_energy
        FROM drives
        WHERE is_complete = 1
        """
    ).fetchone()

    charge_stats = db.execute(
        """
        SELECT COUNT(*) AS total_charges
        FROM charging_sessions
        WHERE is_complete = 1
        """
    ).fetchone()

    total_drives = drive_stats["total_drives"] or 0
    total_energy = drive_stats["total_energy"] or 0
    total_km = drive_stats["total_km"] or 0
    total_charges = charge_stats["total_charges"] or 0
    lifetime_eff = total_km / total_energy if total_energy > 0 else 0

    return {
        "car": car_info,
        "tpms": tpms,
        "odometer": odometer,
        "inside_temp": inside_temp,
        "outside_temp": outside_temp,
        "is_climate_on": is_climate_on,
        "sw_version": sw_version,
        "sw_date": sw_date,
        "total_drives": total_drives,
        "total_charges": total_charges,
        "total_energy": total_energy,
        "total_km": total_km,
        "lifetime_eff": lifetime_eff,
    }


@router.get("/vehicle")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page vehicle information."""
    templates = request.app.state.templates
    data = _fetch_vehicle_data(db)
    return templates.TemplateResponse(
        request=request,
        name="vehicle.html",
        context={"active": "vehicle", **data},
    )


@router.get("/fragment/vehicle")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for vehicle content."""
    templates = request.app.state.templates
    data = _fetch_vehicle_data(db)
    return templates.TemplateResponse(
        request=request,
        name="vehicle.html",
        context={"active": "vehicle", "fragment": True, **data},
    )
