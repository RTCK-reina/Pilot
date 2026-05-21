# PiLot - Tesla Vehicle Management OS

## Overview
PiLot is an appliance OS for Raspberry Pi that logs Tesla vehicle data and serves a web dashboard.
No Docker, no cloud — just microSD + power.

## Database
- SQLite WAL mode: `/var/lib/pilot/pilot.db`
- Key tables: `drives` (trip aggregates), `positions` (5s driving data), `charging_sessions`, `charges`, `cars`, `states`, `settings`

## Efficiency Calculations
- `km/kWh = distance_km / energy_consumed_kwh`
- `Wh/km = energy_consumed_kwh * 1000 / distance_km`
- Gasoline equivalent: `km/kWh × 8.9` (8.9 kWh per liter)
- Energy consumed: `(start_rated_range_km - end_rated_range_km) × cars.efficiency`

## Common Query Patterns
```sql
-- Monthly efficiency
SELECT strftime('%Y-%m', start_time) as month, AVG(efficiency_kmkwh) as avg
FROM drives WHERE is_complete = 1 GROUP BY month;

-- Speed band analysis
SELECT (speed/10)*10 as band, AVG(power) as avg_kw
FROM positions WHERE speed > 0 GROUP BY band;

-- Charging cost
SELECT SUM(cost_jpy) FROM charging_sessions WHERE strftime('%Y-%m', start_time) = '2026-04';
```

## Settings Reference
- `settings` table stores key-value pairs
- `efficiency_unit`: 'km_kwh' | 'wh_km' | 'kwh_100km'
- `locale`: 'ja' | 'en'
- `currency`: 'JPY'

## Architecture
- `src/pilot_common/` — shared DB, config, crypto, IPC notify
- `src/tesla_poller/` — Tesla API polling engine (systemd service)
- `src/pilot_dashboard/` — FastAPI web dashboard (port 80)
- `src/pilot_setup/` — First-boot wizard (port 8080)
- `src/pilot_sync/` — Backup/Google Drive sync
- `src/pilot_watchdog/` — Health monitoring

## Important Notes
- READ-ONLY access to database (never write)
- Respond in Japanese
- Model Y RWD LFP default: 0.149 kWh/km efficiency, 57 kWh usable capacity
