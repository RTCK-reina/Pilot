"""Setup wizard step routes (GET render / POST validate+save)."""

from __future__ import annotations

import json
import subprocess
import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pilot_common.config import get_setting, set_setting, set_setting_json, get_all_settings
from pilot_setup.app import get_db

router = APIRouter(prefix="/setup")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STEP_TEMPLATES = {
    1: "step1_locale.html",
    2: "step2_tesla.html",
    3: "step3_vehicle.html",
    4: "step4_rates.html",
    5: "step5_storage.html",
    6: "step6_options.html",
    7: "step7_complete.html",
}

TOTAL_STEPS = 7


def _current_step(db: sqlite3.Connection) -> int:
    """Return the current setup step (defaults to 1)."""
    raw = get_setting(db, "setup_step", "1")
    return int(raw)


def _advance_step(db: sqlite3.Connection, current: int) -> None:
    """Move to the next step if current matches."""
    stored = _current_step(db)
    if current >= stored and current < TOTAL_STEPS:
        set_setting(db, "setup_step", str(current + 1))


def _step_context(step: int, db: sqlite3.Connection) -> dict:
    """Build common template context for a step."""
    return {
        "step": step,
        "total_steps": TOTAL_STEPS,
        "current_step": _current_step(db),
    }


# ---------------------------------------------------------------------------
# GET /setup/ -> redirect to current step
# ---------------------------------------------------------------------------

@router.get("/")
def setup_root(request: Request, db: sqlite3.Connection = Depends(get_db)):
    step = _current_step(db)
    return RedirectResponse(url=f"/setup/step/{step}", status_code=302)


# ---------------------------------------------------------------------------
# GET /setup/status
# ---------------------------------------------------------------------------

@router.get("/status")
def setup_status(request: Request, db: sqlite3.Connection = Depends(get_db)):
    oauth_complete = get_setting(db, "tesla_oauth_complete", "false") == "true"
    return JSONResponse({
        "current_step": _current_step(db),
        "oauth_complete": oauth_complete,
    })


# ---------------------------------------------------------------------------
# Step 1: Locale & Preferences
# ---------------------------------------------------------------------------

@router.get("/step/1")
def step1_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(1, db)
    ctx["language"] = get_setting(db, "language", "ja")
    ctx["timezone"] = get_setting(db, "timezone", "Asia/Tokyo")
    ctx["efficiency_unit"] = get_setting(db, "efficiency_unit", "km/kWh")
    ctx["currency"] = get_setting(db, "currency", "JPY")
    return templates.TemplateResponse(
        request=request, name="step1_locale.html", context=ctx,
    )


@router.post("/step/1")
def step1_post(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    language: str = Form("ja"),
    timezone: str = Form("Asia/Tokyo"),
    efficiency_unit: str = Form("km/kWh"),
    currency: str = Form("JPY"),
):
    set_setting(db, "language", language)
    set_setting(db, "timezone", timezone)
    set_setting(db, "efficiency_unit", efficiency_unit)
    set_setting(db, "currency", currency)
    _advance_step(db, 1)
    return RedirectResponse(url="/setup/step/2", status_code=303)


# ---------------------------------------------------------------------------
# Step 2: Tesla OAuth
# ---------------------------------------------------------------------------

@router.get("/step/2")
def step2_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(2, db)
    ctx["oauth_complete"] = get_setting(db, "tesla_oauth_complete", "false") == "true"
    # Build QR code URL for phone handoff
    host = request.headers.get("host", "localhost:8080")
    ctx["qr_url"] = f"http://{host}/setup/oauth/start"
    return templates.TemplateResponse(
        request=request, name="step2_tesla.html", context=ctx,
    )


@router.post("/step/2")
def step2_post(request: Request, db: sqlite3.Connection = Depends(get_db)):
    # OAuth must be complete before advancing
    if get_setting(db, "tesla_oauth_complete", "false") != "true":
        return RedirectResponse(url="/setup/step/2", status_code=303)
    _advance_step(db, 2)
    return RedirectResponse(url="/setup/step/3", status_code=303)


# ---------------------------------------------------------------------------
# Step 3: Vehicle Confirmation
# ---------------------------------------------------------------------------

@router.get("/step/3")
def step3_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(3, db)
    # Vehicle info populated during OAuth token exchange or manual entry
    ctx["vehicle_name"] = get_setting(db, "vehicle_name", "---")
    ctx["vehicle_vin"] = get_setting(db, "vehicle_vin", "---")
    ctx["vehicle_model"] = get_setting(db, "vehicle_model", "---")
    ctx["battery_type"] = get_setting(db, "battery_type", "---")
    ctx["sw_version"] = get_setting(db, "sw_version", "---")
    ctx["efficiency_constant"] = get_setting(db, "efficiency_constant", "0.149")
    return templates.TemplateResponse(
        request=request, name="step3_vehicle.html", context=ctx,
    )


@router.post("/step/3")
def step3_post(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    efficiency_constant: str = Form("0.149"),
):
    set_setting(db, "efficiency_constant", efficiency_constant)
    _advance_step(db, 3)
    return RedirectResponse(url="/setup/step/4", status_code=303)


