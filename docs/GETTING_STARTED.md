# Getting Started — franklinwh-modbus

Complete setup guide for **macOS**, **Windows**, and **Ubuntu/Linux**.\
Covers virtual environments, package installation, CLI tools, network scanning, and the SunSpec Modbus reader.

---

## Table of Contents

1. [Create a Virtual Environment](#1-create-a-virtual-environment)
2. [Install the Package](#2-install-the-package)
3. [CLI Tool — franklinwh](#3-cli-tool-franklinwh)
4. [Network Scanner](#4-network-scanner)
5. [SunSpec Modbus Reader](#5-sunspec-modbus-reader-modbus_sunspec2_readerpy)
6. [FranklinWH Extension Registers](#6-franklinwh-extension-registers)
7. [Bonus: Cloud API Alternative](#7-bonus-cloud-api-franklinwh-cloud)

---

## Prerequisites

Before installing the software, confirm these hardware requirements are met:

1. **Firmware:** aGate EMS firmware **V12R02B85D00_250624** (or later). This is the only release this library has been tested on. Check your firmware version in the FranklinWH mobile app under *Device Info → EMS Main*, or via Home Assistant MQTT (`franklinwh/.../cloud_software_version`). Note: the SunSpec register M1.Vr (address 40044) may report a different, older version string (e.g. `V10R01B04D00`) — the app/MQTT version is authoritative.

2. **SunSpec Modbus TCP:** Must be **enabled by your installer or FranklinWH Customer Support** in your country (AU, US, or Canada). This is not enabled by default — contact your installer or raise a support ticket with FranklinWH to request Modbus TCP access on your aGate.

!!! important
    Both prerequisites must be in place before proceeding. Without Modbus TCP enabled on your aGate, the library cannot connect.

---

## 1. Create a Virtual Environment

### macOS

```bash
# Install Python 3.10+ (if not already present)
brew install python@3.12      # or: xcode-select --install (for system Python 3)

# Clone the repo and create a venv
git clone https://github.com/david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv
source venv/bin/activate
```

### Windows

```powershell
# Install Python 3.10+ from https://www.python.org/downloads/
# ✅ Check "Add Python to PATH" during installation

# Clone the repo and create a venv
git clone https://github.com/david2069/franklinwh-modbus.git
cd franklinwh-modbus
python -m venv venv
venv\Scripts\activate
```

### Ubuntu / Linux

```bash
# Install Python 3.10+ and venv
sudo apt update
sudo apt install python3 python3-venv python3-pip git

# Clone the repo and create a venv
git clone https://github.com/david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv
source venv/bin/activate
```

!!! tip
    Your prompt should now show `(venv)` — all `pip install` commands below run inside this environment.

---

## 2. Install the Package

```bash
# Core library only
pip install -e .

# Core + developer tools (pytest)
pip install -e ".[dev]"

# Core + TUI monitor (rich terminal dashboard)
pip install -e ".[dev,monitor]"
```

After installation the `franklinwh` CLI command is available in your shell:

```bash
franklinwh --help
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `pysunspec2 ≥ 1.1.0` | SunSpec model definitions |
| `pymodbus ≥ 3.0.0` | Modbus TCP client |
| `rich ≥ 13.0.0` *(optional)* | TUI monitor dashboard |

---

## 3. CLI Tool — `franklinwh`

The library installs a `franklinwh` console script (also runnable as `python franklinwh_cli.py`).

### Quick Examples

```bash
# System status (read-only — always works)
franklinwh -i YOUR_AGATE_IP --status

# Health check with conflict detection
franklinwh -i YOUR_AGATE_IP --healthcheck

# Check alarms
franklinwh -i YOUR_AGATE_IP --check-alarms

# Interactive terminal dashboard (requires rich)
franklinwh -i YOUR_AGATE_IP --monitor

# Charge at 3 kW for 1 hour then auto-revert
franklinwh -i YOUR_AGATE_IP --charge 3000 --revert 3600

# Discharge at 2 kW for 30 minutes
franklinwh -i YOUR_AGATE_IP --discharge 2000 --duration 1800

# Self-consumption mode
franklinwh -i YOUR_AGATE_IP --mode self_consumption --target-soc 90

# Release control
franklinwh -i YOUR_AGATE_IP --stop
```

!!! important
    **Read operations always work.** Charge, discharge and standby use SunSpec M704. Mode and reserve changes write FranklinWH extension registers, which are undocumented and unconfirmed: on V12R02B60D00 (2026-10-21) they did not take effect.

### Connection Options

| Flag | Default | Description |
|------|---------|-------------|
| `-i` / `--ip` | *(required)* | aGate IP address |
| `-p` / `--port` | `502` | Modbus TCP port |
| `-u` / `--unit` | `2` | Modbus unit/slave ID |
| `-t` / `--timeout` | `10.0` | Connection timeout (seconds) |

See the full [USAGE_GUIDE.md](https://github.com/david2069/franklinwh-modbus/blob/develop/USAGE_GUIDE.md) for all commands and library API examples.

---

## 4. Network Scanner

The network scanner discovers IoT and energy devices on your LAN. Located at `tools/network_scanner.py`.

### Install Scanner Dependencies

```bash
pip install pymodbus requests

# Optional — enhanced table output and mDNS discovery
pip install tabulate colorama zeroconf

# Or all at once:
pip install -r tools/network_scanner_requirements.txt
```

### Supported Device Types

| Device | Identifier | Ports | Detection |
|--------|-----------|-------|-----------|
| **Modbus TCP / SunSpec** | `modbus`, `sunspec` | 502 | SunSpec Model 1 ("SunS" magic bytes) |
| **Enphase Envoy** | `enphase` | 80, 443 | REST API endpoints |
| **SolarEdge** | `solaredge` | 80, 502 | SetApp / Modbus |
| **SPAN Smart Panel** | `span` | 80 | `/api/v1/status` |
| **Home Assistant** | `ha`, `homeassistant` | 8123 | API endpoint |
| **MQTT Broker** | `mqtt`, `broker` | 1883 | CONNECT / CONNACK |
| **Homey Hub** | `homey` | 80 | Athom API |

### Usage Examples

```bash
# Scan entire /24 subnet for all supported devices
python3 tools/network_scanner.py 192.168.1.0/24

# Scan for specific device types only
python3 tools/network_scanner.py 192.168.1.0/24 --devices modbus,span,ha,mqtt

# Single IP with longer timeout
python3 tools/network_scanner.py 192.168.1.50 --timeout 10

# IP range
python3 tools/network_scanner.py 192.168.1.1-192.168.1.100

# Wildcard
python3 tools/network_scanner.py "192.168.1.*"

# JSON output (pipe to file or jq)
python3 tools/network_scanner.py 192.168.1.0/24 -o json > scan_results.json

# CSV output
python3 tools/network_scanner.py 192.168.1.0/24 -o csv > scan_results.csv

# Fast scan — more threads, shorter timeout
python3 tools/network_scanner.py 192.168.1.0/24 --threads 100 --timeout 2
```

### SPAN Panel Check (via CLI)

The `franklinwh` CLI also has a built-in SPAN panel scanner:

```bash
franklinwh -i YOUR_AGATE_IP --check-span
```

This scans the aGate's /24 subnet for SPAN panels. A panel's presence says nothing about extension register writes; only `--test-extension-write` (which writes to the device) checks that by read-back.

---

## 5. SunSpec Modbus Reader (`modbus_sunspec2_reader.py`)

A standalone tool at `tools/modbus_sunspec2_reader.py` for querying any SunSpec-compliant Modbus TCP device — reads models, individual data points, raw registers, and FranklinWH extension registers.

### Install Reader Dependency

```bash
pip install pysunspec2
```

### Basic Syntax

```bash
python3 tools/modbus_sunspec2_reader.py -i <IP> [options]
```

### 5.1. Scan All Models

```bash
# List all models (minimal — IDs and names only)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -d minimal

# Basic info (default — includes Model 1 manufacturer, model, serial)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50

# Compact one-liner (model IDs as ranges)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -c

# Model ID → alias mapping table
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --map
```

### 5.2. Select Specific Models

```bash
# Single model
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 1

# Multiple models (comma-separated)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 1,101,103

# Range of models
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 701-715

# Mixed
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 1,701-706,713-715
```

### 5.3. Detail Levels (`-d`)

| Level | Shows | Use Case |
|-------|-------|----------|
| `minimal` | Model IDs and names | Quick inventory |
| `basic` | + Model 1 manufacturer/model/serial *(default)* | Device identification |
| `values` | Current values with units, types, scale factors | Live monitoring |
| `detailed` | All point names and raw values | Debugging |
| `full` | Everything: addresses, labels, descriptions, enums, scale factors, access | Full register documentation |

```bash
# Current values with units and data types
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 701 -d values

# Full metadata for battery storage models
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 713-715 -d full
```

### 5.4. Tabular Display (`--vals`)

One line per data point with address, name, label, scaled value, units, access, and raw value:

```bash
# Tabular output for inverter model
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 701 -d values --vals

# All models in tabular format
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -d values --vals
```

Output format:
```
Addr   Name                 Label                     Value  Units    F   RW Raw        Type
─────────────────────────────────────────────────────────────────────────────────────────────
40004  W                    Active Power               1500  W        S   R  15000      int16
40006  Hz                   Grid Frequency            60.01  Hz       S   R  6001       uint16
```

### 5.5. Query a Single Point (`--point`)

Read one specific data point using `model_id.point_name` format:

```bash
# Manufacturer name from Model 1
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --point 1.Mn

# Active power from Model 701 (DER AC Measurements)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --point 701.W

# State of Charge from Model 713
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --point 713.SoC

# Watts from Model 103 (Inverter)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --point 103.W
```

### 5.6. Raw Register Read (`--raw`)

Read arbitrary Modbus holding registers by address and count:

```bash
# Read 14 registers starting at address 15500
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 15500:14

# Read a single register at address 40000
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 40000:1

# Non-zero values only (filter out zeros)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 15500:20 --nz

# Raw read + model scan + match values against known points
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 15500:14 --match
```

Raw output format:
```
Addr     Hex    UInt16   Int16    Value           Acc Bits (Binary)    Guess/Notes
──────────────────────────────────────────────────────────────────────────────────
15500    0001   1        1        1               R   0000000000000001 PV Installed (PVUse) (Used)
15502    04D2   1234     1234     1234            R   0000010011010010 PV Total Power (PVOutputP) W
15507    0002   2        2        2               RW  0000000000000010 Operating Mode (OnGridMode) (Self)
```

This sample predates the tool's label change: 15507–15509 now show `R`. `RW` was **speculation (undocumented, unverified)**.

### 5.7. JSON Output (`--json`)

Output results as machine-readable JSON:

```bash
# JSON output for scripting / pipelining
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 1 --json

# Pipe to jq for filtering
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -m 701 -d values --json | jq '.models'
```

### 5.8. Command Reference

| Flag | Description |
|------|-------------|
| `-i` / `--ip` | Device IP address *(required)* |
| `-p` / `--port` | Modbus TCP port (default: `502`) |
| `-u` / `--unit` | Modbus unit ID (default: `1`) |
| `-b` / `--base-address` | SunSpec base address (default: `40000`) |
| `-t` / `--timeout` | Timeout in seconds (default: `2.0`) |
| `-m` / `--models` | Models to scan (e.g. `1,701-715`) |
| `-d` / `--detail` | Detail level: `minimal`, `basic`, `values`, `detailed`, `full` |
| `--point` | Query a single point: `model_id.point_name` |
| `--raw` | Raw register read: `start:count` |
| `-c` / `--compact` | One-line model ID summary |
| `--map` | Model ID → alias mapping table |
| `--vals` | Tabular one-line-per-point display |
| `--nz` | Only show non-zero values in raw read |
| `--match` | Match raw values against known model points |
| `--json` | JSON output |
| `-v` / `--verbose` | Enable debug output |

### FranklinWH-Specific Notes

The FranklinWH aGate uses **base address `1`** (not the standard `40000`). For aGate devices, specify `-b 1` if the default doesn't auto-detect:

```bash
# Explicit base address for aGate
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 -b 1 -d values --vals
```

Unit IDs `1` or `2` both work on the aGate (DA=1).

---

## 6. FranklinWH Extension Registers

The aGate exposes non-standard registers at addresses 15500+ for FranklinWH-specific data. These are **auto-detected** by the raw read decoder in `modbus_sunspec2_reader.py`.

### Documented Extension Registers

#### Read-Only (always accessible)

| Address | Short Name | Description | Type |
|---------|-----------|-------------|------|
| 15500 | `PVUse` | PV Installed | enum: 0=NotUsed, 1=Used |
| 15501 | `apBoxPVUse` | Remote PV Installed | enum: 0=NotUsed, 1=Used |
| 15502 | `PVOutputP` | PV Total Power | W |
| 15503 | `proximalPVOutputP` | PV Proximal Power | W |
| 15504 | `Remote1PV` | PV Remote 1 Power | W |
| 15505 | `Remote2PV` | PV Remote 2 Power | W |
| 15506 | `LoadActiveP` | Home Load | W |
| 15510–15511 | `PVOutputWh` | PV Energy Total | uint32 |
| 15512–15513 | `proximalOutputWh` | PV Energy Proximal | uint32 |

#### Mode and reserves (read-only; writes undocumented)

FranklinWH has never documented these as writable. On V12R02B60D00 (2026-10-21) writes did not take effect.

| Address | Short Name | Description | Values |
|---------|-----------|-------------|--------|
| 15507 | `OnGridMode` | Operating Mode | 1=Backup, 2=Self-Consumption, 3=TOU |
| 15508 | `SelfReserve` | Self-Consumption SOC Reserve | 0–100 % |
| 15509 | `TouReserve` | TOU SOC Reserve | 0–100 % |

### Reading Extension Registers

```bash
# Read all known extension registers (15500–15513)
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 15500:14

# Non-zero only
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 15500:14 --nz

# Match extension values against SunSpec model points
python3 tools/modbus_sunspec2_reader.py -i 192.168.1.50 --raw 15500:14 --match -d values
```

---

## 7. Bonus: Cloud API — `franklinwh-cloud`

The `franklinwh-cloud` library provides an **alternative control path** via the FranklinWH Cloud API. Unlike Modbus TCP (LAN-only, requires network access to the aGate), the Cloud API works **remotely over the internet** using your FranklinWH account credentials — the same API used by the official mobile app.

!!! note
    Modbus TCP and the Cloud API are independent control paths. Both can read status and send commands. Modbus TCP is lower-latency and works offline but requires LAN access. The Cloud API works from anywhere but depends on FranklinWH's cloud infrastructure.

### Install

```bash
pip install franklinwh-cloud
```

Or from source:

```bash
git clone https://github.com/david2069/franklinwh-cloud.git
cd franklinwh-cloud
pip install -e .
```

### Credentials

All Cloud API scripts need your FranklinWH account email and password:

```python
import asyncio
from franklinwh_cloud import FranklinWHCloud

async def main():
    client = FranklinWHCloud(email="you@example.com", password="your_password")
    await client.login()
    await client.select_gateway()   # auto-selects first gateway

    # ... your code here ...

asyncio.run(main())
```

Or load from a config file (`franklinwh.ini`):

```python
client = FranklinWHCloud.from_config("franklinwh.ini")
```

### Read Live Power Flow

```python
stats = await client.get_stats()

# Instantaneous power (kW)
print(f"Solar:   {stats.current.solar_production:.2f} kW")
print(f"Battery: {stats.current.battery_power:.2f} kW")  # negative = charging
print(f"Grid:    {stats.current.grid_power:.2f} kW")
print(f"Home:    {stats.current.home_consumption:.2f} kW")
print(f"SoC:     {stats.current.soc:.0f}%")
print(f"Mode:    {stats.current.work_mode_desc}")
```

### Switch Operating Mode

```python
from franklinwh_cloud.const import SELF_CONSUMPTION, EMERGENCY_BACKUP

# Self-Consumption
await client.set_mode(SELF_CONSUMPTION, None, None, None, None)

# Emergency Backup — indefinite
await client.set_mode(EMERGENCY_BACKUP, None, 1, SELF_CONSUMPTION, None)
#                      mode              soc  forever  nextMode      duration

# Emergency Backup — 2 hours, then revert to Self-Consumption
await client.set_mode(EMERGENCY_BACKUP, None, 2, SELF_CONSUMPTION, 120)
```

### Set Reserve SoC

```python
from franklinwh_cloud.const import SELF_CONSUMPTION

# Set backup reserve to 20%
await client.update_soc(requestedSOC=20, workMode=SELF_CONSUMPTION)
```

### PCS Power Control (Grid Import / Export Limits)

```python
# Read current limits
pcs = await client.get_power_control_settings()

# Set grid export max to 5 kW, import unlimited
await client.set_power_control_settings(
    globalGridDischargeMax=5.0,   # export limit kW (-1=unlimited, 0=disabled)
    globalGridChargeMax=-1,       # import limit kW (-1=unlimited, 0=disabled)
)

# Disable grid export entirely (zero export)
await client.set_power_control_settings(
    globalGridDischargeMax=0,
    globalGridChargeMax=-1,
)
```

### TOU Schedule — Force Grid Charge

```python
from franklinwh_cloud.const import dispatchCodeType, WaveType

# Set a grid-charge window 11:30–15:00, self-consumption outside
await client.set_tou_schedule(
    touMode="CUSTOM",
    touSchedule=[{
        "startTime": "11:30",
        "endTime": "15:00",
        "dispatchId": dispatchCodeType.GRID_CHARGE.value,   # 8 = Grid charge
        "waveType": WaveType.OFF_PEAK.value,              # 0 = Off-peak
    }],
    default_mode="SELF",
)

# Restore full-day self-consumption
await client.set_tou_schedule(touMode="SELF")
```

**Note:** See the [Cloud API Cookbook](https://david2069.github.io/franklinwh-cloud/API_COOKBOOK/) for the full list of `dispatchCodeType` and `WaveType` enum definitions.

### Comparison: Modbus TCP vs Cloud API

| | Modbus TCP (`franklinwh-modbus`) | Cloud API (`franklinwh-cloud`) |
|---|---|---|
| **Network** | LAN only (Ethernet preferred) | Internet (works anywhere) |
| **Latency** | ~10–50 ms | ~200–800 ms |
| **Auth** | None (IP access = access) | Email + password |
| **Offline** | ✅ Works without internet | ❌ Requires cloud |
| **Protocol** | Modbus TCP / SunSpec | HTTPS REST (JSON) |
| **Read** | SunSpec registers + extensions | Full system stats, BMS, TOU, weather |
| **Write** | SunSpec M704 (extension writes undocumented) | Mode, SoC, PCS, TOU, smart circuits |
| **Rate limits** | None | Undocumented (be conservative) |
| **Package** | `pip install franklinwh-modbus` | `pip install franklinwh-cloud` |

!!! tip
    For full Cloud API documentation, see the [API Cookbook](https://github.com/david2069/franklinwh-cloud/blob/main/docs/API_COOKBOOK.md) and [API Client Guide](https://github.com/david2069/franklinwh-cloud/blob/main/API_CLIENT_GUIDE.md).

---

## Quick Reference Card

```bash
# ─── Setup ───────────────────────────────────────────────
git clone https://github.com/david2069/franklinwh-modbus.git
cd franklinwh-modbus
python3 -m venv venv && source venv/bin/activate   # macOS/Linux
pip install -e ".[dev,monitor]"

# ─── Discover Devices ────────────────────────────────────
python3 tools/network_scanner.py 192.168.1.0/24
python3 tools/network_scanner.py 192.168.1.0/24 --devices modbus,span,ha,mqtt

# ─── Read SunSpec Models ─────────────────────────────────
python3 tools/modbus_sunspec2_reader.py -i IP -c                     # model list
python3 tools/modbus_sunspec2_reader.py -i IP -m 701 -d values --vals  # tabular
python3 tools/modbus_sunspec2_reader.py -i IP --point 713.SoC        # single point

# ─── FranklinWH Extensions ──────────────────────────────
python3 tools/modbus_sunspec2_reader.py -i IP --raw 15500:14         # extension regs

# ─── CLI Status & Control ───────────────────────────────
franklinwh -i IP --status
franklinwh -i IP --monitor
franklinwh -i IP --charge 3000 --revert 3600
franklinwh -i IP --stop
```

---

## Further Reading

- [📖 Library & CLI Usage Guide](https://github.com/david2069/franklinwh-modbus/blob/develop/USAGE_GUIDE.md) — full API reference and code examples
- [📚 Documentation Home](index.md) — wiki landing page
- [🔧 SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md) — hardware quirks and workarounds
- [📝 Changelog](https://github.com/david2069/franklinwh-modbus/blob/develop/CHANGELOG.md)
