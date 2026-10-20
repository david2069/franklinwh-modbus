# FranklinWH aGate SunSpec Implementation Quirks

Documenting non-standard behaviors, missing registers, and implementation-specific issues discovered during development.

---

## Model 713 - DER Storage Capacity

### Sta (Status) Register Always 0

**Issue:** The `Sta` register in Model 713 always returns 0 (OFF) regardless of actual battery state.

**SunSpec 2 M713.Sta enum:**
| Value | Meaning |
|-------|---------|
| 0 | OFF |
| 1 | EMPTY |
| 2 | DISCHARGING |
| 3 | CHARGING |
| 4 | FULL |
| 5 | HOLDING |
| 6 | TESTING |

**Observed:** Battery actively charging at -400W (M714.DCW), SoC 79% — M713.Sta remains 0 (OFF).

**Workaround:** Derive battery state from M714 DCW power direction (±50W deadband):
```python
# M714.DCW sign convention (confirmed empirically 2026-03-10):
#   positive = power INTO battery (Charging)
#   negative = power OUT of battery (Discharging)
if dc_power > 50:
    state = 'CHARGING'
elif dc_power < -50:
    state = 'DISCHARGING'
else:
    state = 'IDLE'
```

**Code Location:** `src/franklinwh_modbus/controller.py:read_battery_status()` — returns `battery_state` (derived) and `status_raw` (M713.Sta, always 0)

---

## Model 714 - Battery DC Measurements

### DCA (DC Current) Register Not Populated
**Issue:** The DCA register in Model 714 returns 0 or is not implemented.

**Standard SunSpec Model 714 Fields:**
- `DCW` - DC Power (W) ✅ **Working** — positive=charging (into battery), negative=discharging (out of battery)
- `DCV` - DC Voltage (V): listed as working (undated, V10). **Reads 0 on V12R02B60D00** (port block 1062–1086 all zero, 2026-10-20) 
- `DCA` - DC Current (A) ❌ **Not populated (returns 0)**
- `Tmp` - Battery Temperature (°C): listed as working (undated, V10). **Reads 0 on V12R02B60D00** (2026-10-20)
- `DCWhInj` - DC Energy Injected (Wh) ✅ **Working** — lifetime discharged
- `DCWhAbs` - DC Energy Absorbed (Wh) ✅ **Working** — lifetime charged

**Workaround:** Calculate current from Power/Voltage:
- **Single-Battery System (`NPrt = 1`)**:
  ```python
  dc_current = dc_power / dc_voltage  # Ohm's Law: I = P/V
  ```
- **Multi-Battery System (`NPrt > 1`)**:
  For systems with multiple batteries connected in parallel, the library sums the DC Power (`DCW`) and averages the DC Voltage (`DCV`) across all active repeating blocks (ports) first, then divides to get total system DC current:
  ```python
  avg_voltage = sum(voltages) / len(voltages)
  total_current = total_dc_power / avg_voltage
  ```

**Code Location:** `src/franklinwh_modbus/controller.py:read_battery_status()` (M714 section)

---

## Model 701 - Inverter Measurements

### TmpAmb and TmpCab Implementation
**Status:** ✅ **Working as of aGate firmware**

FranklinWH aGate X implements these temperature registers:
- `TmpAmb` (40105) - Ambient temperature
- `TmpCab` (40106) - Cabinet temperature

Earlier firmware versions may not expose these.

### TotWhInj and TotWhAbs — AC Lifetime Energy Accumulators
**Status:** ✅ **Working** (confirmed 2026-03-23)

The M701 AC lifetime energy accumulators report cumulative grid energy (Wh, acc64 with `TotWh_SF`):

- `TotWhInj` (40089) — Total Energy Injected: lifetime grid **export** (DER → grid)
- `TotWhAbs` (40093) — Total Energy Absorbed: lifetime grid **import** (grid → DER, e.g. grid-charging battery)

These are separate from the M714 DC battery accumulators (`DCWhInj`/`DCWhAbs`). Both register sets are independently useful:

