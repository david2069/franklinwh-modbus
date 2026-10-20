# FranklinWH Modbus TCP Implementation Guide

> **Definitive reference** for controlling FranklinWH aGate battery systems via Modbus TCP.
> Last verified: 2026-03-08 on aGate X (FW V10R01B04D00)

---

## 1. Connection

```
Host:    YOUR_AGATE_IP (default aGate IP)
Port:    502 (Modbus TCP)
Unit ID: 1 or 2 (both work, DA=1)
Base:    Address 1 (NOT standard 40000 for raw TCP)
Timeout: 10s recommended (WiFi can be slow)
```

```python
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()  # Scans SunSpec models, probes extension writability
```

**Models discovered:** 1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715

---

## 2. What You CAN and CANNOT Do

```
┌─────────────────────────────────────────────────────┐
│ ✅ CAN DO (SunSpec M704):     ❌ CANNOT DO:         │
│  • Charge battery at Xw        • Change mode        │
│  • Discharge battery at Xw     • Set reserve %      │
│  • Set idle (standby)          • Switch to Backup   │
│  • Toggle power factor (PF)    • Set max power cap  │
│  • Read ALL registers          • Control ramp rate  │
│  • Auto-revert (software)      • Use heartbeat      │
└─────────────────────────────────────────────────────┘
```

> Extension registers (15507-15509) are read-only. Writes to the FranklinWH extension registers are undocumented and unconfirmed. FranklinWH has not documented these registers and has never documented any of them as writable. Whether FranklinWH must authorise a Modbus client to write them, and how, is unknown. On `V12R02B60D00` (owner observation, 2026-10-21), writes to 15507–15509 did not take effect: the mode did not switch and the reserves did not change. Treat them as read-only.

---

## 3. Complete Writable Register Map

After exhaustive P1-P4 testing, only **5 of 48 M704 registers** accept writes:

| Register | Address | Type | Works? | What It Does |
|----------|---------|------|--------|---|
| `WSetEna` | 40318 | enum16 | ✅ | Enable/disable battery power control |
| `WSetMod` | 40319 | enum16 | ✅ | Power mode (always set to 0) |
| `WSetPct` | 40324 | int16 | ✅ | **Primary control** — charge/discharge % |
| `WSetRvrtTms` | 40327 | uint32 | ⚠️ | Accepts value, countdown never activates |
| `PFWInjEna` | 40298 | enum16 | ✅ | Power factor enable (on by default) |

**Everything else** — WMaxLimPct, VarSet, WRmp, ControllerHb, LocRemCtl — is either read-only (writes silently discarded) or unimplemented (returns `None`).

---

## 4. How to Control the Battery

### Command Sequence (mandatory 4-step)

```
1. STOP:    WSetEna = 0               (disable control)
2. CONFIG:  WSetMod = 0, WSetPct = -X (set mode + power %)
3. ENABLE:  WSetEna = 1               (enable control)
4. VERIFY:  read WSetPct              (confirm value stuck)
```

> **Sign Convention:** `WSetPct` is **inverted** on FranklinWH. Negative = charge, positive = discharge. The library handles this automatically.

### Python API

```python
from franklinwh_modbus.types import BatteryCommand, ControlMode

# Charge at 3000W
cmd = BatteryCommand(power_watts=3000, mode=ControlMode.LIMIT_ABS)
success, msg = ctrl.send_command(cmd)

# Charge with auto-revert after 1 hour (software timer)
ctrl.send_command(cmd, duration_s=3600)

# Check timer
ctrl.get_command_timer_status()  # {'active': True, 'interval_s': 3600}

# Stop / release control
ctrl.reset_control_state()
```

### CLI

