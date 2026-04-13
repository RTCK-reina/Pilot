"""Efficiency analytics route."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, Request

from pilot_dashboard.app import get_db

router = APIRouter()


def _query_efficiency_data(db: sqlite3.Connection) -> dict:
    """Gather all data needed for the efficiency dashboard."""

    # --- Summary stats (all completed drives) ---
    summary_row = db.execute("""
        SELECT
            COUNT(*) as total_drives,
            COALESCE(SUM(distance_km), 0) as total_km,
            COALESCE(SUM(energy_consumed_kwh), 0) as total_kwh,
            COALESCE(AVG(efficiency_kmkwh), 0) as avg_kmkwh,
            COALESCE(AVG(efficiency_whkm), 0) as avg_whkm
        FROM drives
        WHERE is_complete = 1
    """).fetchone()

    total_drives = summary_row["total_drives"]
    total_km = round(summary_row["total_km"], 1)
    total_kwh = round(summary_row["total_kwh"], 1)
    avg_kmkwh = round(summary_row["avg_kmkwh"], 2)
    avg_whkm = round(summary_row["avg_whkm"], 1)

    # Cost per km from charging data
    cost_row = db.execute("""
        SELECT COALESCE(SUM(cost_jpy), 0) as total_cost
        FROM charging_sessions WHERE is_complete = 1
    """).fetchone()
    total_cost = cost_row["total_cost"] if cost_row else 0
    cost_per_km = round(total_cost / total_km, 1) if total_km > 0 else 0

    # --- Trend data (daily avg efficiency + temp for last 30 days) ---
    trend_rows = db.execute("""
        SELECT
            date(start_time) as day,
            AVG(efficiency_kmkwh) as avg_kmkwh,
            AVG(outside_temp_avg) as avg_temp,
            SUM(distance_km) as distance_km,
            COUNT(*) as drive_count
        FROM drives
        WHERE is_complete = 1
          AND start_time >= datetime('now', '-30 days')
        GROUP BY day
        ORDER BY day
    """).fetchall()

    trend_labels = [r["day"] for r in trend_rows]
    trend_efficiency = [round(r["avg_kmkwh"], 2) if r["avg_kmkwh"] else 0 for r in trend_rows]
    trend_temp = [round(r["avg_temp"], 1) if r["avg_temp"] is not None else None for r in trend_rows]

    # --- Energy breakdown (total consumed vs regen) ---
    energy_row = db.execute("""
        SELECT
            COALESCE(SUM(energy_consumed_kwh), 0) as consumed,
            COALESCE(SUM(energy_regen_kwh), 0) as regen
        FROM drives
        WHERE is_complete = 1
    """).fetchone()

    energy_consumed = round(energy_row["consumed"], 1)
    energy_regen = round(energy_row["regen"], 1)
    energy_hvac = round(energy_consumed * 0.12, 1)  # estimated 12% HVAC

    # --- Temperature scatter data ---
    temp_rows = db.execute("""
        SELECT outside_temp_avg as temp, efficiency_kmkwh as kmkwh
        FROM drives
        WHERE is_complete = 1
          AND outside_temp_avg IS NOT NULL
          AND efficiency_kmkwh IS NOT NULL
        ORDER BY start_time DESC
        LIMIT 500
    """).fetchall()

    temp_scatter = [{"x": round(r["temp"], 1), "y": round(r["kmkwh"], 2)} for r in temp_rows]

    # --- Speed band data ---
    speed_rows = db.execute("""
        SELECT
            (speed / 10) * 10 as speed_band,
            AVG(power) as avg_power_kw,
            COUNT(*) as sample_count
        FROM positions
        WHERE speed IS NOT NULL AND speed > 0 AND power IS NOT NULL
        GROUP BY speed_band
        ORDER BY speed_band
    """).fetchall()

    speed_labels = [str(r["speed_band"]) for r in speed_rows]
    speed_values = [round(r["avg_power_kw"], 1) if r["avg_power_kw"] else 0 for r in speed_rows]

    # --- Daily breakdown (last 30 days) for the table ---
    daily_rows = db.execute("""
        SELECT
            date(start_time) as day,
            SUM(distance_km) as distance_km,
            SUM(energy_consumed_kwh) as energy_kwh,
            AVG(efficiency_kmkwh) as avg_kmkwh,
            CASE WHEN SUM(energy_consumed_kwh) > 0
                 THEN SUM(energy_regen_kwh) * 100.0 / SUM(energy_consumed_kwh)
                 ELSE 0 END as regen_pct,
            AVG(outside_temp_avg) as avg_temp
        FROM drives
        WHERE is_complete = 1
          AND start_time >= datetime('now', '-30 days')
        GROUP BY day
        ORDER BY day DESC
    """).fetchall()

    daily_breakdown = []
    for r in daily_rows:
        daily_breakdown.append({
            "day": r["day"],
            "distance_km": round(r["distance_km"], 1) if r["distance_km"] else 0,
            "energy_kwh": round(r["energy_kwh"], 1) if r["energy_kwh"] else 0,
            "avg_kmkwh": round(r["avg_kmkwh"], 2) if r["avg_kmkwh"] else 0,
            "regen_pct": round(r["regen_pct"], 1) if r["regen_pct"] else 0,
            "avg_temp": round(r["avg_temp"], 1) if r["avg_temp"] is not None else None,
        })

    # --- Monthly charging cost ---
    cost_rows = db.execute("""
        SELECT
            strftime('%Y-%m', start_time) as month,
            COALESCE(SUM(cost_jpy), 0) as total_cost_jpy,
            COALESCE(SUM(charge_energy_added), 0) as total_kwh,
            COUNT(*) as session_count
        FROM charging_sessions
        WHERE is_complete = 1
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """).fetchall()

    cost_labels = [r["month"] for r in reversed(cost_rows)]
    cost_values = [int(r["total_cost_jpy"]) for r in reversed(cost_rows)]

    return {
        # Summary
        "total_drives": total_drives,
        "total_km": total_km,
        "total_kwh": total_kwh,
        "avg_kmkwh": avg_kmkwh,
        "avg_whkm": avg_whkm,
        "cost_per_km": cost_per_km,
        # Trend chart
        "trend_labels_json": json.dumps(trend_labels),
        "trend_efficiency_json": json.dumps(trend_efficiency),
        "trend_temp_json": json.dumps(trend_temp),
        # Energy breakdown
        "energy_consumed": energy_consumed,
        "energy_regen": energy_regen,
        "energy_hvac": energy_hvac,
        # Temperature scatter
        "temp_scatter_json": json.dumps(temp_scatter),
        # Speed distribution
        "speed_labels_json": json.dumps(speed_labels),
        "speed_values_json": json.dumps(speed_values),
        # Daily breakdown table
        "daily_breakdown": daily_breakdown,
        # Monthly cost
        "cost_labels_json": json.dumps(cost_labels),
        "cost_values_json": json.dumps(cost_values),
    }


@router.get("/efficiency")
def page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Full-page efficiency dashboard."""
    templates = request.app.state.templates
    data = _query_efficiency_data(db)
    return templates.TemplateResponse(
        request=request,
        name="efficiency.html",
        context={"active": "efficiency", **data},
    )


@router.get("/fragment/efficiency")
def fragment(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """SPA fragment for efficiency content."""
    templates = request.app.state.templates
    data = _query_efficiency_data(db)
    return templates.TemplateResponse(
        request=request,
        name="efficiency.html",
        context={"active": "efficiency", "fragment": True, **data},
    )
