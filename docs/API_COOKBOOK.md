# API Cookbook

Worked examples for `franklinwh-modbus`: read the aGate, control the battery, and use the FranklinWH extension registers. The TUI monitor is the showcase. Every panel and key is mapped to the API call behind it, so you can rebuild any part of it in your own code.

> **Before you start**
>
> - **One Modbus client per aGate.** The aGate serves one Modbus TCP client at a time. Stop any bridge, Home Assistant integration or other tool before running these examples, or they will fight over the connection.
> - **Reads are safe; writes change your system.** Every example that writes is marked ⚠️. Try those with `dry_run=True` first.
> - **Addresses are Modbus PDU addresses** (0-based, as sent on the wire). See [SunSpec Quirks → Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map).
> - Examples use `192.0.2.10` for the aGate's IP; use yours.

---

## 1. Connect and disconnect

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController(ip_address="192.0.2.10")   # port 502, unit id 2 by default
if not ctrl.connect():                                 # scans the SunSpec models (map at PDU 0)
    raise SystemExit(f"Could not connect: {ctrl.last_error}")
try:
    ...                                                # your reads and commands
finally:
    ctrl.disconnect()                                  # always: frees the aGate's single client slot
```

| Call | What it does | Writes? |
|---|---|---|
| `connect()` | Opens the TCP session, scans for the "SunS" marker and models, and reads the M702 power ratings. **Never writes** (since 0.9.6). | No |
| `disconnect()` | Closes the session. | No |
| `is_connected()` | Reads the "SunS" marker to check the link. | No |
| `reconnect()` | Closes and reopens the session and rescans. | No |
| `data_age_s`, `consecutive_failures`, `last_error` | Link health: seconds since the last good read, failed reads in a row, and the last error. | No |

---

## 2. A status snapshot: power, state and energy

```python
bat   = ctrl.read_battery_status()   # M713 + M714
grid  = ctrl.read_grid_status()      # M701
solar = ctrl.read_solar_status()     # M502 + extension registers 15500–15513, 16000
mode  = ctrl.read_native_mode()      # extension registers 15507–15509
ext   = solar.get("extension") or {}

# Instantaneous power (W). Use .get(): a model that fails is left out and listed in 'partial'
solar_w   = solar.get("total_solar_w", solar.get("ac_power_w"))
battery_w = bat.get("battery_power_w")     # + discharging, − charging (M714 DCW)
grid_w    = grid.get("grid_power_w")       # + import, − export (M701 W)
home_w    = ext.get("home_load_ext")       # 16000 (~1 W), else 15506 (~100 W steps)
soc       = bat.get("soc")                 # %

# Operating state
mode_name = mode.get("mode_name")          # see §8.3 on mode codes
bat_state = bat.get("battery_state")       # "Charging" / "Discharging" / "Idle" (±50 W deadband)
grid_ok   = grid.get("connection_state") == "Connected"   # M701 ConnSt

# Energy (Wh): lifetime counters only; Modbus has no daily totals
grid_in_wh  = grid.get("grid_import_wh")   # M701 TotWhAbs
grid_out_wh = grid.get("grid_export_wh")   # M701 TotWhInj

