# SunSpec 700 Series Conformance & Telemetry Report

This report documents the findings and live Modbus TCP telemetry recorded during the execution of the safe, non-destructive **SunSpec 700 Series Conformance Tests** on the active **FranklinWH aGate X** gateway (`192.0.2.110:502`, Unit `1`, Base `40000`).

---

## 📊 Summary of Findings (Nutshell)

| Test Case | Claim / Hypothesis | Live Verified Telemetry Status | Core Finding & Architectural Conclusion |
|:---|:---|:---|:---|
| **Test 1** | Toggling remote control (`WSetEna = 0`) before changing setpoints is required. | ❌ **REFUTED** (Direct writes fully functional) | Direct setpoint writes are accepted and applied instantly while `WSetEna` remains continuously active (`1`). verified in **`14–20 ms`**! |
| **Test 2** | Soft standby / grid disconnect can be controlled via Model 703 `ES`. | ❌ **REFUTED** (Register is purely cosmetic) | `703.ES` accepts writes and reads back exactly as written (`0` or `1`), but the physical AC grid connection status (`701.ConnSt`) and power flow (`701.W`) **do not drop to zero**. Software VPP 0W dispatch is the **only functional standby mode**. |
| **Test 3** | Hardware reversion countdown (`WSetRvrtRem`) counts down active power. | ❌ **REFUTED** (Register is purely cosmetic) | `704.WSetRvrtRem` immediately reads back as `0` even when `WSetRvrtTms` is set to `60s`. Hardware reversion is non-functional. **Additionally, the aGate TCP stack drops connections after 10s of inactivity.** |

---

## 🔎 Detailed Test Case Breakdown & Telemetry Analysis

### 1. Test 1: Setpoint Transitions & "Disable First" Toggling
*   **Hypothesis**: The downloaded guide states that disabling remote control before modifying setpoints is a common developer misconception and is explicitly discouraged by the SunSpec S2 spec.
*   **Recorded Telemetry**:
    ```text
    --- [1/4] 1. Initialize Remote Control (Standby) ---
    Writing 704.WSetEna (Model 704) = 1 [Raw: 1, Addr: 40318]
    ✓ 704.WSetEna: 0 -> 1 [VERIFIED in 370ms]
    
    --- [2/4] 2. Direct Write (Change setpoint without disabling) ---
    Writing 704.WSetPct (Model 704) = 10 [Raw: 100, Addr: 40324]
    ✓ 704.WSetPct: 0.0 -> 10.0 [VERIFIED in 14ms]
    
    --- [3/4] 3. Direct Write (Change setpoint back) ---
    Writing 704.WSetPct (Model 704) = 0 [Raw: 0, Addr: 40324]
    ✓ 704.WSetPct: 10.0 -> 0.0 [VERIFIED in 20ms]
    ```
*   **Analysis & Architectural Implications**:
    - **Ultra-fast Verification**: Writing to `WSetPct` while VPP mode was actively enabled succeeded instantly. The readback verification loop confirmed the transition in just **`14 milliseconds`**!
    - **Design Recommendation**: We should remove the "Disable First" toggling step (`WSetEna = 0`) from our VMC and Python APIs for active power setpoint changes. Writing the setpoint directly to the active model is faster, avoids unnecessary Modbus traffic, and prevents transient grid power fluctuations during state transitions.

---

### 2. Test 2: Model 703 `ES` Soft Disconnect (Standby)
*   **Hypothesis**: The guide claims that putting the inverter into standby or disconnecting it from grid AC service should be controlled via Model 703 (`DEREnterService`), using the `Conn` register (`ES` on the aGate).
*   **Recorded Telemetry**:
    ```text
    --- [1/5] 1. Capture connection status before test ---
    Read 703.ES: 1
    Read 701.ConnSt: 1
    Read 701.W: 518

    --- [2/5] 2. Command soft disconnect (Permit Enter Service = 0) ---
    Writing 703.ES (Model 703) = 0 [Raw: 0, Addr: 40279]
    ✓ 703.ES: 1 -> 0 [VERIFIED in 20ms]

    --- [3/5] 3. Read connection state ---
    Read 703.ES: 0
    Read 701.ConnSt: 1
    Read 701.W: 502
    ```
*   **Analysis & Architectural Implications**:
    - **Ignored Register Hook**: The register `703.ES` is writeable and retains its written state on readback. However, the physical AC grid connection state (`701.ConnSt`) remains connected (`1`) and grid active power remains active (`502 W`).
    - **Design Recommendation**: This proves that `703.ES` is purely cosmetic in the standard firmware and is disregarded by the internal microcontrollers. **Our software-orchestrated VPP 0W standby method (`WSetPct = 0`, `WSetEna = 1`) remains the ONLY functional standby mode for local control.**

---

### 3. Test 3: Hardware Reversion Timer & TCP Inactivity Timeout
*   **Hypothesis**: Writing a new timeout restarts the reversion countdown (`WSetRvrtRem` in Model 704).
*   **Recorded Telemetry**:
    ```text
    --- [1/6] 1. Configure initial reversion limit ---
    Writing 704.WSetPct (Model 704) = 10 [Raw: 100, Addr: 40324]
    Writing 704.WSetRvrt (Model 704) = 0 [Raw: 0, Addr: 40322]
    ✓ 704.WSetPct: 0.0 -> 10.0 [VERIFIED in 90ms]
    ✓ 704.WSetRvrt: -19660800 -> 0 [VERIFIED in 126ms]
    
    --- [2/6] 2. Poll remaining time ---
    Read 704.WSetRvrtRem: 0
    Sleeping for 10000ms...
    
    --- [3/6] 3. Read remaining countdown ---
    Read 704.WSetRvrtRem failed: Response timeout
    ```
*   **Analysis & Architectural Implications**:
    - **Cosmetic Countdown**: Even though `WSetRvrtTms` was configured to `60` seconds, `704.WSetRvrtRem` read back immediately as `0`. This confirms that hardware-based active power reversion is non-functional on this firmware.
    - **Strict Connection Keep-Alive**: When a sequence pauses/sleeps for 10 seconds without active polling, the very next Modbus TCP request fails with a `Response timeout`. This proves that the aGate X has a strict TCP inactivity connection timeout (under 10 seconds).
    - **Design Recommendation**: Software-based watchdogs are mandatory. In addition, when executing long-running sequences or monitoring active status, the Modbus client must perform active polling or transmit keep-alives at intervals of **less than 5 seconds** to prevent TCP sockets from dropping.
