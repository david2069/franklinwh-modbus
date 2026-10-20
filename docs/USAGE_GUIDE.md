# franklinwh-modbus — Library & CLI Usage Guide

Complete guide for using the `franklinwh-modbus` library and CLI.

> **Package name:** `pip install franklinwh-modbus`  
> **Python import:** `from franklinwh_modbus import ...`  
> Not to be confused with `franklinwh-python` (Cloud API).

---

## Table of Contents

1. [Prerequisites & Safety](#prerequisites--safety)
2. [Installation & Setup](#installation--setup)
3. [CLI Quick Reference](#cli-quick-reference)
4. [Library Usage Examples](#library-usage-examples)
5. [Common Operations](#common-operations)
6. [Advanced Features](#advanced-features)
7. [API Reference](#api-reference)

---

## Prerequisites & Safety

### Network Requirements

!!! warning
    **WiFi connections are highly undesirable** for Modbus TCP control. WiFi latency, packet loss, and disconnections can cause missed keep-alive cycles, leaving the aGate stuck in VPP Mode.

- **Fixed IP address required** — the aGate must have a static/reserved IP on your LAN
- **LAN Ethernet preferred** — wired connection between Modbus client and aGate for reliability
- **WiFi:** Functional but unreliable for sustained control sessions; acceptable for read-only status checks

### Register Access — Read vs Write

The library accesses the aGate via two mechanisms:

**SunSpec Models (always readable — no provisioning needed):**

All standard SunSpec registers are readable by any Modbus TCP client. This includes battery status, grid power, solar production (proximal and remote AC/DC), system alarms, nameplate data, and control status. The CLI `--status`, `--healthcheck`, `--check-alarms`, and TUI monitor all use these read-only registers.

**FranklinWH Extension Registers (read-only; writes undocumented):**

| Register | Address | Access |
|----------|---------|--------|
| OnGridMode | 15507 | R (writes undocumented) |
| SelfReserve | 15508 | R (writes undocumented) |
| TOUReserve | 15509 | R (writes undocumented) |

These extension registers hold the aGate operating mode and reserve levels.

Writes to the FranklinWH extension registers are undocumented and unconfirmed. FranklinWH has not documented these registers and has never documented any of them as writable. Whether FranklinWH must authorise a Modbus client to write them, and how, is unknown. On `V12R02B60D00` (owner observation, 2026-10-21), writes to 15507–15509 did not take effect: the mode did not switch and the reserves did not change. Treat them as read-only.

The library's setters (`set_native_mode()`, `set_self_consumption_reserve()`, `set_tou_reserve()`) attempt the write, read the register back, and return `(ok, message)` with the read-back result. They do not promise any effect.

FranklinWH has no obligation to support end-customer use of Modbus TCP for any purpose. Standard SunSpec M704 power commands (`send_command()`: charge, discharge, standby) are separate from the extension registers. Read-only features (`--status`, `--healthcheck`, TUI monitor) work.

### Mobile App Conflicts

!!! caution
    **Do not use the FranklinWH mobile app to send commands** (charge, discharge, or schedule events) while this library is actively controlling the aGate. Conflicting commands cause unpredictable behavior and may damage equipment.

**Before starting library control:**
1. Set your aGate to **Emergency Backup** or **Self-Consumption** mode in the mobile app
2. Avoid scheduling any events in the mobile app
3. Do not manually trigger charge/discharge from the app

### VPP Mode Indicator

When **any remote client API** takes direct control of the aGate — whether via Modbus TCP (this library) or the FranklinWH Cloud API (used by VPP providers) — the FranklinWH mobile app displays the operating mode as:

> **"VPP Mode"** (Virtual Power Plant)

This replaces the normal mode display (Self-Consumption, Time-of-Use, or Emergency Backup). **This is normal and expected** — it confirms that a remote client has direct control of the aGate. VPP Mode remains active as long as the Modbus TCP keep-alive or Cloud API polling is maintaining the connection.

> **Note:** Only one aGate is displayed at a time in the mobile app. VPP Mode appears for the currently selected aGate.

📸 See [VPP Mode Visual Reference](./docs/VPP_MODE_REFERENCE.md) for mobile app screenshots showing before, during, and after control.

### Releasing Control

!!! important
    **Always release control when done.** If control is not released, the aGate remains in VPP Mode until the Modbus keep-alive times out (typically 60–120 seconds).

**Via CLI:**
```bash
python3 franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

**Via library:**
```python
ctrl.reset_control_state()   # Sends WSetEna=0 to release control
ctrl.disconnect()             # Close Modbus TCP connection
```

**After failure or crash:**
```bash
# Reconnect and force release
python3 franklinwh_cli.py -i YOUR_AGATE_IP --stop --reset-on-start
```

If `--stop` fails (e.g. network unreachable), the aGate will automatically revert to its previous mode after the keep-alive timeout.

---

## Installation & Setup

### Install as Package (Recommended)

```bash
git clone git@github.com:david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate

# Core library + dev tools
pip install -e ".[dev]"

# With TUI monitor support
pip install -e ".[dev,monitor]"
```

### For External Projects (e.g. FranklinWH Energy Manager)

```bash
# Path dependency during development
pip install -e /path/to/franklinwh-modbus

# Or when published to PyPi (future)
pip install franklinwh-modbus
```

### Import Patterns

```python
# Core library imports (always available)
from franklinwh_modbus import FranklinWHController, VirtualModeController, VirtualMode
from franklinwh_modbus import BatteryCommand, ControlMode, HealthStatus

# For CLI/scripts with signal handling
from franklinwh_modbus import run_with_signal_handling

# Optional monitor import (requires 'pip install franklinwh[monitor]')
try:
    from franklinwh_modbus import CLIMonitor, MonitorConfig
except ImportError:
    pass  # rich not installed
```

### Install Extras

| Extra | Packages | Install |
|-------|----------|---------|
| Core | pysunspec2, pymodbus | `pip install franklinwh-modbus` |
| `[monitor]` | rich | `pip install franklinwh-modbus[monitor]` |
| `[dev]` | pytest, pytest-mock | `pip install franklinwh-modbus[dev]` |

---

## Migration from Standalone Script

> **Note:** `franklinwh_control_standalone.py` is deprecated.
> The library (`franklinwh_modbus`) is the replacement.

### Before (Standalone — deprecated)
```python
from franklinwh_control_standalone import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
```

### After (Library — v0.9.0)
```python
from franklinwh_modbus import FranklinWHController
ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()
```

### Key Differences

| Aspect | Standalone | Library v0.9.0 |
|--------|------------|----------------|
| Install | `sys.path` hack | `pip install -e .` |
| Import | `franklinwh_control_standalone` | `franklinwh` |
| Signal handling | In library (breaks consumers) | Opt-in via `run_with_signal_handling()` |
| Package | Single script | Proper package with `__init__.py` |

---

## CLI Quick Reference

### Basic Commands

```bash
# View system status
python franklinwh_cli.py -i YOUR_AGATE_IP --status

# Health check
python franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck

# Check alarms (detailed)
python franklinwh_cli.py -i YOUR_AGATE_IP --check-alarms

# Clear alarms
python franklinwh_cli.py -i YOUR_AGATE_IP --clear-alarms
```

### Battery Control

```bash
# Charge at 3000W for 1 hour
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --duration 3600

# Discharge at 2000W for 30 minutes
python franklinwh_cli.py -i YOUR_AGATE_IP --discharge 2000 --duration 1800

# Maximum charge (uses rated power from nameplate)
python franklinwh_cli.py -i YOUR_AGATE_IP --max-charge --duration 3600

# Maximum discharge
python franklinwh_cli.py -i YOUR_AGATE_IP --max-discharge --duration 3600

# Standby (0W)
python franklinwh_cli.py -i YOUR_AGATE_IP --standby

# Release control to cloud
python franklinwh_cli.py -i YOUR_AGATE_IP --stop
```

### Virtual Modes

```bash
# Self-consumption mode
python franklinwh_cli.py -i YOUR_AGATE_IP --mode self_consumption --target-soc 90

# Emergency backup
python franklinwh_cli.py -i YOUR_AGATE_IP --mode emergency_backup --target-soc 95

# Peak shaving
python franklinwh_cli.py -i YOUR_AGATE_IP --mode peak_shave --threshold 2000

# Manual mode with power
python franklinwh_cli.py -i YOUR_AGATE_IP --mode manual --charge 3000
```

### Safety Limits & Conflict Detection

```bash
# Charge with max SoC limit (exit when reached)
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --max-charge-soc 95

# Discharge with min SoC limit (exit when reached)
python franklinwh_cli.py -i YOUR_AGATE_IP --discharge 3000 --min-discharge-soc 20

# Force operation despite limits
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --force

# Skip conflict detection (advanced users only)
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --assume-clean-state
```

### Auto-Revert Timer (Safety)

```bash
# Charge for 1 hour, then automatically release control
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --revert 3600

# Discharge for 30 minutes, then auto-revert
python franklinwh_cli.py -i YOUR_AGATE_IP --discharge 3000 --revert 1800

# Self-consumption mode with safety timeout
python franklinwh_cli.py -i YOUR_AGATE_IP --mode self_consumption --target-soc 90 --revert 7200
```

### Target SoC Auto-Stop

Charge or discharge until a specific SoC is reached, then automatically stop:

```bash
# Charge until 95% SoC, then stop
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --target-soc-auto 95

# Discharge until 30% SoC, then stop
python franklinwh_cli.py -i YOUR_AGATE_IP --discharge 3000 --target-soc-auto 30

# Combined with duration (whichever comes first)
python franklinwh_cli.py -i YOUR_AGATE_IP --charge 3000 --target-soc-auto 95 --duration 3600
```

**How it works:**
1. Checks if target is achievable (target > current for charge, target < current for discharge)
2. Starts operation at specified power
3. Monitors SoC every 5 seconds
4. Stops and releases control when target reached
5. Shows progress updates with current SoC

---

## Library Usage Examples

### Basic Connection

```python
from franklinwh_modbus import FranklinWHController

# Create controller
ctrl = FranklinWHController(
    ip_address='YOUR_AGATE_IP',
    port=502,
    unit_id=2,
    timeout=10.0
)

# Connect
if not ctrl.connect():
    print("Failed to connect")
    exit(1)

# Always disconnect when done
ctrl.disconnect()
```

### Read Battery Status

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Read battery status
status = ctrl.read_battery_status()
print(f"SoC: {status['soc']:.1f}%")
print(f"SoH: {status['soh']:.1f}%")
print(f"DC Power: {status['dc_power']:.0f}W")
print(f"Temperature: {status['temperature']:.1f}°C")
print(f"Cycles: {status['cycles']}")

ctrl.disconnect()
```

### Direct Battery Control

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Charge at 3000W
cmd = BatteryCommand(power_watts=3000)
success, msg = ctrl.send_command(cmd)
print(f"Charge: {msg}")

# Discharge at 2000W (negative = discharge)
cmd = BatteryCommand(power_watts=-2000)
success, msg = ctrl.send_command(cmd)
print(f"Discharge: {msg}")

# Standby (0W)
cmd = BatteryCommand(power_watts=0)
success, msg = ctrl.send_command(cmd)
print(f"Standby: {msg}")

# Release control to cloud
ctrl.reset_control_state()

ctrl.disconnect()
```

### Virtual Mode Controller

```python
from franklinwh_modbus import (
    FranklinWHController,
    VirtualModeController,
    VirtualMode
)

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Create virtual mode controller
vmc = VirtualModeController(
    ctrl,
    max_charge_soc=95,
    min_discharge_soc=20
)

# Set mode and run
vmc.set_mode(VirtualMode.SELF_CONSUMPTION, target_soc=90)
vmc.run_continuous(duration_seconds=3600)  # Run for 1 hour

ctrl.disconnect()
```

### Check Alarms

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Read alarms
alarms = ctrl.read_alarms()
print(f"System Alarm: 0x{alarms['system_alrm']:08X}")
print(f"DC Port Alarm: 0x{alarms['dc_port_alrm']:08X}")

# Check if blocking
can_operate, blocking = ctrl.check_blocking_alarms()
if blocking:
    print(f"Blocking alarms: {', '.join(blocking)}")

ctrl.disconnect()
```

### Health Check

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Run health check
health = ctrl.healthcheck()
print(f"Healthy: {health.healthy}")
print(f"Message: {health.message}")
if health.details:
    print(f"SoC: {health.details.get('soc', 0):.1f}%")

ctrl.disconnect()
```

### Read Grid Status

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

grid = ctrl.read_grid_status()
print(f"Grid Power: {grid['grid_power_w']:.0f}W")
print(f"Voltage: {grid['voltage_v']:.1f}V")
print(f"Frequency: {grid['frequency_hz']:.2f}Hz")
print(f"Connected: {grid['connection_state']}")

ctrl.disconnect()
```

### Read Solar Status

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

solar = ctrl.read_solar_status()
print(f"AC Power: {solar['ac_power_w']:.0f}W")
print(f"DC Power: {solar['battery_dc_power_w']:.0f}W")

# Extension registers
if solar.get('extension'):
    ext = solar['extension']
    print(f"Total Solar: {ext['total_solar']:.0f}W")
    print(f"Proximal: {ext['proximal_solar']:.0f}W")

ctrl.disconnect()
```

---

## Common Operations

### Operation: Charge Until Target SoC

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand
import time

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

target_soc = 90
charge_power = 3000

while True:
    status = ctrl.read_battery_status()
    current_soc = status['soc']
    
    if current_soc >= target_soc:
        print(f"Target reached: {current_soc:.1f}%")
        break
    
    # Send charge command
    cmd = BatteryCommand(power_watts=charge_power)
    ctrl.send_command(cmd)
    
    print(f"SoC: {current_soc:.1f}% / {target_soc}%")
    time.sleep(10)

# Release control
ctrl.reset_control_state()
ctrl.disconnect()
```

### Operation: Discharge Until Min SoC

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand
import time

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

min_soc = 20
discharge_power = 3000

while True:
    status = ctrl.read_battery_status()
    current_soc = status['soc']
    
    if current_soc <= min_soc:
        print(f"Min SoC reached: {current_soc:.1f}%")
        break
    
    # Send discharge command (negative)
    cmd = BatteryCommand(power_watts=-discharge_power)
    ctrl.send_command(cmd)
    
    print(f"SoC: {current_soc:.1f}% (min: {min_soc}%)")
    time.sleep(10)

# Release control
ctrl.reset_control_state()
ctrl.disconnect()
```

### Operation: Monitor and Log

```python
from franklinwh_modbus import FranklinWHController
import time
import json
from datetime import datetime

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

data_log = []

try:
    for _ in range(60):  # 10 minutes at 10s intervals
        battery = ctrl.read_battery_status()
        grid = ctrl.read_grid_status()
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'soc': battery['soc'],
            'dc_power': battery['dc_power'],
            'grid_power': grid['grid_power_w'],
            'voltage': grid['voltage_v']
        }
        data_log.append(entry)
        
        print(f"{entry['timestamp']}: SoC={entry['soc']:.1f}%, "
              f"DC={entry['dc_power']:.0f}W, Grid={entry['grid_power']:.0f}W")
        
        time.sleep(10)
finally:
    # Save log
    with open('battery_log.json', 'w') as f:
        json.dump(data_log, f, indent=2)
    
    ctrl.disconnect()
```

---

## Advanced Features

### Startup State Checking (Conflict Detection)

Check system state before sending commands to detect conflicts with aGate Cloud API:

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Get full system state including conflicts
state = ctrl.check_state()

print(f"SoC: {state['soc']:.1f}%")
print(f"Grid Connected: {state['grid_connected']}")
print(f"Battery Activity: {state['battery_activity']}")
print(f"aGate Mode: {state['ongrid_mode']}")

# Check for conflicts (e.g., aGate actively controlling)
conflicts = state.get('conflicts', [])
if conflicts:
    print("⚠️ Conflicts detected:")
    for conflict in conflicts:
        print(f"  • {conflict}")
    print("Use --reset-on-start or reset_control_state() to take over")
else:
    print("✓ No conflicts - safe to proceed")

# Check alarms
alarms = state.get('alarms', {})
if not alarms.get('can_operate', True):
    print(f"🚨 Blocking alarms: {alarms.get('blocking', [])}")

ctrl.disconnect()
```

### Auto-Revert Timer (Library Implementation)

Implement auto-revert functionality in your Python code:

```python
from franklinwh_modbus import FranklinWHController, BatteryCommand
import threading
import time

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

# Set up auto-revert timer
def revert_control():
    """Release control back to cloud after timeout."""
    try:
        print("⏰ Auto-revert timer: Releasing control...")
        ctrl.reset_control_state()
        print("✓ Control released")
    except Exception as e:
        print(f"Revert failed: {e}")

# Start timer for 1 hour
revert_seconds = 3600
timer = threading.Timer(revert_seconds, revert_control)
timer.start()
print(f"⏱️  Auto-revert set for {revert_seconds} seconds")

# Send command
cmd = BatteryCommand(power_watts=3000)
success, msg = ctrl.send_command(cmd)
print(f"Command: {msg}")

# Keep program running or do other work
try:
    time.sleep(revert_seconds + 10)  # Wait for timer
except KeyboardInterrupt:
    print("Interrupted by user")
finally:
    # Cancel timer if still active
    if timer.is_alive():
        timer.cancel()
    
    # Ensure control is released
    ctrl.reset_control_state()
    ctrl.disconnect()
```

### Off-Grid Detection

Validate grid connection before operating:

```python
from franklinwh_modbus import FranklinWHController

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

state = ctrl.check_state()

if not state['grid_connected']:
    print("🚨 OFF-GRID DETECTED")
    print(f"Connection state: {state.get('connection_state', 'Unknown')}")
    print(f"Voltage: {state.get('grid_voltage', 0):.1f}V")
    
    # Decide whether to proceed
    allow_off_grid = input("Proceed anyway? (yes/no): ")
    if allow_off_grid.lower() != 'yes':
        print("Exiting")
        ctrl.disconnect()
        exit(1)
else:
    print("✓ Grid connected - safe to operate")

# Continue with control operation...
ctrl.disconnect()
```

### SunSpec InfoPoint Sequencer

The Sequencer is a powerful tool for orchestrating complex, multi-step register operations with built-in verification and safety checks. It is ideal for testing hardware responses and automating multi-register control flows.

**Key Features:**
- **Step-by-Step Execution**: Define sequences in JSON files or in-line CLI strings.
- **Wait Conditions (`wait_for`)**: Poll registers until a specific value or condition is met (e.g., SoC >= 95%).
- **Verification**: Automatically polls post-write to ensure the hardware has accepted the command.
- **Fail-Fast Safety**: Prematurely exits the sequence with an error code if a condition is not met or a write fails.

#### Basic Usage (CLI)

```bash
# Execute a sequence from a file
python tools/franklinwh_cli.py -i YOUR_AGATE_IP --sequence-file examples/curtailment_sequence.json

# Execute in-line read sequence (Note: single quotes around the double-quoted JSON)
python tools/franklinwh_cli.py -i YOUR_AGATE_IP --sequence '{"reads": ["714.DCW", "701.W"]}'

# Execute a single-step write sequence via in-line JSON
python tools/franklinwh_cli.py -i YOUR_AGATE_IP --sequence '{"704.WMaxLimPctEna": 1, "704.WMaxLimPct": 50}'

# WARNING: Custom setpoints override standard cloud control. Always release when done!
# Release remote control (stop VPP mode) and return to normal automatic cloud control:
python tools/franklinwh_cli.py -i YOUR_AGATE_IP --stop
python tools/franklinwh_cli.py -i YOUR_AGATE_IP --sequence '{"704.WSetEna": 0, "704.WSetPct": 0}'
```

#### JSON Sequence Schema

```json
[
  {
    "name": "SoC Gating",
    "wait_for": {
      "point": "713.SoC",
      "operator": ">=",
      "value": 90,
      "timeout_ms": 300000
    },
    "abort_on_failure": true
  },
  {
    "name": "Apply Limits",
    "writes": {
      "704.WMaxLimPctEna": 1,
      "704.WMaxLimPct": 50
    },
    "verify": true
  }
]
```

**Supported Operators:** `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`.

---

## API Reference

### FranklinWHController

#### Constructor
```python
FranklinWHController(
    ip_address: str,
    port: int = 502,
    unit_id: int = 2,
    timeout: float = 10.0
)
```

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | bool | Establish Modbus connection |
| `disconnect()` | None | Close connection |
| `read_battery_status()` | dict | SoC, SoH, power, temp |
| `read_grid_status()` | dict | Voltage, current, power, PF |
| `read_solar_status()` | dict | AC power, DC power, extensions |
| `read_control_status()` | dict | WSet, WSetEna, WSetMod |
| `read_native_mode()` | dict | OnGridMode, reserves |
| `read_alarms()` | dict | System and DC port alarms |
| `send_command(cmd)` | (bool, str) | Send BatteryCommand |
| `reset_control_state()` | bool | Release to cloud |
| `clear_alarms()` | (bool, str) | Reset alarm registers |
| `healthcheck()` | HealthStatus | System health check |
| `check_blocking_alarms()` | (bool, list) | Check if alarms block operation |
| `check_state()` | dict | Full system state with conflict detection |
| `get_enum_desc(model_id, point_name, value)` | str | Resolve PICS enum value to string description |

### VirtualModeController

#### Constructor
```python
VirtualModeController(
    franklinwh_controller: FranklinWHController,
    max_charge_soc: int = 100,
    min_discharge_soc: int = 0,
    soc_ramp_window: int = 10
)
```

#### Methods

| Method | Description |
|--------|-------------|
| `set_mode(mode, **kwargs)` | Set virtual mode with parameters |
| `calculate_power()` | Calculate optimal power for current mode |
| `execute_once()` | Execute single control cycle |
| `run_continuous(duration, stop_event)` | Run mode continuously (library-safe) |
| `tick()` | Single control tick (returns True/False) |
| `verify_command_execution()` | Verify commanded vs actual power |

#### Running Continuously

**For library consumers** (e.g. FranklinWH Energy Manager):
```python
import threading
from franklinwh_modbus import FranklinWHController, VirtualModeController, VirtualMode

ctrl = FranklinWHController('YOUR_AGATE_IP')
ctrl.connect()

vmc = VirtualModeController(ctrl)
vmc.set_mode(VirtualMode.SELF_CONSUMPTION, target_soc=90)

# Use stop_event for cooperative shutdown — no signal hijacking
stop = threading.Event()
vmc.run_continuous(duration_seconds=3600, stop_event=stop)
# Call stop.set() from another thread to stop gracefully
```

**For CLI/scripts** (with Ctrl+C handling):
```python
from franklinwh_modbus import VirtualModeController, run_with_signal_handling

# Installs SIGINT/SIGTERM handlers, restores them on exit
run_with_signal_handling(vmc, duration_seconds=3600)
```

#### Modes

| Mode | Description | Parameters |
|------|-------------|------------|
| `VirtualMode.SELF_CONSUMPTION` | Minimize grid import | `target_soc`, `reserve` |
| `VirtualMode.EMERGENCY_BACKUP` | Maximize backup | `target_soc` |
| `VirtualMode.TIME_OF_USE` | Schedule-based | `schedule` |
| `VirtualMode.GRID_ZERO` | Minimize grid import/export | - |
| `VirtualMode.PEAK_SHAVE` | Limit grid power | `threshold` |
| `VirtualMode.MANUAL` | Direct power control | `power_watts` |

---

## Sign Conventions

| Value | Meaning |
|-------|---------|
| Power > 0 | Charging (importing from grid/solar) |
| Power < 0 | Discharging (exporting to grid/home) |
| Power = 0 | Standby / Idle |

---

## Troubleshooting

### Import Error: `NameError: name 'Layout' is not defined`

**Cause:** Type annotations in `monitor.py` reference `rich` types.

**Fix:** Ensure you're using the latest version with `from __future__ import annotations`.

**Verification:**
```bash
python -c "
import sys
sys.path.insert(0, 'src')
from franklinwh_modbus import FranklinWHController
print('✓ Import successful')
"
```

### Import Error: `ModuleNotFoundError: No module named 'franklinwh'`

**Cause:** `src/` directory not in Python path.

**Fix:**
```python
import sys
sys.path.insert(0, '/path/to/modbus/src')  # Note: src/ subdirectory
from franklinwh_modbus import FranklinWHController
```

### Connection Error: `No route to host`

**Cause:** aGate not reachable on network.

**Fix:**
1. Verify aGate IP address: `ping YOUR_AGATE_IP`
2. Check aGate is powered on and connected to WiFi
3. Verify firewall allows Modbus TCP (port 502)

### Connection Timeout

**Cause:** WiFi latency or aGate busy.

**Fix:** Increase timeout:
```bash
python franklinwh_cli.py -i YOUR_AGATE_IP -t 10 --status
```

### Control Conflicts with Cloud API

**Cause:** aGate native mode (Self-Consumption, etc.) is actively controlling battery.

**Fix Options:**
1. Use `--reset-on-start` to force takeover (CLI)
2. Change aGate mode via FranklinWH app first
3. Wait for current operation to complete

---

## Additional Resources

- **Hardware Testing:** See [docs/HARDWARE_TEST_GUIDE.md](docs/HARDWARE_TEST_GUIDE.md)
- **Safety Rules:** See [docs/SAFETY_CONTROLS.md](docs/SAFETY_CONTROLS.md)
- **SunSpec Quirks:** See [docs/FRANKLINWH_SUNSPEC_QUIRKS.md](docs/FRANKLINWH_SUNSPEC_QUIRKS.md)
- **Changelog:** See [CHANGELOG.md](CHANGELOG.md)

---

*Version 0.9.0 — Last Updated: 2026-03-07*