# Was anything missing this poll?
missing = bat.get("partial", []) + solar.get("partial", [])
```

For a daily figure, store a lifetime reading at midnight and subtract it from the current one.

### Every field, by method

| Method | Keys |
|---|---|
| `read_battery_status()` | `soc`, `soh`, `wh_rating`, `wh_available`, `battery_power_w`, `battery_state`, `battery_current_a`, `battery_temp_c`, `individual_batteries` (per port: `port`, `power_w`, `voltage_v`, `current_a`, `temp_c`), `status_raw`, `partial` |
| `read_grid_status()` | `grid_power_w`, `grid_va`, `grid_var`, `voltage_v`, `frequency_hz`, `current_a`, `power_factor`, `connection_state`, `inverter_state`, `grid_mode`, `ac_type`, `ambient_temp_c`, `cabinet_temp_c`, `grid_import_wh`, `grid_export_wh` |
| `read_solar_status()` | `ac_power_w`, `total_solar_w`, `battery_dc_power_w`, `extension` (`pv_total`, `pv_proximal`, `pv_remote1`, `pv_remote2`, `total_solar`, `home_load_ext`, `home_load_ext_quantized`, `ongrid_mode`, `self_reserve`, `tou_reserve`), `partial` |
| `read_native_mode()` | `mode_raw`, `mode_name`, `self_reserve_pct`, `tou_reserve_pct` |
| `read_control_status()` | `wset_enabled`, `wset_pct`, `wset_pct_raw`, `wset_watts`, `wset_mode`, `loc_rem_ctl`, `loc_rem_ctl_name`, `wset_revert_watts`, `wset_revert_time_s`, `wset_revert_remain_s` |
| `read_nameplate()` | `manufacturer`, `model`, `serial`, `version` |
| `read_alarms()` | `system_alrm`, `dc_port_alrm`, `battery_sta`, `solar_evt`, `vendor_info`, `decoded`, `error` |

A failed read returns `{}`, or a result with `partial`/`error`, and is logged at warning level. Check `partial` and `error` before trusting a zero.

---

## 3. The TUI monitor as a showcase

```bash
python3 tools/franklinwh_cli.py -i 192.0.2.10 --monitor            # dark theme
python3 tools/franklinwh_cli.py -i 192.0.2.10 --monitor --theme amber -q
```

Or from Python:

```python
from franklinwh_modbus import CLIMonitor, MonitorConfig, HAS_MONITOR

if HAS_MONITOR:                                   # needs the 'rich' extra
    CLIMonitor(MonitorConfig(ip_address="192.0.2.10", refresh_rate=5.0, theme="dark")).run()
