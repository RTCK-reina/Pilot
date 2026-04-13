"""Dashboard entry point for systemd."""

from __future__ import annotations

import uvicorn

from pilot_dashboard.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("pilot_dashboard.main:app", host="0.0.0.0", port=80, log_level="info")
