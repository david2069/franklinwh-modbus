# Compliance Analysis & Hardware Verification Plan (SunSpec 700 Series)

This document provides a rigorous compliance analysis of the new SunSpec 700 Series documentation (`docs/SUNSPEC2_700_SERIES_GUIDE_2.md`) compared to our current implementation, and establishes a **safe, non-destructive testing plan** to physically verify these claims on active hardware.

---

## 🔍 Key Findings & Comparative Analysis

We have analyzed the claims in the new guide against our active codebase and the [aGate X Device Scan Manifest](/docs/SUNSPEC_DEVICE_SNAPSHOT.md). The findings reveal several critical points that must be verified:

### 1. The "Disable First" Toggling Pattern
*   **The Claim**: The official SunSpec S2 specification explicitly discourages disabling a control function before writing new values: *“It is not recommended to disable... set values first, enable last.”*
*   **Our Current Implementation**: In our `VirtualModeController` and Python APIs, we execute a "Disable First" toggling sequence (`WSetEna = 0` → write setpoint → `WSetEna = 1`). While this is safe, it causes unnecessary transient state changes in the inverter.
*   **Testing Requirement**: We must test if direct setpoint writes are accepted and applied instantly by the aGate when `WSetEna = 1` remains continuously active, without toggling `WSetEna = 0`.

### 2. Model 703 `ES` Soft Disconnect (Standby)
*   **The Claim**: Inverter standby (soft disconnect) should be controlled via Model 703 (`DEREnterService`), using the `Conn` register: `Conn = 0` (disconnect/standby), `Conn = 1` (reconnect).
*   **Our Current Implementation**: We emulate standby in software by commanding `0W` active power dispatch (`704.WSetPct = 0`, `704.WSetEna = 1`).
*   **Crucial Naming Mismatch**: The downloaded guide calls this register `Conn`. However, our authoritative device snapshot confirms that on the aGate X, this point is named **`ES` (Permit Enter Service)** at address `40279`:
    ```text
    40279  ES     Permit Enter Service               1               RW -          enum16
    ```
    Attempting to write `es.Conn.value = 0` would raise an `AttributeError` in pySunSpec2. It must be addressed as `es.ES.value`.
*   **Testing Requirement**: We must verify if writing `703.ES = 0` physically soft-disconnects the inverter (ceases AC output) on the aGate, and if writing `703.ES = 1` reconnects it successfully.

### 3. Reversion Timer Resetting
*   **The Claim**: Writing a new reversion timeout (`WSetRvrtTms` or `WMaxLimPctRvrtTms`) while the control is active automatically reinitializes and restarts the countdown.
*   **Our Current Implementation**: We have documented the hardware reversion timer (`WSetRvrtTms` / `WSetRvrtRem` in Model 704) as functional on some firmware but ignored or non-functional on others.
*   **Testing Requirement**: We need to test if rewriting `WSetRvrtTms` actually reinitializes `WSetRvrtRem` and resets the physical hardware countdown timer.

### 4. Mode Scale Factors & Sign Conventions
*   **The Claim**: `WSetMod = 0` represents Percent-of-Max mode, and `WSetMod = 1` represents Watts mode. Signed `WSet` (int32) is used for exact Watts (positive = export, negative = import).
*   **Our Current Implementation**: We actively utilize percentage mode (`WSetPct`) and have partial support for Watts mode.
*   **Testing Requirement**: Validate that the aGate conforms exactly to the `WSetMod` enum mapping and that signed `WSet` (int32) acts as a high-precision alternative to `WSetPct`.

---

## 📋 Non-Destructive Hardware Verification Plan

To gather physical evidence without disrupting home power or causing unsafe battery states, we will define a series of safe, automated **Dry-Run Sequence Tests** and read-only diagnostic sweeps.

### Phase 1: Pre-Flight Read Sweep (Establish Baseline)
Before writing any registers, we will execute a complete read sweep of Models 701, 702, 703, and 704 to confirm the exact register structures and active settings.

```bash
# Read entire Model 703 (Enter Service) and Model 704 (Controls)
python3 tools/franklinwh_cli.py -i <YOUR_IP> --sequence '{"reads": ["703.ES", "703.ESDlyTms", "704.WSetMod", "704.WSetEna", "704.WSetPct"]}'
```

---

### Phase 2: "Disable First" vs "Direct Write" Test
We will test if the aGate can process setpoint transitions while remaining continuously enabled.