```

Each refresh calls six read methods once (`CLIMonitor.fetch_data()` in `monitor.py`), then draws the panels from the results.

### 3.1 Panels → API

| Panel | Shows | API call and keys | Registers |
|---|---|---|---|
| **Power Flow Summary** | Solar, battery, grid and home W, plus battery state | `read_solar_status()['extension']['total_solar']`, `read_battery_status()['battery_power_w']` and `['battery_state']`, `read_grid_status()['grid_power_w']`, `...['extension']['home_load_ext']` | 15502, M714 DCW, M701 W, 16000/15506 |
| **Battery State of Charge** | SoC bar, active reserve, SC and TOU reserves | `read_battery_status()['soc']`, `get_effective_reserve_level()`, `read_native_mode()['self_reserve_pct']` and `['tou_reserve_pct']` | M713 SoC, 15507–15509 |
| **DC Power (Battery)** | DC W and A, temperature, SoH, available and rated Wh | `read_battery_status()`: `battery_power_w`, `battery_current_a`, `battery_temp_c`, `soh`, `wh_available`, `wh_rating` | M714, M713 |
| **AC Power** | V, A, Hz, PF, VA, VAR, grid mode, AC type | `read_grid_status()`: `voltage_v`, `current_a`, `frequency_hz`, `power_factor`, `grid_va`, `grid_var`, `grid_mode`, `ac_type` | M701 |
| **Solar AC Inputs** | Total, proximal and remote 1/2 W | `read_solar_status()['extension']`: `total_solar`, `pv_proximal`, `pv_remote1`, `pv_remote2` | 15502–15505 |
| **Lifetime Energy** | Battery charged/discharged, grid import/export, solar generated | `read_grid_status()['grid_import_wh']` and `['grid_export_wh']`; battery from `get_model(714)` `DCWhAbs`/`DCWhInj` (see §3.3) | M701, M714, M502 |
| **Power Timeline (60 min)** | Sparkline of battery, solar and grid | The panel's own history of the values above | — |
| **Device Info** | Model, serial, firmware, mode, control source | `read_nameplate()`, `read_native_mode()['mode_name']`, `read_control_status()['wset_enabled']` and `['loc_rem_ctl_name']` | M1, 15507, M704, M715 |
| **Alarms & Status** | Active alarms | `read_alarms()`, `active_alarms()` | M701, M713, M714, M502 |
| **Command Console** | The result of each key command | Results of the calls in §3.2 | — |

If the home load register reads 0, the TUI falls back to a balance: `home = solar + battery + grid`.

### 3.2 Keys → API

| Key | TUI action | Equivalent call | Writes? |
|---|---|---|---|
| `c` + watts | Charge | `send_command(BatteryCommand(power_watts=+W))` | ⚠️ M704 |
| `d` + watts | Discharge | `send_command(BatteryCommand(power_watts=-W))` | ⚠️ M704 |
| `s` | Standby (0 W, keep control) | `send_command(BatteryCommand(power_watts=0))` | ⚠️ M704 |
| `r` | Release control to the aGate | `reset_control_state()` | ⚠️ M704 |
| `m` / `M` | Max charge / max discharge | `send_command(BatteryCommand(power_watts=±ctrl.RATED_MAX_CHARGE_W))` | ⚠️ M704 |
| `+` / `-` | ±100 W from the current setting | `send_command(...)` with the adjusted value | ⚠️ M704 |
| `o` + 1–4 | Native mode | `set_native_mode(n)` | ⚠️ 15507 |
| `v` + % | Self-consumption reserve | `set_self_consumption_reserve(pct)` | ⚠️ 15508 |
| `t` + % | TOU reserve | `set_tou_reserve(pct)` | ⚠️ 15509 |
| `R`, `1`–`9`, `h`, `q` | Pause, refresh rate, help, quit | — | No |

> The `o`, `v` and `t` keys appear only when the extension registers are known to be writable, which currently requires running the write test first. See #73.

### 3.3 Build your own panel: lifetime energy

The TUI reads battery lifetime energy straight from model 714, which the library doesn't wrap yet:

```python
m714 = ctrl.get_model(714)
m714.read()
sf = ctrl._get_scale_factor(m714, 'DCWH_SF') or 0
ports = m714.blocks[1:] if len(getattr(m714, 'blocks', [])) > 1 else [m714]
charged_wh    = sum(p.DCWhAbs.value * 10**sf for p in ports if p.DCWhAbs.value is not None)
discharged_wh = sum(p.DCWhInj.value * 10**sf for p in ports if p.DCWhInj.value is not None)
```

---

## 4. CLI commands with their Python equivalents

All commands take `-i <aGate IP>`. Add `--dry-run` to any control command to see what it would send without writing.

| Command | Does | Python equivalent | Writes? |
|---|---|---|---|
| `--status` (`--detail` for everything) | Status summary | the reads in §2 | No |
| `--healthcheck` | Health report | `ctrl.healthcheck()` → `HealthStatus(healthy, message, recommendations, details)` | No |
| `--check-alarms` | Lists alarms; exits 1 on any active alarm or a failed read | `ctrl.active_alarms()` | No |
| `--monitor` | TUI | `CLIMonitor(...).run()` | Only on key commands |
| `--charge W` / `--discharge W` | Charge or discharge at W | `ctrl.dispatch('charge', W)` / `ctrl.dispatch('discharge', W)` | ⚠️ M704 |
| `--max-charge` / `--max-discharge` | At the M702 rating | `ctrl.dispatch('charge', 'max')` | ⚠️ M704 |
| `--standby` | 0 W, keep control | `ctrl.dispatch('standby')` | ⚠️ M704 |
| `--stop` | Release control | `ctrl.dispatch('stop')` or `ctrl.reset_control_state()` | ⚠️ M704 |
| `--revert SECONDS` | Software timer that releases control | `send_command(cmd, duration_s=S)`; see the warning in §5 | ⚠️ M704 |
| `--target-soc-auto PCT` | Stop when SoC reaches PCT | `ctrl.dispatch('charge', W, target_soc=PCT, blocking=True)` | ⚠️ M704 |
| `--mode backup\|self\|tou` | Native mode | `ctrl.set_native_mode(n)`; see §8.3 first | ⚠️ 15507 |
| `--self-reserve PCT` / `--tou-reserve PCT` | Reserves | `set_self_consumption_reserve(pct)` / `set_tou_reserve(pct)` | ⚠️ 15508 / 15509 |
| `--vmode self\|tou\|peak-shave\|…` | Software ("virtual") mode loop | `VirtualModeController`, §6 | ⚠️ M704 |
| `--clear-alarms` | Reset alarms | `ctrl.clear_alarms()` | ⚠️ M715 AlarmReset |
| `--test-extension-write` | Tests whether 15507–15509 are writable | `ctrl.test_extension_writability()` | ⚠️ **writes test values to mode and reserves** |

```bash
python3 tools/franklinwh_cli.py -i 192.0.2.10 --status --detail
python3 tools/franklinwh_cli.py -i 192.0.2.10 --charge 2000 --revert 600 --dry-run
python3 tools/franklinwh_cli.py -i 192.0.2.10 --stop
```

---

## 5. Battery control from Python ⚠️

Sign convention for commands: **positive = charge, negative = discharge, 0 = standby.**

```python
from franklinwh_modbus import BatteryCommand

