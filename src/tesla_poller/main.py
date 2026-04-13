"""Tesla poller main loop — asyncio event loop with dynamic polling intervals.

Entry point for the tesla-poller systemd service.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pilot_common.config import get_setting
from pilot_common.constants import POLL_INTERVAL, VehicleState
from pilot_common.crypto import decrypt
from pilot_common.db import get_connection

from tesla_poller.api_client import OwnerAPIClient
from tesla_poller.data_recorder import ensure_car, record_charge, record_position, record_state
from tesla_poller.session_detector import SessionDetector
from tesla_poller.sleep_guard import SleepGuard
from tesla_poller.state_manager import StateManager

logger = logging.getLogger(__name__)


class Poller:
    """Main polling orchestrator."""

    def __init__(self, conn: sqlite3.Connection, api: OwnerAPIClient, vin: str):
        self._conn = conn
        self._api = api
        self._vin = vin
        self._running = False

        self._state_manager = StateManager()
        self._sleep_guard = SleepGuard(self._state_manager)

        # Register sleep guard for state change tracking
        self._state_manager.on_state_change(self._sleep_guard.on_state_change)
        self._state_manager.on_state_change(self._on_state_change)

        # Will be initialized after car is ensured in DB
        self._car_id: int | None = None
        self._session_detector: SessionDetector | None = None

    async def run(self) -> None:
        """Main polling loop."""
        self._running = True

        # Resolve vehicle ID and ensure car in DB
        vehicles = await self._api.get_vehicles()
        vehicle = next((v for v in vehicles if v.get("vin") == self._vin), None)
        if not vehicle:
            logger.error("Vehicle VIN %s not found in account", self._vin)
            return

        # Get initial vehicle data to populate car record
        initial_data = await self._api.get_vehicle_data(self._vin)
        self._car_id = ensure_car(self._conn, self._vin, initial_data)

        efficiency = self._conn.execute(
            "SELECT efficiency FROM cars WHERE id = ?", (self._car_id,)
        ).fetchone()[0]

        self._session_detector = SessionDetector(self._conn, self._car_id, efficiency)
        self._state_manager.on_state_change(self._session_detector.on_state_change)

        # Process initial data
        self._state_manager.update_from_vehicle_data(initial_data)
        self._session_detector.set_current_data(initial_data)
        record_position(self._conn, self._car_id, self._session_detector.current_drive_id, initial_data)

        logger.info("Poller started: vin=%s car_id=%d", self._vin, self._car_id)

        while self._running:
            state = self._state_manager.state
            interval = self._get_interval(state)

            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Poll error (will retry)")
                await asyncio.sleep(30)

        logger.info("Poller stopped")

    async def _poll_once(self) -> None:
        """Execute one polling cycle."""
        if self._sleep_guard.should_use_lightweight_api:
            vehicles = await self._api.get_vehicles()
            vehicle = next((v for v in vehicles if v.get("vin") == self._vin), None)
            if vehicle:
                self._state_manager.update_from_vehicle_list(vehicle)
        else:
            data = await self._api.get_vehicle_data(self._vin)
            self._state_manager.update_from_vehicle_data(data)

            if data.get("state") != "asleep" and self._car_id:
                self._session_detector.set_current_data(data)

                state = self._state_manager.state
                if state == VehicleState.DRIVING:
                    record_position(
                        self._conn, self._car_id,
                        self._session_detector.current_drive_id, data,
                    )
                elif state == VehicleState.CHARGING:
                    if self._session_detector.current_charge_id:
                        record_charge(
                            self._conn,
                            self._session_detector.current_charge_id, data,
                        )
                else:
                    # Idle/online — record position less frequently for state tracking
                    record_position(self._conn, self._car_id, None, data)

    def _get_interval(self, state: VehicleState) -> int:
        """Get polling interval for current state."""
        if state == VehicleState.IDLE and self._state_manager.is_sleep_guard_active:
            return POLL_INTERVAL[VehicleState.ONLINE]  # 90s in sleep guard mode
        return POLL_INTERVAL.get(state, 60)

    def _on_state_change(
        self, old: VehicleState, new: VehicleState, timestamp: float
    ) -> None:
        """Record state transitions to DB."""
        if self._car_id:
            record_state(self._conn, self._car_id, new.value)

    def stop(self) -> None:
        self._running = False


async def async_main(db_path: str = "/var/lib/pilot/pilot.db") -> None:
    """Async entry point."""
    conn = get_connection(db_path)

    # Load tokens
    secrets_dir = get_setting(conn, "secrets_dir", "/var/lib/pilot/secrets")
    access_token = decrypt(get_setting(conn, "tesla_access_token", ""), secrets_dir=secrets_dir)
    refresh_token = decrypt(get_setting(conn, "tesla_refresh_token", ""), secrets_dir=secrets_dir)
    vin = get_setting(conn, "tesla_vin", "")

    if not refresh_token or not vin:
        logger.error("Tesla tokens or VIN not configured. Run setup wizard first.")
        sys.exit(1)

    async def on_token_refresh(new_access: str, new_refresh: str) -> None:
        from pilot_common.crypto import encrypt
        from pilot_common.config import set_setting
        set_setting(conn, "tesla_access_token", encrypt(new_access, secrets_dir=secrets_dir))
        set_setting(conn, "tesla_refresh_token", encrypt(new_refresh, secrets_dir=secrets_dir))

    api = OwnerAPIClient(
        access_token=access_token,
        refresh_token=refresh_token,
        on_token_refresh=on_token_refresh,
    )

    poller = Poller(conn, api, vin)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, poller.stop)

    try:
        await poller.run()
    finally:
        await api.close()
        conn.close()


def main() -> None:
    """Sync entry point for systemd."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
