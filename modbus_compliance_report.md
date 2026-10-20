# FranklinWH Modbus Conformance & Compliance Scorecard

*Generated on: 2026-05-23 21:40:56*

## Device Metadata
- **Manufacturer**: FranklinWH Technologies Co., Ltd
- **Model**: aGate X
- **Serial Number**: <SERIAL>
- **IP Address**: 192.0.2.110:502
- **Slave Unit ID**: 1

## Write plane Status (Extension Registers)
> [!IMPORTANT]
> **🔒 EXTENSION WRITES NOT APPLIED**: Proprietary extension registers are **read-only** on this unit. FranklinWH has not documented them or any mechanism that enables writes. Active power control (M704) remains fully writable.

## Compliance Audit Results
| Model | Register Point | Expected Status | Live Verified | Observed Value / Details |
|:---|:---|:---|:---|:---|
| **Model 1** (Common Model) | *Discovery* | Implemented | ✅ | Model present |
| | `Mn` | Implemented | ✅ Implemented | FranklinWH Technologies Co., Ltd |
| | `Md` | Implemented | ✅ Implemented | aGate X |
| | `SN` | Implemented | ✅ Implemented | <SERIAL> |
| **Model 502** (PV AC Measurement) | *Discovery* | Implemented | ✅ | Model present |
| | `OutPw` | Implemented | ✅ Implemented | 0 <br>*Quirk: Coarse resolution (~100W steps), small nocturnal parasitic loads round up to 500-600W generation* |
| **Model 701** (DER Measurement) | *Discovery* | Implemented | ✅ | Model present |
| | `TmpAmb` | Implemented | ✅ Implemented | 183 |
| | `TmpCab` | Implemented | ✅ Implemented | 272 |
| | `TotWhInj` | Implemented | ✅ Implemented | 4634131 |
| | `TotWhAbs` | Implemented | ✅ Implemented | 1532087 |
| | `DERMode` | Implemented | ✅ Implemented | 1 <br>*Quirk: Includes FranklinWH-specific PV_CLIPPED state (bit 2) used during daytime off-grid PV curtailment* |
| **Model 702** (DER Capacity) | *Discovery* | Implemented | ✅ | Model present |
| | `WMaxRtg` | Broken | ⚠️ Broken (Firmware Defect) | 0 <br>*Known Issue: Always returns 0 or 1000 in Modbus but allows writes that read back exactly as written* |
| | `WChaRteMaxRtg` | Implemented | ✅ Implemented | 5000 |
| | `WDisChaRteMaxRtg` | Implemented | ✅ Implemented | 5000 |
| | `WChaRteMax` | Unimplemented | ❌ Unimplemented | None (Null) |
| | `WDisChaRteMax` | Unimplemented | ❌ Unimplemented | None (Null) |
| | `VAChaRteMax` | Unimplemented | ❌ Unimplemented | None (Null) |
| | `VADisChaRteMax` | Unimplemented | ❌ Unimplemented | None (Null) |
| **Model 704** (DER AC Controls) | *Discovery* | Implemented | ✅ | Model present |
| | `WSetEna` | Implemented | ✅ Implemented | 0 |
| | `WSetPct` | Implemented | ✅ Implemented | 0 <br>*Quirk: Inverted sign convention: negative is charge, positive is discharge* |
| | `WSetRvrtTms` | Broken | ✅ Implemented | 60 <br>*Quirk: Countdown timer counts down but does NOT revert active power settings at expiry* |
| | `WMaxLimPct` | Unimplemented | ✅ Implemented | 1000 |
| | `VarSetEna` | Unimplemented | ✅ Implemented | 0 |
| **Model 710** (DER Heartbeat) | *Discovery* | Implemented | ✅ | Model present |
| | `ControllerHb` | Unimplemented | ❓ unsupported | N/A |
| | `DERHb` | Unimplemented | ❓ unsupported | N/A |
| **Model 713** (DER Storage Capacity) | *Discovery* | Implemented | ✅ | Model present |
| | `WHRtg` | Implemented | ✅ Implemented | 13600 |
| | `SoC` | Implemented | ✅ Implemented | 630 |
| | `Sta` | Broken | ⚠️ Broken (Firmware Defect) | 0 <br>*Known Issue: Always returns 0 (OFF) regardless of whether charging or discharging* |
| **Model 714** (DER Storage AC Measurement) | *Discovery* | Implemented | ✅ | Model present |
| | `DCW` | Implemented | ✅ Implemented | 500 <br>*Quirk: Sign convention: positive is power absorbed (charging), negative is power injected (discharging)* |
| | `DCA` | Unimplemented | ✅ Implemented | 0 |
| **Model 715** (DER Lifecycle) | *Discovery* | Implemented | ✅ | Model present |
| | `LocRemCtl` | Partially_Implemented | ✅ Implemented | 1 <br>*Quirk: Reports Local (1) and is read-only, yet permits M704 power writes* |

## Extensions & Mirrors Audit
| Extension Register | Purpose | Live Status | Details |
|:---|:---|:---|:---|
| `15506` (Home Load) | Coarse active home load in Watts (snaps to ~100W steps) | ❓ Unread | No telemetry returned |
| `15507` (Operating Mode) | Native mode control: 1=Backup, 2=Self-Consumption, 3=TOU, 4=Manual. Writes undocumented. | ✅ Readable | Value: 2 |
| `15508` (Self-Consumption Reserve) | Self-consumption floor reserve percentage. Writes undocumented. | ✅ Readable | Value: 6 |
| `15509` (TOU Reserve) | Time-of-Use floor reserve percentage. Firmware defect: register always mirrors 15508 and cannot be configured independently via Modbus. | ✅ Readable | Value: 6 |
| `16000` (High-Resolution Home Load) | Undocumented high-precision home load mirror in Watts (~1W resolution vs ~100W). Used preferentially by the library. | ✅ Readable | Value: 454 |

## Safety & Orchestration Recommendations
1. **Software watchdogs are mandatory**: Since `WSetRvrtTms` countdown does not revert power setpoints and `ControllerHb` is non-functional, always provide safe timeouts `duration_s` on all power commands.
2. **Calculated Current**: `M714.DCA` is 0. Use calculated current: `I = Power / Voltage`.
3. **Battery State**: `M713.Sta` is 0. Rely on dynamic power direction: Positive is charging, negative is discharging.
4. **Reserve Controls**: Extension write registers are read-only. For battery throttling and reserve limits, rely entirely on the library's **software-based Virtual Mode Controller (VMC)**.