ok, msg = ctrl.send_command(BatteryCommand(power_watts=2000), dry_run=True)   # preview
ok, msg = ctrl.send_command(BatteryCommand(power_watts=2000))                 # charge 2 kW

check = ctrl.verify_dispatch(expected_w=2000, timeout_s=20)   # did the battery actually respond?
print(check["ok"], check["actual_w"], check["reason"])

ctrl.reset_control_state()   # release control: WSetEna=0, verified by reading it back
```

High-level alternative with durations and percentages:

```python
ctrl.dispatch('discharge', '40%', duration='30m')           # 40 %, sent as WSetPct (percent), for 30 minutes
ctrl.dispatch('charge', 'max', target_soc=90, blocking=True)
ctrl.dispatch('stop')
```

- **Over-limit requests are clamped to the M702 rating, keeping the direction** (#28). The aGate itself does no range check (PICS Issue 5).
- **Release control yourself.** The aGate's own revert timer (`WSetRvrtTms`) counts down but doesn't release. `duration_s` and `--revert` run a software timer on a background thread, **without your lock** (#54). If you share the controller across threads, release from your own watchdog instead.
- **Releasing control on exit:** in 0.10.0, stopping a virtual mode could skip the release (#71). Upgrade to the release that fixes #71, or call `reset_control_state()` yourself.

### 5.1 Recording every write

Pass `write_trace` to get one `WriteRecord` for every Modbus write the library sends, with the aGate's reply. It covers model writes (`send_command`, `reset_control_state`, …), the extension setters and `clear_alarms`. It is off by default.

```python
from franklinwh_modbus import FranklinWHController, WriteRecord

writes: list[WriteRecord] = []
ctrl = FranklinWHController("192.0.2.110", unit_id=1, write_trace=writes.append)
ctrl.write_source = "schedule:evening"   # passed through unchanged; you decide what it means

for w in writes:
    print(w.describe())
# e.g. for a refused percent write:
# Modbus write FC06 40324 704.WSetPct [0xFF9C] -> exception 3, firmware V12R02B60D00, source schedule:evening
```

| Field | Meaning |
|---|---|
| `timestamp` | Epoch seconds (UTC) |
| `address`, `function` | PDU address; 6 for one register, 16 for several |
| `values` | Raw uint16 register values as sent |
| `ok` | True only for a normal write response |
| `exception_code` | The Modbus exception code when the aGate refuses, e.g. 3 |
| `error` | Any other failure: short response, socket error |
| `point` | `'<model>.<point>'` when the address is a scanned SunSpec point, else `None` |
| `firmware` | M1 `Vr` when known |
| `source` | `ctrl.write_source` at the time of the write |

A callback that raises is logged and never affects the write. Without a callback, the same records go to the `franklinwh_modbus.writes` logger at DEBUG. Storing, showing and exporting them is up to your application. `SunSpecSequencer(..., write_trace=...)` records the sequencer's raw writes the same way.

---

## 6. Virtual modes ⚠️

Software modes that compute a battery command each tick from live readings:

```python
from franklinwh_modbus import VirtualModeController, VirtualMode, run_with_signal_handling