```bash
# Charge at 3000W (fire and forget — persists after CLI exits)
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000

# Charge with auto-revert
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --revert 3600

# Check status (won't kill active commands)
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --status

# Stop
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

---

## 5. Key Hardware Quirks

### 5.1 The LocRemCtl Paradox

M715 `LocRemCtl` (addr 1089) is **read-only, always "Local" (1)**. Per SunSpec 2, this should mean the DER rejects ALL writes. FranklinWH violates this — it **selectively** accepts power writes while ignoring lifecycle features:

| Feature | SunSpec 2 Expects | FranklinWH Does |
|---------|-------------------|-----------------|
| Power writes (WSetPct) | ❌ Reject | ✅ Accepts |
| Reversion countdown | N/A | ⚠️ Not verified with proper sequencing† |
| Controller heartbeat | ❌ Reject | ⚠️ Not verified with proper sequencing† |
| LocRemCtl write | Allow | ❌ Read-only |

**Impact:** All lifecycle features (heartbeat, reversion timer) currently implemented in **software**. †Re-verification with proper SunSpec 6-phase sequencing pending — see `SUNSPEC_DER_SEQUENCING_REFERENCE.md`.

### 5.2 Command Persistence

Commands **persist indefinitely** after disconnect. The aGate holds the last WSetPct value until:
- Another `send_command()` overwrites it
- `reset_control_state()` sets WSetEna=0
- The aGate is power-cycled

There is **no automatic timeout** — hardware reversion (`WSetRvrtTms`) accepts values but never executes. Use the library's software timer (`duration_s` parameter).

### 5.3 Battery State Register Unreliable

M713 `Sta` is **always 0 (OFF)** regardless of actual state. Derive battery state from M714 `DCW`:

```python
if dc_power < -50:   state = 'CHARGING'
elif dc_power > 50:  state = 'DISCHARGING'
else:                state = 'IDLE'
```

### 5.4 Sign Convention

| Register | Software | Hardware |
|----------|----------|----------|
| `WSet` | Positive = Charge | Positive = Charge |
| `WSetPct` | Positive = Charge | **Negative = Charge** |

The library automatically inverts: `m704.WSetPct.value = -pct_raw`

### 5.5 WSet vs WSetPct Conflict

Writing to `WSet` (absolute watts) alongside `WSetPct` causes **mode flickering** on the aGate. The library uses **only WSetPct**. `WSet` is zeroed during `reset_control_state()`.

### 5.6 Extension Registers: Writes Undocumented

| Address | Name | Access | Notes |
|---------|------|--------|-------|
| 15507 | OnGridMode | R (writes undocumented) | 1=Backup, 2=Self-Consumption, 3=TOU |
| 15508 | SelfReserve | R (writes undocumented) | Reserve SOC % |
| 15509 | TouReserve | R (writes undocumented) | ⚠️ **Always mirrors 15508** (firmware defect) |

Writes to the FranklinWH extension registers are undocumented and unconfirmed. FranklinWH has not documented these registers and has never documented any of them as writable. Whether FranklinWH must authorise a Modbus client to write them, and how, is unknown. On `V12R02B60D00` (owner observation, 2026-10-21), writes to 15507–15509 did not take effect: the mode did not switch and the reserves did not change. Treat them as read-only.

The library's setters (`set_native_mode()`, `set_self_consumption_reserve()`, `set_tou_reserve()`) attempt the write, read the register back, and return `(ok, message)` with the read-back result. They do not promise any effect.

Earlier versions of this guide said that writes need a "SPAN Modbus" unlock that FranklinWH enables for SPAN Smart Panel owners, and that a SPAN panel on the network or a cloud `spanFlag` setting predicts writability. That was **speculation (undocumented, unverified)** and has been removed. SPAN is a third-party smart-panel company; nothing here implies any relationship between SPAN and FranklinWH or this library.

#### Checking your unit

`--test-extension-write` (or `ctrl.test_extension_writability()`) writes test values to 15507–15509, reads them back and restores them. ⚠️ It writes to the device. The read-back is the only reliable answer.

#### Mode Control Tiers (Web App)

The admin console defines three control tiers. Tier 1 assumes extension writes work, which is **speculation (undocumented, unverified)**:

| Tier | Method | Capability |
|------|--------|------------|
| ⚡ Tier 1: Extension writes | Direct Modbus register writes (undocumented; not applied on V12R02B60D00) | Full mode/reserve control (Phase 4) |
| ☁️ Tier 2: Cloud Bypass | Mode changes via Cloud API | Mode control, data stays Modbus |
| 📖 Tier 3: Read-Only | View only | No control |

> **TODO:** Mode Control Tier selection should move from MQTT Admin to a **Setup Wizard** — it's a one-time configuration decision, not an MQTT setting.

### 5.7 PFWInjEna (Power Factor)

`PFWInjEna` (40298) is **enabled by default (=1)** and **writable**:
- Enabled (=1): PF ≈ unity (-1 raw, SF -3)
- Disabled (=0): PF = 0.003 (essentially no correction)
- **Do not leave disabled** — it controls the aGate's default PF correction

### 5.8 SunSpec2 Library Quirks

The `sunspec2` Python client remaps addresses internally. Extension registers (15000+, 15500+) must be read via **raw Modbus TCP socket**, not `sunspec2.client.read()`:

```python
import struct
sock = ctrl.dev.client.socket
req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, addr, count)
sock.sendall(req)
resp = sock.recv(256)
```

### 5.9 M715 Address Space

M715 registers are read and written at their **PDU addresses** (1087–1095, as in the FranklinWH PICS). Offsetting by 40000 (PDU 41087+) returned exception 2 (`ILLEGAL_DATA_ADDRESS`) on V10R01B04D00; V12R02B60D00 mirrors the map at 40000. Use the PDU address. The aGate's SunSpec map starts at PDU 0; see QUIRKS, Register Addressing.

---

## 6. Software vs Hardware Features

| Feature | Hardware | Software (Library) |
|---------|----------|-------------------|
| Charge/Discharge | ✅ M704 WSetPct | ✅ `send_command()` |
| Auto-Revert Timer | ❌ WSetRvrtTms broken | ✅ `duration_s` param |
| Heartbeat | ❌ ControllerHb ignored | ❌ Not implemented |
| SoC Ramp | ❌ WRmp unimplemented | ✅ `--soc-ramp-window` |
| Battery State | ❌ M713.Sta always 0 | ✅ Derived from M714 DCW |
| Conflict Detection | N/A | ✅ `check_state()` |
| Mode Control | ❌ Extensions read-only | ⚠️ Virtual modes (power-only) |

---

## 7. Reading System State

```python
# Battery
bat = ctrl.read_battery_status()
# → soc, dc_power, dc_voltage, temperature, battery_state

