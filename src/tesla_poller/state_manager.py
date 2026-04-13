"""Vehicle state machine managing polling behavior.

States: online, asleep, offline, driving, charging, idle
Transitions are derived from API response fields.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from pilot_common.constants import IDLE_TO_SLEEP_GUARD_SECONDS, VehicleState

logger = logging.getLogger(__name__)

# Callbacks type: (old_state, new_state, timestamp)
StateChangeCallback = Callable[[VehicleState, VehicleState, float], None]


class StateManager:
    """Finite state machine for vehicle state tracking."""

    def __init__(self) -> None:
        self._state = VehicleState.ONLINE
        self._idle_since: float | None = None
        self._state_changed_at: float = time.monotonic()
        self._callbacks: list[StateChangeCallback] = []

    @property
    def state(self) -> VehicleState:
        return self._state

    @property
    def idle_duration(self) -> float:
        """Seconds since idle state began. Returns 0 if not idle."""
        if self._idle_since is None:
            return 0.0
        return time.monotonic() - self._idle_since

    @property
    def is_sleep_guard_active(self) -> bool:
        """True if idle long enough that we should stop vehicle_data polls."""
        return self.idle_duration > IDLE_TO_SLEEP_GUARD_SECONDS

    def on_state_change(self, callback: StateChangeCallback) -> None:
        """Register a callback for state transitions."""
        self._callbacks.append(callback)

    def _transition(self, new_state: VehicleState) -> None:
        if new_state == self._state:
            return

        old = self._state
        now = time.monotonic()
        logger.info("State transition: %s -> %s", old.value, new_state.value)
        self._state = new_state
        self._state_changed_at = now

        if new_state == VehicleState.IDLE:
            self._idle_since = now
        else:
            self._idle_since = None

        for cb in self._callbacks:
            try:
                cb(old, new_state, now)
            except Exception:
                logger.exception("State change callback error")

    def update_from_vehicle_list(self, vehicle: dict[str, Any]) -> VehicleState:
        """Update state from lightweight vehicle list response.

        This endpoint does NOT wake the car, so we can only detect:
        - online (state == "online")
        - asleep (state == "asleep")
        - offline (state == "offline")
        """
        api_state = vehicle.get("state", "unknown")

        if api_state == "asleep":
            self._transition(VehicleState.ASLEEP)
        elif api_state == "offline":
            self._transition(VehicleState.OFFLINE)
        elif api_state == "online":
            if self._state in (VehicleState.ASLEEP, VehicleState.OFFLINE):
                self._transition(VehicleState.ONLINE)
            # If already in IDLE/DRIVING/CHARGING, don't downgrade to ONLINE
        return self._state

    def update_from_vehicle_data(self, data: dict[str, Any]) -> VehicleState:
        """Update state from full vehicle_data response.

        Detects driving, charging, and idle based on response fields.
        """
        if data.get("state") == "asleep":
            self._transition(VehicleState.ASLEEP)
            return self._state

        drive_state = data.get("drive_state", {})
        charge_state = data.get("charge_state", {})

        shift_state = drive_state.get("shift_state")
        speed = drive_state.get("speed")
        charging_state = charge_state.get("charging_state")

        # Driving: shift_state is D/R/N (not None/P)
        if shift_state and shift_state in ("D", "R", "N"):
            self._transition(VehicleState.DRIVING)
        elif charging_state == "Charging":
            self._transition(VehicleState.CHARGING)
        elif self._state == VehicleState.DRIVING:
            # Was driving, now stopped -> idle
            self._transition(VehicleState.IDLE)
        elif self._state == VehicleState.CHARGING:
            # Was charging, now stopped
            if charging_state in ("Complete", "Stopped", "Disconnected", None):
                self._transition(VehicleState.IDLE)
        elif self._state in (VehicleState.ONLINE, VehicleState.ASLEEP, VehicleState.OFFLINE):
            self._transition(VehicleState.IDLE)
        # If already IDLE, stay IDLE

        return self._state

    def force_state(self, state: VehicleState) -> None:
        """Force a state transition (e.g., on startup)."""
        self._transition(state)
