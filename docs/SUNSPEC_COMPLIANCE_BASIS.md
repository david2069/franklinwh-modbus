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
| **SunSpec Information Model Specification (#12041)** | v1.9 (its page headers read "Information Model Overview - Version 1.8") | Defines the "SunS" marker (0x53756E53) at a well-known base address, the model chain, scale factors, and error handling (pp. 16–21). |
| **SunSpec DER Information Model Specification** | v1.2 | Defines enable and reversion behaviour (§3.2–3.3, pp. 12–14) and Models 701–714, including M704 DER AC Controls (§4.4, pp. 40–46). |
| **SunSpec model definitions** | as bundled with pysunspec2 1.3.6 | Point names, types and descriptions, including the Common Model (1) and M704. |
| **MODBUS Application Protocol Specification** | V1.1b3 (2012-04-26) | **Source of truth for Modbus addressing and naming:** 0-based PDU addresses, holding registers, FC03 (Read), FC06 (Write Single), FC16 (Write Multiple). Published at modbus.org/specifications. |
| **MODBUS Messaging on TCP/IP Implementation Guide** | V1.0b (2006-10-24) | Modbus TCP framing (MBAP header, unit identifier). Published at modbus.org/specifications. |

## 2. The 6-Phase Sequencing Basis (The "Why")

The SunSpec documents define what each register means. The order of writes comes from #12041's multi-write procedure (§5 below).

### Basis: Write the Settings, Then the Enable
**Citation**: *#12041 v1.9, Procedures for Multi-Write Operations, p. 21*
> "Enable Procedure: 1. All settings are written 2. The activation field is enabled"

**Changing a setpoint while enabled.** The two SunSpec documents differ here:
- #12041 v1.9, p. 21: "Changes do NOT take effect, even if the activation field is already enabled, until the activation field is enabled."
- DER Information Model v1.2, §3.3 Modbus Enable, p. 14: "If an enable is set to 1, any changes to the corresponding settings will be applied to the DER. Rewriting the enable is not required for the changes to be applied."

For Models 701–714 the library follows the DER Information Model (§3.3), the more specific document. The aGate behaves that way on V12R02B60D00: a setpoint changed while enabled takes effect without rewriting `WSetEna` (`SUNSPEC_M704_V12_CONFORMANCE_RESULTS.md`, c1).

**Implementation in our Sequencer**:
To prevent "Ghost Ramps" or invalid power spikes, our sequencer follows this mandatory sequence:
1.  **Phase 3 (Write Setpoint)**: We write the target value (e.g., `WSetPct`) first.
2.  **Phase 4 (Write Enable)**: We write `WSetEna=1` as a separate, final Modbus transaction.
*   *Why*: If we wrote `WSetEna=1` first, the hardware might attempt to discharge at the *previous* or *default* value before our new setpoint arrives.

### Basis: Discovery at the Base Addresses
**Citation**: *#12041 v1.9, Modbus Register Mappings, p. 16*
> "All SunSpec device maps begin at one of the well-known base addresses and start with the well-known 32-bit 'SunS' identifier (0x53756e53). This allows for discovery of SunSpec compatible devices. If the base register does not return this value, the alternate base registers are checked. If this test fails, the device is not SunSpec compatible."

**Implementation**: the library looks for "SunS" at the preferred and alternate base addresses (§6). The aGate's map starts at PDU 0, an alternate base, which is compliant. The extension registers (15000+, 15500+, 16000+) are outside the SunSpec map.

## 3. Scale Factor Formula Basis

**Citation**: *#12041 v1.9, Scale Factors, p. 16*
> "The scale factor explicitly shifts the decimal point to the left (negative value) or the right (positive value)."

So the physical value is the raw value × 10^SF. The same page gives the `sunssf` range as −10 … 10, and says "If a value is implemented and has an associated scale factor, the scale factor must also be implemented."

**Example on the aGate**: `WMaxRtg` (M702) is 5000 W and M704 `WSetPct_SF` is −1 on both firmwares. A 500 W discharge is 10.0 %, written as raw `100` (100 × 10^−1 = 10.0).

## 4. Hardware Violation Classification

When our test (following the basis above) returns a failure, we classify it as a **PICS Violation** if the manufacturer's **Protocol Implementation Conformance Statement** claims support for a register that fails our 6-phase validation.

**Reference**: *UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx* (FranklinWH official claim; proprietary, not distributed in this repository).

---

## 5. Multi-Write Operations (Official Procedures)

**Source**: *SunSpec Information Model Specification (#12041), v1.9, pp. 19–21*

### Procedures for Multi-Write Operations (p. 21)
> "For operations that require multiple writes (e.g. set operating parameters and then enable), the procedure is recommended. It is not recommended to disable the control to update the settings."

#### Enable Procedure:
1.  **All settings are written**
2.  **The activation field is enabled**

#### Change Procedure:
1.  **Changed settings are written.** Changes do NOT take effect, even if the activation field is already enabled, until the activation field is enabled.
2.  **The activation field is enabled.**

For Models 701–714, the DER Information Model v1.2 §3.3 says the opposite for changes while enabled (see §2).

### Organization of Control Read/Write Values
**Citation**: *Organization of Control Read/Write Values, pp. 19–20*
> "Control operations that rely on a group of settings must have a register to control the activation (enabling / disabling) of the control. To facilitate that goal, the following guidelines are recommended:
> - Related writable settings field are organized in a contiguous block
> - **Activation fields are located at the end of the settings block**
> - Activation fields only operate on the behavior related to that settings block"

---

## 6. Logical vs. Wire Addressing (The PDU Basis)

**Source**: *#12041 v1.9, Base and Alternate Base Register Addresses, p. 17*: "Preferred Base Register: 40001", "Alternate Base Register: 50001", "Alternate Base Register: 00001", and "To read register 40001, use the hexadecimal offset of 0x9C40 (40000) on the wire." The other two offsets follow the same rule.

| Type | Logical Address | Wire/PDU Offset (Hex) |
|:---|:---:|:---:|
| **Preferred Base** | 40001 | 0x9C40 (40000) |
| **Alternate Base** | 50001 | 0xC350 (50000) |
| **Alternate Base** | 00001 | 0x0000 (0) |

**What the library does:** these are the starting PDU addresses where SunSpec allows the "SunS" marker to sit; the "logical address" column is the Modicon 4xxxx-style reference for the same register. **The aGate's map starts at PDU 0** (V10R01B04D00), so the library scans with `base_address=0` (`controller.py`, `sequencer.py`). PDU 40000+ returned exception 2 on V10R01B04D00 and mirrors the map on V12R02B60D00. `discovery.py` probes 0, 40000, 50000 and 30000 to find other devices' maps. Addresses in these docs are PDU addresses; see QUIRKS, Register Addressing.

---

## 7. Error Handling & Unimplemented Behavior

**Source**: *#12041 v1.9, Error Handling, p. 19*

### Read-Only Registers (The "Silent Discard" Basis)
> "The following behavior is defined when attempting to write to a read-only register or read from a write-only register.
> - **WRITE to R: The written value is ignored. No exception is generated.**"

**Validation**:
This confirms that the aGate returning a Modbus ACK (Success) while failing to update a register (like `WMaxLimPctEna`) is **technically compliant** with the SunSpec standard IF that register is internally flagged as Read-Only by the manufacturer.

### Unimplemented Registers
> "Unimplemented registers should have the following behavior:
> - **READ**: The value returned is the SunSpec unimplemented value.
> - **WRITE**: The written value is ignored. No exception is generated."

The unimplemented value depends on the type, for example `0xFFFF` for `uint16` and `0x8000` for `sunssf` (p. 16).

**Validation**:
This explains why `WChaRteMax` (259) returns `0xFFFF`. It is the official SunSpec way of saying the feature is not supported in this firmware version.

### Invalid Setting Value (The "Validation Failure" Basis)
> "When a setting is written with an unsupported value for the implementation, the following must occur:
> - **An exception "3" Illegal Data Value must be returned** and processing of the write operation must terminate. Previous registers may have been written but no subsequent registers can be written.
> - Such limitations must be documented in the PICS"

**Violation (V10R01B04D00)**: the aGate accepted `WSetPct` = 1500 raw (150 %, scale −1) without exception 3 (2026-03-13).

**On V12R02B60D00**: the aGate returns exception 3 for `WSetPct` above 100 raw (10.0 %) and for every negative `WSetPct` or `WSet` (#104). That is the required response, but the limits are not documented in the PICS, which the same page requires.

