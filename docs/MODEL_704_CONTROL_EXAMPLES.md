# SunSpec Model 704 Control Examples & Handover Handbook

This document provides a comprehensive handbook of **Model 704 (Active Power & Power Factor Control)** capabilities on the FranklinWH aGate system. It outlines the exact register layouts, write sequences, safety protocols, and real-world control patterns.

---

## 🔒 Writability Disclaimer & Hardware Support

> [!IMPORTANT]
> **FranklinWH Extensions & Write Permissions**
> - **Active Power Remote Control (`WSet` Group)** is fully functional and writable on all standard FranklinWH aGate installations.
> - **Active Power Curtailment (`WMaxLimPct` Group)** writes were silently discarded in testing. FranklinWH extension register writes are undocumented and unconfirmed: FranklinWH has never documented any of them as writable, and on V12R02B60D00 (2026-10-21) writes to 15507–15509 did not take effect. Treat both as read-only.
> - When writing registers, writes to read-only registers will return a Modbus **Success (ACK)** packet but will be **silently ignored/discarded** internally by the gateway's firmware. The only way to verify successful writes is through readback verification.

---

## ⏱️ The SunSpec 6-Phase Sequencing Protocol

To ensure reliable control state transitions and prevent hardware race conditions or Modbus buffer overflows, all control operations must be executed in a structured, phased sequence:

```
Phase 0: PRE-FLIGHT READS       ← Captured baseline telemetry; no writes yet.
Phase 1: CONFIGURE MODE         ← Write configuration and operating mode registers.
Phase 2: SAFETY / REVERSION     ← Write reversion rates, timeouts, and reversion flags.
Phase 3: WRITE SETPOINT         ← Write the target active power / limit setpoint.
Phase 4: ENABLE (Commit)        ← Write the enable register last — this is the "go" trigger.
Phase 5: VERIFY READBACK        ← Read back the registers to confirm they are accepted.
```

### Hardware Settling and Timing Requirements
- **Command Settling Delay**: Allow at least **`200ms`** between configuring parameters and writing the enable register.
- **Modbus Inter-command Delay**: Allow at least **`100ms`** between individual writes to prevent Modbus TCP/serial buffer overflows.
- **Ramp Processing Delay**: Allow at least **`500ms`** after enabling a mode before reading back telemetry or initiating verification loops.

---

## 🔄 Safety Flow Integration (Standby & Clean Release)

To guarantee predictable physical transitions and prevent the battery from becoming locked in remote VPP mode permanently, all active power control sequences should utilize the following safety flow:

1. **Initial Standby Initialization**: Before dispatching charge/discharge power, initialize remote VPP mode with `0W` power flow. This establishes control safely without sudden power spikes.
   ```python
   model704.WSetMod = 0    # Absolute watts mode
   model704.WSetPct = 0    # 0% / 0W setpoint
   model704.WSetEna = 1    # Enable remote control last
   ```
2. **Core Operation Execution**: Transition the setpoint to the desired dispatch value.
3. **Explicit Cleanup & Handover**: Upon sequence completion or exit, always release control explicitly to return the aGate to its native automatic operating mode (e.g. Self-Consumption, Backup).
   ```python
   model704.WSetEna = 0    # Disable remote control
   model704.WSetPct = 0    # Reset setpoint to 0
   ```

---

## 📖 Model 704 Control Examples

### Group 3: Limit Maximum Export Power
Use these registers to restrict the maximum power exported from the battery/inverter to the grid.

> [!WARNING]
> These curtailment registers silently discarded writes in testing. FranklinWH has not documented any setting that changes this.

#### Use Case A: Temporary 5kW Export Limit (50% of a 10kW Inverter)
Utility requires a temporary 5kW export limit, reverting to 100% rated capacity after 1 hour (3600 seconds).

```python
# Sequential Write Sequence:
model704.WMaxLimPct = 50          # 1. Setpoint: 50% of rated capacity
model704.WMaxLimPctRvrt = 100     # 2. Reversion value: Revert to 100% on timeout
model704.WMaxLimPctRvrtTms = 3600 # 3. Timeout: 3600 seconds (1 hour)
model704.WMaxLimPctEnaRvrt = 1    # 4. Enable reversion safety
model704.WMaxLimPctEna = 1        # 5. Enable the limit (write last)
```

#### Use Case B: Permanent 3kW Export Limit (30% of a 10kW Inverter)
A permanent export limit with reversion disabled.