# Solar + Grid + Load
solar = ctrl.read_solar_production()
grid  = ctrl.read_grid_status()

# Control status
ctl = ctrl.read_control_status()
# → wset_enabled, wset_pct, wset_watts

# Native mode (aGate's cloud setting)
mode = ctrl.read_native_mode()
# → mode_name, self_reserve_pct, tou_reserve_pct

# Health check (zombie state detection)
h = ctrl.healthcheck()
# → healthy, message, recommendations
```

---

## 8. Related Documentation

| Document | What It Covers |
|----------|---------------|
| [DER_CONTROL_REFERENCE.md](./DER_CONTROL_REFERENCE.md) | Full register map — all 48 M704 + 6 M715 fields |
| [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) | Detailed quirk analysis (LocRemCtl, M713, extensions) |
| [ORCHESTRATION_AND_CONTROL.md](./ORCHESTRATION_AND_CONTROL.md) | Command sequences, SoC ramping, entry points |
| `VERIFICATION_BASELINE.md` | Full register dump + cross-verification |

### Test Evidence

| Test | Result | Evidence |
|------|--------|----------|
| P1: Heartbeat | ❌ Confirmed non-functional (6-phase re-test) | `tests/results/2026-03-08_p1_control_tests.md` |
| P1: WSetRvrtTms | ✅ **WORKS** (60s accepted, countdown active) | Re-tested 2026-03-13 with proper sequencing |
| P2: WMaxLimPct | ❌ Confirmed non-functional (enable silently discarded) | `tests/results/2026-03-08_p2p4_control_tests.md` |
| P3: VarSet | ❌ Confirmed non-functional (VarSetEna silently discarded) | Re-tested 2026-03-13 with 6-phase protocol |
| PCS WChaRteMax/WDisChaRteMax | ❌ Confirmed 0xFFFF (not writable) | `tests/results/2026-03-13_pcs_charge_rate_write_probe.md` |
| P4: WRmp | ❌ Unimplemented | Same file |
| PFWInjEna | ✅ Writable | Same file |
| Extension write-probe | ❌ Read-only | `tests/results/2026-03-08_extension_write_probe.md` |

---

*Device: FranklinWH aGate X (SN: XXXXXXXXXXXXXXXXXXXX, FW: V10R01B04D00)*
*Last Updated: 2026-03-09*
