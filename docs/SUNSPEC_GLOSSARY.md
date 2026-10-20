# SunSpec Alliance Modbus Glossary & Index

This document serves as the definitive reference for all SunSpec Info Points and FranklinWH Extension registers implemented in the aGate firmware. 

## Glossary Status Codes
*   **I (Implemented)**: Logic exists in the library to handle this point.
*   **V (Verified)**: Physically tested on FranklinWH hardware and confirmed functional.
*   **U (Unimplemented)**: Register exists but returns `None`, `0`, or ignores writes (Hardware limitation).
*   **T (Untested)**: Register discovered but behavior has not yet been validated.

---

> **Addresses:** "PDU address" is the 0-based Modbus address sent on the wire, as listed in the FranklinWH PICS. The "PDU + 40000" column is where a device whose SunSpec map starts at 40000 would place the point. The aGate's map starts at PDU 0. PDU 40000+ returned exception 2 on V10R01B04D00, and mirrors the map on V12R02B60D00. It is not the Modicon 4xxxx reference, which would be PDU + 40001. See QUIRKS, Register Addressing.

## 1. FranklinWH Extension Registers (15500+)
**Purpose**: Proprietary registers for operating modes, solar granularity, and internal reserves.

| Point | PDU address | Status | Description |
| :--- | :---: | :---: | :--- |
| **PVUse** | 15500 | **I, V** | **PV Installed (Native)**: Indicates if proximal solar is configured. |
| **apBoxPVUse** | 15501 | **I, V** | **Remote PV Installed**: Indicates if aPbox/aHub solar is configured. |
| **PVOutputP** | 15502 | **I, V** | **Total PV Power (W)**: Combined production from all solar sources. |
| **proximalPVOutputP**| 15503 | **I, V** | **Proximal PV Power (W)**: Production from direct aGate solar inputs. |
| **Remote1PV** | 15504 | **I, V** | **Remote 1 PV (W)**: Production from the first remote accessory (aPbox). |
| **Remote2PV** | 15505 | **I, V** | **Remote 2 PV (W)**: Production from the second remote accessory. |
| **LoadActiveP** | 15506 | **I, V** | **Home Load Power (W)**: Current real-time consumption of the home. |
| **OnGridMode** | 15507 | **I, V** | **Operating Mode**: 1=Emergency Backup, 2=Self-Consumption, 3=Time-of-Use. |
| **SelfReserve** | 15508 | **I, V** | **Self-Consumption SOC Reserve (%)**: Minimum SoC target for self-consumption. |
| **TouReserve** | 15509 | **I, V** | **TOU SOC Reserve (%)**: Minimum SoC target during TOU discharge. |

---

## 2. M704 — DER AC Controls
**Purpose**: Primary control path for active and reactive power.

| Point | PDU address | PDU + 40000 (map at 40000; not the aGate) | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **WSetEna** | 318 | 40318 | **I, V** | **Remote Control Enable**: Master switch for external control. Must be `1` for the aGate to accept power setpoints. |
| **WSetMod** | 319 | 40319 | **I, V** | **Power Setpoint Mode**: Configuration mode for power commands. |
| **WSet** | 320 | 40320 | **I, V** | **Power Setpoint (W)**: Command battery power in absolute Watts. Negative=Charge, Positive=Discharge. |
| **WSetPct** | 324 | 40324 | **I, V** | **Power Setpoint (%)**: Command battery power as a percentage of `WMaxRtg`. |
| **WSetRvrtTms** | 327 | 40327 | **I, V** | **Dead-man Timer**: Reversion timeout. Confirmed functional 2026-05-14. |
| **PFWInjEna** | 298 | 40298 | **I, V** | **Power Factor Enable**: Enables reactive power/PF control. |

---

## 3. M713 — Storage Capacity
**Purpose**: Battery energy ratings and State of Charge.

