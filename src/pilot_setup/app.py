"""FastAPI application factory for PiLot Setup Wizard."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pilot_common.constants import DB_PATH_DEFAULT
from pilot_common.db import get_connection

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"
TOKENS_CSS_DIR = Path(__file__).parent.parent / "pilot_dashboard" / "static"


def create_app(db_path: str = DB_PATH_DEFAULT) -> FastAPI:
    """Create and configure the setup wizard FastAPI app."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.db = get_connection(db_path)
        # OAuth CSRF state tokens: {state_string: True}
        app.state.oauth_states: dict[str, bool] = {}
        # Track whether OAuth completed (for phone handoff polling)
        app.state.oauth_complete = False
        yield
        app.state.db.close()

    app = FastAPI(title="PiLot Setup", lifespan=lifespan)

    # Mount setup-specific static files
    if STATIC_DIR.exists():
        app.mount("/static/setup", StaticFiles(directory=str(STATIC_DIR)), name="setup_static")

    # Mount shared dashboard static (tokens.css lives here)
    if TOKENS_CSS_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(TOKENS_CSS_DIR)), name="shared_static")

    app.state.templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    # Register routes
    from pilot_setup.routes.wizard import router as wizard_router
    from pilot_setup.routes.oauth import router as oauth_router

    app.include_router(wizard_router)
    app.include_router(oauth_router)

    return app


def get_db(request: Request):
    """Dependency to get the database connection."""
    return request.app.state.db


def get_templates(request: Request) -> Jinja2Templates:
    """Dependency to get template engine."""
    return request.app.state.templates
