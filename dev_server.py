"""Dev server with rich seeded sample data for visual testing."""
import os
import uvicorn
from pilot_common.db import get_connection

DB_PATH = "/tmp/pilot_dev.db"

# Remove old dev DB to start fresh
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = get_connection(DB_PATH)

# Car
conn.execute("""
    INSERT INTO cars (id, vin, model, trim, battery_type, exterior_color, car_version,
                      efficiency, usable_battery_capacity_kwh)
    VALUES (1, '5YJ3E1EAXPF000001', 'Model Y', 'RWD', 'LFP', 'MidnightSilver',
            '2025.50.6 abc123', 0.149, 57.0)
""")

# Drives — 15 trips over 2 weeks with realistic variation
import random
random.seed(42)
for i in range(15):
    day = 13 - i
    if day < 1:
        day = 28 + day
        month = 3
    else:
        month = 4
    hour = 7 + (i % 12)
    dist = round(random.uniform(8, 120), 1)
    energy = round(dist * random.uniform(0.120, 0.220), 2)
    whkm = round(energy * 1000 / dist, 1) if dist > 0 else 0
    kmkwh = round(dist / energy, 2) if energy > 0 else 0
    temp = round(random.uniform(5, 28), 1)
    road = random.choice(["city", "highway", "mixed"])
    soc_start = random.randint(50, 95)
    soc_end = max(10, soc_start - random.randint(5, 40))
    dur = round(dist / random.uniform(25, 80) * 60, 1)
    spd_max = random.randint(60, 130)
    spd_avg = round(dist / (dur / 60), 1) if dur > 0 else 0
    range_start = round(soc_start / 100 * 248, 1)
    range_end = round(soc_end / 100 * 248, 1)

    conn.execute(f"""
        INSERT INTO drives (car_id, start_time, end_time, distance_km, duration_min,
            energy_consumed_kwh, efficiency_whkm, efficiency_kmkwh, road_type,
            outside_temp_avg, start_battery_level, end_battery_level,
            start_rated_range_km, end_rated_range_km,
            speed_max, speed_avg, is_complete)
        VALUES (1, '2026-{month:02d}-{day:02d}T{hour:02d}:00:00',
                '2026-{month:02d}-{day:02d}T{hour:02d}:{int(dur):02d}:00',
                {dist}, {dur}, {energy}, {whkm}, {kmkwh}, '{road}', {temp},
                {soc_start}, {soc_end}, {range_start}, {range_end},
                {spd_max}, {spd_avg}, 1)
    """)

# Charging sessions — 6 sessions
charger_types = [
    ("home_ac", 7.4, 28),
    ("supercharger", 150, 55),
    ("home_ac", 7.4, 28),
    ("supercharger", 120, 55),
    ("home_ac", 7.4, 28),
    ("chademo", 50, 45),
]
for i, (ctype, max_power, rate) in enumerate(charger_types):
    day = 12 - i * 2
    if day < 1:
        day = 28 + day
        month = 3
    else:
        month = 4
    added = round(random.uniform(15, 50), 1)
    cost = round(added * rate)
    soc_s = random.randint(10, 40)
    soc_e = min(100, soc_s + random.randint(30, 60))
    dur = round(added / max_power * 60, 1) if ctype != "home_ac" else round(added / max_power * 60, 0)

    conn.execute(f"""
        INSERT INTO charging_sessions (car_id, start_time, end_time, charge_energy_added,
            max_charger_power, cost_jpy, cost_per_kwh, charger_type,
            start_battery_level, end_battery_level, duration_min, is_complete)
        VALUES (1, '2026-{month:02d}-{day:02d}T22:00:00', '2026-{month:02d}-{day:02d}T23:30:00',
                {added}, {max_power}, {cost}, {rate}, '{ctype}',
                {soc_s}, {soc_e}, {dur}, 1)
    """)

# Positions — scattered for TPMS, battery health
for i in range(30):
    day = 13 - i
    if day < 1:
        day = 28 + day
        month = 3
    else:
        month = 4
    soc = random.randint(20, 100)
    conn.execute(f"""
        INSERT INTO positions (car_id, timestamp, latitude, longitude, speed,
            battery_level, rated_range_km, outside_temp,
            tpms_fl, tpms_fr, tpms_rl, tpms_rr, power, odometer)
        VALUES (1, '2026-{month:02d}-{day:02d}T12:00:00',
                {34.6937 + random.uniform(-0.05, 0.05)},
                {135.5023 + random.uniform(-0.05, 0.05)},
                {random.randint(0, 100)}, {soc}, {round(soc/100*248, 1)},
                {round(random.uniform(8, 30), 1)},
                {round(random.uniform(2.7, 3.1), 2)},
                {round(random.uniform(2.7, 3.1), 2)},
                {round(random.uniform(2.7, 3.1), 2)},
                {round(random.uniform(2.7, 3.1), 2)},
                {round(random.uniform(-20, 50), 1)},
                {12000 + i * 30})
    """)

# Current state
conn.execute("INSERT INTO states (car_id, state, start_time) VALUES (1, 'idle', '2026-04-13T10:00:00')")

# Software updates
conn.execute("INSERT INTO software_updates (car_id, version, timestamp) VALUES (1, '2025.50.6', '2026-03-15T00:00:00')")
conn.execute("INSERT INTO software_updates (car_id, version, timestamp) VALUES (1, '2025.44.2', '2026-02-01T00:00:00')")
conn.execute("INSERT INTO software_updates (car_id, version, timestamp) VALUES (1, '2025.38.1', '2025-12-20T00:00:00')")

conn.commit()
conn.close()
print(f"DB seeded at {DB_PATH}")

from pilot_dashboard.app import create_app
app = create_app(DB_PATH)
uvicorn.run(app, host="127.0.0.1", port=8888)
