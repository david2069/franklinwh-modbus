# Modbus TCP vs Cloud API — Metrics Comparison

The same aGate can be read two ways:

- **Modbus TCP Server (aGate :502)**: read locally by a Modbus client such as this library, `franklinwh-modbus`.
- **Cloud API**: [franklinwh-cloud](https://github.com/david2069/franklinwh-cloud) `get_stats()` over the FranklinWH cloud (`getDeviceCompositeInfo`, cmdType 203, `result.runtimeData`).

This page maps each metric across the two. franklinwh-cloud keeps its own copy of this table, linked to its own examples: **[Cloud API vs Modbus TCP](https://david2069.github.io/franklinwh-cloud/MODBUS_CLOUD_COMPARISON/)**. The two are maintained separately on purpose. Code examples for every Modbus field are in the [API Cookbook](API_COOKBOOK.md#2-a-status-snapshot-power-state-and-energy).

> **Evidence.** Modbus names are from this library's `develop` (`controller.py`). Cloud names, units and signs are from franklinwh-cloud's code (`models.py`, `mixins/stats.py`, `const/modes.py`), as reported by its maintainer session on 2026-10-19. A mapping marked **INFERRED** or **ASSUMED** has not been confirmed by a side-by-side capture. One site's data is a candidate, not a rule.

## Units and signs

| | Modbus client | Cloud API |
|---|---|---|
| Power | W | kW |
| Energy | Wh, **lifetime** counters | kWh, **daily** (resets at local midnight; ASSUMED site-local) |
| Grid sign | `+` import (per these docs; unconfirmed on device) | `+` import, `−` export |
| Battery sign | `−` charging | `−` charging, `+` discharging |

The cloud grid sign was observed live on 2026-10-17: `grid_use` = −2.7 kW while exporting (solar 2.9 kW, home 0.2 kW).

## Power and state

| Metric | Modbus (franklinwh-modbus) | Modbus source | Cloud (`stats.current.…`) | Cloud raw key | Notes |
|---|---|---|---|---|---|
| Solar power | `read_solar_status()['total_solar_w']`, else `['ac_power_w']` (W) | Extension total, else M502 `OutPw` | `solar_production` (kW) | `p_sun` | |
| Generator power | — | — | `generator_production` (kW) | `p_gen` | Not over Modbus |
| Battery power | `read_battery_status()['battery_power_w']` (W) | M714 `DCW`, summed over ports | `battery_use` (kW) | `p_fhp` | Modbus is the DC side; whether `p_fhp` is AC or DC is unknown, so the equivalence is **INFERRED** |
| Grid power | `read_grid_status()['grid_power_w']` (W) | M701 `W` | `grid_use` (kW) | `p_uti` | Same sign convention (see above) |
| Home load | `read_solar_status()['extension']['home_load_ext']` (W) | Extension 16000 (~1 W), else 15506 (~100 W steps) | `home_load` (kW) | `p_load` | 16000 is undocumented |
| Battery SoC | `read_battery_status()['soc']` (%) | M713 `SoC` | `battery_soc` (%) | `soc` | |
| Smart circuit / V2L power | — | — | `switch_1_load`, `switch_2_load`, `v2l_use` (kW) | cmdType 311 (not composite) | Cloud only |
| Operating mode | `read_native_mode()['mode_name']` | Extension 15507 | `work_mode` / `work_mode_desc` | `result.currentWorkMode` (1 TOU, 2 Self-Consumption, 3 Emergency Backup) | Compare by **name**: the 15507 values in this library are under review (#75). The mode doesn't change during a remote dispatch (see the VPP row) |
| Active programme | — | — | `tou_mode` / `tou_mode_desc` | `runtimeData.mode` / `.name` | A programme ID, **not** a run status |
| Run status | No direct register; nearest is `read_battery_status()['battery_state']` | M714 `DCW` sign with a ±50 W deadband | `run_status` / `run_status_desc` | `runtimeData.run_status` | **INFERRED** mapping |
| External control (VPP) | `read_control_status()['wset_enabled']` | M704 `WSetEna` | `tou_mode == 9`, `effective_mode == "VPP mode"` | `runtimeData.mode` = 9 | The cloud showed `mode` 9 within a minute of a Modbus force discharge (one site, 2026-10-14). See [VPP Mode Reference](VPP_MODE_REFERENCE.md) |
| Grid connection | `read_grid_status()['connection_state']` (3 states) | M701 `ConnSt` | `grid_connection_state` (4 states) | Derived; see below | Closest raw cloud field: `main_sw[0]` |

### Grid connection: 3 Modbus states vs 4 cloud states

The cloud value is **derived**, not read from one field ([cloud page](https://david2069.github.io/franklinwh-cloud/MODBUS_CLOUD_COMPARISON/)):

| Modbus `ConnSt` | Cloud state | How the cloud library decides |
|---|---|---|
| Connected | `CONNECTED` | `main_sw[0] == 1` (grid relay closed) |
| Disconnected (**INFERRED**) | `OUTAGE` | `offGridFlag` set, or relay open and `offgridState == 0` |
| Disconnected (**INFERRED**) | `SIMULATED_OFF_GRID` | Relay open (or `offgridreason` set) and `selectOffgrid` → `offgridState == 1` |
| — | `NOT_GRID_TIED` | Site configured with no grid |
| Fault | — | No cloud counterpart identified |

Modbus can't tell a user-simulated island from a real outage; the cloud needs an extra `selectOffgrid` call for that.

## Energy

| Metric | Modbus (lifetime Wh) | Modbus source | Cloud (`stats.totals.…`, daily kWh) | Cloud raw key | Notes |
|---|---|---|---|---|---|
| Solar | — | — | `solar` | `kwh_sun` | Not over Modbus |
| Generator | — | — | `generator` | `kwh_gen` | Not over Modbus |
| Grid import | `read_grid_status()['grid_import_wh']` | M701 `TotWhAbs` | `grid_import` | `kwh_uti_in` | Modbus daily = difference of two readings |
| Grid export | `read_grid_status()['grid_export_wh']` | M701 `TotWhInj` | `grid_export` | `kwh_uti_out` | As above |
| Battery charge | The TUI reads it; a library wrapper is queued ([example](API_COOKBOOK.md#33-build-your-own-panel-lifetime-energy)) | M714 `DCWhAbs` | `battery_charge` | `kwh_fhp_chg` | |
| Battery discharge | The TUI reads it; a library wrapper is queued ([example](API_COOKBOOK.md#33-build-your-own-panel-lifetime-energy)) | M714 `DCWhInj` | `battery_discharge` | `kwh_fhp_di` | |
| Home | — | — | `home_use` | `kwh_load` | Not over Modbus |

For a cloud **lifetime** figure to compare with the Modbus counters, franklinwh-cloud uses `get_power_details(type=5, …)`. Nobody has checked yet whether the cloud lifetime total and the Modbus counter agree.

## Modbus-only data

See the [API Cookbook](API_COOKBOOK.md#every-field-by-method) for every key.

- **Battery:** SoH, capacity (`wh_rating`, `wh_available`), DC current and temperature, and a per-battery breakdown.
- **Grid:** voltage, frequency, VA, VAR, power factor and temperatures. The cloud has some of these via `get_stats(include_electrical=True)`: cmdType 211, an extra call.
- **Reserves:** extension 15508 and 15509. 15509 repeats 15508 on current firmware (#63).
- **Read quality and control state:** remote-control state, and the `partial` and `error` read-quality flags.

## Choosing a source

| | Modbus TCP Server (aGate :502) | Cloud API |
|---|---|---|
| Network | Local LAN only | Internet + FranklinWH cloud |
| Clients | **One Modbus client at a time** | Rate limits shared per account |
| Daily totals, solar/home energy, programme name | No | Yes |
| Electrical detail, per-battery data | Yes | Partial |
| Tells simulated off-grid from outage | No | Yes |
