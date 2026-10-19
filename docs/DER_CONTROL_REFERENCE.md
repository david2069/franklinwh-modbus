# DER Control Register Reference

*Last Updated: 2026-05-15 18:57*

Complete reference of all DER control registers on the FranklinWH aGate, documenting what we use, what works, what's untested, and the future test plan.

**Cross-references:** [ORCHESTRATION_AND_CONTROL.md](./ORCHESTRATION_AND_CONTROL.md) (legacy command sequencing), [FRANKLINWH_SUNSPEC_QUIRKS.md](./FRANKLINWH_SUNSPEC_QUIRKS.md) (known quirks)

---

## 1. Model 704 — DER Control AC (Battery Control)

### Active Power Control (WSet Group)

These are the primary battery control registers. **This is what we use.**

| Address | Field | Label | Type | RW | PICS Status | Used | Status | Code Reference |
|---------|-------|-------|------|----|-------------|------|--------|----------------|
| 40318 | `WSetEna` | Active Power Enable | enum16 | RW | supported | ✅ | ✅ **Working** | `send_command()` step 1 (disable=0) & 3 (enable=1) |
| 40319 | `WSetMod` | Active Power Mode | enum16 | RW | supported | ✅ | ✅ **Working** | `send_command()` step 2 (set=0) |
| 40320 | `WSet` | Active Power Setpoint (W) | int32 | RW | supported | ❌ | ⚠️ **Avoided** | Not used — causes mode flickering when set alongside WSetPct |
| 40322 | `WSetRvrt` | Reversion Power (W) | int32 | RW | supported | ❌ | 🔲 **Untested** | Read by `read_control_status()` only |
| 40324 | `WSetPct` | Active Power Setpoint (%) | int16 | RW | supported | ✅ | ✅ **Working** | `send_command()` step 2 — **sign inverted** (see quirks) |
| 40325 | `WSetPctRvrt` | Reversion Power (%) | int16 | RW | supported | ❌ | 🔲 **Untested** | Could set fallback power level |
| 40326 | `WSetEnaRvrt` | Reversion Enable | enum16 | RW | supported | ❌ | 🔲 **Untested** | What happens when command reverts |
| 40327 | `WSetRvrtTms` | Reversion Timeout (s) | uint32 | RW | supported | ⚠️ | ⚠️ **Config only** | Value accepted & persists, but countdown never activates (TESTED 2026-03-08) |
| 40329 | `WSetRvrtRem` | Reversion Time Remaining (s) | uint32 | R | supported | ✅ | ❌ **Non-functional** | Always 0 — countdown never activates despite WSetRvrtTms being set (TESTED 2026-03-08) |

!!! important
    **Sign Convention Quirk:** `WSetPct` is inverted on FranklinWH hardware. Positive values = discharge (in standard SunSpec, positive = charge). The library inverts: `m704.WSetPct.value = -pct_raw`. See `FRANKLINWH_SUNSPEC_QUIRKS.md`.

!!! warning
    **WSet vs WSetPct:** Writing to `WSet` (absolute watts) alongside `WSetPct` causes mode flickering on the aGate. The library uses **only WSetPct** for all power commands. `WSet` is zeroed during `reset_control_state()` but never used for active control.

**Current Command Sequence:**
```
1. STOP:    WSetEna = 0               (disable control)
2. CONFIG:  WSetMod = 0, WSetPct = -X (set mode, set power %)
3. ENABLE:  WSetEna = 1               (enable control)
4. VERIFY:  read WSetPct              (confirm value took)
```

**Code entry points:**
- `controller.py:send_command()` — primary charge/discharge interface
- `controller.py:reset_control_state()` — stop and release control
- `controller.py:read_control_status()` — read all WSet fields
- `controller.py:healthcheck()` — zombie state detection

---

### Max Power Limit (WMaxLim Group)

**Not currently used by the library.** Could limit max inverter power.

