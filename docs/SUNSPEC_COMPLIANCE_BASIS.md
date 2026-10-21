# SunSpec Compliance & Validation Basis

This document defines the technical and authoritative basis for the testing protocols used in the `franklinwh-modbus` project. All verification tests are designed to adhere to the official standards published by the **SunSpec Alliance**. FranklinWH is listed by the Alliance at [sunspec.org/contributing-members/franklin-wh](https://sunspec.org/contributing-members/franklin-wh/).

## 1. Authoritative Reference Documents

In the absence of vendor-specific Modbus documentation from FranklinWH, this implementation defers **religiously** to the official SunSpec Alliance specifications as the absolute source of truth for all development, testing, and compliance auditing.

| Document ID | Title | Purpose |
|-------------|-------|---------|
| **#12041** | [SunSpec Information Model Specification](https://sunspec.org/about-sunspec-specifications/) | Core protocol architecture, addressing, and data types. |
| **700-Series** | [SunSpec DER Information Models](https://sunspec.org/about-sunspec-specifications/) | Specific definitions for Models 701–715 (Energy Storage & Control). |

> [!IMPORTANT]
> All developers and testers MUST consult the **SunSpec Specification Package** (available at [sunspec.org](https://sunspec.org/)) before proposing any change to control logic or register interpretation.

### Citations

| Standard | Version | Role in this Project |
|:---|:---|:---|
| **SunSpec Information Model** | v1.1 | Defines the "SunS" marker (0x53756E53) at a well-known starting PDU address (0, 40000 or 50000), the model chain, and Scale Factor math. |
| **SunSpec DER Control (704)** | v1.0 | Defines the M704 register map, `WSetEna` master triggers, and `WSetMod` behaviors. |
| **SunSpec Device Info (1)** | v1.1 | Defines the Common Model (Manufacturer, Version, Serial Number). |
| **MODBUS Application Protocol Specification** | V1.1b3 (2012-04-26) | **Source of truth for Modbus addressing and naming:** 0-based PDU addresses, holding registers, FC03 (Read), FC06 (Write Single), FC16 (Write Multiple). Published at modbus.org/specifications. |
| **MODBUS Messaging on TCP/IP Implementation Guide** | V1.0b (2006-10-24) | Modbus TCP framing (MBAP header, unit identifier). Published at modbus.org/specifications. |

## 2. The Sequencing Basis (The "Why")

Quotes in this section are verbatim from the SunSpec documents named, under their own section headings. Earlier versions of this file quoted text that couldn't be found in any SunSpec document (#95); it has been removed.

### Basis: enabling and changing a control

**DER Information Model Specification v1.2, §3.3 Modbus Enable:**
> "When the enable field is set to 0, any changes made to the setting will not take effect."
> "If an enable is set to 1, any changes to the corresponding settings will be applied to the DER. Rewriting the enable is not required for the changes to be applied."

**#12041, *Procedures for Multi-Write Operations*:**
> "It is not recommended to disable the control to update the settings."

**Conflict:** #12041's *Change Procedure* (§5 below) says changes do not take effect until the activation field is enabled, even if it is already enabled. DER v1.2 §3.3 says rewriting the enable is not required. For 700-series models we follow DER v1.2.

**What the library does, and why it differs:** `send_command()` writes `WSetEna=0`, then `WSetMod` and the setpoint, then `WSetEna=1`. Writing `WSetEna=0` first is our own choice, not a SunSpec requirement, and #12041 recommends against it. It is a variance from the standard.

### Basis: discovery and base address

**#12041, *Base and Alternate Base Register Addresses*:** "Device Modbus maps begin at one of three well-known Modbus base addresses": 40001 (preferred), 50001 and 00001, which are offsets 40000, 50000 and 0 on the wire. The map starts with the 'SunS' identifier (0x53756e53).

**SunSpec Modbus Conformance Test Procedures v1.4, DEV-1:** the content must be "located at one of the SunSpec standard Modbus start addresses (0, 40000, or 50000)".

**Implementation:** a map at any of the three addresses is compliant. The aGate's map starts at PDU 0 (§6). The library's own 15500 range is a FranklinWH extension, outside SunSpec.

## 3. Scale Factor Basis

**DER Information Model v1.2, Model 704:** `WSetPct` is in Pct, with scale factor `WSetPct_SF`. The engineering value is `raw × 10^SF`, the standard SunSpec convention for `sunssf` points.

**Worked example** (aGate, `WSetPct_SF` = −1 on V10R01B04D00 and V12R02B60D00, as declared in PICS SM-000028):
-   A 500 W discharge on a 5 kW aPower is 10 %.
-   Raw register value = 10 / 10^−1 = `100`.
-   Raw `1000` = 100 %; raw `1500` = 150 %.

## 4. Hardware Violation Classification

When our test (following the basis above) returns a failure, we classify it as a **PICS Violation** if the manufacturer's **Protocol Implementation Conformance Statement** claims support for a register that fails our 6-phase validation.

**Reference**: *UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx* (FranklinWH's declaration for SunSpec certificate SM-000028; not copied into this repository).

---

## 5. Multi-Write Operations (Official Procedures)

**Source**: *SunSpec Alliance Interoperability Specification — Information Model Specification (#12041), v1.9*

### Procedures for Multi-Write Operations
> "For operations that require multiple writes (e.g. set operating parameters and then enable), the procedure is recommended. It is not recommended to disable the control to update the settings."

#### Enable Procedure:
1.  **All settings are written**
2.  **The activation field is enabled**

#### Change Procedure:
1.  **Changed settings are written.** Changes do NOT take effect, even if the activation field is already enabled, until the activation field is enabled.
2.  **The activation field is enabled.**

DER Information Model v1.2 §3.3 differs for 700-series models: rewriting the enable is not required (§2).

### Organization of Control Read/Write Values
**Citation**: *#12041, Organization of Control Read/Write Values*
> "Control operations that rely on a group of settings must have a register to control the activation (enabling / disabling) of the control. To facilitate that goal, the following guidelines are recommended:
> - Related writable settings field are organized in a contiguous block
> - **Activation fields are located at the end of the settings block**"

---

## 6. Logical vs. Wire Addressing (The PDU Basis)

**Source**: *#12041, Base and Alternate Base Register Addresses*

| Type | Logical Address | Wire/PDU Offset (Hex) |
|:---|:---:|:---:|
| **Preferred Base** | 40001 | 0x9C40 (40000) |
| **Alternate Base** | 50001 | 0xC350 (50000) |
| **Alternate Base** | 00001 | 0x0000 (0) |

**What the library does:** these are the starting PDU addresses where SunSpec allows the "SunS" marker to sit; the "logical address" column is the Modicon 4xxxx-style reference for the same register. **The aGate's map starts at PDU 0** (V10R01B04D00), so the library scans with `base_address=0` (`controller.py`, `sequencer.py`). PDU 40000+ returned exception 2 on V10R01B04D00 and mirrors the map on V12R02B60D00. `discovery.py` probes 0, 40000, 50000 and 30000 to find other devices' maps. Addresses in these docs are PDU addresses; see QUIRKS, Register Addressing.

---

## 7. Error Handling & Unimplemented Behavior

**Source**: *#12041, Error Handling*

### Read-Only Registers (The "Silent Discard" Basis)
> "The following behavior is defined when attempting to write to a read-only register or read from a write-only register.
> - **WRITE to R: The written value is ignored. No exception is generated.**"

**Validation**:
Under #12041, an acknowledged write that doesn't change a register is compliant only if the register is read-only. The PICS declares `WMaxLimPctEna` RW, so this doesn't apply to it.

**Conflict:** the Conformance Test Procedures v1.4 (EXC-2) require a write to a read-only register to get exception 2, 3 or 4. Certification uses v1.4.

### Unimplemented Registers
> "Unimplemented registers should have the following behavior:
> - **READ**: The value returned is the SunSpec unimplemented value.
> - **WRITE**: The written value is ignored. No exception is generated."

**Validation**:
The unimplemented value for a `uint16` is `0xFFFF`. This is consistent with `WChaRteMax` (259) reading `0xFFFF`, although the PICS declares `WChaRteMax` RW.

### Invalid Setting Value (The "Validation Failure" Basis)
> "When a setting is written with an unsupported value for the implementation, the following must occur:
> - **An exception '3' Illegal Data Value must be returned** and processing of the write operation must terminate."

**Violation**:
**V10R01B04D00:** accepted raw `WSetPct=1500` (150 % at SF −1) without exception 3 (2026-03-13 test).

**V12R02B60D00:** returns exception 3 for raw values above 100 and for all negative values (#92). That is the required behaviour for unsupported values, but the PICS declares Max 100 in engineering units (100 %, raw 1000) and records no limitation. See the V12 conformance plan (PR #94), §4.

