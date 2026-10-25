# aGate Full Model Map (Audit Trail)

**Firmware:** `V10R01B04D00`  
**Date:** 2026-05-14  
**Unit ID:** 1 (Baseline)  
**Library Version:** `franklinwh-modbus v0.1.0`  

This document lists all SunSpec models discovered on the FranklinWH aGate system.

**Raw Data Source:** [AGATE_FULL_SCAN_2026-05-14.txt](AGATE_FULL_SCAN_2026-05-14.txt) (Captured all values, including zeros)

## 📋 Summary of Discovered Models

The aGate exposes **17** models in the SunSpec block (starting at address 40000).

| Model ID | Name | Description | Status |
|:---:|---|---|---|
| **1** | Common | Device metadata (Manufacturer, Model, Serial, Version) | ✅ Verified |
| **502** | Solar Module | PV string-level data (if configured) | ✅ Detected |
| **701** | DER Measure AC | Real-time AC telemetry (Power, Voltage, Freq) | ✅ Verified |
| **702** | DER Capacity | Hardware ratings (WMaxRtg, VAMaxRtg, etc.) | ✅ Verified |
| **703** | DER Enter Service | Grid connection requirements/timers | ✅ Detected |
| **704** | **DER Control AC** | **Primary power control (WSet, WSetPct, Reversion)** | ⚠️ Verified* |
| **705** | DER Volt-Var | Reactive power vs Voltage curves | ✅ Detected |
| **706** | DER Volt-Watt | Real power vs Voltage curves | ✅ Detected |
| **707** | DER Trip LV | Low Voltage ride-through settings | ✅ Detected |
| **708** | DER Trip HV | High Voltage ride-through settings | ✅ Detected |
| **709** | DER Trip LF | Low Frequency ride-through settings | ✅ Detected |
| **710** | DER Trip HF | High Frequency ride-through settings | ✅ Detected |
| **711** | DER Freq-Droop | Frequency-Watt (HZ) control settings | ✅ Detected |
| **712** | DER Watt-Var | Reactive power vs Real power curves | ✅ Detected |
| **713** | DER Storage Capacity | Battery ratings (WHoldMax, WMaxDischa, etc.) | ✅ Verified |
| **714** | DER Measure DC | Battery stack telemetry (Voltage, Current) | ✅ Verified |
| **715** | **DER Control** | **Lifecycle control (Heartbeat, Alarms)** | ⚠️ Verified* |

*\* Control functionality is subject to PICS limitations (see PICS_CONFORMANCE_CROSS_REFERENCE.md).*

---

## 🔍 Detailed Model Breakdown

### Model 1: Common Info
- **Manufacturer**: FranklinWH Technologies Co., Ltd
- **Model**: aGate X
- **Version**: V10R01B04D00
- **Serial**: SN-REDACTED-XXXX

### Model 704: DER Control AC (SunSpec 700-series)
*Crucial for Remote Control operations.*
- **WSetEna**: Control Enable (0=Local, 1=Remote)
- **WSetMod**: Control Mode (0 = W_MAX_PCT percent, 1 = WATTS; DER Information Model v1.2)
- **WSetPct**: Discharge/Charge rate in %
- **WSetRvrtTms**: **NOW FUNCTIONAL** (Confirmed 2026-05-14). Countdown active.

### Model 715: DER Control (Lifecycle)
- **LocRemCtl**: Read-only (Fixed to Local=1)
- **ControllerHb**: Heartbeat (Currently silent-discard)
- **DERHb**: Device Heartbeat echo (Always 0)

---

## 📝 Historical Baseline Notes
- **2026-03-08**: Initial scan performed on Unit ID 2. `WSetRvrtTms` marked as non-functional.
- **2026-05-14**: Re-baseline to **Unit ID 1**. Corrected sequencer logic (removed -1 offset). **`WSetRvrtTms` confirmed as functional (countdown active).**
- **Decision**: Unit ID 1 is the authoritative control port. All future tests and production commands should use `-u 1`.
