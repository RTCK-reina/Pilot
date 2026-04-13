"""Data classes for PiLot domain objects."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Car:
    id: int = 0
    vin: str = ""
    model: str | None = None
    trim: str | None = None
    battery_type: str | None = None
    exterior_color: str | None = None
    car_version: str | None = None
    efficiency: float = 0.149
    usable_battery_capacity_kwh: float = 57.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Position:
    id: int = 0
    car_id: int = 0
    drive_id: int | None = None
    timestamp: str = ""
    latitude: float | None = None
    longitude: float | None = None
    speed: int | None = None
    power: float | None = None
    odometer: float | None = None
    battery_level: int | None = None
    usable_battery_level: int | None = None
    rated_range_km: float | None = None
    est_range_km: float | None = None
    elevation: int | None = None
    heading: int | None = None
    inside_temp: float | None = None
    outside_temp: float | None = None
    is_climate_on: bool = False
    battery_heater: bool = False
    tpms_fl: float | None = None
    tpms_fr: float | None = None
    tpms_rl: float | None = None
    tpms_rr: float | None = None
    fan_status: int | None = None


@dataclass
class Drive:
    id: int = 0
    car_id: int = 0
    start_time: str = ""
    end_time: str | None = None
    start_lat: float | None = None
    start_lng: float | None = None
    end_lat: float | None = None
    end_lng: float | None = None
    start_address: str | None = None
    end_address: str | None = None
    distance_km: float | None = None
    duration_min: float | None = None
    start_odometer: float | None = None
    end_odometer: float | None = None
    start_battery_level: int | None = None
    end_battery_level: int | None = None
    start_rated_range_km: float | None = None
    end_rated_range_km: float | None = None
    outside_temp_avg: float | None = None
    speed_max: int | None = None
    speed_avg: float | None = None
    power_max: float | None = None
    power_min: float | None = None
    total_ascent_m: int | None = None
    total_descent_m: int | None = None
    energy_consumed_kwh: float | None = None
    energy_regen_kwh: float | None = None
    efficiency_whkm: float | None = None
    efficiency_kmkwh: float | None = None
    road_type: str | None = None
    is_complete: bool = False


@dataclass
class ChargingSession:
    id: int = 0
    car_id: int = 0
    start_time: str = ""
    end_time: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    charger_type: str | None = None
    charger_brand: str | None = None
    start_battery_level: int | None = None
    end_battery_level: int | None = None
    charge_energy_added: float | None = None
    charge_energy_used: float | None = None
    max_charger_power: float | None = None
    duration_min: float | None = None
    outside_temp_avg: float | None = None
    cost_jpy: float | None = None
    cost_per_kwh: float | None = None
    is_complete: bool = False


@dataclass
class Charge:
    id: int = 0
    charging_session_id: int = 0
    timestamp: str = ""
    battery_level: int | None = None
    usable_battery_level: int | None = None
    charge_energy_added: float | None = None
    charger_power: float | None = None
    charger_voltage: int | None = None
    charger_current: int | None = None
    charger_phases: int | None = None
    outside_temp: float | None = None
    battery_heater: bool = False
    conn_charge_cable: str | None = None
    fast_charger_type: str | None = None


@dataclass
class VehicleStateRecord:
    id: int = 0
    car_id: int = 0
    state: str = ""
    start_time: str = ""
    end_time: str | None = None


@dataclass
class SoftwareUpdate:
    id: int = 0
    car_id: int = 0
    version: str = ""
    timestamp: str = ""