| Address | Field | Label | Type | RW | PICS Status | Current Value | Status |
|---------|-------|-------|------|----|-------------|---------------|--------|
| 40310 | `WMaxLimPctEna` | Max Power Limit Enable | enum16 | RW | supported | 0 (disabled) | ❌ **Read-only** (P2 tested) |
| 40311 | `WMaxLimPct` | Max Power Limit (%) | uint16 | RW | supported | 100% (raw: 1000) | ❌ **Read-only** (P2 tested) |
| 40312 | `WMaxLimPctRvrt` | Reversion Limit (%) | uint16 | RW | unimplemented | None | ❌ Unimplemented |
| 40313 | `WMaxLimPctEnaRvrt` | Reversion Enable | enum16 | RW | unimplemented | None | ❌ Unimplemented |
| 40314 | `WMaxLimPctRvrtTms` | Reversion Timeout (s) | uint32 | RW | unimplemented | None | ❌ Unimplemented |
| 40316 | `WMaxLimPctRvrtRem` | Reversion Time Remaining | uint32 | R | unimplemented | None | ❌ Unimplemented |

!!! note
    **Potential Use Case:** Could be used to cap inverter output during grid-sensitive periods or to implement soft power ramp-down. Worth testing if the aGate respects this limit.

---

### Power Factor Control (PFW Groups)

**Not currently used by the library.** Controls inverter power factor.

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40298 | `PFWInjEna` | PF Enable (W Inject) | enum16 | RW | **1 (enabled!)** | ✅ **Writable** — toggles actual PF |
| 40299 | `PFWInjEnaRvrt` | PF Reversion Enable (Inj) | enum16 | RW | None | ❌ Unimplemented |
| 40300 | `PFWInjRvrtTms` | PF Reversion Time (Inj) | uint32 | RW | None | ❌ Unimplemented |
| 40302 | `PFWInjRvrtRem` | PF Rev Time Remaining | uint32 | R | None | ❌ Unimplemented |
| 40304 | `PFWAbsEna` | PF Enable (W Absorb) | enum16 | RW | None | ❌ Unimplemented |
| 40305 | `PFWAbsEnaRvrt` | PF Reversion Enable (Abs) | enum16 | RW | None | ❌ Unimplemented |
| 40306 | `PFWAbsRvrtTms` | PF Reversion Time (Abs) | uint32 | RW | None | ❌ Unimplemented |
| 40308 | `PFWAbsRvrtRem` | PF Rev Time Remaining | uint32 | R | None | ❌ Unimplemented |

!!! warning
    `PFWInjEna` = 1 — **Active and WRITABLE.** When enabled (=1): M701 PF = -1 (≈ unity). When disabled (=0): PF = 3 (0.003, essentially no correction). **Do not leave disabled** — the aGate's default PF correction is applied through this register.

---

### Reactive Power Control (VarSet Group)

**Not currently used by the library.** Controls reactive power (Var) output.

| Address | Field | Label | Type | RW | PICS Status | Current Value | Status |
|---------|-------|-------|------|----|-------------|---------------|--------|
| 40331 | `VarSetEna` | Reactive Power Enable | enum16 | RW | supported | 0 | ❌ **Read-only** (P3 tested) |
| 40332 | `VarSetMod` | Reactive Power Mode | enum16 | RW | supported | 1 | ❌ Read-only (pre-configured) |
| 40333 | `VarSetPri` | Reactive Power Priority | enum16 | RW | supported | 2 | ❌ Read-only (pre-configured) |
| 40334 | `VarSet` | Reactive Power (Var) | int32 | RW | supported | 0 | ❌ **Read-only** (P3 tested) |
| 40336 | `VarSetRvrt` | Reversion Reactive Power | int32 | RW | unimplemented | None | ❌ Unimplemented |
| 40338 | `VarSetPct` | Reactive Power (%) | int16 | RW | unimplemented | None | ❌ Unimplemented |
| 40339 | `VarSetPctRvrt` | Reversion Reactive (%) | int16 | RW | unimplemented | None | ❌ Unimplemented |
| 40340 | `VarSetEnaRvrt` | Reversion Enable | enum16 | RW | unimplemented | None | ❌ Unimplemented |
| 40341 | `VarSetRvrtTms` | Reversion Timeout (s) | uint32 | RW | unimplemented | None | ❌ Unimplemented |
| 40343 | `VarSetRvrtRem` | Reversion Time Remaining | uint32 | R | unimplemented | None | ❌ Unimplemented |

