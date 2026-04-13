"""Tests for sleep guard / vampire drain prevention."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import PropertyMock, patch

from pilot_common.constants import IDLE_TO_SLEEP_GUARD_SECONDS, VehicleState
from tesla_poller.sleep_guard import SleepGuard
from tesla_poller.state_manager import StateManager

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestSleepGuardBasic:
    def test_not_lightweight_when_driving(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))
        guard = SleepGuard(sm)
        assert guard.should_use_lightweight_api is False

    def test_not_lightweight_when_recently_idle(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_idle.json"))
        guard = SleepGuard(sm)
        assert guard.should_use_lightweight_api is False

    def test_lightweight_when_asleep(self):
        sm = StateManager()
        sm.force_state(VehicleState.ASLEEP)
        guard = SleepGuard(sm)
        assert guard.should_use_lightweight_api is True

    def test_lightweight_when_offline(self):
        sm = StateManager()
        sm.force_state(VehicleState.OFFLINE)
        guard = SleepGuard(sm)
        assert guard.should_use_lightweight_api is True


class TestSleepGuardActivation:
    def test_activates_after_idle_threshold(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_idle.json"))
        guard = SleepGuard(sm)

        # Simulate idle_since being far in the past
        sm._idle_since = time.monotonic() - IDLE_TO_SLEEP_GUARD_SECONDS - 10
        assert sm.is_sleep_guard_active is True
        assert guard.should_use_lightweight_api is True
        assert guard.metrics.sleep_attempts == 1


class TestSleepMetrics:
    def test_sleep_success_tracked(self):
        sm = StateManager()
        guard = SleepGuard(sm)
        sm.on_state_change(guard.on_state_change)

        guard._guard_active = True
        guard.metrics.sleep_attempts = 1
        sm.force_state(VehicleState.IDLE)
        sm.force_state(VehicleState.ASLEEP)

        assert guard.metrics.sleep_successes == 1
        assert guard._guard_active is False

    def test_sleep_prevented_on_drive(self):
        sm = StateManager()
        guard = SleepGuard(sm)
        sm.on_state_change(guard.on_state_change)

        guard._guard_active = True
        guard.metrics.sleep_attempts = 1
        sm.force_state(VehicleState.IDLE)
        sm.force_state(VehicleState.DRIVING)

        assert guard.metrics.sleep_prevented == 1
        assert guard._guard_active is False