# ---------------------------------------------------------------------------
# Step 4: Electricity Rates
# ---------------------------------------------------------------------------

@router.get("/step/4")
def step4_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(4, db)
    ctx["rate_type"] = get_setting(db, "rate_type", "fixed")
    ctx["rate_fixed"] = get_setting(db, "rate_fixed", "27")
    ctx["rate_night"] = get_setting(db, "rate_night", "17")
    ctx["rate_day"] = get_setting(db, "rate_day", "27")
    ctx["rate_peak"] = get_setting(db, "rate_peak", "35")
    ctx["rate_sc"] = get_setting(db, "rate_sc", "55")
    ctx["currency"] = get_setting(db, "currency", "JPY")
    return templates.TemplateResponse(
        request=request, name="step4_rates.html", context=ctx,
    )


@router.post("/step/4")
def step4_post(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    rate_type: str = Form("fixed"),
    rate_fixed: str = Form("27"),
    rate_night: str = Form("17"),
    rate_day: str = Form("27"),
    rate_peak: str = Form("35"),
    rate_sc: str = Form("55"),
):
    set_setting(db, "rate_type", rate_type)
    set_setting(db, "rate_fixed", rate_fixed)
    set_setting(db, "rate_night", rate_night)
    set_setting(db, "rate_day", rate_day)
    set_setting(db, "rate_peak", rate_peak)
    set_setting(db, "rate_sc", rate_sc)
    _advance_step(db, 4)
    return RedirectResponse(url="/setup/step/5", status_code=303)


# ---------------------------------------------------------------------------
# Step 5: Storage Configuration
# ---------------------------------------------------------------------------

@router.get("/step/5")
def step5_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(5, db)
    ctx["storage_usb"] = get_setting(db, "storage_usb", "false") == "true"
    ctx["storage_gdrive"] = get_setting(db, "storage_gdrive", "false") == "true"

    # Detect USB SSD
    usb_detected = False
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for dev in data.get("blockdevices", []):
                if dev.get("type") == "disk" and dev.get("name", "").startswith("sd"):
                    usb_detected = True
                    break
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    ctx["usb_detected"] = usb_detected
    return templates.TemplateResponse(
        request=request, name="step5_storage.html", context=ctx,
    )


@router.post("/step/5")
def step5_post(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    storage_usb: str = Form("false"),
    storage_gdrive: str = Form("false"),
):
    set_setting(db, "storage_usb", storage_usb)
    set_setting(db, "storage_gdrive", storage_gdrive)
    _advance_step(db, 5)
    return RedirectResponse(url="/setup/step/6", status_code=303)


# ---------------------------------------------------------------------------
# Step 6: Optional Tools
# ---------------------------------------------------------------------------

@router.get("/step/6")
def step6_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(6, db)
    ctx["tailscale_enabled"] = get_setting(db, "tailscale_enabled", "false") == "true"
    ctx["claude_enabled"] = get_setting(db, "claude_enabled", "false") == "true"
    ctx["claude_api_key"] = get_setting(db, "claude_api_key", "")
    ctx["github_cli_enabled"] = get_setting(db, "github_cli_enabled", "false") == "true"
    return templates.TemplateResponse(
        request=request, name="step6_options.html", context=ctx,
    )


@router.post("/step/6")
def step6_post(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    tailscale_enabled: str = Form("false"),
    claude_enabled: str = Form("false"),
    claude_api_key: str = Form(""),
    github_cli_enabled: str = Form("false"),
):
    set_setting(db, "tailscale_enabled", tailscale_enabled)
    set_setting(db, "claude_enabled", claude_enabled)
    if claude_api_key:
        from pilot_common.crypto import encrypt
        set_setting(db, "claude_api_key", encrypt(claude_api_key))
    set_setting(db, "github_cli_enabled", github_cli_enabled)
    _advance_step(db, 6)
    return RedirectResponse(url="/setup/step/7", status_code=303)


# ---------------------------------------------------------------------------
# Step 7: Summary & Launch
# ---------------------------------------------------------------------------

@router.get("/step/7")
def step7_get(request: Request, db: sqlite3.Connection = Depends(get_db)):
    templates = request.app.state.templates
    ctx = _step_context(7, db)
    # Gather all settings for summary display
    ctx["settings"] = get_all_settings(db)
    return templates.TemplateResponse(
        request=request, name="step7_complete.html", context=ctx,
    )


@router.post("/step/7")
def step7_post(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Activate services and mark setup as complete."""
    set_setting(db, "setup_complete", "true")
    set_setting(db, "setup_step", str(TOTAL_STEPS))

    # Activate tesla-poller and pilot-dashboard, disable pilot-setup
    services = [
        ("tesla-poller.service", "start"),
        ("pilot-dashboard.service", "start"),
        ("pilot-setup.service", "stop"),
    ]
    for service, action in services:
        try:
            subprocess.run(
                ["sudo", "systemctl", action, service],
                capture_output=True, text=True, timeout=15,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Dev environment — systemctl not available
            pass

    try:
        subprocess.run(
            ["sudo", "systemctl", "disable", "pilot-setup.service"],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return RedirectResponse(url="/setup/step/7?done=1", status_code=303)
