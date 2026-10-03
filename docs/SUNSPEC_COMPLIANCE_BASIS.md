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
| **SunSpec Information Model** | v1.1 | Defines PDU discovery (Base 40000), "SunS" identification, and Scale Factor math. |
| **SunSpec DER Control (704)** | v1.0 | Defines the M704 register map, `WSetEna` master triggers, and `WSetMod` behaviors. |
| **SunSpec Device Info (1)** | v1.1 | Defines the Common Model (Manufacturer, Version, Serial Number). |
| **Modbus Application Protocol** | v1.1b | Defines FC03 (Read), FC06 (Write Single), and FC16 (Write Multiple). |

## 2. The 6-Phase Sequencing Basis (The "Why")

While the SunSpec 704 specification defines register *meaning*, the **SunSpec 2 State Machine** and implementer guides (e.g., *SunSpec Device Integration Guide*) mandate a specific orchestration to ensure safety and atomicity.

### Basis: The "Atomic Trigger" Requirement
**Citation**: *SunSpec 704, Section 3.1.1 (Enable Control)*
> "The Enable register (`*Ena`) must be used to activate a control group. The DER must not react to changes in setpoint registers until the Enable register is transitioned from 0 to 1."

**Implementation in our Sequencer**:
To prevent "Ghost Ramps" or invalid power spikes, our sequencer follows this mandatory sequence:
1.  **Phase 3 (Write Setpoint)**: We write the target value (e.g., `WSetPct`) first.
2.  **Phase 4 (Write Enable)**: We write `WSetEna=1` as a separate, final Modbus transaction.
*   *Why*: If we wrote `WSetEna=1` first, the hardware might attempt to discharge at the *previous* or *default* value before our new setpoint arrives.

### Basis: PDU Addressing (The Discovery Paradox)
**Citation**: *SunSpec Information Model, Section 4.2 (Discovery)*
> "The SunSpec identifier (0x5375, 0x6e53) must be located at the base address + 0. For Modbus TCP, the base address is commonly 40,000."

**Implementation**: 
Our `modbus_sunspec2_reader.py` follows this discovery basis. If the "SunS" marker is not found at 40000, the device is considered non-compliant. The "Addressing Paradox" we documented is the bridge between this official SunSpec 40000 block and FranklinWH's proprietary 15500 block.

## 3. Scale Factor Formula Basis

**Citation**: *SunSpec Information Model, Section 3.3.2 (Scaled Integer)*
> "Scaled integers are represented by a base value and a scale factor (SF). The physical value is calculated as: `Value = Base * 10^SF`."

**Validation**:
If `WMaxRtg` is 10,000 and we want to charge at 500W:
-   `WSetPct` requires a percentage.
-   M704 `WSetPct_SF` is -2.
-   Target % = 5.00%.
-   Raw register write = `500` (since $500 \times 10^{-2} = 5.00$).

## 4. Hardware Violation Classification

When our test (following the basis above) returns a failure, we classify it as a **PICS Violation** if the manufacturer's **Protocol Implementation Conformance Statement** claims support for a register that fails our 6-phase validation.

**Reference**: `docs/UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx` (FranklinWH Official Claim).

---

## 5. Multi-Write Operations (Official Procedures)

**Source**: *SunSpec Alliance Interoperability Specification — Information Model Specification (#12041), v1.9*

### Procedures for Multi-Write Operations
> "For operations that require multiple writes (e.g. set operating parameters and then enable), the following procedure is recommended. It is not recommended to disable the control to update the settings."

#### Enable Procedure:
1.  **All settings are written**
2.  **The activation field is enabled**

#### Change Procedure:
1.  **Changed settings are written.** Changes do NOT take effect, even if the activation field is already enabled, until the activation field is enabled.
2.  **The activation field is enabled.**

### Organization of Control Read/Write Values
**Citation**: *Section 19*
> "Control operations that rely on a group of settings must have a register to control the activation (enabling / disabling) of the control. To facilitate that goal, the following guidelines are recommended:
> - Related writable settings fields are organized in a contiguous block.
> - **Activation fields are located at the end of the settings block.**"

---

## 6. Logical vs. Wire Addressing (The PDU Basis)

**Source**: *SunSpec Information Model Overview, Section 18*

| Type | Logical Address | Wire/PDU Offset (Hex) |
|:---|:---:|:---:|
| **Preferred Base** | 40001 | 0x9C40 (40000) |
| **Alternate Base** | 50001 | 0xC350 (50000) |
| **Alternate Base** | 00001 | 0x0000 (0) |

**Validation Strategy**:
Our library targets the **Wire Offset 40000** exactly as mandated by the standard for reading register 40001. Any attempt to use 1-based indexing in a 0-based PDU environment is a common source of "off-by-one" errors which our `SunSpecSequencer` now explicitly avoids.

---

## 7. Error Handling & Unimplemented Behavior

**Source**: *SunSpec Information Model Overview, Section 18-19*

### Read-Only Registers (The "Silent Discard" Basis)
> "The following behavior is defined when attempting to write to a read-only register: **WRITE to R: The written value is ignored. No exception is generated.**"

**Validation**:
This confirms that the aGate returning a Modbus ACK (Success) while failing to update a register (like `WMaxLimPctEna`) is **technically compliant** with the SunSpec standard IF that register is internally flagged as Read-Only by the manufacturer.

### Unimplemented Registers
> "Unimplemented registers should have the following behavior:
> - **READ**: The value returned is the SunSpec unimplemented value (typically `0xFFFF`).
> - **WRITE**: The written value is ignored. No exception is generated."

**Validation**:
This explains why `WChaRteMax` (259) returns `0xFFFF`. It is the official SunSpec way of saying the feature is not supported in this firmware version.

### Invalid Setting Value (The "Validation Failure" Basis)
> "When a setting is written with an unsupported value for the implementation, the following must occur:
> - **An exception '3' Illegal Data Value must be returned** and processing of the write operation must terminate."

**Violation**:
The aGate **violates** this requirement. It accepts `WSetPct=1500` (which is 1500% power) without returning Exception 3. This indicates a lack of mandatory input validation at the Modbus layer.

