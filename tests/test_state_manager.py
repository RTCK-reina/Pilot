"""Tests for vehicle state machine transitions."""

from __future__ import annotations

import json
from pathlib import Path

from pilot_common.constants import VehicleState
from tesla_poller.state_manager import StateManager

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestStateTransitionsFromVehicleData:
    def test_initial_state_is_online(self):
        sm = StateManager()
        assert sm.state == VehicleState.ONLINE

    def test_driving_detected(self):
        sm = StateManager()
        data = _load("vehicle_data_driving.json")
        result = sm.update_from_vehicle_data(data)
        assert result == VehicleState.DRIVING

    def test_charging_detected(self):
        sm = StateManager()
        data = _load("vehicle_data_charging.json")
        result = sm.update_from_vehicle_data(data)
        assert result == VehicleState.CHARGING

    def test_idle_from_online(self):
        sm = StateManager()
        data = _load("vehicle_data_idle.json")
        result = sm.update_from_vehicle_data(data)
        assert result == VehicleState.IDLE

    def test_driving_to_idle_on_park(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))
        assert sm.state == VehicleState.DRIVING

        sm.update_from_vehicle_data(_load("vehicle_data_idle.json"))
        assert sm.state == VehicleState.IDLE

    def test_charging_to_idle_on_complete(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_charging.json"))
        assert sm.state == VehicleState.CHARGING

        data = _load("vehicle_data_idle.json")
        data["charge_state"]["charging_state"] = "Complete"
        sm.update_from_vehicle_data(data)
        assert sm.state == VehicleState.IDLE

    def test_asleep_from_vehicle_data(self):
        sm = StateManager()
        result = sm.update_from_vehicle_data({"state": "asleep"})
        assert result == VehicleState.ASLEEP


class TestStateTransitionsFromVehicleList:
    def test_asleep_detected(self):
        sm = StateManager()
        sm.update_from_vehicle_list({"state": "asleep"})
        assert sm.state == VehicleState.ASLEEP

    def test_offline_detected(self):
        sm = StateManager()
        sm.update_from_vehicle_list({"state": "offline"})
        assert sm.state == VehicleState.OFFLINE

    def test_online_from_asleep(self):
        sm = StateManager()
        sm.force_state(VehicleState.ASLEEP)
        sm.update_from_vehicle_list({"state": "online"})
        assert sm.state == VehicleState.ONLINE

    def test_does_not_downgrade_driving_to_online(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))
        assert sm.state == VehicleState.DRIVING

        sm.update_from_vehicle_list({"state": "online"})
        assert sm.state == VehicleState.DRIVING  # should NOT downgrade


class TestStateChangeCallbacks:
    def test_callback_fires(self):
        sm = StateManager()
        events: list[tuple[VehicleState, VehicleState]] = []
        sm.on_state_change(lambda old, new, ts: events.append((old, new)))

        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))
        assert len(events) == 1
        assert events[0] == (VehicleState.ONLINE, VehicleState.DRIVING)

    def test_no_callback_on_same_state(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))

        events: list = []
        sm.on_state_change(lambda old, new, ts: events.append((old, new)))
        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))
        assert len(events) == 0


class TestIdleDuration:
    def test_idle_duration_zero_when_not_idle(self):
        sm = StateManager()
        assert sm.idle_duration == 0.0

    def test_idle_duration_positive_when_idle(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_idle.json"))
        assert sm.idle_duration >= 0.0
        assert sm.state == VehicleState.IDLE

    def test_idle_resets_on_driving(self):
        sm = StateManager()
        sm.update_from_vehicle_data(_load("vehicle_data_idle.json"))
        sm.update_from_vehicle_data(_load("vehicle_data_driving.json"))
        assert sm.idle_duration == 0.0
