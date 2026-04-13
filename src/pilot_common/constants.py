"""Vehicle efficiency defaults, polling intervals, and classification thresholds."""

from __future__ import annotations

from enum import Enum

# --- Vehicle efficiency defaults ---

VEHICLE_DEFAULTS: dict[str, dict[str, float]] = {
    "Model Y RWD LFP": {
        "efficiency": 0.149,  # kWh/km (rated)
        "usable_capacity_kwh": 57.0,
        "nominal_capacity_kwh": 60.0,
    },
    "Model Y Long Range": {
        "efficiency": 0.149,
        "usable_capacity_kwh": 72.0,
        "nominal_capacity_kwh": 75.0,
    },
    "Model 3 RWD LFP": {
        "efficiency": 0.133,
        "usable_capacity_kwh": 57.0,
        "nominal_capacity_kwh": 60.0,
    },
    "Model 3 Long Range": {
        "efficiency": 0.133,
        "usable_capacity_kwh": 72.0,
        "nominal_capacity_kwh": 75.0,
    },
}

DEFAULT_EFFICIENCY = 0.149  # kWh/km — Model Y RWD LFP
DEFAULT_USABLE_CAPACITY_KWH = 57.0

# Gasoline energy density (kWh per liter)
GASOLINE_ENERGY_DENSITY_KWH_PER_L = 8.9


# --- Vehicle states ---

class VehicleState(str, Enum):
    ONLINE = "online"
    ASLEEP = "asleep"
    OFFLINE = "offline"
    DRIVING = "driving"
    CHARGING = "charging"
    IDLE = "idle"


# --- Polling intervals (seconds) ---

POLL_INTERVAL: dict[VehicleState, int] = {
    VehicleState.DRIVING: 5,
    VehicleState.CHARGING: 60,
    VehicleState.IDLE: 30,       # first 15 minutes
    VehicleState.ONLINE: 90,     # idle > 15 min, use lightweight API
    VehicleState.ASLEEP: 120,
    VehicleState.OFFLINE: 300,
}

IDLE_TO_SLEEP_GUARD_SECONDS = 15 * 60  # 15 minutes


# --- Road type classification thresholds ---

HIGHWAY_SPEED_THRESHOLD_KMH = 80
HIGHWAY_RATIO_THRESHOLD = 0.60  # 60% of samples > 80 km/h -> highway
CITY_SPEED_THRESHOLD_KMH = 30
CITY_RATIO_THRESHOLD = 0.40     # 40% of samples < 30 km/h -> city


# --- Database ---

DB_PATH_DEFAULT = "/var/lib/pilot/pilot.db"
SECRETS_DIR = "/var/lib/pilot/secrets"
SALT_FILE = "device.salt"

# SQLite cache size auto-detection threshold (bytes)
LOW_MEMORY_THRESHOLD_BYTES = 1_500_000_000  # 1.5 GB
CACHE_SIZE_LOW = -4000   # 4 MB (Pi 3B)
CACHE_SIZE_NORMAL = -8000  # 8 MB (Pi 4+)


# --- IPC ---

NOTIFY_SOCKET_PATH = "/run/pilot/notify.sock"


# --- Supercharger default rate ---

SC_DEFAULT_RATE_JPY_PER_KWH = 55