| Register | Model | Measures | Example Value |
|----------|-------|----------|---------------|
| `TotWhInj` | M701 (AC) | Grid export (inverter → grid) | ~4.46 MWh |
| `TotWhAbs` | M701 (AC) | Grid import (grid → inverter) | ~1.32 MWh |
| `DCWhInj` | M714 (DC) | Battery discharged | ~5.84 MWh |
| `DCWhAbs` | M714 (DC) | Battery charged | ~5.96 MWh |

**Code Location:** `src/franklinwh_modbus/controller.py:read_grid_status()` returns `grid_export_wh` and `grid_import_wh`

### DERMode Bitfield — PV Curtailment (PV_CLIPPED)

**Status:** ✅ **Supported per PICS conformance (M701, Address 78)**

The DERMode register is a bitfield indicating the current DER operating mode:

| Bit | Name | Description |
|:---:|------|-------------|
| 0 | `GRID_FOLLOWING` | Normal grid-connected operation (frequency/voltage follows grid) |
| 1 | `GRID_FORMING` | Off-grid/island mode (aPower generates its own AC reference) |
| 2 | `PV_CLIPPED` | PV curtailment active — solar output is being limited |

!!! important
    **PV_CLIPPED is a FranklinWH-specific operational state**, most relevant in **off-grid/backup mode**. When the aPower switches to Grid Forming (bit 1), it can only handle a limited amount of solar input. If a solar inverter (e.g., SolarEdge SE 11400) produces more power than a single aPower can absorb (~6kW), the aPower signals PV curtailment through DERMode bit 2.
        FranklinWH recommends:
    - **Single aPower:** Derate solar inverter using SolarEdge PRI (Power Reduction Interface) to keep off-grid peak below 6kW
    - **Two aPowers:** Provides sufficient capacity for larger solar arrays without curtailment
        **References:**
    - [SolarEdge De-rate in Off-Grid Mode](https://service.franklinwh.com/en/support/solutions/articles/73000622969-solar-edge-string-inverter-de-rate-in-off-grid-back-up-mode)
    - FranklinWH PV Curtailment White Paper (PDF)

**Code:** `controller.py` reads DERMode as `grid_mode`:
```python
# Bit 0 = Grid Following, Bit 1 = Grid Forming, Bit 2 = PV Clipped
if der_mode_raw & (1 << 2):
    grid_mode = 'PV Clipped'
elif der_mode_raw & (1 << 1):
    grid_mode = 'Grid Forming'
elif der_mode_raw & (1 << 0):
    grid_mode = 'Grid Following'
```

!!! note
    We have not directly observed `PV_CLIPPED` in testing — our system has no solar at night and operates on-grid. This bit would only appear during daytime off-grid events with active PV curtailment.

---

## Extension Registers

The FranklinWH extension registers (15000–15043, 15500–15513, 16000–16002), with access, units, library accessors and evidence, are listed in one place: **[FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md)**.

Quirks covered there:
- 15509 (TOU reserve) reads the same value as 15508 on **V10R01B04D00** (confirmed 2026-10-18). This is **fixed on V12R02B60D00**, where 15509 holds the TOU reserve (2026-10-20/21; [snapshot](SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md); #63).
- The 15507 operating-mode values are under review (#75).
- 16000 gives the home load at ~1 W resolution (15506 is in ~100 W steps).

### Official SunSpec PICS Reference

FranklinWH's SunSpec Alliance certification document is the PICS spreadsheet *UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx*. It is FranklinWH's proprietary document and is **not distributed in this repository** (removed before the public release, 2026-03-17); obtain it from FranklinWH.

This XLSX documents:
- "Unimplemented" info points, listed by PDU address (owner-confirmed: e.g. ControllerHb 1092)
- Extension register definitions (SPAN tab)
- The SOC reserve defect

!!! warning
    **We do not fully trust this document.** Our live testing has found discrepancies between what the PICS document claims and actual aGate behavior. Always verify against the live device. Use the PICS as a starting point, not ground truth.

Register-by-register PICS findings: [PICS Conformance](PICS_CONFORMANCE_CROSS_REFERENCE.md).

---

## Extension Registers (15000–15043) — Undocumented

Mirrors of SunSpec values (e.g. 15020 = M713 `WHRtg`). Writes are accepted at protocol level but silently discarded (write probe, 2026-03-08). The aGate answers on every unit ID with the same device. See [FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md) and the raw scans in the [Extensions Manifest](FRANKLINWH_EXTENSIONS_MANIFEST.md).

---

## Model 704 - Battery Control

### WSet vs WSetPct Sign Convention
**Issue:** Hardware uses inverted sign convention for WSetPct.

| Parameter | Software Convention | Hardware Convention |
|-----------|---------------------|---------------------|
| `WSet` | Positive=Charge | Positive=Charge |
| `WSetPct` | Positive=Charge | **Negative=Charge** |

**Workaround:** Always invert WSetPct value when writing:
```python
m704.WSetPct.value = -pct_raw  # Invert for hardware
```

---

## ⚠️ Write Access Asymmetry & Remote Control Handoff

> **This is the most significant implementation quirk affecting library design.**

### Control Architecture: Remote Control Clean Handoff

When `WSetEna=1` is written to M704, the aGate **automatically activates Remote Control** (mobile app displays this as "VPP Mode"). This is a **clean handoff**, not a split-brain architecture:

1. **`WSetEna=1`** → aGate activates Remote Control, native mode (Self-Consumption/TOU) is **suspended**
2. **M704 commands** control battery power exclusively while Remote Control is active
3. **`WSetEna=0`** → Remote Control deactivates, native mode **cleanly resumes**

See [VPP_MODE_REFERENCE.md](VPP_MODE_REFERENCE.md) for the Remote Control visual reference (mobile app screenshots show "VPP Mode").

### Write Access Table

| Control Plane | Registers | Read | Write | What It Controls |
|---------------|-----------|------|-------|------------------|
| **SunSpec M704** | 40318-40354 | ✅ | ✅ | Battery power via Remote Control (WSet, WSetPct, WSetEna) |
| **FranklinWH Extensions** | 15507-15509 | ✅ | ❌ Read-Only* | Operating mode, SoC reserves |
| **M702 Rate Settings** | 40259-40262 | ✅ | ❌ (tested 2026-03-13) | Charge/discharge rate limits |

*Extension write access requires **SPAN Modbus** unlock — enabled by FranklinWH Support for SPAN panel owners.

### What This Means in Practice

```
┌─────────────────────────────────────────────────────────────┐
│ We CAN do (SunSpec M704):              WE CANNOT do:        │
│ ✅ Charge battery at 3000W             ❌ Change mode to TOU │
│ ✅ Discharge battery at 2000W          ❌ Set reserve to 30% │
│ ✅ Set idle (stop charge/discharge)    ❌ Switch to Backup   │
│ ✅ Read all status + extensions        ❌ Change any mode    │
│ ✅ Release control (native resumes)    ❌ Set PCS rate limits│
└─────────────────────────────────────────────────────────────┘
```

### SunSpec2 Compliance Matrix

> See `SUNSPEC_DER_SEQUENCING_REFERENCE.md` for proper phased sequencing protocol.

| Feature | SunSpec2 Spec | FranklinWH Reality | Library Workaround | Vendor Fix? |
|---------|--------------|-------------------|-------------------|-------------|
| LocRemCtl handoff | Remote (0) enables writes | Always Local (1), read-only; yet M704 writes work | None needed — power writes accepted despite Local | Report as spec deviation |
| Controller heartbeat | Client writes ControllerHb; DER monitors | ❌ Confirmed non-functional (write accepted, readback=0) | Not implemented — no alternative | Report as defect |
| Reversion timer (WSetRvrtTms) | DER counts down, auto-reverts power | ✅ **WORKS with proper sequencing!** Timer=60s accepted, countdown active (59→55→52) | Software `threading.Timer` via `duration_s` (may become optional) | N/A — working correctly |
| Reversion enable (WSetEnaRvrt) | Enables reversion behavior | ✅ **WORKS!** Readback=1 after write | N/A | N/A — working correctly |
| Battery state (M713.Sta) | Reflects CHARGING/DISCHARGING/IDLE | Always 0 (OFF) | Derived from M714.DCW ±50W deadband | Report; workaround is robust |
| DC Current (M714.DCA) | Reports battery DC current | Always 0 | Calculated: I = P/V from DCW/DCV | Report; workaround is robust |
| Ramp rate (WRmp) | Smooths power transitions | Returns None (unimplemented) | Software SoC ramp via `--soc-ramp-window` | Report; software ramp is different concept |
| Extension register writes | N/A (vendor-specific) | Read-only without SPAN Modbus unlock | Cloud API bypass (Tier 2) for mode changes | SPAN unlock required; vendor provisioning |
| Remote Control activation | WSetEna=1 starts remote DER control | ✅ Works — activates Remote Control (exclusive) | None needed — works as intended | N/A — working correctly |
| Command persistence | WSetRvrtTms reverts after timeout | WSetRvrtTms countdown active; WSetEna persists after timer expiry (partial implementation?) | Software timer + `reset_control_state()` remains recommended | Investigate: does countdown actually revert power? |
| Throttle % (ThrotPct) | Reports inverter power curtailment % | ✅ Readable (40180), always 0% in testing | None — read-only info point | N/A — may activate under thermal/grid stress |
| Throttle source (ThrotSrc) | Bitfield of throttle cause | 0xFFFFFFFF (unimplemented) | Not implemented — no alternative | Report; no workaround possible |
| Grid charge/discharge limits | `WChaRteMax` / `WDisChaRteMax` (RW per spec) | ❌ Confirmed: registers return 0xFFFF, writes silently discarded even with Remote Control + proper sequencing | Cloud API `setPowerControl` is only path | Report as defect |
| VA charge/discharge limits | `VAChaRteMax` / `VADisChaRteMax` (RW per spec) | ❌ Confirmed: 0xFFFF, writes discarded | Cloud API only | Report as defect |
| Max power limit (WMaxLimPct) | Caps inverter output at % of rated | ❌ **Confirmed non-functional.** WMaxLimPctEna write silently discarded (readback=0). WMaxLimPct readable (1000) but enable never sticks | Not implemented | Report as defect |
| Reactive power enable (VarSetEna) | Enables reactive power control | ❌ **Confirmed non-functional.** Write accepted, readback=0 (silently discarded). VarSetMod/VarSetPri readable but VarMaxInj/Abs=0xFFFF | Not implemented | Report as defect |

> **Test methodology:** All features re-tested 2026-03-13 using proper SunSpec 6-phase protocol (Pre-flight → Mode → Safety → Setpoint → Enable → Verify) with 200-500ms inter-phase settling. See `SUNSPEC_DER_SEQUENCING_REFERENCE.md`.
>
> **Test evidence:** `tests/results/2026-03-13_pcs_charge_rate_write_probe.md`, `tests/results/2026-03-08_p1_control_tests.md`

### Crash-Orphan Risk

!!! caution
    If the consumer application crashes while `WSetEna=1`, the aGate remains in Remote Control indefinitely (mobile app continues to show "VPP Mode"). There is no hardware timeout to auto-revert (WSetRvrtTms behavior unverified). The library provides `reset_control_state()` for graceful shutdown, but **crash recovery is a consumer responsibility**, not a library concern.

### The LocRemCtl Paradox (Model 715) — TESTED 2026-03-08

Model 715 `LocRemCtl` (PDU address 1089) reports `1` = **Local Control** and is **read-only**.

**Per SunSpec 2 spec:**
- `LocRemCtl = 1` (Local) → DER should **reject ALL** Modbus client writes
- `LocRemCtl = 0` (Remote) → DER accepts write commands from Modbus clients

**FranklinWH violates this fundamentally.** The aGate:
- ✅ Accepts M704 power writes (WSetEna, WSetPct, WSetMod) despite being in Local mode
- ❌ Ignores M715 lifecycle writes (ControllerHb — **confirmed non-functional** even with proper sequencing)
- ✅ **WSetRvrtTms WORKS** with proper sequencing (countdown active, 59→55→52)

This creates a **selective-write hybrid** that is non-standard:

| Feature | SunSpec 2 Expectation (Local) | FranklinWH Actual |
|---------|-------------------------------|-------------------|
| Power writes (WSetPct) | ❌ Reject | ✅ Accepts |
| Power enable (WSetEna) | ❌ Reject | ✅ Accepts |
| Reversion config (WSetRvrtTms) | ❌ Reject | ✅ Accepts value |
| Reversion countdown (WSetRvrtRem) | N/A | ✅ **Active!** Counts down correctly (59→55→52) |
| Controller heartbeat (ControllerHb) | ❌ Reject | ❌ **Confirmed non-functional** (write accepted, readback=0) |
| DER heartbeat (DERHb) | N/A | ❌ Always 0 |
| LocRemCtl write | Allow | ❌ Read-only |

**Test evidence:** See `tests/results/2026-03-08_p1_control_tests.md`

### Design Implications

1. **Remote Control provides clean control handoff:** When `WSetEna=1`, the aGate suspends native mode and grants exclusive Modbus control. This is cooperative, not conflicting.

2. **Hardware reversion timer available:** WSetRvrtTms **works** — the aGate counts down and (potentially) reverts the power setpoint. However, WSetEna may persist after timer expiry. Further investigation needed on whether power actually reverts or just the countdown is cosmetic.

3. **ControllerHb remains non-functional:** Even with proper sequencing, heartbeat writes are silently discarded. Software watchdog (`duration_s` / `--revert`) remains the primary safety mechanism.

4. **Virtual modes operate within Remote Control:** Our virtual Self-Consumption/TOU/Peak-Shave modes work by calculating power targets and issuing M704 commands while Remote Control is active.

4. **Library vs consumer boundary:** The library exposes `send_command()` and `reset_control_state()`. Crash recovery, watchdog timers, and session lifecycle are **consumer responsibilities** (e.g. FEM's `ModbusControlService`).

5. **SPAN Modbus Unlock Changes Everything:** If write access to extensions is enabled, the library could fully control the aGate — changing modes, setting reserves, etc. This is a fundamentally different operating mode that the library should detect and adapt to.

### Detection of Write Capability

```python
# The library tests write capability during connect()
# by attempting a write to extension registers
def _probe_extension_writable(self):
    """Test if extension registers accept writes."""
    try:
        # Read current value, write it back, verify
        current = read_register(15508)  # SelfReserve
        write_register(15508, current)  # Write same value
        return True  # SPAN Modbus unlock is active
    except:
        return False  # Standard read-only
```

### Related

- `SUNSPEC_DER_SEQUENCING_REFERENCE.md` — Proper 6-phase SunSpec control protocol
- `TODO_INTENT_BASED_CONFLICT_DETECTION.md` — Re-scoped with Remote Control handoff model
- [VPP_MODE_REFERENCE.md](VPP_MODE_REFERENCE.md) — Remote Control visual reference (mobile app: "VPP Mode")

---

## SunSpec2 Client — Address Remapping

**Issue:** The SunSpec2 Python library (`sunspec2.modbus.client.ModbusClientTCP`) remaps register addresses internally. The `client.read()` method adjusts addresses based on SunSpec model base offsets, causing "Modbus exception 2" (illegal address) when attempting to read FranklinWH proprietary extension registers (15000+ and 15500+).

The SunSpec2 client also does **not** expose `read_holding_registers()` — it has only `read()` and `_read()`.

**Workaround:** Use raw Modbus TCP socket for all extension register reads:
```python
import struct
client = self.dev.client
sock = client.socket
req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, start_addr, count)
sock.settimeout(self.timeout)  # Important for WiFi networks
sock.sendall(req)
resp = sock.recv(256)
```

**Code Location:** `src/franklinwh_modbus/controller.py:_read_extension_solar()`, `read_native_mode()`

---

## Register Addressing — PDU Addresses (Modbus) and the SunSpec Map

### Source of truth: Modbus terms

Addressing is a **Modbus** matter, not a SunSpec one: there is no "SunSpec address base". These docs use the Modbus Organization's terms, from the *MODBUS Application Protocol Specification V1.1b3* (2012-04-26) and the *MODBUS Messaging on TCP/IP Implementation Guide V1.0b* (2006-10-24). Both are published at https://www.modbus.org/specifications (download requires accepting the Modbus EULA; titles and dates as listed there, PDF text not re-checked for this page).

| Term | Meaning | Example (ControllerHb) |
|------|---------|------------------------|
| **PDU address** | 0-based number sent in the request PDU, 0–65535. This is what goes on the wire. | **1092** |
| **Register number** | The same register counted from 1 in the data model (register *N* is PDU address *N*−1). | 1093 |
| **Holding register** | The data table read with function code 3 and written with 6 (single) or 16 (multiple). All aGate points used here are holding registers. | — |
| **4xxxx reference** | Legacy Modicon convention, not an address: the leading 4 means "holding register", so 40001 = holding register 1 = PDU address 0. | 41093 |

**In these docs, every register address is a PDU address unless it says otherwise.** That includes the FranklinWH PICS addresses (owner-confirmed: the official PICS aligns with PDU addresses; e.g. ControllerHb 1092, matching `SUNSPEC_DEVICE_SNAPSHOT.md`) and the extension registers (15000–15043, 15500–15513, 16000–16002).

### What SunSpec adds: the "SunS" map

SunSpec defines where its register map starts, not how Modbus addresses work. A SunSpec device map begins with the 32-bit marker **"SunS" (0x53756E53)** at one of the well-known starting PDU addresses, **0, 40000 or 50000**, followed by Model 1 (Common). Models are chained blocks of `ID`, `L` (length) and `L` registers of points, and the chain ends with ID 0xFFFF.

**On the aGate (firmware V10R01B04D00): the map starts at PDU address 0.** Model 1's ID is at PDU 2. sunspec2 finds it by scanning with `base_address=0`.

### What works on the aGate (tested 2026-03-15)

```
Standard SunSpec models (M1–M715), holding registers:
  ├── sunspec2 library:      scans from PDU 0, then reads models  → ✅ WORKS
  ├── pymodbus / raw TCP:    PDU address 0 … 1125, e.g. 1092      → ✅ WORKS
  └── map probed at 40000:   PDU 40000+ (e.g. 41092)              → V10: ❌ exception 2 | V12: ✅ mirror (see below)

FranklinWH extension registers (outside the SunSpec chain):
  ├── sunspec2 library:      can't address them (not in the chain) → ❌
  ├── pymodbus / raw TCP:    PDU address 15500, 15507 …           → ✅ WORKS
  └── offset by 40000:       PDU 55500+                           → V10: ❌ exception 2 | V12: not tested
```

#### Firmware difference: the 40000 mirror (2026-10-20)

On **V12R02B60D00** the aGate **also serves its whole SunSpec map at PDU 40000**. A read-only check on 2026-10-20 found:
- the "SunS" marker at both PDU 0 and PDU 40000;
- PDU 40070–40071 equal to PDU 70–71 (701 ID and L);
- PDU 41092–41093 readable;
- **PDU 50000 still returns exception 2.**

On **V10R01B04D00** (tested 2026-03-15), PDU 40000+ returned exception 2. Either the firmware added the mirror or the March test missed it; we can't tell which.

What this means:
- **Keep using PDU 0 addresses.** They work on both firmwares.
- **pysunspec2's `scan()` tries 40000 first,** so on V12 it finds the map at 40000 and records `dev.base_addr = 40000`. **Any client that probes 40000 first binds to the mirror,** including this library today: its `base_address` is ignored with pysunspec2 1.3.6 (#84). Model reads still work, because the mirror matched PDU 0. **Writes to the mirror are unverified.** `is_connected()` probes `dev.base_addr` (#71), so it works either way.
- **Extension registers have not been tested at a 40000 offset on V12.** Use their listed PDU addresses.

A tool configured to subtract 40001 (or add 40000) will miss: send the PDU address as listed.

### Which code uses raw PDU addresses

The extension registers sit outside the SunSpec chain, so sunspec2 can't reach them. These functions send their PDU addresses in hand-built requests:

| Function | Registers (PDU) |
|----------|-----------------|
| `_read_extension_solar()` | 15500–15513, 16000 |
| `read_native_mode()` | 15507–15509 |
| `test_extension_writability()` | 15507–15509 (**writes**) |
| `clear_alarms()` | 1094 (M715 `AlarmReset`) |

Everything else (`connect()`, `send_command()`, the `read_*_status()` methods, Remote Control) goes through sunspec2 model access, which handles addressing after the scan:

```python
# controller.py __init__
base_address: int = 0  # sunspec2 scans for "SunS" starting at PDU 0

# SunSpecModbusClientDeviceTCP.scan():
# 1. reads PDU 0 → finds "SunS"
# 2. walks the model chain from PDU 2 (Model 1 ID)
# 3. stores each model's address; later reads use them
```

### UID aliasing (observed 2026-03-15)

The aGate ignores the Modbus unit identifier: every UID tried (1, 2, 3, 126, 247) returned the same 17 models from a scan at PDU 0. Scans at 50000 found nothing. Scans at 40000 were recorded as "varies" in the 2026-03-15 notes, while direct reads at PDU 40000+ return exception 2 (above). That entry is unexplained and not re-tested; treat it as unverified.

We use `unit_id=2` (FranklinWH default), but any UID works.

### Rules for new code

1. **Standard SunSpec reads and writes:** use sunspec2 model access, never hand-built addresses.
2. **Extension registers (15000+, 15500+, 16000+):** send the listed **PDU address** with function code 3 (read) or 6/16 (write).
3. **Use PDU 0 addresses; don't rely on a 40000 offset.** The aGate's map starts at PDU 0. PDU 40000+ returned exception 2 on V10R01B04D00 and is a mirror of the SunSpec map on V12R02B60D00 (above). Neither has been tested for extension registers.
4. **UID doesn't matter,** but use `unit_id=2` for consistency with FranklinWH docs.

---

## Register 16000 — High-Resolution Home Load (Discovered 2026-03-15)

16000 gives the home load at ~1 W resolution, while 15506 is in ~100 W steps. Measured 2026-03-15: 1004/1000, 929/900, 812/800 and 835/800 W (16000/15506). The library uses 16000 and falls back to 15506. It's undocumented, so firmware could change it. 16001 and 16002 are covered in [FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md).

---

## Model 502 — Power Rounding (Scale Factor Quantization)

**Discovered:** 2026-03-12 · **Severity:** Low (cosmetic) · **Reported to:** FranklinWH Support

FranklinWH aGate SunSpec registers round power values to coarse resolution (~100W steps) due to integer registers with limited scale factors. Small power flows are quantized upward, making them appear much larger than actual.

**Example:** Enphase Envoy S Metered standby draw (~50-100W parasitic load on the PV circuit at night) appears as **500-600W of "solar generation"** in both Modbus (`M502.OutPw`) and Cloud API readings. The aGate is the source of truth for both, so the coarse value propagates everywhere.

**Impact:**
- Solar power entities show non-zero values at night (confusing but not harmful)
- `--status` shows `Solar: 500W Producing` when actual solar generation is 0W
- Home load calculation (`(calc)`) is inflated by the phantom solar component
- Energy totals may include phantom solar contribution from parasitic loads

**No software fix possible** — the quantization happens in aGate firmware before the registers are read. The Cloud API mirrors the same coarse values since both originate from the aGate's internal metering.

**Possible future mitigation:** Time-based solar gating (zero solar output between sunset and sunrise) or a configurable dead-band threshold. Neither is implemented yet.

---

## Serial Number Structure (Unconfirmed)

!!! warning
    FranklinWH does not publicly document their serial number encoding scheme. The following structure is our **best guess** based on observed patterns across aGate and aPower devices. It should not be treated as authoritative.

FranklinWH serial numbers appear to encode device type, hardware revision, and unique ID:

```
XXXXXXXXXXXXXXXXXXXX
│       │  │        │
│       │  │        └── Unique serial (last 8 chars)
│       │  └─────────── Hardware revision (3 chars, e.g. "A02") — unconfirmed
│       └────────────── Device type prefix — unconfirmed
└────────────────────── Full serial (20 chars)
```

**Why this matters (if correct):**
- Hardware revision may determine capabilities — some revs may have more/fewer functions
- Extract rev from serial: `serial[8:11]` (e.g. `"A02"`) — **unverified assumption**
- Example: aGate `A02` vs `A03` may differ in supported Modbus registers
- Available from `M1.SN` (Model 1 Common, address 40052)

---

## Model 704 — Hardware Reversion is Cosmetic (PICS Issue 4)

**Issue:** WSetRvrtTms (327) countdown works (30→0), but **does NOT revert power** at expiry. WSetEna and WSetPct are unchanged 186 seconds post-expiry. The SunSpec dead-man switch is non-functional.

**Evidence:** 186s extended observation, WSetRvrtTms=1 (1s edge case) also non-functional. Corroborated by FranklinWH app ("VPP Mode" persisted), MQTT, and Home Assistant.

**Severity:** CRITICAL — combined with non-functional ControllerHb (1092), there is **zero hardware safety mechanism** on this firmware.

**Workaround:** Software-only dead-man via `send_command(duration_s=N)` in `controller.py`:
```python
# Software timeout is the ONLY safety mechanism
ctrl.send_command(BatteryCommand(-5000), duration_s=300)  # 5min auto-release
```

**Code Location:** `controller.py` — `send_command()` docstring documents this explicitly.

**Full Details:** [`PICS_CONFORMANCE_CROSS_REFERENCE.md`](./PICS_CONFORMANCE_CROSS_REFERENCE.md) — Issue 4

---

## Model 704 — No Input Validation on WSet/WSetPct (PICS Issue 5)

**Issue:** The device accepts WSet=15000W (150% of WMaxRtg=10000W) and WSetPct=±1500 (±150%) without Modbus exception, alarm, or clamping. Values read back exactly as written.

**Severity:** HIGH — downstream clamping status unknown. Software must enforce range limits.

**Workaround:** Two layers of clamping in the library:
1. `BatteryCommand.__post_init__()` — clamps to ±10000W at construction time
2. `controller._validate_power()` — clamps to device-reported WMaxRtg at write time

**Code Location:** `types.py` and `controller.py`

**Full Details:** [`PICS_CONFORMANCE_CROSS_REFERENCE.md`](./PICS_CONFORMANCE_CROSS_REFERENCE.md) — Issue 5

---

## Model 704 — Reactive Power Not Controllable (All Paths Exhausted)

**Issue:** No Modbus-accessible reactive power or PF control path exists on this firmware.

**Paths tested:**
| Path | Register | Result |
|------|----------|--------|
| VarSetEna (331) | M704 | Silently discards all writes — 0/160 tests |
| PFWInjEna (298) | M704 | Writable but PF setpoints (267/268) are 0xFFFF |
| CtrlModes FIXED_VAR | M702 | Firmware claims available but no Modbus path |

**Conclusion:** The device manages reactive power internally. This is **final** — no further investigation paths remain.

**Full Details:** [`PICS_CONFORMANCE_CROSS_REFERENCE.md`](./PICS_CONFORMANCE_CROSS_REFERENCE.md) — Issues 1, 3, 6

---

## General Notes

- **Scale Factors:** Always read SF registers dynamically — they can change
- **Model Discovery:** aGate implements models 1, 502, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 711, 712, 713, 714, 715
- **Write Sequencing:** All SunSpec DER control groups require proper phased sequencing (Phase 0-5). See `SUNSPEC_DER_SEQUENCING_REFERENCE.md`
- **Timing:** Minimum 100-500ms inter-phase settling. aGate round-trip ~98ms average. Do not rapid-fire writes.
- **Timeout:** WiFi networks to the aGate can be slow; always use configurable timeout (default 10s)
- **Addressing:** read and write every register at its PDU address (see [Register Addressing](#register-addressing-pdu-addresses-modbus-and-the-sunspec-map)). An undated earlier note said M704 also answered at a 40000 offset, while M715 did not. That conflicts with the 2026-03-15 test (PDU 40000+ → exception 2) and is unverified.

---

*Last Updated: 2026-03-22 (terminology: VPP Mode → Remote Control, PICS Issue 4 reversion cosmetic, Issue 5 no input validation, reactive power exhausted)*  
*Device Tested: FranklinWH aGate X (SN: XXXXXXXXXXXXXXXXXXXX, FW: V10R01B04D00)*