```python
# Sequential Write Sequence:
model704.WMaxLimPct = 30          # 1. Setpoint: 30% of capacity (3kW)
model704.WMaxLimPctEnaRvrt = 0    # 2. Disable reversion (make limit permanent)
model704.WMaxLimPctEna = 1        # 3. Enable the limit (write last)
```

#### Disable Export Limiting
Exiting and turning off all export limits:

```python
model704.WMaxLimPctEna = 0        # Turn off export limit control
```

---

### Group 4: Set Exact Power Output
Use these registers to force the battery to charge or discharge at an exact rate under remote VPP control. 

* **Positive (+) values**: Discharging (exporting power to home/grid).
* **Negative (-) values**: Charging (importing power from solar/grid).

#### Use Case A: Force Battery Discharge at 1000W (Absolute Mode)
Force battery discharge at exactly 1000W, reverting to 0W idle after 30 minutes (1800 seconds).

```python
# Sequential Write Sequence:
model704.WSetMod = 0              # 1. Configure mode: 0 = absolute watts mode
model704.WSet = 1000              # 2. Setpoint: 1000W discharge (positive)
model704.WSetRvrt = 0             # 3. Reversion value: Revert to 0W on timeout
model704.WSetRvrtTms = 1800       # 4. Timeout: 1800 seconds (30 minutes)
model704.WSetEnaRvrt = 1          # 5. Enable reversion safety
model704.WSetEna = 1              # 6. Enable remote control (write last)
```

#### Use Case B: Force Battery Charge at 2000W (Absolute Mode)
Force battery charge at exactly 2000W from the grid, reverting to 0W idle after 2 hours (7200 seconds).

```python
# Sequential Write Sequence:
model704.WSetMod = 0              # 1. Configure mode: absolute watts mode
model704.WSet = -2000             # 2. Setpoint: -2000W charge (negative)
model704.WSetRvrt = 0             # 3. Reversion value: Revert to 0W
model704.WSetRvrtTms = 7200       # 4. Timeout: 7200 seconds (2 hours)
model704.WSetEnaRvrt = 1          # 5. Enable reversion safety
model704.WSetEna = 1              # 6. Enable remote control (write last)
```

#### Use Case C: Discharge at 50% Rate (Percentage Mode)
Discharge at 50% of rated max capacity using percentage mode, reverting to 0% after 1 hour (3600 seconds).

```python
# Sequential Write Sequence:
model704.WSetMod = 1              # 1. Configure mode: 1 = percentage mode
model704.WSetPct = 50             # 2. Setpoint: 50% of rated capacity
model704.WSetPctRvrt = 0          # 3. Reversion value: Revert to 0%
model704.WSetRvrtTms = 3600       # 4. Timeout: 3600 seconds (1 hour)
model704.WSetEnaRvrt = 1          # 5. Enable reversion safety
model704.WSetEna = 1              # 6. Enable remote control (write last)
```

#### Disable Active Power Dispatch (Release Control)
Explicitly stop VPP operations and restore native automatic operation:

```python
model704.WSetEna = 0              # Disable remote control
```

---

### Group 1 & 2: Power Factor Control
Use these registers to enable reactive power / power factor offset operations required by local utilities.

* **Scale Factor**: Power Factor (PF) values use a standard scale factor of **`-3`**, meaning a PF of `0.95` is represented as raw value `950`, and a PF of `0.90` is represented as raw value `900`.

#### Use Case A: 0.95 Power Factor During Export
Utility requires 0.95 power factor when exporting power to the grid (injection).

```python
model704.PFWInjEna = 1            # Enable PF control for injection (export)
```

#### Use Case B: 0.90 Power Factor During Import
Maintain 0.90 power factor when absorbing/charging from the grid.

```python
model704.PFWAbsEna = 1            # Enable PF control for absorbing (import)
```

---

## 🛠️ Real-World Scenario Sequences

### Scenario A: Time-of-Use (TOU) Arbitrage
Charge the battery from the grid during off-peak hours (midnight to 6am at 3kW), and discharge to home loads during peak hours (4pm to 9pm at 5kW).

#### 1. Off-Peak Charge Step (Midnight)
```python
model704.WSetMod = 0
model704.WSet = -3000             # -3000W charge from grid
model704.WSetRvrtTms = 21600      # 21600 seconds (6 hours)
model704.WSetEnaRvrt = 1          # Revert to 0W after off-peak ends
model704.WSetEna = 1              # Enable
```

