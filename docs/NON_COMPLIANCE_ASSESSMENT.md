# Formal Non-Compliance Assessment

**Device**: FranklinWH aGate X  
**Firmware**: `V10R01B04D00`  
**Reference Standard**: *SunSpec Alliance Interoperability Specification — Information Model Specification (#12041)*  
**Assessment Date**: 2026-05-14  

---

## 1. Executive Summary

This assessment documents specific instances where the FranklinWH aGate hardware deviates from the mandatory requirements defined in the SunSpec Information Model Specification. These deviations impact the reliability of external DER control and violate the expected error-handling behavior of a SunSpec-compliant interface.

## 2. Identified Non-Compliance Items

### 2.1 Failure to Return Mandatory Exception 3 (Illegal Data Value)
**Point(s) Impacted**: M704.WSetPct (324), M704.WSet (320)  
**Requirement**: *#12041 v1.9, Error Handling — Invalid Setting Value, p. 19*  
> "When a setting is written with an unsupported value for the implementation... An exception '3' Illegal Data Value **must be returned** and processing of the write operation must terminate."

**Finding**: **NON-COMPLIANT**.  
The hardware accepts values exceeding its physical and rated capacity (e.g., `WSetPct = 1500`) with a Modbus success code (ACK). This failure to validate and reject out-of-range setpoints violates the mandatory input validation requirements of the standard.

### 2.2 Inconsistent Implementation of PICS-Declared "Supported RW" Points
**Point(s) Impacted**: M704.WMaxLimPctEna (310), M704.VarSetEna (331), M715.ControllerHb (1092)  
**Requirement**: *SunSpec PICS Protocol Implementation Conformance Statement*  
> "All points declared as 'Supported' and 'Read/Write' (RW) must persist state changes and initiate the associated hardware behavior."

**Finding**: **NON-COMPLIANT**.  
These registers are officially declared as **Supported RW** in the manufacturer's PICS, yet they exhibit **non-compliant write-ignore behavior**. Writes are acknowledged as successful but have no effect on the register state or the hardware. Under #12041 v1.9, Error Handling (p. 19), this behavior is only acceptable for registers declared as **Read-Only (R)**.

### 2.3 Null Physical Efficacy of Functional Reversion Timer
**Point(s) Impacted**: M704.WSetRvrtTms (327), M704.WSetRvrtRem (329)  
**Requirement**: *SunSpec 704 — DER Control Model*  
> "The reversion timer must trigger a physical state transition to the defined reversion setpoint upon reaching zero."

**Finding**: **NON-COMPLIANT**.  
While the register implementation of the countdown timer is functional (it accepts writes and performs a decrementing countdown), it has **null physical efficacy**. The hardware does not initiate the mandatory power reversion or release the Remote Control enable (`WSetEna`) upon timer expiry.

## 3. Impact Assessment

The combination of **non-compliant write-ignore behavior** and the lack of **Exception 3 validation** creates an "unreliable control state" where the client software cannot definitively confirm hardware readiness via Modbus acknowledgments alone. 

## 4. Remediation Recommendations

1.  **Firmware Update**: Align Modbus layer error-handling with #12041 v1.9, Error Handling, p. 19 (throw Exception 3 for out-of-range values).
2.  **PICS Correction**: Re-classify non-functional control registers as **Read-Only (R)** or **Unimplemented (0xFFFF)** until physical support is released.
3.  **Physical Linkage**: Connect the `WSetRvrtTms` software countdown to the hardware's active-power state machine.