#### Test Sequence (`test_direct_setpoint_transition.json`)
```json
[
  {
    "step": "1. Initialize Remote Control (Standby)",
    "writes": {
      "704.WSetMod": 0,
      "704.WSetPct": 0,
      "704.WSetEna": 1
    },
    "verify": true,
    "sleep_ms": 1000,
    "note": "Establish active VPP control at 0W"
  },
  {
    "step": "2. Direct Write (Change setpoint without disabling)",
    "writes": {
      "704.WSetPct": 10
    },
    "verify": true,
    "sleep_ms": 1000,
    "note": "Write 10% discharge directly to see if the hardware accepts it without toggling WSetEna"
  },
  {
    "step": "3. Direct Write (Change setpoint back)",
    "writes": {
      "704.WSetPct": 0
    },
    "verify": true,
    "sleep_ms": 1000,
    "note": "Verify direct write back to 0% standby"
  },
  {
    "step": "4. Clean Release",
    "writes": {
      "704.WSetEna": 0,
      "704.WSetPct": 0
    },
    "verify": true,
    "sleep_ms": 500,
    "note": "Graceful release"
  }
]
```
*   **Evidence Collection**: If Step 2 succeeds, it proves the "Disable First" toggling is completely unnecessary, allowing us to streamline the codebase and eliminate transient power flow glitches.

---

### Phase 3: Model 703 `ES` Soft Disconnect (Standby) Test
We will safely test if the aGate supports soft disconnects through the entrance service module.

#### Test Sequence (`test_model703_soft_standby.json`)
```json
[
  {
    "step": "1. Capture connection status before test",
    "reads": [
      "703.ES",
      "701.ConnSt",
      "701.W"
    ]
  },
  {
    "step": "2. Command soft disconnect (Permit Enter Service = 0)",
    "writes": {
      "703.ES": 0
    },
    "verify": true,
    "sleep_ms": 2000,
    "note": "Disable entrance service. The battery should soft-disconnect from the AC grid."
  },
  {
    "step": "3. Read connection state",
    "reads": [
      "703.ES",
      "701.ConnSt",
      "701.W"
    ],
    "note": "Verify if 701.ConnSt changes or AC power drops to 0W"
  },
  {
    "step": "4. Command soft reconnect (Permit Enter Service = 1)",
    "writes": {
      "703.ES": 1
    },
    "verify": true,
    "sleep_ms": 2000,
    "note": "Permit entrance service to restore connection."
  },
  {
    "step": "5. Verify reconnection",
    "reads": [
      "703.ES",
      "701.ConnSt"
    ]
  }
]
```
*   **Evidence Collection**: If `703.ES` verifies successfully as `0` and `1`, and `701.ConnSt` reflects the changes, it confirms Model 703 soft disconnect is fully functional on standard firmware. If Step 2 returns Success but `ES` remains `1` on readback, it is silently ignored (read-only).

---

### Phase 4: Hardware Reversion Timer Refresh Test
We will test if writing a new timeout restarts the reversion countdown.

#### Test Sequence (`test_reversion_timer_refresh.json`)
```json
[
  {
    "step": "1. Configure initial reversion limit",
    "writes": {
      "704.WSetMod": 0,
      "704.WSetPct": 10,
      "704.WSetRvrt": 0,
      "704.WSetRvrtTms": 60,
      "704.WSetEnaRvrt": 1,
      "704.WSetEna": 1
    },
    "verify": true,
    "sleep_ms": 1000,
    "note": "Set 60s reversion"
  },
  {
    "step": "2. Poll remaining time",
    "reads": [
      "704.WSetRvrtRem"
    ],
    "sleep_ms": 10000,
    "note": "Sleep 10 seconds to let the timer count down"
  },
  {
    "step": "3. Read remaining countdown",
    "reads": [
      "704.WSetRvrtRem"
    ]
  },
  {
    "step": "4. Refresh reversion timer",
    "writes": {
      "704.WSetRvrtTms": 120
    },
    "verify": true,
    "sleep_ms": 1000,
    "note": "Write a new 120s timeout while active"
  },
  {
    "step": "5. Verify remaining time has refreshed",
    "reads": [
      "704.WSetRvrtRem"
    ]
  },
  {
    "step": "6. Clean Release",
    "writes": {
      "704.WSetEna": 0,
      "704.WSetPct": 0
    },
    "verify": true
  }
]
```

---

## 📈 Success Criteria & Verification Matrix

| Claim to Verify | Test Phase | Expected Functional Behavior | Fallback / Known Exception |
|:---|:---|:---|:---|
| **Direct writes without disable** | Phase 2 | Success. `WSetPct` changes immediately while `WSetEna = 1`. | Requires `WSetEna = 0` between transitions. |
| **Model 703 Soft Disconnect** | Phase 3 | Success. `703.ES = 0` ceases AC inverter output. | Register `ES` is read-only or ignored (returns ACK but remains 1). |
| **Reversion Timer Restart** | Phase 4 | Success. `WSetRvrtRem` resets to new `WSetRvrtTms` value. | `WSetRvrtRem` never counts down (static 0 or 60). |
