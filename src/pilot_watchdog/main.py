"""Watchdog main loop — periodic health checks with automatic recovery.

Runs every 30 seconds, executes all lightweight checks on each cycle and
the expensive ``check_db_integrity`` once per day. On critical failures,
attempts to restart the relevant service via :mod:`pilot_watchdog.recovery`.

Entry point for the pilot-watchdog systemd service.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import date

from pilot_common.constants import DB_PATH_DEFAULT
from pilot_common.db import get_connection

from pilot_watchdog.checks import (
    CheckResult,
    Status,
    check_dashboard,
    check_db_integrity,
    check_poller,
    check_storage,
    check_token_expiry,
)
from pilot_watchdog.recovery import restart_service

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30

# Map check names to the systemd service that should be restarted on failure.
_RECOVERY_MAP: dict[str, str] = {
    "poller": "tesla-poller",
    "dashboard": "pilot-dashboard",
}


class Watchdog:
    """Main watchdog loop."""

    def __init__(self, db_path: str = DB_PATH_DEFAULT):
        self._db_path = db_path
        self._running = False
        self._last_integrity_date: date | None = None

    def run(self) -> None:
        """Block and poll until a termination signal is received."""
        self._running = True
        conn = get_connection(self._db_path)

        logger.info("Watchdog started (interval=%ds)", CHECK_INTERVAL_SECONDS)

        try:
            while self._running:
                self._run_cycle(conn)
                # Sleep in small increments so SIGTERM is handled promptly
                deadline = time.monotonic() + CHECK_INTERVAL_SECONDS
                while self._running and time.monotonic() < deadline:
                    time.sleep(1)
        finally:
            conn.close()
            logger.info("Watchdog stopped")

    def _run_cycle(self, conn) -> None:
        """Execute one check cycle."""
        results: list[CheckResult] = []

        # Lightweight checks — every cycle
        results.append(check_poller(conn))
        results.append(check_dashboard())
        results.append(check_storage())
        results.append(check_token_expiry(conn))

        # Expensive integrity check — daily only
        today = date.today()
        if self._last_integrity_date != today:
            results.append(check_db_integrity(conn))
            self._last_integrity_date = today

        # Log and attempt recovery
        for r in results:
            if r.status == Status.OK:
                logger.debug("[%s] %s", r.name, r.message)
            elif r.status == Status.WARN:
                logger.warning("[%s] %s", r.name, r.message)
            elif r.status == Status.CRITICAL:
                logger.error("[%s] %s", r.name, r.message)
                self._attempt_recovery(r)

    def _attempt_recovery(self, result: CheckResult) -> None:
        """Try to restart the service associated with a failed check."""
        service = _RECOVERY_MAP.get(result.name)
        if service:
            logger.info("Attempting recovery: restart %s", service)
            restart_service(service)

    def stop(self, *_args) -> None:
        """Signal handler for clean shutdown."""
        logger.info("Received shutdown signal")
        self._running = False


def main() -> None:
    """Sync entry point for systemd."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    watchdog = Watchdog()

    signal.signal(signal.SIGTERM, watchdog.stop)
    signal.signal(signal.SIGINT, watchdog.stop)

    try:
        watchdog.run()
    except Exception:
        logger.exception("Watchdog fatal error")
        sys.exit(1)


if __name__ == "__main__":
    main()