#### 2. Peak Discharge Step (4:00 PM)
```python
model704.WSetMod = 0
model704.WSet = 5000              # 5000W discharge to home/grid
model704.WSetRvrtTms = 18000      # 18000 seconds (5 hours)
model704.WSetEnaRvrt = 1          # Revert to 0W after peak ends
model704.WSetEna = 1              # Enable
```

---

### Scenario B: Zero Export
Completely prevent any power from exporting to the grid (essential in zero-export compliance zones).

```python
model704.WMaxLimPct = 0           # 0% export power allowed
model704.WMaxLimPctEnaRvrt = 0    # Disable reversion (make limit permanent)
model704.WMaxLimPctEna = 1        # Enable the limit
```

---

### Scenario C: Emergency Backup Hold
Stop all battery discharge to preserve capacity for a forecasted grid outage or severe weather emergency.

```python
model704.WSetMod = 0
model704.WSet = 0                 # Force 0W discharge flow
model704.WSetRvrtTms = 86400      # Hold for 24 hours (86400 seconds)
model704.WSetEnaRvrt = 1          # Revert to standard mode after 24h
model704.WSetEna = 1              # Enable Remote Hold
```

---

## 🗃️ Model 704 Register Address Reference

| Register Point | Modbus PDU Addr | SunSpec Type | Scale Factor | Range / Values | Description |
|:---|:---|:---|:---|:---|:---|
| **`WMaxLimPctEna`** | `310` | `enum16` | — | `0` = Disabled, `1` = Enabled | Enable active power curtailment limit. |
| **`WMaxLimPct`** | `311` | `uint16` | `-2` / `-1` | `0` to `100` (%) | Target active power curtailment limit rate. |
| **`WMaxLimPctEnaRvrt`**| `313` | `enum16` | — | `0` = Disabled, `1` = Enabled | Enable reversion for curtailment. |
| **`WMaxLimPctRvrt`** | `312` | `uint16` | `-2` / `-1` | `0` to `100` (%) | Reversion value for curtailment. |
| **`WMaxLimPctRvrtTms`**| `314` (32-bit) | `uint32` | — | `0` to `86400` (s) | Reversion timeout duration in seconds. |
| **`WSetEna`** | `318` | `enum16` | — | `0` = Disabled, `1` = Enabled | Enable remote active power dispatch (VPP). |
| **`WSetMod`** | `319` | `enum16` | — | `0` = Watts, `1` = Percent | Active power mode. |
| **`WSet`** | `320` (32-bit) | `int32` | `0` | `-10000` to `10000` (W) | Target active power setpoint (Watts mode). |
| **`WSetPct`** | `324` | `int16` | `-2` / `-1` | `-100` to `100` (%) | Target active power setpoint (Percent mode). |
| **`WSetEnaRvrt`** | `328` | `enum16` | — | `0` = Disabled, `1` = Enabled | Enable reversion for dispatch. |
| **`WSetRvrt`** | `325` (32-bit) | `int32` | `0` | `-10000` to `10000` (W) | Reversion value (Watts mode). |
| **`WSetPctRvrt`** | `326` | `int16` | `-2` / `-1` | `-100` to `100` (%) | Reversion value (Percent mode). |
| **`WSetRvrtTms`** | `327` | `uint32` | — | `0` to `86400` (s) | Reversion timeout duration in seconds. |
| **`WSetRvrtRem`** | `329` | `uint32` | — | `0` to `86400` (s) | Remaining time before reversion. |
| **`PFWInjEna`** | `330` | `enum16` | — | `0` = Disabled, `1` = Enabled | Enable PF control during export (injection). |
| **`PFWAbsEna`** | `331` | `enum16` | — | `0` = Disabled, `1` = Enabled | Enable PF control during import (absorption). |

---

## 🖥️ Executing Sequences via the CLI

All sequences detailed in this guide are pre-configured as JSON sequence files located under the `examples/sequencer/` directory.

To run any sequence, invoke the `franklinwh_cli.py` utility with the `--sequence-file` option:

```bash
# Execute a temporary export limit sequence
python3 tools/franklinwh_cli.py -i <YOUR_AGATE_IP> --sequence-file examples/sequencer/limit_export_temporary.json

# Execute an active discharge dispatch sequence
python3 tools/franklinwh_cli.py -i <YOUR_AGATE_IP> --sequence-file examples/sequencer/discharge_watts_temporary.json
```

To run dry-run validation on a sequence file (which reads initial states and simulates execution without executing writes):
```bash
python3 tools/franklinwh_cli.py -i <YOUR_AGATE_IP> --sequence-file examples/sequencer/scenario_tou_charge.json --dry-run
```
