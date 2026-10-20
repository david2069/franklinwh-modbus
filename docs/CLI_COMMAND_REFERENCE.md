# CLI Command Reference

*Last Updated: 2026-05-15 18:56 | Version: 1.2.0*

The `franklinwh_cli.py` tool is the primary interface for controlling and monitoring FranklinWH aGate systems via Modbus TCP. It supports both native hardware modes and advanced virtual software orchestration.

### Master Option Reference

| Category | Option | Purpose / Function | Typical Use Case |
|:---------|:-------|:-------------------|:-----------------|
| **Connection** | `-i`, `--ip` | Target device network address. | **Mandatory** for all operations. |
| | `-p`, `--port` | Modbus network port (default: `502`). | Adjusting when connecting via a custom port forwarding setup. |
| | `-u`, `--unit` | Modbus Unit ID (Slave ID, default: `2`). | Use `2` for aGate, `1` for direct PDU access. |
| | `-b`, `--base-address` | Base Modbus address (default: `40000`). | Adjusting address offset if the registers are shifted. |
| | `-t`, `--timeout` | Connection wait time (seconds, default: `10.0`). | Increase if on a high-latency WiFi or cellular link. |
| **Modes** | `--mode` | Change **Native Hardware** operating mode. | Switching between Backup, SC, and TOU permanently. |
| | `--vmode` | Run **Virtual Software** orchestration loop. | Orchestrating Peak Shaving, Manual, or Grid-Zero modes. |
| **Actions** | `--power` | Manual power in watts (+charge, -discharge). | Legacy/compatibility option for orchestrated power control. |
| | `--charge` | Import power from grid to battery at specified watts. | Force charging before an outage or a low-rate window. |
| | `--discharge` | Export power from battery at specified watts. | Reducing grid usage during expensive Peak periods. |
| | `--max-charge` | Force charge at full inverter nameplate rating. | Rapidly filling battery when charge window is short. |
| | `--max-discharge` | Force discharge at full inverter nameplate rating. | Maximizing export/offset during peak event hours. |
| | `--standby` | Idle the battery (0W power flow). | Disabling battery charging/discharging temporarily. |
| | `--stop` | Release Modbus remote control (WSetEna=0). | Returning control to native cloud automation. |
| **Limits** | `--target-soc` | Target SoC goal for virtual actions (default: `100`). | Charging battery to exactly 80% to preserve lifetime. |
| | `--reserve` | Minimum backup SoC floor for virtual modes (default: `20`).| Ensuring a reserve is kept for power outages. |
| | `--self-reserve` | Set native Self-Consumption reserve SOC percentage. | Permanently setting the hardware self-consumption floor. |
| | `--tou-reserve` | Set native TOU reserve SOC percentage. | Permanently setting the hardware Time-of-Use floor. |
| | `--threshold` | Power trigger limit for Peak Shaving (default: `2000`). | Starting discharge only when home load exceeds 2kW. |
| | `--max-charge-soc`| Safety ceiling for charging (default: `100`). | Auto-stopping a charge at 95% to avoid cell stress. |
| | `--min-discharge-soc`| Safety floor for discharging (auto-read if not set).| Auto-stopping discharge to protect battery from deep drain. |
| | `--soc-ramp-window`| SoC ramping range percentage (default: `10`). | Smoothly scaling power flow when approaching SoC limits. |
| | `--target-soc-auto`| Target SoC percentage for auto-stop. | Automatically stopping command execution at target. |
| **Safety** | `--revert` | Software watchdog timer (seconds). | **Critical Safety**: Auto-stop if your PC/script crashes. |
| | `--duration` | Total run time limit in seconds. | Charging for exactly 30 minutes (1800s) then exiting. |
| | `--force` | Bypass safety SoC limits. | Forcing discharge below 10% during emergency validation. |
| | `--off-grid-permitted`| Allow battery commands in off-grid state. | Permitting charge/discharge during backup mode. |
| | `--assume-clean-state`| Skip startup register conflict checks. | Bypassing initial verification checks to speed up startup. |
| **Automation** | `--sequence` | Execute an in-line JSON sequence string. | Enabling remote control and setting charge rate in one line. |
| | `--sequence-file`| Execute a multi-step JSON sequence file. | Running a complex automated multi-step hardware test. |
| | `--schedule-file`| Load a 24-hour TOU JSON schedule. | Fully automating battery logic based on utility tariffs. |
| | `--show-schedule`| Display a loaded schedule file. | Inspecting and printing schedule details in the terminal. |
| | `--validate-schedule`| Validate a schedule file schema. | Checking custom schedules for errors before running them. |
| | `--brief` | Enable minimal sequencer output. | Reducing logs for automated logging and monitoring systems. |
| **Diagnostics** | `--status` | Snapshot of current metrics. | Checking SoC and current power flow via terminal. |
| | `--monitor` | Launch interactive terminal dashboard (TUI). | Real-time visual monitoring of system parameters. |
| | `--healthcheck` | Comprehensive hardware diagnostic scan. | Troubleshooting "Zombie States" or Modbus connection issues. |
| | `--check-alarms` | Decode hardware error and alarm bitfields. | Diagnosing battery internal faults or grid error codes. |
| | `--clear-alarms` | Clear/reset persistent alarms. | Writing to AlarmReset to clear transient alarm codes. |
| | `--test-extension-write`| Test extension register writability. | Writing test values to 15507-15509 and reading them back (⚠️ writes to the device). |
| | `--check-span` | Scan network for SPAN panel integrations. | Locating and checking compatible smart panels on the LAN. |
| **UI & Output** | `-v`, `--verbose` | Enable verbose debug logging. | Troubleshooting detailed Modbus transaction sequences. |
| | `-q`, `--quiet` | Suppress non-error output. | Useful for scripting or when launching the monitor. |
| | `--detail` | Enable detailed status output. | Seeing raw register values in the status summary. |
| | `--theme` | Change dashboard color palette. | Using 'Paper' theme for high-contrast visibility. |

> [!IMPORTANT]
> **Writability Disclaimer:** `--mode`, `--self-reserve` and `--tou-reserve` write FranklinWH extension registers. Writes to the FranklinWH extension registers are undocumented and unconfirmed. FranklinWH has not documented these registers and has never documented any of them as writable. Whether FranklinWH must authorise a Modbus client to write them, and how, is unknown. On `V12R02B60D00` (owner observation, 2026-10-21), writes to 15507–15509 did not take effect: the mode did not switch and the reserves did not change. Treat them as read-only. The CLI/TUI reads each write back and reports the result.

---

## Example Scenarios

### Force Charge for 1 Hour with Safety Timeout
```bash
# Charges at 3000W, reverts to cloud control automatically after 3600s
python3 tools/franklinwh_cli.py -i 192.0.2.110 --charge 3000 --revert 3600 --loop
```

### Run Virtual Peak Shaving
```bash
python3 tools/franklinwh_cli.py -i 192.0.2.110 --vmode peak_shave --threshold 1500
```

### Execute a Hardware Test Sequence
```bash
python3 tools/franklinwh_cli.py -i 192.0.2.110 --sequence-file examples/test_write_reversion.json
```