vmc = VirtualModeController(ctrl, min_discharge_soc=20, max_charge_soc=95)
vmc.set_mode(VirtualMode.SELF_CONSUMPTION, dry_run=True)   # compute and report only
vmc.set_mode(VirtualMode.PEAK_SHAVE, peak_shave_threshold=3000)  # applies immediately
run_with_signal_handling(vmc, duration_seconds=3600)       # Ctrl+C releases control
```

Modes: `SELF_CONSUMPTION`, `TIME_OF_USE`, `PEAK_SHAVE`, `GRID_ZERO`, `EMERGENCY_BACKUP`, `MANUAL`. The SoC limiter ramps commands near `min_discharge_soc` and `max_charge_soc`.

---

## 7. Alarms and health

The library **reports**; your code **decides** what an alarm means for operation.

```python
alarms = ctrl.read_alarms()
if alarms.get("error"):
    print("Could not read alarms:", alarms["error"])     # never treat this as "no alarms"
for name in ctrl.active_alarms(alarms):                   # e.g. "GROUND_FAULT", "Port 1: OVER_TEMP"
    print(name)

health = ctrl.healthcheck()
print(health.healthy, health.message, health.details.get("alarms"))
```

Names come from the SunSpec model definitions (M701 `Alrm`, M714 per-port `DCAlrm`, M502 `Evt`, M713 `Sta`). `check_blocking_alarms()` is deprecated.

---

## 8. FranklinWH extension registers

### 8.1 What they are

Alongside the SunSpec models, FranklinWH exposes **proprietary holding registers** for things SunSpec doesn't cover: the operating mode, the reserves, the solar breakdown and the home load.

- **They sit outside the SunSpec model chain.** sunspec2 can't see them, so the library reads them with plain FC3 requests at their **PDU address**.
- **Read them directly at the address listed.** Don't offset by 40000 or 40001: a 40000 offset hasn't been tested for extension registers, and on V10R01B04D00 it returned exception 2.
- **They are vendor-specific and partly undocumented.** Behaviour can change with firmware. Treat every value as "measured on firmware X on date Y", not as a specification.

### 8.2 Map

The full register list, with access, units, library accessors and evidence, is on its own page: **[FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md)**. In short: 15502–15506 solar and home load, 15507 mode, 15508–15509 reserves, 15510–15513 PV energy, and 16000 high-resolution home load.

### 8.3 Reading them yourself

```python
import struct

def read_ext(ctrl, pdu, count=1):
    """FC3 read of extension holding registers at their PDU address."""
    sock = ctrl.dev.client.socket
    sock.sendall(struct.pack('>HHHBBHH', 0, 0, 6, ctrl.unit_id, 3, pdu, count))
    resp = sock.recv(9 + 2 * count)
    if resp[7] & 0x80:                      # exception response
        raise IOError(f"Modbus exception {resp[8]} at PDU {pdu}")
    return list(struct.unpack(f'>{count}H', resp[9:9 + 2 * count]))

mode_raw, sc_reserve, tou_reserve = read_ext(ctrl, 15507, 3)
```

Prefer `read_native_mode()` and `read_solar_status()`, which already do this and handle failures. Use your own reads only for registers the library doesn't wrap.

**Mode codes:** compare modes by **name** (`mode_name`), not by number. The code and the QUIRKS doc currently disagree on 15507's values, and the cloud API uses its own numbering (#75).

### 8.4 Writing them ⚠️

- `set_native_mode()`, `set_self_consumption_reserve()` and `set_tou_reserve()` write the register and read it back. Each returns `(ok, message)`, and `dry_run=True` previews.
- Writes are accepted only on units where FranklinWH has enabled them. Elsewhere they fail silently, which is why the setters read back.
- `connect()` never writes. `test_extension_writability()` **does**: it writes test values to the mode and reserves and then restores them, so run it only when you mean to.
- Wait until #75 is resolved before writing modes 1, 3 or 4.

---

## 9. Modbus vs the FranklinWH cloud API

See **[Modbus TCP vs Cloud API — Metrics Comparison](MODBUS_CLOUD_COMPARISON.md)** for a field-by-field map, with units, signs, grid states, energy and evidence labels. For the cloud side, see the [franklinwh-cloud API Cookbook](https://david2069.github.io/franklinwh-cloud/API_COOKBOOK/).