---

### Ramp Rate Control

**Not currently used.** Controls how fast power ramps up/down.

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40345 | `WRmp` | Normal Ramp Rate | uint16 | RW | None | ❌ **Unimplemented** (P4 tested) |
| 40346 | `WRmpRef` | Ramp Rate Reference | enum16 | RW | None | ❌ **Unimplemented** (P4 tested) |
| 40347 | `VarRmp` | Reactive Ramp Rate | uint16 | RW | None | ❌ Unimplemented |

---

### Anti-Islanding

| Address | Field | Label | Type | RW | Current Value | Status |
|---------|-------|-------|------|----|---------------|--------|
| 40348 | `AntiIslEna` | Anti-Islanding Enable | enum16 | RW | None | 🔲 Untested — **DO NOT disable** |

### Scale Factors

| Address | Field | Value | Applied To |
|---------|-------|-------|-----------|
| 40349 | `PF_SF` | -3 | Power Factor (÷1000) |
| 40350 | `WMaxLimPct_SF` | -1 | Max Power Limit (÷10) |
| 40351 | `WSet_SF` | 0 | Active Power (×1) |
| 40352 | `WSetPct_SF` | -1 | Active Power % (÷10) |
| 40353 | `VarSet_SF` | 0 | Reactive Power (×1) |
| 40354 | `VarSetPct_SF` | -1 | Reactive Power % (÷10) |

---

## 2. Model 715 — DER Control

> **Note:** Addresses are Modbus **PDU addresses** (0-based, as sent on the wire), e.g. M715 at 1087–1095, matching the FranklinWH PICS. 4xxxx references such as 41088+ are not addresses; reading PDU 41087+ returns exception 2 (ILLEGAL DATA ADDRESS). See QUIRKS, Register Addressing.

| PDU address | Field | Label | Type | RW | PICS Status | Current Value | Status | Notes |
|---------|-------|-------|------|----|-------------|---------------|--------|-------|
| 1089 | `LocRemCtl` | Control Mode | enum16 | ❌ R | supported | **1 (Local)** | ❌ **Read-only** | SunSpec says writable — aGate ignores (see LocRemCtl Paradox) |
| 1090 | `DERHb` | DER Heartbeat | uint32 | R | supported | 0 | ❌ **Non-functional** | Always 0 — DER heartbeat protocol not implemented (TESTED) |
| 1092 | `ControllerHb` | Controller Heartbeat | uint32 | RW* | supported | 0 | ❌ **Non-functional** | Write accepted, value silently ignored (TESTED via sunspec2 + raw TCP) |
| 1094 | `AlarmReset` | Alarm Reset | uint16 | RW | supported | 0 | 🔲 Untested | Used in `check_blocking_alarms()` but never written |
| 1095 | `OpCtl` | Set Operation | enum16 | RW | supported | 0 | 🔲 Untested | Start/Stop/Standby the DER |

!!! caution
    **LocRemCtl Paradox:** Per SunSpec 2, `LocRemCtl=1` (Local) should mean the DER rejects ALL client writes. FranklinWH violates this — M704 power writes work, but lifecycle features (heartbeat, reversion countdown) are non-functional. This is a **selective-write hybrid** unique to FranklinWH. See `FRANKLINWH_SUNSPEC_QUIRKS.md` for full analysis.

!!! important
    **ControllerHb TESTED 2026-03-08:** Writes accepted at protocol level (no Modbus exception) via both sunspec2 model.write() and raw TCP func 16 at address 1092. Value stays 0 after all writes. **aGate firmware silently discards heartbeat writes.** See `tests/results/2026-03-08_p1_control_tests.md`.

---

