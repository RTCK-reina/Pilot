"""Setup wizard entry point for systemd."""

from __future__ import annotations

import uvicorn

from pilot_setup.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("pilot_setup.main:app", host="0.0.0.0", port=8080, log_level="info")
