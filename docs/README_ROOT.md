# franklinwh-modbus

[![Modbus TCP](https://img.shields.io/badge/modbus-tcp-orange.svg)](https://modbus.org)
[![SunSpec](https://img.shields.io/badge/sunspec-2.0-yellow.svg)](https://sunspec.org)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

A Python library for controlling FranklinWH battery storage systems via Modbus TCP, optimized for the aGate gateway with SunSpec model support and FranklinWH extension registers.

> 📖 **New to Modbus TCP?** See the [documentation site](https://david2069.github.io/franklinwh-modbus/) for an introduction to Modbus TCP, SunSpec, and how this library compares to the Cloud API.

> **Note:** This is the Modbus TCP library (`pip install franklinwh-modbus`).  
> 
> Python import: `from franklinwh_modbus import FranklinWHController`
>
>>  For the non-Modbus TCP FranklinWH david2069 franklinwh-cloud Cloud API, see [franklinwh-cloud](https://github.com/david2069/franklinwh-cloud).
>
>>  For the non-Modbus TCP FranklinWH richo franklinwh-python Cloud API, see [franklinwh-python](https://pypi.org/project/franklinwh-python/). 

> **Status:** Published on PyPI (`pip install franklinwh-modbus`) and actively maintained.

## Quick Links

- [🚀 Getting Started](./docs/GETTING_STARTED.md) — setup, install, CLI, network scanner & SunSpec reader
- [📖 Library & CLI Usage Guide](./USAGE_GUIDE.md)
- [📚 Documentation](./docs/README.md)
- [🧪 Hardware Test Guide](./docs/HARDWARE_TEST_GUIDE.md)
- [📝 Changelog](./CHANGELOG.md)

## ⚠️ Important — Before You Start

### Network Requirements

- **Fixed IP address required** — the aGate must have a static/reserved IP on your LAN.
- **LAN Ethernet strongly preferred** — wired connection for reliable Modbus TCP control.
- ⚠️ **WiFi is highly undesirable** — latency and packet loss can cause missed keep-alive cycles, leaving the aGate stuck in VPP Mode.

### Extension Register Access

**Read operations always work** — battery status, grid power, solar production (proximal and remote), system alarms, and all SunSpec model data are readable by any Modbus TCP client without provisioning. The CLI `--status`, `--healthcheck`, and TUI monitor all work out of the box.

**Extension registers (15507–15509: OnGridMode, SelfReserve, TOUReserve):** Writes to the FranklinWH extension registers are undocumented and unconfirmed. FranklinWH has not documented these registers and has never documented any of them as writable. Whether FranklinWH must authorise a Modbus client to write them, and how, is unknown. On `V12R02B60D00` (owner observation, 2026-10-21), writes to 15507–15509 did not take effect: the mode did not switch and the reserves did not change. Treat them as read-only.

The library's setters (`set_native_mode()`, `set_self_consumption_reserve()`, `set_tou_reserve()`) attempt the write, read the register back, and return `(ok, message)` with the read-back result. They do not promise any effect.

**Note:** Standard SunSpec M704 power commands (charge/discharge) are separate from the extension registers.

### Avoiding Control Conflicts

!!! caution
    **Do not use the FranklinWH mobile app** to send charge/discharge commands or schedule events while this library is actively controlling the aGate. Conflicting commands will cause unpredictable behavior.

- **Recommended:** Set your aGate to **Emergency Backup** or **Self-Consumption** mode via the mobile app *before* starting library control — this reduces the likelihood of conflicting Cloud API activity.
- **VPP Mode indicator:** While any remote client API is actively controlling the aGate — Modbus TCP (this library) or the FranklinWH Cloud API (VPP providers) — the mobile app displays **"VPP Mode"**. This is normal and confirms direct control is active. See [VPP Mode Visual Reference](./docs/VPP_MODE_REFERENCE.md) for mobile app screenshots.
- **On failure or loss of connectivity:** Always release control using `--stop`:

```bash
# Via CLI
python3 franklinwh_cli.py -i YOUR_AGATE_IP --stop

# Via library
ctrl.reset_control_state()
ctrl.disconnect()
```

!!! warning
    If control is not released, the aGate **persists the last command indefinitely**. Hardware heartbeat (`ControllerHb`) and reversion timer (`WSetRvrtTms`) do not work on FranklinWH — use `--revert N` or `send_command(cmd, duration_s=N)` for software-side auto-revert.

## Installation

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

## Library Usage

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand

# Connect to aGate
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Read battery status (battery_state derived from DC power, not unreliable M713.Sta)
status = ctrl.read_battery_status()
print(f"SoC: {status['soc']:.1f}%  State: {status['battery_state']}")

# Charge at 3000W with 1-hour software timeout (auto-reverts to cloud control)
cmd = BatteryCommand(power_watts=3000, mode='charge')
ctrl.send_command(cmd, duration_s=3600)

# Release control (or let timeout handle it)
ctrl.reset_control_state()
ctrl.disconnect()
```

## CLI Quick Start

```bash
# System status
python3 franklinwh_cli.py -i YOUR_AGATE_IP --status

# Health check with conflict detection
python3 franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck

# Charge at 3000W with auto-revert after 2 hours
python3 franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --revert 7200

# Native hardware mode (Register 15507)
python3 franklinwh_cli.py -i YOUR_AGATE_IP --mode self-consumption

# Virtual software mode (Orchestrated control loop)
python3 franklinwh_cli.py -i YOUR_AGATE_IP --vmode self_consumption --target-soc 90

# Terminal UI monitor (requires `rich`)
python3 franklinwh_cli.py -i YOUR_AGATE_IP --monitor

# Release control
python3 franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Modbus TCP** | Direct register read/write via pymodbus |
| **SunSpec Models** | Models 1, 701-706, 713-715 |
| **FranklinWH Extensions** | Registers 15507-15509 (OnGridMode, reserves) |
| **Virtual Modes** | Self-Consumption, Emergency Backup, TOU, Peak Shave, Manual |
| **Conflict Detection** | Detects aGate Cloud API activity before taking control |
| **SoC Safety** | Reserve validation, target checking, safety margins |
| **Alarm Monitoring** | System, DC port, battery, solar alarms |
| **Auto-Revert** | Software timeout (hardware reversion non-functional on FranklinWH) |

## Project Structure

```
franklinwh-modbus/
├── src/franklinwh_modbus/          # Core library (the package)
│   ├── controller.py        # FranklinWHController — Modbus interface
│   ├── modes.py             # VirtualModeController — control modes
│   ├── types.py             # BatteryCommand, VirtualMode, enums
│   ├── schedule.py          # TOUSchedule — time-of-use
│   ├── monitor.py           # CLIMonitor — TUI (optional, needs rich)
│   └── constants.py         # Register addresses, limits
├── tools/franklinwh_cli.py   # CLI tool (consumes the library)
├── tests/                   # Unit + integration + hardware tests
├── docs/                    # Documentation
├── tools/                   # Utility scripts
└── schedules/               # TOU schedule definitions
```

## Supported Hardware

| Model | Status | Notes |
|-------|--------|-------|
| FranklinWH aPower | ✅ Full Support | Battery storage |
| FranklinWH aGate | ✅ Full Support | Communication gateway |

## SunSpec Model Support

> **Note:** aGate uses base address **1** (not standard 40000). Unit ID **1** or **2** both work (DA=1).

| Model | Description | Read | Write | Notes |
|-------|-------------|------|-------|-------|
| 1 | Common | ✅ | ❌ | |
| 502 | Solar Module | ✅ | ❌ | PV production (proximal + remote) |
| 701 | DER AC Measurement | ✅ | ❌ | |
| 702 | DER Capacity | ✅ | ❌ | Nameplate ratings |
| 703 | Enter Service | ✅ | ❌ | |
| 704 | DER AC Controls | ✅ | ✅ | WSetPct/WSetEna confirmed working |
| 705 | DER Volt-Var | ✅ | ⚠️ | Untested |
| 706 | DER Volt-Watt | ✅ | ⚠️ | Untested |
| 713 | DER Storage Capacity | ✅ | ❌ | ⚠️ Sta always 0 (unreliable) |
| 714 | DER DC Measurement | ✅ | ❌ | DCW used for battery-state derivation; multi-stack aware |
| 715 | DERCtl | ✅ | ❌ | LocRemCtl read-only, heartbeat non-functional |

## FranklinWH Extension Registers

| Register | Address | Access | Description |
|----------|---------|--------|-------------|
| OnGridMode | 15507 | R (writes undocumented) | 1=Backup, 2=Self-Consumption, 3=TOU |
| Self Reserve SOC | 15508 | R (writes undocumented) | Self-consumption reserve percentage (0-100) |
| TOU Reserve SOC | 15509 | R (writes undocumented) | ⚠️ Known defect: always mirrors 15508 |

See [FRANKLINWH_SUNSPEC_QUIRKS.md](./docs/FRANKLINWH_SUNSPEC_QUIRKS.md) for all documented hardware quirks.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License — see [LICENSE](./LICENSE) for details.

## Support

- 🐛 [Report a Bug](https://github.com/david2069/franklinwh-modbus/issues/new?template=bug_report.md)
- 💡 [Request a Feature](https://github.com/david2069/franklinwh-modbus/issues/new?template=feature_request.md)
- 📖 [CLI Command Reference](./docs/CLI_COMMAND_REFERENCE.md)
- 📖 [Modbus Reader Reference](./docs/MODBUS_READER_REFERENCE.md)
- 📖 [Full Documentation](./docs/README.md)