## 3. FranklinWH Extension Controls (15507–15509)

| Address | Field | Label | Type | RW | PICS Status | Current Value | Status | Notes |
|---------|-------|-------|------|----|-------------|---------------|--------|-------|
| 15507 | `OnGridMode` | Operating Mode | uint16 | R* | supported | 2 (Self-Consumption) | ✅ **Read works** | ❌ Write blocked without SPAN |
| 15508 | `SelfReserve` | Self-Consumption Reserve | uint16 | R* | supported | 20 (%) | ✅ **Read works** | ❌ Write blocked without SPAN |
| 15509 | `TouReserve` | TOU Reserve | uint16 | R* | supported | 20 (%) | ✅ **Read works** | ❌ Write blocked without SPAN |

*R = Read-only without SPAN Modbus unlock. See `FRANKLINWH_SUNSPEC_QUIRKS.md` "Write Access Asymmetry".

---

## 4. Test Status Summary

```
Legend:  ✅ Working   ⚠️ Partial   🔲 Untested   ❌ Broken/Blocked
```

| Category | Registers | Status | Evidence |
|----------|-----------|--------|----------|
| **Battery Power (WSetPct)** | 40318-40324 | ✅ Working | Live verified — charge/discharge confirmed |
| **WSet (absolute watts)** | 40320 | ⚠️ Avoided | Causes flickering when used with WSetPct |
| **Reversion Config (WSetRvrtTms)** | 40327 | ⚠️ Config only | Value accepted & persists, but countdown never activates (TESTED) |
| **Reversion Countdown (WSetRvrtRem)** | 40329 | ❌ Non-functional | Always 0 — hardware timer not implemented (TESTED) |
| **Reversion Power** | 40322/40325 | 🔲 Untested | Could set fallback power after timeout |
| **Max Power Limit** | 40310-40316 | 🔲 Untested | Could cap inverter output |
| **Power Factor** | 40298-40308 | ✅ PFWInjEna writable | PFWInjEna toggles actual PF. All Rvrt regs unimplemented |
| **Reactive Power** | 40331-40343 | ❌ Read-only | VarSetEna/VarSet writes silently discarded |
| **Ramp Rates** | 40345-40347 | 🔲 Untested | Could smooth power transitions |
| **Controller Heartbeat** | 1092 | ❌ Non-functional | Write accepted, value silently ignored (TESTED) |
| **DER Heartbeat** | 1090 | ❌ Non-functional | Always 0 (TESTED) |
| **OpCtl (Start/Stop)** | 1095 | 🔲 Untested | Could start/stop DER |
| **LocRemCtl** | 1089 | ❌ Read-only | SunSpec handoff not supported; LocRemCtl Paradox (TESTED) |
| **Extension Mode/Reserves** | 15507-15509 | ❌ Write blocked | Need SPAN Modbus unlock |

---

## 5. Future Test Plan

### Priority 1 — Command Persistence and Keep-Alive — TESTED 2026-03-08

| Test | What to Do | Result | Evidence |
|------|-----------|--------|----------|
| **Write ControllerHb** | Write incrementing counter to 1092 | ❌ **Non-functional** — writes silently ignored | Test 1a/1b/1c |
| **Set WSetRvrtTms** | Write timeout to 40327, issue command | ⚠️ **Config only** — value persists but countdown never activates | Test 2a/2b/2c |
| **Monitor WSetRvrtRem** | Read countdown after timeout set | ❌ **Always 0** — hardware timer not implemented | Test 2b/2c |

!!! important
    **Root cause: LocRemCtl Paradox.** Both features are SunSpec 2 remote controller lifecycle features that require `LocRemCtl=0` (Remote). The aGate keeps this at 1 (Local) and read-only, selectively accepting power writes but ignoring lifecycle features. **Software-side watchdog must be implemented instead.** See `FRANKLINWH_SUNSPEC_QUIRKS.md`.

