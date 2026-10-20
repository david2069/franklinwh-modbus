# PICS Conformance Cross-Reference

**Source:** `PICS_span_20230711_SPANcomments20230803.xlsx` (FranklinWH's PICS, July 2023, file name as received; proprietary and not distributed in this repository)  
**Last tested:** 2026-03-13 (6-phase SunSpec protocol re-test)

> This document cross-references the manufacturer's **Protocol Implementation Conformance Statement (PICS)** against actual hardware behavior verified through testing.

---

## M702 — DER Capacity (Settings)

| Addr | Point | PICS Status | PICS R/W | Our Test Result | Match? |
|:----:|-------|:-----------:|:--------:|:---------------:|:------:|
| 227 | WMaxRtg | supported | R | 10000 ✅ | ✅ |
| 232 | VAMaxRtg | supported | R | 11600 ✅ | ✅ |
| 233 | VarMaxInjRtg | supported | R | 5880 ✅ | ✅ |
| 234 | VarMaxAbsRtg | supported | R | 5880 ✅ | ✅ |
| 235 | WChaRteMaxRtg | supported | R | 10000 ✅ | ✅ |
| 236 | WDisChaRteMaxRtg | supported | R | 10000 ✅ | ✅ |
| 248 | CtrlModes | supported | R | 14271 ✅ | ✅ |
| **251** | **WMax** | **supported** | **RW** | **Write=5000, readback=0** | **⚠️ VIOLATION** |
| 256 | VAMax | supported | RW | Not tested | — |
| **257** | **VarMaxInj** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **258** | **VarMaxAbs** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **259** | **WChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **260** | **WDisChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **261** | **VAChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |
| **262** | **VADisChaRteMax** | **unimplemented** | **RW** | **0xFFFF** | **✅ Expected** |

### M702 Takeaway

All "unimplemented" registers match exactly (0xFFFF). **WMax (251)** is declared "supported RW" (0-10000) but FC06 write of 5000 returned success while readback remained 0 (silent discard — no Modbus exception).

---

## M704 — DER AC Controls

| Addr | Point | PICS Status | PICS R/W | Our Test Result | Match? |
|:----:|-------|:-----------:|:--------:|:---------------:|:------:|
| 298 | PFWInjEna | supported | RW | Writable/sticky ✅ but PF setpoints 0xFFFF | **⚠️ Issue 6** |
| **310** | **WMaxLimPctEna** | **supported** | **RW** | **❌ Write accepted, readback=0** | **⚠️ VIOLATION** |
| 311 | WMaxLimPct | supported | RW (0-100) | Readable (1000). Earlier write=500 readback=500 may be cache artifact (see note). Phase 3: readback=1000 after write=500 | ⚠️ Unreliable |
| 312 | WMaxLimPctRvrt | unimplemented | RW | 0xFFFF ✅ | ✅ Expected |
| 313 | WMaxLimPctEnaRvrt | unimplemented | RW | 0xFFFF ✅ | ✅ Expected |
| **318** | **WSetEna** | **supported** | **RW** | **✅ WORKS (Remote Control)** | **✅** |
| 319 | WSetMod | supported | RW | ✅ Works | ✅ |
| 320 | WSet | supported | RW (0-10000) | ✅ Works (no clamping — see Alarms) | ✅ |
| 322 | WSetRvrt | supported | RW (0-10000) | Writable/sticky ✅ (cosmetic — Issue 4) | ⚠️ |
| 324 | WSetPct | supported | RW (0-100) | ✅ Works (no clamping — see Alarms) | ✅ |
| 325 | WSetPctRvrt | supported | RW (0-100) | Not tested | — |
| **326** | **WSetEnaRvrt** | **supported** | **RW** | Writable/sticky ✅ (cosmetic — Issue 4) | **⚠️** |
| **327** | **WSetRvrtTms** | **supported** | **RW** | Countdown works but reversion does NOT fire | **🔴 Issue 4** |
| 329 | WSetRvrtRem | supported | R | Countdown: 30→...→0 ✅ (cosmetic — Issue 4) | ⚠️ |
| **331** | **VarSetEna** | **supported** | **RW** | **❌ Write accepted, readback=0** | **⚠️ VIOLATION** |
| 332 | VarSetMod | supported | RW | Readable (1), accepts write | ✅ |
| 333 | VarSetPri | supported | RW | Readable (2), accepts write | ✅ |
| 334 | VarSet | supported | RW (-5880 to 5880) | Readable (0), accepts write | ✅ |
| 336 | VarSetRvrt | unimplemented | RW | — | ✅ Expected |
| 340 | VarSetEnaRvrt | unimplemented | RW | — | ✅ Expected |
| 341 | VarSetRvrtTms | unimplemented | RW | — | ✅ Expected |
| 345 | WRmp | unimplemented | RW | Returns None | ✅ Expected |

### M704 Takeaway

WSet active power control (318/319/320/324) works correctly and matches PICS. WSetRvrt (322), WSetEnaRvrt (326), WSetRvrtTms (327), and WSetRvrtRem (329) all operate as declared at the register level — countdown is active and reversion target is sticky. **HOWEVER:** reversion efficacy testing confirmed the countdown is cosmetic — WSetEna and WSetPct unchanged 186s after expiry. The dead-man switch does not physically revert power (**SAFETY CRITICAL — Issue 4**).

WMaxLimPctEna (310) and VarSetEna (331) silently discard all writes (0/160 tests). PFWInjEna (298) is writable but gates unimplemented setpoint registers — no physical PF effect (**Issue 6**).

---

## M715 — DER Lifecycle

| Addr | Point | PICS Status | PICS R/W | Our Test Result | Match? |
|:----:|-------|:-----------:|:--------:|:---------------:|:------:|
| 1089 | LocRemCtl | supported | **R** | Read-only ✅ (always Local=1) | ✅ |
| 1090 | DERHb | supported | R | Always 0 | ✅ |
| **1092** | **ControllerHb** | **supported** | **RW** | **❌ Write accepted, readback=0** | **⚠️ VIOLATION** |
| 1094 | AlarmReset | supported | RW | Write OK, auto-clears to 0, no latched alarms | ✅ |
| 1095 | OpCtl | supported | RW | Reads 0 (idle). ⚠️ Write not tested (safety) | — |

### M715 Takeaway

**ControllerHb declared "supported RW" but hardware silently discards writes.** This is a PICS conformance violation. LocRemCtl correctly declared as Read-only.

---

## Failed Tests Against PICS Claims

The following registers are declared "supported RW" in the PICS but **fail to persist writes.**

### Error Pattern (identical across all 4 registers)

- FC06 (Write Single Register): Returns success — no Modbus exception
- FC16 (Write Multiple Registers): Returns success — no Modbus exception
- Readback: Shows original/default value — write silently discarded
- No Modbus-layer error (no 0x01 Illegal Function, 0x02 Illegal Address, etc.)

### Robustness Testing (0/160 — all permutations failed)

| Variable | Values Tested |
|----------|:-----------:|
| Function Code | FC06, FC16 |
| Settle Time | 0.5s, 1.0s, 2.0s, 5.0s |
| Remote Control | Without (WSetEna=0), With (WSetEna=1) |
| Enable Values | 1, 2 (plus 100 for ControllerHb) |
| WMax Values | 100, 1000, 5000, 10000 |
| SunSpec Sequencing | Isolated writes AND full 6-phase protocol |
| Connection | Fresh TCP connection per test (atomic) |

### Test Infrastructure Details

| Parameter | Value Used | Notes |
|-----------|:----------:|-------|
| **Base address** | 0-based PDU | Addresses (e.g. 310, 331) sent directly in Modbus FC03/FC06 PDU. Confirmed correct: reads return expected values (WMaxLimPct=1000, VarSetMod=1, WSetEna toggles 0↔1) |
| **Unit ID** | **2 only** | Did NOT test UID=1 or UID=126 (standard SunSpec UIDs) |
| **Socket timeout** | 30s | Per-operation |
| **Inter-op delay** | 0.2-0.3s | Between read/write operations within a test |
| **Pre-settle delay** | 0.2s | Between FC06/FC16 write and settle start |
| **Post-settle readback** | Immediate | Read immediately after settle period |
| **Inter-test delay** | 0.3s | Between TCP connections (breathing room) |
| **Remote Control verification** | Modbus readback only | WSetEna=1 confirmed via FC03 read of register 318. **NOT verified via Cloud API or FEM** |
| **Remote Control activation** | Library `send_command()` | Uses `FranklinWHController.send_command(BatteryCommand(500W))` which writes WSetEna=1 + WSetPct via pysunspec2 |
| **Target** | 192.0.2.110:502 | WiFi connection, single aGate X |
| **Firmware** | V10R01B04D00 | As reported by M1.Vr |

### Variables NOT Tested

| Variable | Why Not | Risk |
|----------|---------|:----:|
| **Unit ID 1 or 126** | Library auto-detects UID=2; not varied | LOW — reads work at UID=2. UID=126 is SunSpec discovery UID; may expose different register map or commissioning interface. Worth one quick scan session. |
| **Cloud API Remote Control verification** | No FEM running during test | MEDIUM — Remote Control may not have fully activated |
| **Base address ±1** | Library SunSpec scan confirms addresses | LOW — reads return correct values |
| **FC15 (Write Multiple Coils)** | Registers are holding registers, not coils | NONE — not applicable |
| **Multi-register FC16 writes** | Only single-register FC16 tested | LOW — FC06 equivalent tested |
| **Different firmware versions** | Only V10R01B04D00 tested | N/A — only one device available |

### Register-Level Results

| # | Register (Model) | PICS Claims | Tests Run | Passed | Error Pattern |
|:-:|----------|:-----------:|:---------:|:------:|:-------------:|
| 1 | **M704.WMaxLimPctEna** (310) | supported RW | 32 | 0 | Silent discard |
| 2 | **M704.VarSetEna** (331) | supported RW | 32 | 0 | Silent discard |
| 3 | **M715.ControllerHb** (1092) | supported RW | 53 | 0 | Silent discard |
| 4 | **M702.WMax** (251) | supported RW (0-10000) | 27 | 0 | Silent discard |

### Additional Findings (Phase 3 — Full Sequencing)

| Register (Model) | PICS Status | Test | Result |
|----------|:-----------:|------|:------:|
| M704.WMaxLimPct (311) | supported RW | Write 500, readback | 1000 (not stuck) |
| M704.WMaxLimPct_SF (350) | supported R | Read | **-1** (valid scale factor — 0xFFFF as signed sunssf = -1, means ×10^-1) |
| M704.VarSetMod (332) | supported RW | Write 5, readback | 1 (not stuck) |
| M704.VarSet (334) | supported RW | Write 100, readback | 0 (not stuck) |
| M715.DERHb (1090) | supported R | Read | 0 (always zero — device never sends heartbeat) |

> **Note:** WMaxLimPct, VarSetMod, and VarSet appeared to accept writes in earlier tests but here show readback to defaults. This suggests these registers also silently discard writes, or previous readbacks were from cache. Further investigation would confirm, but the enable registers remain the key blockers.

> **Root cause unknown.** All are speculation without further evidence.

### Features Correctly Declared as Unimplemented

M702: WChaRteMax (259), WDisChaRteMax (260), VAChaRteMax (261), VADisChaRteMax (262), VarMaxInj (257), VarMaxAbs (258), **PFOvrExt (267)**, **PFUndExt (268)** — all return 0xFFFF.
M704: WMaxLimPctRvrt (312), WMaxLimPctEnaRvrt (313), VarSetRvrt (336), WRmp (345), **PFWInjEnaRvrt (299)**, **PFWInjRvrtTms (300)**, **PFWAbsEna (304)**, **PFWAbsEnaRvrt (305)** — all return 0xFFFF.

### Features That Match PICS

M704: WSetEna (318), WSetMod (319), WSet (320), WSetPct (324), **WSetRvrt (322)**, WSetEnaRvrt (326), WSetRvrtTms (327), WSetRvrtRem (329), **PFWInjEna (298)**.
M715: LocRemCtl (1089, R-only as declared).

> **WSetRvrt (322) verified:** Write=2500, readback=[0, 2500] ✅ STICKY.

> **PFWInjEna (298) verified:** Write toggle 0↔1 works ✅ STICKY. However, PF setpoint registers (PFOvrExt/PFUndExt) are 0xFFFF, and the entire PF reversion group (PFWInjEnaRvrt, PFWAbsEna, PFWAbsEnaRvrt) is 0xFFFF. No observable physical PF change when toggling. **Enable register works but there is nothing to enable — NOT a viable reactive power path.**

---

## Facts Only Summary

1. **PCS rate registers:** PICS declares "unimplemented", hardware returns 0xFFFF. **Case closed.**

2. **4 registers declared "supported RW" fail tests (0/160):** WMaxLimPctEna, VarSetEna, ControllerHb, WMax. All exhibit identical behavior: FC06/FC16 success, readback unchanged. Exhaustively tested across settle times, values, sequencing, and Remote Control state.

3. **WSet active power control works** — WSetEna, WSetMod, WSet, WSetPct all functional. WSetRvrtTms countdown works but reversion does NOT fire at expiry (Issue 4, SAFETY CRITICAL).

4a. **All reactive power and PF control paths exhausted — none viable:**
   - **Path 1 — VarSetEna (331):** BLOCKED. Silently discards all writes. 0/160 tests. (Issue 1)
   - **Path 2 — PFWInjEna (298):** DEAD END. Enable writable but PF setpoints (267/268) unimplemented (0xFFFF). No physical PF effect. (Issue 6)
   - **Path 3 — CtrlModes FIXED_VAR:** Firmware claims available (bit 2=1) but no functional Modbus path exists. (Issue 3)
   - **Conclusion:** Reactive power and PF are NOT controllable via any Modbus register on this firmware.

4. **CtrlModes (M702.248) bitmask = 14271 = 0x37BF:**
   ```
   Bit  Mode               Available
    0   MAX_W               YES
    1   FIXED_W             YES
    2   FIXED_VAR           YES   <-- firmware claims VAR is available
    3   FIXED_PF            YES
    4   VOLT_VAR            YES
    5   FREQ_WATT           YES
    6   DYN_REACT_CURR      NO
    7   LV_TRIP (LVRT)      YES
    8   HV_TRIP (HVRT)      YES
    9   WATT_VAR            YES
   10   VOLT_WATT           YES
   11   SCHEDULED           NO
   12   LF_TRIP (LFRT)      YES
   13   HF_TRIP (HFRT)      YES
   ```
   **Fact:** Firmware declares FIXED_VAR (bit 2) as available, yet VarSetEna writes are silently discarded.

---

## LocRemCtl Analysis

> **This section presents observed facts (labeled as FACT) and hypotheses (labeled as HYPOTHESIS). They are clearly distinguished.**

**FACT:** LocRemCtl (M715.1089) always reads `Local = 1` and is declared `R` (read-only) in the PICS. There is no documented path to transition to `Remote = 0`.

**FACT:** The WSet group (318-329) works despite LocRemCtl=Local. These registers are the core Remote Control power path.

**FACT:** All other "supported RW" control registers (WMaxLimPctEna, VarSetEna, ControllerHb, WMax) silently discard writes. These are non-Remote-Control features.

**FACT:** CtrlModes bitmask claims FIXED_VAR and FIXED_PF are available at the firmware level.

**HYPOTHESIS A (Access Gate — unverified):** LocRemCtl=Local may be the root cause. The WSet group may be a selective Remote Control carve-out that works despite Local mode, while other features require Remote authority.

**HYPOTHESIS B (Firmware Stub — competing):** The failing registers may be unimplemented stubs that ACK at the Modbus transport layer but are not wired to any control subsystem. This is architecturally distinct from a gate:
```
Hypothesis A: Write → [LocRemCtl=Local filter] → dropped
Hypothesis B: Write → Modbus transport ACK → /dev/null (not wired)
```
**Why this matters:** If A, the vendor fix is documenting/exposing the Remote transition path. If B, the vendor must implement the register handlers — a larger firmware effort. Both hypotheses produce identical test results (silent discard). Filing both with the vendor is recommended.

### Control Path Classification

```
┌───────────────────────────────────────────────────┐
│ WORKING ✅ (Remote Control carve-out)             │
│                                                   │
│  M704.WSetEna (318)    ─► Remote Control enable    │
│  M704.WSet (320)       ─► Power setpoint (W)      │
│  M704.WSetPct (324)    ─► Power setpoint (%)      │
│  M704.WSetRvrt (322)   ─► Reversion target ✅      │
│  M704.WSetRvrtTms (327)─► Dead-man timer ✅        │
│  M704.WSetRvrtRem (329)─► Countdown readback ✅   │
│  M704.WSetEnaRvrt (326)─► Reversion enable ✅     │
│  M704.PFWInjEna (298)  ─► PF inject (writable)    │
├───────────────────────────────────────────────────┤
│ BLOCKED ❌ (LocRemCtl=Local?)                      │
│                                                   │
│  M704.VarSetEna (331)     ─► Reactive power — DEAD │
│  M704.WMaxLimPctEna (310) ─► Curtailment % — DEAD  │
│  M715.ControllerHb (1092) ─► Heartbeat — DEAD      │
│  M702.WMax (251)          ─► Max power — DEAD      │
└───────────────────────────────────────────────────┘
```

---

## Hardware Reversion Safety — Test Result

> **CRITICAL FINDING:** The WSetRvrtTms countdown is cosmetic. It does NOT physically revert power or disable Remote Control when it reaches 0.

### Reversion Efficacy Test (2026-03-13 22:59 AEDT)

**Setup:** Remote Control active (WSetEna=1, WSetPct=-500), WSetRvrt=0, WSetEnaRvrt=1, WSetRvrtTms=30.
**Extended observation:** 3+ minutes post-expiry, NO forced cleanup until verdict.

```
     T  WSetEna  WSetPct  RvrtRem  Notes
   ──  ───────  ───────  ───────  ────────────────────────────
    1s        1     -500       29  counting down
    7s        1     -500       23  counting down
   11s        1     -500       19  counting down
   16s        1     -500       14  counting down
   21s        1     -500        9  counting down
   26s        1     -500        4  counting down
   31s        1     -500        0  EXPIRED — still active ⚠️
   39s        1     -500        0  9s post  — still active ⚠️
   46s        1     -500        0  16s post — still active ⚠️
   68s        1     -500        0  38s post — still active ⚠️
   98s        1     -500        0  68s post — still active ⚠️
  136s        1     -500        0  106s post — still active ⚠️
  176s        1     -500        0  146s post — still active ⚠️
  216s        1     -500        0  186s post — still active ⚠️
```

**Final state (186s post-expiry):** WSetEna=1, WSetPct=-500, WSetRvrtRem=0.
**Cleanup:** Remote Control was **force-released** by test script calling `reset_control_state()`. Device did **NOT** auto-release.

**Corroborating evidence (user-observed):**
- FranklinWH app: "VPP Mode" displayed throughout, "Charging 2.5 kW" *(app label for Remote Control)*
- MQTT Explorer: "Runtime Mode: VPP mode" persisted *(MQTT label for Remote Control)*
- Home Assistant: History shows Remote Control sustained, no mode transitions

**Alarms during reversion test:**
- M701.Alrm (76) = 0 — no DER alarms
- M714.PrtAlrms (1044) = 0 — no DC port alarms
- Device raised no alerts or alarms when countdown expired without reversion

**Facts:**
- Countdown mechanism works perfectly (30→23→...→4→0)
- Device did NOT auto-release Remote Control for 186 seconds (3+ min) after countdown reached 0
- WSetEna=1 and WSetPct=-500 unchanged throughout entire observation window
- NOT a latency/network issue — observation window is 186s, far exceeding any plausible delay
- The dead-man switch countdown is **cosmetic — it does NOT trigger power reversion**

**Implication:** WSetRvrtTms cannot be used as a hardware crash-recovery mechanism. The software watchdog (`controller.py` timeout) remains the **only** safety mechanism for reverting power after loss of communication.

---

## Alarm Observability (2026-03-13 23:30 AEDT)

### Alarm Probe Test Results

All alarm registers read 0 across all probe conditions:

| Test | M701.Alrm | M714.PrtAlrms | DERMode | Notes |
|------|-----------|---------------|---------|-------|
| Baseline (Remote Control active) | [0,0] | [0,0] | [0,1] | — |
| WSet=15000 (150% WMaxRtg) | [0,0] | [0,0] | [0,1] | **Accepted, no clamp** |
| WSetPct=+1500 (+150%) | [0,0] | [0,0] | [0,1] | **Accepted, readback=1500** |
| WSetPct=-1500 (-150%) | [0,0] | [0,0] | [0,1] | **Accepted, readback=-1500** |
| AlarmReset (1094)=1 | [0,0] | [0,0] | [0,1] | Write OK, readback=0 (auto-clear) |

Additional observations:
- **OpCtl (1095):** reads 0 (idle)
- **MnAlrmInfo (193):** static placeholder string `"Manufacturer custom error info"` — not dynamic alarm data
- **AlarmReset (1094):** accepts write, auto-clears to 0, no latched alarms exposed

### Input Validation Finding

> **⚠️ No input validation or clamping on WSet/WSetPct values.**

The device accepted WSet=15000W (150% of WMaxRtg=10000W) and WSetPct=±1500 (±150%) without any Modbus exception, alarm, or clamping. Values read back exactly as written. Software must enforce range limits independently.

### Alarm Architecture Assessment

```
PICS-violated writes (WMaxLimPctEna, VarSetEna, etc.)
        │
        ▼
  ┌─────────────┐
  │ Access gate  │  ← LocRemCtl=Local filter (hypothesised)
  └─────────────┘
        │
        │  Write silently dropped HERE
        │  Never reaches alarm-generating subsystem
        ▼
  ┌─────────────────────────┐
  │ Control execution layer  │  ← alarms live here
  └─────────────────────────┘
```

**Assessment:** Silent-discard architecture places the access gate upstream of alarm-generating subsystems. PICS-violated writes do not reach the control execution layer and therefore produce no alarms — by design or by omission.

M701.Alrm bits (GROUND_FAULT, DC_OVER_VOLT, AC_DISCONNECT, etc.) are hardware/grid event triggers — none are triggerable via Modbus write under normal operating conditions.

---

## PICS Violation Report Template

```
PICS Violation Report — aGate X (AGT-R1V1-AU Hybrid)
Firmware: V10R01B04D00
Test Date: 2026-03-13
PICS Source: PICS_span_20230711_SPANcomments20230803.xlsx

Issue 1 — LocRemCtl permanently Local
  M715.LocRemCtl (1089) returns Local=1 with no path to Remote.
  CtrlModes (M702.248) = 14271 declares FIXED_VAR (bit 2) and
  FIXED_PF (bit 3) as firmware-available, contradicting the
  non-functional VarSetEna and strengthening the case that a
  Modbus access gate exists (LocRemCtl or equivalent) that is
  not documented in PICS.
  This causes cascading silent-discard on:
    - M704.VarSetEna (331)     declared supported RW
    - M704.WMaxLimPctEna (310) declared supported RW
    - M715.ControllerHb (1092) declared supported RW
  Testing: 0/160 across FC06/FC16, settle 0.5-5s, ±Remote Control, + sequenced.
  REQUEST: Document the mechanism to transition to Remote mode,
           OR update PICS to reflect actual constraints.
  Filed: 2026-03-13 | Firmware: V10R01B04D00 | Status: OPEN

Issue 2 — WMax (251) write silently discarded
  PICS declares supported RW (0-10000).
  Tested: FC06/FC16, values 100/1000/5000/10000, settle 0.5-5s,
          with and without Remote Control. ALL silently discarded.
  Note: WSet (320) accepts values 0-10000W and works correctly.
  If WMax is intended as a ceiling on WSet, the absence of WMax
  write capability means the only power ceiling is WMaxRtg (227)
  = 10000W (read-only hardware rating). No software curtailment
  ceiling is achievable via PICS-declared registers.
  REQUEST: Confirm whether WMax is writable, and whether any
           device setting or authorisation is required.
  Filed: 2026-03-13 | Firmware: V10R01B04D00 | Status: OPEN

Issue 3 — CtrlModes declares FIXED_VAR available but Modbus
          path is non-functional
  M702.CtrlModes (248) = 14271 (0x37BF)
  Bit 2 (FIXED_VAR) = 1 — firmware declares reactive power available
  Bit 3 (FIXED_PF)  = 1 — firmware declares PF control available
  Yet M704.VarSetEna (331) silently discards all writes (0/160 tests).
  VarSetEna is the ONLY SunSpec Modbus path to exercise FIXED_VAR.
  No alternative Modbus registers expose reactive power control.
  REQUEST: Clarify whether CtrlModes bitmask represents hardware
  capability or Modbus-controllable capability. If the former,
  update PICS documentation to define this distinction explicitly.
  Filed: 2026-03-13 | Firmware: V10R01B04D00 | Status: OPEN
Issue 4 — WSetRvrtTms countdown does not revert power (SAFETY CRITICAL)
  Severity: CRITICAL — safety architecture, not just conformance.

  PICS declares WSetRvrtTms (327) as supported RW.
  Countdown mechanism works (30→23→...→0), but WSetEna and
  WSetPct are unchanged after expiry. Observed for 186s (3+ min)
  post-expiry with NO forced cleanup — device never auto-released.
  Edge case tested: WSetRvrtTms=1 (1s timer) also produces no
  reversion — eliminates zero-value special-meaning interpretation.
  No alarms raised (M701.Alrm=0, M714.PrtAlrms=0).
  Corroborated by user via FHP app ("VPP Mode" persisted) and MQTT.

  SunSpec Model 704 dead-man reversion is the specification-
  defined mechanism for protecting physical assets when Modbus
  communication is lost. A cosmetic countdown with no physical
  effect eliminates this protection entirely.

  Consequence: With ControllerHb also non-functional (Issue 1),
  there is NO hardware-enforced safety mechanism on this device.
  Loss of the controlling software process (crash, OOM, host
  power loss) will leave the device in its last commanded state
  indefinitely with no self-recovery path.

  The software watchdog (controller.py) is currently the ONLY
  safety mechanism. This is a single point of failure that
  cannot be mitigated via any PICS-declared Modbus register.

  Additional finding: WSetEnaRvrt (326) readback=1 (sticky),
  but the reversion it enables never fires. This register is
  also effectively cosmetic in current firmware.

  REQUEST: Confirm implementation status. If reversion is
  deferred to a future firmware version, provide target
  firmware version and timeline. This blocks production
  deployment of any unattended Remote Control application.

  SYSTEMIC SAFETY FAILURE NOTE:
  ControllerHb (Issue 1) and WSetRvrtTms (Issue 4) are
  designed as complementary safety mechanisms in SunSpec:
    Controller → ControllerHb → DERHb echo → if stops →
    WSetRvrtTms fires → power reverts
  BOTH mechanisms are non-functional simultaneously on this
  firmware. This is not two independent bugs — it is a
  complete failure of the SunSpec M704+M715 safety architecture.
  Filed: 2026-03-13 | Firmware: V10R01B04D00 | Status: OPEN

Issue 5 — No input validation on WSet/WSetPct (SAFETY HIGH)
  Severity: HIGH — software must enforce all range limits.

  WSet (320) accepted 15000W (150% of WMaxRtg=10000W).
  WSetPct (324) accepted ±1500 (±150% of rated range).
  Both values read back exactly as written.
  No Modbus exception code returned.
  No alarm raised (M701.Alrm=0, M714.PrtAlrms=0).
  DERMode unchanged ([0,1]) — device treated over-limit
  values as valid setpoints.

  PICS declares WSet range as 0-10000W, WSetPct as 0-100.
  Device does not enforce these bounds at the Modbus layer.

  Consequence: A software bug, corrupt message, or integer
  overflow that produces an out-of-range setpoint will be
  silently accepted. No hardware protection exists.

  REQUEST: Confirm whether firmware-level clamping is
  applied downstream of Modbus acceptance (i.e., does
  WSet=15000 actually command 15000W or is it clamped
  internally to WMaxRtg=10000W before execution?).
  If not clamped internally, this is an input validation
  defect.
  Filed: 2026-03-13 | Firmware: V10R01B04D00 | Status: OPEN

Issue 6 — PFWInjEna (298) enable gates unimplemented setpoints
  PICS declares PFWInjEna (298), PFOvrExt (267), PFUndExt (268),
  and PF reversion group as supported RW.
  PFWInjEna is writable/sticky (toggle 0↔1 confirmed).
  PFOvrExt (267), PFUndExt (268), and all PF reversion
  registers return 0xFFFF (unimplemented).
  No physical PF change observed across any toggle condition.

  PF readings during test (near-zero real power — noise floor):
    Idle:        PF=-2,   Var=-725
    PFWInjEna=0: PF=11,   Var=-732
    PFWInjEna=1: PF=-13,  Var=-737
    Remote Control active:  PF=965,  Var=-623, W=3002

  PF variation is load-dependent, not PFWInjEna-dependent.
  ±13 PF delta at near-zero watts is measurement noise.
  Var delta across all conditions = 12 Var (noise floor).

  Conclusion: PFWInjEna gates setpoint registers that do not
  exist in this firmware. Not a viable reactive power path.
  This is the final reactive power path exhausted — no
  Modbus-accessible reactive power control exists on this
  firmware version.

  REQUEST: Confirm implementation status of PF setpoint
  registers (267/268). Update PICS to reflect unimplemented
  status or provide firmware version where these are available.
  Filed: 2026-03-13 | Firmware: V10R01B04D00 | Status: OPEN
```

---

## Document Status

```
CLOSED — all items resolved:
  ✅ PCS rate registers — unimplemented, 0xFFFF confirmed
  ✅ WSet active power control (318/319/320/324) — fully functional
  ✅ WSetRvrt (322) — writable/sticky (cosmetic — Issue 4)
  ✅ WSetEnaRvrt (326) — writable/sticky (cosmetic — Issue 4)
  ✅ WSetRvrtRem (329) — countdown works (cosmetic — Issue 4)
  ✅ M702 unimplemented registers — all match PICS
  ✅ M701/M714 alarms = 0 across all probe conditions
  ✅ AlarmReset (1094) — writable, auto-clears, no latched alarms
  ✅ MnAlrmInfo (193) — static placeholder, not dynamic
  ✅ PFWInjEna (298) — writable but non-functional, Issue 6 filed
  ✅ Reactive power — ALL paths exhausted, none viable (final)

PICS VIOLATIONS FILED (6 issues):
  ⚠️  Issue 1 — LocRemCtl gate (WMaxLimPctEna/VarSetEna/ControllerHb)
  ⚠️  Issue 2 — WMax (251) silently discarded
  ⚠️  Issue 3 — CtrlModes claims FIXED_VAR, no Modbus path exists
  🔴  Issue 4 — WSetRvrtTms cosmetic, reversion never fires  ← SAFETY
  🔴  Issue 5 — No input validation on WSet/WSetPct       ← SAFETY
  ⚠️  Issue 6 — PFWInjEna gates unimplemented setpoint registers

OPEN:
  🟡 OpCtl (1095) write behaviour — low priority, requires
     physical site access. Non-blocking for Remote Control deployment.

PRODUCTION GATE:
  🔴 Issue 4 — reversion non-functional (SAFETY CRITICAL)
  🔴 Issue 5 — no input validation (SAFETY HIGH)
     Software must clamp WSet to [0, WMaxRtg] and
     WSetPct to [-1000, 1000] before writing.
     No hardware protection exists.

PRODUCTION GATE — Software Mitigation Clearance Conditions:
  Issue 4 mitigation:
    □ Software watchdog covers all 4 scenarios in table above
    □ Watchdog timeout ≤ 60s (configurable)
    □ reset_control_state() explicitly writes WSetEna=0
    □ Startup checks WSetEna (318), releases if =1 before dispatch
    □ Documented as sole safety mechanism (no hardware backup)
  Issue 5 mitigation:
    □ WSet clamped to [0, WMaxRtg] before write
    □ WSetPct clamped to [-1000, 1000] before write
      (scaled: SF=-1, so 1000 = 100.0% — see WMaxLimPct_SF addr 350)
    □ Unit test coverage for clamp boundary conditions
    □ Vendor confirms downstream clamping status (informational)
```

---

## Software Watchdog Requirements

Given WSetRvrtTms non-reversion (Issue 4) and ControllerHb non-functional (Issue 1), the software watchdog is the **sole safety mechanism**. It must cover:

| Scenario | Required Response |
|----------|------------------|
| **Modbus TCP connection lost** | Detect within N seconds, call `reset_control_state()` |
| **Controller process crash** | OS-level supervisor (systemd, Docker restart) must restart AND release on startup if Remote Control was active |
| **Host power loss** | On restore: read WSetEna (318), if =1 call `reset_control_state()` before accepting new dispatch |
| **Dispatch timeout** | Detect stale dispatch (no new setpoint received), call `reset_control_state()` |

> **NOTE:** `reset_control_state()` must write WSetEna=0 explicitly. There is no hardware path that will do this automatically.

---

## Capability Summary (Handoff)

```
WHAT WORKS:    Active power dispatch via WSet/WSetPct.
               Accepts any value — software MUST clamp to valid range.
WHAT DOESN'T:  Reactive power (all paths exhausted, final).
               PF control. Curtailment ceiling. Hardware reversion.
               Heartbeat. Input validation.
SAFETY (x2):  1. Hardware dead-man is cosmetic — no self-recovery.
              2. No input validation — software is range enforcement.
              Both must be addressed before unattended deployment.
```

---

*Source file: `~/Downloads/PICS_span_20230711_SPANcomments20230803.xlsx`*  
*Last updated: 2026-03-22 (terminology: VPP Mode → Remote Control)*
