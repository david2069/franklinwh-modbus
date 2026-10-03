# FranklinWH Modbus

Unofficial Python library & CLI for controlling **FranklinWH** battery storage systems via Modbus TCP, optimized for the aGate gateway.

!!! warning "Important Disclaimer"
    This library is **unofficial** and **not endorsed, supported, or affiliated with FranklinWH** in any way.

    It is provided **"AS IS"**, for **educational and informational purposes only**, without warranty of any kind, express or implied, including but not limited to warranties of merchantability or **fitness for any particular purpose**. The author(s) and contributor(s) of this library and its documentation accept **no responsibility or liability** for any consequences of its use, and make **no warranty that it is fit for any purpose**.

    **By using this library, you acknowledge that:**

    - This software **writes to energy hardware** and can charge, discharge and stop your battery
    - You assume **all risk** associated with its use
    - It may break without notice due to **firmware changes** by FranklinWH
    - Behaviour observed on one firmware or model may not hold on yours
    - You will use it responsibly

    **Do NOT contact FranklinWH support** about defects, issues or feature requests for this software. They did not write it and cannot help with it. Raise them at [github.com/david2069/franklinwh-modbus/issues](https://github.com/david2069/franklinwh-modbus/issues) instead.

!!! info "SunSpec Alliance membership"
    FranklinWH is a **SunSpec Alliance contributing member**:
    [sunspec.org/contributing-members/franklin-wh](https://sunspec.org/contributing-members/franklin-wh/)

    That membership is why the aGate speaks SunSpec at all — the device exposes
    the standard SunSpec information models (1, 701–715, 502) that this library
    reads and writes, alongside FranklinWH's own manufacturer extension block at
    15500+.

    For how this library's conformance work is grounded, see
    [SunSpec Compliance Basis](SUNSPEC_COMPLIANCE_BASIS.md) for the specification
    documents used, and [PICS Conformance Cross-Reference](PICS_CONFORMANCE_CROSS_REFERENCE.md)
    for what this device was observed to implement.

!!! note "Related Project"
    For the FranklinWH Cloud API (non-Modbus), see [franklinwh-cloud](https://david2069.github.io/franklinwh-cloud/).

---

## Overview

**FranklinWH Modbus** provides direct, vendor-agnostic local network control over your aGate via the Modbus TCP protocol. Because it communicates directly with the hardware on your LAN, it operates entirely offline, bypasses cloud limits, and offers near-instantaneous response times (≤50ms).

👉 **[Read the complete guide on What Modbus TCP is, its challenges, and how it compares to the Cloud API](WHAT_IS_MODBUS_TCP.md)**

---

## FranklinWH Implementation Coverage

What the **aGate X / aPower S** system implements via Modbus TCP:

### ✅ Working

| Function | Model | Details |
|----------|-------|---------|
| Battery charge / discharge / standby | M704 (WSetPct) | Primary control mechanism — percentage of rated max |
| Battery SoC, SoH, DC power | M713 / M714 | M713.Sta unreliable (always 0) — state derived from M714.DCW |
| Battery lifetime energy | M714 (DCWhInj / DCWhAbs) | Cumulative charge and discharge (Wh) |
| AC grid power, voltage, frequency | M701 | Full implementation including per-phase data |
| Grid lifetime energy | M701 (TotWhInj / TotWhAbs) | Cumulative grid export and import (Wh) |
| Solar AC output power | M502 (OutPw / OutWh) | AC-coupled solar production and lifetime total |
| Grid protection trip curves | M707–M710 | Under/over voltage and frequency (read + write) |
| Volt-Var / Volt-Watt curves | M705 / M706 | Readable; writes untested |
| Frequency droop response | M711 | Readable; writes untested |
| Temperatures | M701 (TmpAmb / TmpCab) | Ambient and cabinet temperature |

### ❌ Not Functional

| Function | Model | Issue |
|----------|-------|-------|
| DER heartbeat | M715 (ControllerHb) | Ignored by aGate — use software timeout instead |
| Hardware reversion timer | M704 (WSetRvrtTms) | Non-functional — software auto-revert used |
| DC battery voltage | M714 (DCV) | Register not populated |
| DC battery current | M714 (DCA) | Always returns 0 — calculate from P/V |
| Solar voltage / current | M502 (OutV / InV) | Not populated |

### ⚠️ Requires SPAN Unlock

| Function | Register | Without SPAN |
|----------|----------|-------------|
| Work mode switching | Ext 15507 (OnGridMode) | Read-only |
| Self-consumption reserve | Ext 15508 | Read-only |
| TOU reserve | Ext 15509 | Read-only (also mirrors 15508 — known defect) |

## Features

- **[Modbus TCP](WHAT_IS_MODBUS_TCP.md)** — Direct register read/write via pymodbus + SunSpec 2.0
- **[SunSpec Models](DER_CONTROL_REFERENCE.md)** — Models 1, 701–706, 713–715
- **[FranklinWH Extensions](FRANKLINWH_SUNSPEC_QUIRKS.md)** — Registers 15507–15509 (OnGridMode, reserves)
- **[CLI Tool](CLI_COMMAND_REFERENCE.md)** — `franklinwh_cli.py` with charge, discharge, standby, healthcheck, and a live **[TUI monitor](TUI_MONITOR_GUIDE.md)**
- **[Virtual Modes](VIRTUAL_MODE_SPECIFICATIONS.md)** — Self-Consumption, Emergency Backup, TOU, Peak Shave, Manual
- **[Safety Controls](SAFETY_CONTROLS.md)** — SoC validation, alarm monitoring, conflict detection, auto-revert
- **[Target SoC](ORCHESTRATION_AND_CONTROL.md)** — Charge/discharge to specific SoC with auto-stop

## Quick Start

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

## CLI

```bash
CLI="python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP"

$CLI --status                    # Compact status
$CLI --healthcheck               # System health check
$CLI --charge 3000               # Charge at 3000W
$CLI --discharge 2000            # Discharge at 2000W
$CLI --standby                   # Force battery idle
$CLI --charge 3000 --target-soc-auto 80 --loop  # Charge to 80%
$CLI --stop                      # Release control
$CLI --monitor                   # Interactive TUI dashboard
```

## Library

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Read battery status
status = ctrl.read_battery_status()
print(f"SoC: {status['soc']:.1f}%  State: {status['battery_state']}")

# Charge at 3000W with 1-hour auto-revert
cmd = BatteryCommand(power_watts=3000, mode='charge')
ctrl.send_command(cmd, duration_s=3600)

# Release control
ctrl.reset_control_state()
ctrl.disconnect()
```

## SunSpec Model Support

| Model | Description | Read | Write | Notes |
|-------|-------------|:----:|:-----:|-------|
| 1 | Common | ✅ | ❌ | |
| 502 | Solar Module | ✅ | ❌ | PV production (proximal + remote) |
| 701 | DER AC Measurement | ✅ | ❌ | DERMode: Grid Following, Grid Forming, PV Clipped |
| 702 | DER Capacity | ✅ | ❌ | Nameplate ratings |
| 703 | Enter Service | ✅ | ❌ | |
| 704 | DER AC Controls | ✅ | ✅ | WSetPct/WSetEna confirmed working |
| 705 | DER Volt-Var | ✅ | ⚠️ | Untested |
| 706 | DER Volt-Watt | ✅ | ⚠️ | Untested |
| 713 | DER Storage Capacity | ✅ | ❌ | ⚠️ Sta always 0 (unreliable) |
| 714 | DER DC Measurement | ✅ | ❌ | DCW used for battery-state derivation; multi-stack aware |
| 715 | DERCtl | ✅ | ❌ | LocRemCtl read-only, heartbeat non-functional |

## Documentation

Explore the sidebar for detailed guides on:

- **[Modbus Guide](FRANKLINWH_MODBUS_GUIDE.md)** — Start here: definitive implementation guide
- **[Model 704 Control Examples](MODEL_704_CONTROL_EXAMPLES.md)** — Handbook and JSON sequence examples for power control
- **[SunSpec 700 Series Guide 2](SUNSPEC2_700_SERIES_GUIDE_2.md)** — Core reference for 700 series Modbus standard rules
- **[SunSpec 700 Series Verification Plan](SUNSPEC_700_SERIES_VERIFICATION_PLAN.md)** — Non-destructive verification strategy
- **[Conformance & Telemetry Report](SUNSPEC_700_SERIES_TEST_REPORT.md)** — Telemetry and findings from the live aGate hardware tests
- **[CLI Command Reference](CLI_COMMAND_REFERENCE.md)** — All switches tested with live output
- **[SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md)** — Hardware-specific quirks and workarounds
- **[DER Control Reference](DER_CONTROL_REFERENCE.md)** — Complete M704/M715 register map
- **[Safety Controls](SAFETY_CONTROLS.md)** — 10 safety rules for development