| Point | PDU address | PDU + 40000 (map at 40000; not the aGate) | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **WHRtg** | 1035 | 41035 | **I, V** | **Total Energy Rating (Wh)**: The nameplate capacity of the battery system. |
| **WHAvail** | 1036 | 41036 | **I, V** | **Available Energy (Wh)**: Remaining energy available for discharge. |
| **SoC** | 1037 | 41037 | **I, V** | **State of Charge (%)**: Percentage of battery charge remaining. |
| **Sta** | 1033 | 41033 | **I, U** | **Storage Status**: 1=Empty, 2=Discharging, 3=Charging. *Note: Always returns 0 on FranklinWH.* |

---

## 4. M714 — DC Measurement
**Purpose**: Granular DC-side battery telemetry.

| Point | PDU address | PDU + 40000 (map at 40000; not the aGate) | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **DCW** | 1067 | 41067 | **I, V** | **DC Power (W)**: Real-time battery flow. Positive=Charging, Negative=Discharging. |
| **DCV** | 1069 | 41069 | **I, V** | **DC Voltage (V)**: Combined DC bus voltage of the battery strings. |
| **DCA** | 1070 | 41070 | **I, U** | **DC Current (A)**: Battery current. *Note: Returns 0. Derive via I = P/V.* |
| **Tmp** | 1071 | 41071 | **I, V** | **Internal Temperature (°C)**: Internal battery cell/stack temperature. |
| **DCWhInj** | 1073 | 41073 | **I, V** | **DC Energy Injected (Wh)**: Lifetime energy discharged from the battery. |
| **DCWhAbs** | 1075 | 41075 | **I, V** | **DC Energy Absorbed (Wh)**: Lifetime energy charged into the battery. |

---

## 5. M701 — DER Measurement
**Purpose**: Real-time AC grid and inverter telemetry.

| Point | PDU address | PDU + 40000 (map at 40000; not the aGate) | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **St** | 73 | 40073 | **I, V** | **Operating State**: 1=Off, 2=Sleeping, 3=Starting, 4=Mppt, 5=Throttled, 6=Shutting down, 7=Fault, 8=Standby. |
| **W** | 80 | 40080 | **I, V** | **Total Active Power (W)**: Real-time grid power. Positive=Import, Negative=Export. |
| **LNV** | 86 | 40086 | **I, V** | **Phase Voltage (L-N)**: Measured AC line voltage. |
| **Hz** | 87 | 40087 | **I, V** | **Frequency (Hz)**: Measured AC grid frequency. |
| **TmpAmb** | 105 | 40105 | **I, V** | **Ambient Temp (°C)**: Temperature outside the aGate enclosure. |
| **TmpCab** | 106 | 40106 | **I, V** | **Cabinet Temp (°C)**: Temperature inside the aGate electronics cabinet. |
| **TotWhInj** | 89 | 40089 | **I, V** | **Lifetime Grid Export (Wh)**: Total AC energy sent to the grid. |
| **TotWhAbs** | 93 | 40093 | **I, V** | **Lifetime Grid Import (Wh)**: Total AC energy pulled from the grid. |

---

## 6. M1 — Common
**Purpose**: Device identification and metadata.

| Point | PDU address | PDU + 40000 (map at 40000; not the aGate) | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Mn** | 4 | 40004 | **I, V** | **Manufacturer**: "FranklinWH Technologies Co., Ltd". |
| **Md** | 20 | 40020 | **I, V** | **Model**: "aGate X". |
| **Vr** | 44 | 40044 | **I, V** | **Firmware Version**: The currently installed firmware version. |
| **SN** | 52 | 40052 | **I, V** | **Serial Number**: Unique device identifier. |
| **DA** | 68 | 40068 | **I, V** | **Device Address**: Modbus Unit ID / Slave ID. |

---

## 7. M715 — DER Lifecycle
**Purpose**: Safety heartbeats and control authorization.

| Point | PDU address | PDU + 40000 (map at 40000; not the aGate) | Status | Description |
| :--- | :---: | :---: | :---: | :--- |
| **LocRemCtl** | 1089 | 41089 | **I, V** | **Control Status**: 0=Remote, 1=Local. *Note: FranklinWH is always Local(1).* |
| **ControllerHb**| 1092 | 41092 | **I, U** | **Heartbeat**: Watchdog counter. *Note: Accepted but ignored by aGate.* |
