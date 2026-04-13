"""FastAPI application factory for PiLot Dashboard."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pilot_common.constants import DB_PATH_DEFAULT
from pilot_common.db import get_connection

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"


def create_app(db_path: str = DB_PATH_DEFAULT) -> FastAPI:
    """Create and configure the dashboard FastAPI app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.db = get_connection(db_path)
        yield
        app.state.db.close()

    app = FastAPI(title="PiLot Dashboard", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.state.templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    # Register routes
    from pilot_dashboard.routes.api import router as api_router
    from pilot_dashboard.routes.home import router as home_router
    from pilot_dashboard.routes.ws import router as ws_router
    from pilot_dashboard.routes.efficiency import router as efficiency_router
    from pilot_dashboard.routes.drives import router as drives_router
    from pilot_dashboard.routes.charging import router as charging_router
    from pilot_dashboard.routes.battery import router as battery_router
    from pilot_dashboard.routes.vehicle import router as vehicle_router
    from pilot_dashboard.routes.settings import router as settings_router

    app.include_router(api_router)
    app.include_router(home_router)
    app.include_router(ws_router)
    app.include_router(efficiency_router)
    app.include_router(drives_router)
    app.include_router(charging_router)
    app.include_router(battery_router)
    app.include_router(vehicle_router)
    app.include_router(settings_router)

    return app


def get_db(request: Request) -> sqlite3.Connection:
    """Dependency to get the database connection."""
    return request.app.state.db


def get_templates(request: Request) -> Jinja2Templates:
    """Dependency to get template engine."""
    return request.app.state.templates