### Priority 2 — Power Limiting and Ramp Control

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **WMaxLimPct** | Write 50% limit to 40311, enable at 40310 | Inverter caps at 50% rated power | Medium — limits output |
| **WRmp ramp rate** | Write ramp value to 40345 | Power changes gradually instead of step | Low |
| **VarSet reactive** | Enable VarSet, write small Var value | Observe reactive power output | Low |

### Priority 3 — Power Factor Investigation

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **Read PF target** | Investigate what PFWInjEna=1 is doing | Understand default PF behavior | None — read only |
| **Disable PFWInjEna** | Write PFWInjEna=0, observe PF change | Determine if PF control is enforced | Medium |

### Priority 4 — DER Operations

| Test | What to Do | Expected Outcome | Risk |
|------|-----------|-------------------|------|
| **OpCtl start/stop** | Write OpCtl values to 41095 | May start/stop the inverter | ⚠️ **High — could disconnect** |
| **AlarmReset** | Write to 41094 after a fault | Clear fault condition | Low |

---

## 6. Tool Commands for Testing

```bash
# Read all M704 control registers (ground truth)
python3 tools/modbus_sunspec2_reader.py -i YOUR_AGATE_IP -t 10 -dvalues --vals | grep -A 50 'Model 704'

# Read M715 control registers
python3 tools/modbus_sunspec2_reader.py -i YOUR_AGATE_IP -t 10 -dvalues --vals | grep -A 12 'Model 715'

# Read extension mode/reserves
python3 tools/modbus_sunspec2_reader.py -i YOUR_AGATE_IP -t 10 --raw 15507:3

# Library: read control status
python3 -c "
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()
print(ctrl.read_control_status())
print(ctrl.read_native_mode())
ctrl.disconnect()
"

# Library: healthcheck (includes zombie detection)
python3 -c "
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()
h = ctrl.healthcheck()
print(f'Healthy: {h.healthy}')
print(f'Message: {h.message}')
for k,v in h.details.items(): print(f'  {k}: {v}')
for r in h.recommendations: print(f'  ⚠️  {r}')
ctrl.disconnect()
"
```

---

## 7. Retrospective: Why Past Tests Failed

!!! note
    Previous attempts at battery control were largely "winging it" — writing to registers without understanding:
    - **Correct addresses** — legacy code used PDU offsets (317, 318, 319) instead of absolute addresses (40318, 40319, 40320)
    - **Sign conventions** — WSetPct is inverted on FranklinWH hardware (positive=discharge, not charge)
    - **Sequencing requirements** — M704 requires a multi-step STOP→CONFIG→ENABLE→VERIFY sequence; single writes are ignored
    - **WSet vs WSetPct conflict** — writing both causes mode flickering; must use only WSetPct
    - **FranklinWH quirks** — LocRemCtl handoff not supported, extension registers read-only
        This document now provides the correct baseline for future formal use-case testing of each register group.

---

## 8. Future TODO: FranklinWH App Parity

Goals for feature parity with the FranklinWH mobile app:

- [ ] **Manual Controls** — mimic the app's manual charge/discharge with power level selection (partially working via `send_command()`)
- [ ] **TOU Scheduling** — implement time-of-use schedule programming (requires extension register 15507 write access OR virtual mode emulation)
- [ ] **Max Power Settings** — the app allows setting max charge/discharge power limits (map to WMaxLimPct? or extension registers?)
- [ ] **Custom Inverter/Grid Operations** — app offers grid export limits and inverter power caps (map to VarSet or WMaxLim groups?)
- [ ] **Reserve Level Management** — app sets Self-Consumption and TOU reserve percentages (extension registers 15508-15509, currently read-only)

!!! important
    Achieving full App parity likely requires the **SPAN Modbus unlock** for extension register writes. Without it, we can emulate some behaviors via M704 power commands, but cannot natively change modes or reserves.

---

*Last Updated: 2026-03-08 (P1 tests complete)*  
*Test Results: `tests/results/2026-03-08_p1_control_tests.md`*  
*See also: [ORCHESTRATION_AND_CONTROL.md](./ORCHESTRATION_AND_CONTROL.md) for command sequencing diagrams*
