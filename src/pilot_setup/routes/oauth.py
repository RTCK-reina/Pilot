"""Tesla OAuth 2.0 routes for the setup wizard."""

from __future__ import annotations

import json
import secrets
import sqlite3
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pilot_common.config import get_setting, set_setting
from pilot_common.crypto import encrypt
from pilot_setup.app import get_db

router = APIRouter(prefix="/setup/oauth")

# ---------------------------------------------------------------------------
# Tesla OAuth 2.0 constants
# ---------------------------------------------------------------------------

TESLA_AUTH_URL = "https://auth.tesla.com/oauth2/v3/authorize"
TESLA_TOKEN_URL = "https://auth.tesla.com/oauth2/v3/token"
TESLA_API_BASE = "https://fleet-api.prd.na.vn.cloud.tesla.com"

# These would normally come from environment or settings
TESLA_CLIENT_ID = "pilot-setup"
TESLA_SCOPE = "openid vehicle_device_data vehicle_cmds vehicle_charging_cmds"


def _build_callback_url(request: Request) -> str:
    """Build the OAuth callback URL based on the request origin."""
    host = request.headers.get("host", "localhost:8080")
    scheme = request.headers.get("x-forwarded-proto", "http")
    return f"{scheme}://{host}/setup/oauth/callback"


# ---------------------------------------------------------------------------
# GET /setup/oauth/start  -- redirect to Tesla auth
# ---------------------------------------------------------------------------

@router.get("/start")
def oauth_start(request: Request):
    """Redirect the user to Tesla's OAuth authorization page."""
    state = secrets.token_urlsafe(32)
    request.app.state.oauth_states[state] = True

    callback_url = _build_callback_url(request)

    params = {
        "response_type": "code",
        "client_id": TESLA_CLIENT_ID,
        "redirect_uri": callback_url,
        "scope": TESLA_SCOPE,
        "state": state,
    }

    auth_url = f"{TESLA_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


# ---------------------------------------------------------------------------
# GET /setup/oauth/callback  -- exchange code for tokens
# ---------------------------------------------------------------------------

@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: sqlite3.Connection = Depends(get_db),
):
    """Exchange the authorization code for access and refresh tokens."""
    # Validate CSRF state
    if state not in request.app.state.oauth_states:
        return JSONResponse(
            {"error": "Invalid state parameter. Possible CSRF attack."},
            status_code=400,
        )
    del request.app.state.oauth_states[state]

    callback_url = _build_callback_url(request)

    # Exchange code for tokens
    token_data = {
        "grant_type": "authorization_code",
        "client_id": TESLA_CLIENT_ID,
        "code": code,
        "redirect_uri": callback_url,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(TESLA_TOKEN_URL, data=token_data)

    if resp.status_code != 200:
        return JSONResponse(
            {"error": "Token exchange failed", "detail": resp.text},
            status_code=502,
        )

    tokens = resp.json()
    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")

    # Encrypt and store tokens
    set_setting(db, "tesla_access_token", encrypt(access_token))
    set_setting(db, "tesla_refresh_token", encrypt(refresh_token))
    set_setting(db, "tesla_token_expires_in", str(tokens.get("expires_in", 0)))
    set_setting(db, "tesla_oauth_complete", "true")

    # Signal phone handoff polling
    request.app.state.oauth_complete = True

    # Try to fetch vehicle info with the new token
    await _fetch_vehicle_info(access_token, db)

    # Redirect back to step 2 (which will show success state)
    return RedirectResponse(url="/setup/step/2", status_code=302)


# ---------------------------------------------------------------------------
# GET /setup/oauth/status  -- polling endpoint for phone handoff
# ---------------------------------------------------------------------------

@router.get("/status")
def oauth_status(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """JSON polling endpoint so the kiosk page can detect phone OAuth completion."""
    complete = get_setting(db, "tesla_oauth_complete", "false") == "true"
    return JSONResponse({"oauth_complete": complete})


# ---------------------------------------------------------------------------
# Internal: fetch vehicle info after OAuth
# ---------------------------------------------------------------------------

async def _fetch_vehicle_info(access_token: str, db: sqlite3.Connection) -> None:
    """Attempt to fetch vehicle list and populate settings."""
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{TESLA_API_BASE}/api/1/vehicles",
                headers=headers,
            )

        if resp.status_code != 200:
            return

        data = resp.json()
        vehicles = data.get("response", [])
        if not vehicles:
            return

        vehicle = vehicles[0]  # Use first vehicle
        set_setting(db, "vehicle_id", str(vehicle.get("id", "")))
        set_setting(db, "vehicle_vin", vehicle.get("vin", ""))
        set_setting(db, "vehicle_name", vehicle.get("display_name", ""))

        # Try to get more details
        vid = vehicle.get("id")
        if vid:
            detail_resp = await _fetch_vehicle_detail(access_token, vid)
            if detail_resp:
                _populate_vehicle_details(detail_resp, db)

    except (httpx.HTTPError, KeyError, json.JSONDecodeError):
        pass


async def _fetch_vehicle_detail(access_token: str, vehicle_id: int) -> dict | None:
    """Fetch detailed vehicle data."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{TESLA_API_BASE}/api/1/vehicles/{vehicle_id}/vehicle_data",
                headers=headers,
            )
        if resp.status_code == 200:
            return resp.json().get("response", {})
    except (httpx.HTTPError, json.JSONDecodeError):
        pass
    return None


def _populate_vehicle_details(data: dict, db: sqlite3.Connection) -> None:
    """Save vehicle details from the API response to settings."""
    vehicle_config = data.get("vehicle_config", {})
    vehicle_state = data.get("vehicle_state", {})

    model_map = {
        "modely": "Model Y",
        "model3": "Model 3",
        "models": "Model S",
        "modelx": "Model X",
    }
    car_type = vehicle_config.get("car_type", "")
    model_name = model_map.get(car_type, car_type)

    trim = vehicle_config.get("trim_badging", "")
    if trim:
        model_name = f"{model_name} {trim}"

    set_setting(db, "vehicle_model", model_name)

    # Battery type from plaid/performance/standard flags
    battery_type = "NCA"
    if vehicle_config.get("lfp_battery", False):
        battery_type = "LFP"
    set_setting(db, "battery_type", battery_type)

    # Software version
    sw = vehicle_state.get("car_version", "")
    if sw:
        set_setting(db, "sw_version", sw.split(" ")[0])
