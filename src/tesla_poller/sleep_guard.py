"""Vampire drain prevention via sleep guard logic.

After 15 minutes of idle, switches from vehicle_data (wakes car) to
vehicles-only polling (does not wake car). Tracks sleep success metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pilot_common.constants import VehicleState
from tesla_poller.state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class SleepMetrics:
    """Tracks sleep guard effectiveness."""
    sleep_attempts: int = 0       # times we entered sleep guard mode
    sleep_successes: int = 0      # times car actually went to sleep
    sleep_prevented: int = 0      # times car came back online without sleeping
    total_guard_seconds: float = 0.0


class SleepGuard:
    """Determines whether to use lightweight or full API calls."""

    def __init__(self, state_manager: StateManager) -> None:
        self._sm = state_manager
        self._guard_active = False
        self._guard_started_at: float = 0.0
        self.metrics = SleepMetrics()

    @property
    def should_use_lightweight_api(self) -> bool:
        """True if we should only call get_vehicles() (not get_vehicle_data)."""
        state = self._sm.state
        if state in (VehicleState.ASLEEP, VehicleState.OFFLINE):
            return True
        if state == VehicleState.IDLE and self._sm.is_sleep_guard_active:
            if not self._guard_active:
                self._guard_active = True
                self.metrics.sleep_attempts += 1
                logger.info(
                    "Sleep guard activated (idle %.0fs). Switching to lightweight API.",
                    self._sm.idle_duration,
                )
            return True
        return False

    def on_state_change(
        self,
        old: VehicleState,
        new: VehicleState,
        timestamp: float,
    ) -> None:
        """Track sleep guard metrics on state transitions."""
        if not self._guard_active:
            return

        if new == VehicleState.ASLEEP:
            self.metrics.sleep_successes += 1
            self.metrics.total_guard_seconds += timestamp - self._guard_started_at
            self._guard_active = False
            logger.info("Sleep guard success: car entered sleep")

        elif new in (VehicleState.DRIVING, VehicleState.CHARGING):
            self.metrics.sleep_prevented += 1
            self._guard_active = False
            logger.info("Sleep guard ended: car became %s", new.value)

        elif new == VehicleState.ONLINE:
            # Car woke up on its own (e.g., precondition, Sentry Mode)
            self._guard_active = False
            logger.info("Sleep guard ended: car woke up to online")
