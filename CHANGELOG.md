# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Upgrade notes
Behaviour changes that can affect code built on the library:
- `connect()` no longer runs the extension writability test, so `_extension_writable` stays `None` after connecting. Call `test_extension_writability()` explicitly if you need it. **That call writes 15507–15509.** (#24)
- `VirtualModeController` calculators (`_calc_*`) return the opposite sign from before: positive = charge, negative = discharge, matching `BatteryCommand`. Subclasses or direct callers must follow. (#20)
- Self-consumption grid-charges only below `self_reserve_pct` (default 20%), not below `target_soc`, and no longer refuses to start with a full battery. (#20)
- `verify_command_execution()` returns `ok=False` when the readback fails. It used to assume success. (#21)
- Failed status reads log at **warning** level (first failure, then at most once a minute, then on recovery) instead of debug. (#22)

### Fixed
- **`connect()` no longer writes to the device.** It ran the extension writability test on every connection: it wrote 15507 (operating mode), 15508 and 15509 (reserves) with test values and restored them only if the readback matched. On a unit where those registers are writable, every connect (including every bridge reconnect) briefly changed the mode and reserves, and a dropped link could leave them changed (a 100% reserve was tested as 0%). The test is now the explicit `test_extension_writability()`, still run by `--test-extension-write`. (#24)
- Virtual-mode calculators now return the `BatteryCommand` convention (positive = charge, negative = discharge) that the SoC limiter and `send_command()` expect. Self-consumption, peak-shave and the TOU `discharge` strategy returned the opposite sign, so the limiter ramped and blocked the wrong direction (a charge near the discharge floor was cut back or blocked without any log), and the inverted setpoint went out as a positive `WSetPct`, which the device ignores. Reported by @balloobbot in #12. (#20)
- Self-consumption grid-charges at full power only below `self_reserve_pct` (`--reserve`, previously accepted but unused). Between the reserve and `target_soc` it covers home load from the battery and charges from excess solar. Before, it charged whenever SoC was below `target_soc`, which defaults to 100. Starting self-consumption with a full battery is no longer refused. (#20)
- `--power`/`--duration` honours `--min-discharge-soc 0` instead of coercing it to 20. The 20% default on that path is unchanged. (#20)
- `VirtualModeController.verify_command_execution()` compared the never-written `M704.WSet` with battery power, so it always passed. It now reads the setpoint back from `WSetPct` and reports a failed readback instead of assuming success. (#21)

### Added
- `FranklinWHController.verify_dispatch(expected_w, tolerance_pct=20, timeout_s=0)` reads back `WSetEna`/`WSetPct` and `M714.DCW`, compares them in the `BatteryCommand` convention, and returns `ok`, `dispatched`, `commanded_w`, `actual_w` and `reason`. It detects a dispatch the device accepted but did not act on. With `timeout_s` it polls while the battery ramps. Tolerance has a 100 W floor (M714.DCW reads in 100 W steps), and commands under 150 W are verified on the setpoint only. (#21)
- Controller I/O health: `last_success_ts`, `last_error`, `last_error_ts`, `consecutive_failures` and `data_age_s`, so callers can tell a dead link from an empty read. (#22)
- The SoC limiter logs when it ramps a command (once per distinct value), not only when it blocks one. (#20)

### Changed
- Failed status reads (`read_battery_status`, `read_grid_status`, `read_solar_status`, `read_control_status`) log at warning level on the first failure and then at most once a minute, plus once on recovery. They were logged at debug level only. Return values are unchanged (`{}` on failure). (#22)

## [0.9.5] - 2026-10-07

### Added
- `franklinwh_modbus.discovery` — read-only discovery of SunSpec Modbus devices, for finding an aGate on a host or subnet without re-implementing Modbus I/O. `probe(host, …)` checks the `SunS` marker at bases 0, 40000, 50000 and 30000 and reads the Common model nameplate in one request; `scan(subnet, …)` TCP-checks port 502 in parallel and probes only the open hosts (private ranges and at most 254 hosts unless told otherwise). Only SunSpec devices returning the Common model (1) count as `sunspec`; anything else listening is `unknown` (reason in `error`), and nothing listening is `closed`. `is_franklinwh` flags a SunSpec device whose manufacturer names FranklinWH; `summary` gives a one-line description. Works with both pymodbus unit-id keywords (`slave=` / `device_id=`). Documented in `docs/DISCOVERY.md`.

### Changed
- `tools/network_scanner.py`: `ModbusSunspecProber` now delegates to `discovery.probe()` (same output, same 3-attempt behaviour), so the tool and the library share one SunSpec probe.

## [0.9.4] - 2026-10-04

### Fixed
- `--dry-run` no longer writes to the device. `set_mode()` applies a mode immediately via `execute_once()` but took no `dry_run` parameter, so `franklinwh_cli.py --vmode ... --dry-run` engaged control (`WSetEna=1`, `WSetPct=100.0`) and then reported "no commands sent". Confirmed on an aGate X (`V10R01B04D00`); the orphaned dispatch pins the battery until released. Both CLI entry points were affected (`--vmode` and `--power`/`--duration`). `set_mode()` and `execute_once()` now take `dry_run`, matching `set_native_mode()` and its siblings. (#13)

### Changed
- Removed the unverified "SPAN Modbus unlock" attribution from all messages, logs, help text and the capability manifest. The library stated that extension register writes (15507-15509) fail because an installer option needs unlocking; that was inference, never confirmed by FranklinWH, and reached end users as actionable advice. Messages now report only what is observed: writes are accepted at the protocol level but not applied on the firmware tested. `--check-span` no longer infers writability from panel presence. `_span_writable` renamed to `_extension_writable`. (#14)
- Package metadata and LICENSE now use the GitHub handle rather than a real name.

### Added
- Legal disclaimer (`DISCLAIMER` in `constants.py`), logged once per process at `FranklinWHController` construction and reproduced in `readme.md` and `docs/index.md`. States that this library is unofficial and unaffiliated, that it writes to energy hardware and can charge, discharge and stop a battery, and that FranklinWH support should not be contacted about defects or feature requests for this software. (#14)
- Documentation of FranklinWH's SunSpec Alliance contributing membership on the docs front page and in `SUNSPEC_COMPLIANCE_BASIS.md`. (#14)
- Regression tests asserting a dry run never reaches `send_command` without `dry_run` set (`tests/unit/test_dry_run_no_writes.py`). (#13)

## [0.9.3] - 2026-06-15

### Added
- Multi-battery parallel stack support in SunSpec Model 714 (`DER Storage DC Measurement`), including summing power/energy, voltage averaging, and peak temperature tracking across parallel battery stacks.
- Per-battery telemetry array (`individual_batteries`) in `read_battery_status()` for granular battery stack diagnostics.
- Repeating block suffix tag notation (e.g., `714.DCW_1`, `714.DCW_2`) in `SunSpecSequencer` to target specific repeating block registers.
- Support for scanning and displaying repeating blocks with cache-aware scale factor resolution and suffix formatting in the diagnostic reader tool (`modbus_sunspec2_reader.py`).
- Certified PICS-compliant enum resolution utility (`get_pics_enum_desc`) and `FranklinWHController.get_enum_desc` for client applications (FEAT-PICS-ENUM-RESOLVER)
- Prominent TUI Control status header (`Control: Remote (r=release)` or `Control: Local`) and active VPP setpoint warning alerts (`WSetEna` and `WSetPct`) on the interactive dashboard (FEAT-MONITOR-VPP-WARNINGS)
- SunSpec InfoPoint Sequencer for automated register control sequences
- Diagnostic conformance suite for hardware register verification
- Comprehensive SunSpec Model Reference documentation (`SUNSPEC_MODEL_REFERENCE.md`)
- MIT License, CONTRIBUTING.md, GitHub issue/PR templates
- Branch protection rulesets for `develop` and `master`
- Repository topics for discoverability
- Grid lifetime energy metrics (`M701.TotWhInj`, `M701.TotWhAbs`) in `read_grid_status()`, monitor TUI, and `--status --detail` (FEAT-MONITOR-GRID-LIFETIME)
- Standby Handshake during release of remote control (`reset_control_state`) to force `0W` power output and wait for the inverter to ramp down/stabilize before setting `WSetEna=0`. Prevents abrupt transients on physical hardware.
- Unit test coverage for Standby Handshake (`tests/unit/test_standby_handshake.py`) testing active VPP delays, inactive control bypasses, and 0-second overrides.
- Automated `uint32` data width support, scale factor resolution, and enum symbol mapping in the `SunSpecSequencer` for proprietary extension registers.
- Step-level inline overrides for sequencing reads and writes, allowing custom type/scaling configurations dynamically, supporting `"addr"`, `"point"`, and `"address"` configuration keys.

### Fixed
- **CRITICAL:** Fixed bug in `verify_command_execution()` where scale factor lookup failed due to using `self` instead of `self.ctrl`.
- Synchronized Grid and Battery telemetry signs with confirmed hardware behavior (Negative = Charge/Import). Resolves directional labeling conflict in CLI and Monitor (Batch 4 / Issue #6).
- Corrected `battery_state` derivation in `controller.py` to match physical power flow.
- **CRITICAL:** Added missing `Union` to the `typing` import in `controller.py`; method parameter annotations using `Union[...]` raised `NameError: name 'Union' is not defined` at import on Python ≤ 3.13 (the eager-annotation versions, incl. CI's 3.12). Python 3.14's deferred annotation evaluation (PEP 649) had masked it in local dev runs.

### Changed
- Replaced hardcoded IP addresses with `YOUR_AGATE_IP` placeholder
- Replaced device serial numbers with `XXXXXXXXXXXXXXXXXXXX` placeholder
- Updated `setup.py` email to GitHub noreply address
- Cleaned docs/ and tools/ indexes for public visibility
- Updated `reset_control_state` method signature to accept a configurable `handshake_wait_s` parameter (default `1.0` seconds) to control the standby handshake duration.

### Removed
- Internal test results, archive directory, agent configs from tracked files
- 53 one-off tool scripts (9 curated tools remain)
- Internal design docs and proprietary references

## [0.9.0] - 2026-03-16

### Fixed
- **CRITICAL:** WSetPct charge rate calculation used wrong denominator (`WMaxRtg=1000W` instead of `WChaRteMaxRtg=5000W`). Requesting 1200W charge now correctly produces WSetPct=-24% instead of -120%. (DEF-001)
- `actual_power` read-back in `read_full_status()` now uses direction-aware charge/discharge rates
- Success messages display correct rated capacity (5000W) instead of WMaxRtg (1000W)
- "ORPHANED VPP DETECTED" warning downgraded to INFO — WSetEna=1 is normal persistent state (DEF-002)
- Removed EXTENSION REGISTERS section from `--status` output; retained in `--healthcheck` (DEF-003)

### Added
- High-resolution home load from Register 16000 (~1W precision vs 10W from extensions)
- Propagated high-res home load to CLI, standalone tool, and demo
- Base-1 addressing reference in QUIRKS.md
- PICS-driven safety improvements: orphan VPP check, input validation, alarm definitions
- M801/M802 battery model scan — confirmed non-existence on aGate
- Register 15000-15043 correlation analysis

### Changed
- Conflict detection now uses energy context (solar, load, grid) to reduce false positives
- PICS conformance cross-reference updated with vendor submission findings

## [0.8.0] - 2026-03-10

### Added
- Package namespace renamed from `franklinwh` to `franklinwh_modbus` (avoids conflict with Cloud API)
- SunSpec DER sequencing reference documentation
- Comprehensive hardware test guide
- VPP Mode visual reference with mobile app screenshots

### Changed
- CLI restructured to use library imports (`from franklinwh_modbus import ...`)

## [0.7.0] - 2026-03-08

### Added
- Extension register write probing (15507-15509 writability detection)
- Virtual mode specifications (Self-Consumption, Emergency Backup, TOU, Peak Shave, Manual)
- Orchestration and control documentation with sequence diagrams
- Safety controls documentation (10 safety rules)
- Software timeout (watchdog) implementation for VPP commands
- Battery state derivation from DC power (replacing unreliable M713.Sta)

### Fixed
- SoC proximity ramping for charge/discharge near target
- Control conflict detection with aGate native modes

## [0.6.0] - 2026-02-24

### Added
- MQTT publisher with Home Assistant discovery
- TUI monitor (`--monitor`) using Rich library
- TOU schedule support with JSON definitions
- Modbus throttling analysis and rate limiting
- Network scanner for aGate discovery

### Fixed
- Connection stability with threaded status fetching and timeout guards
- MQTT keepalive tuning for persistent sessions

## [0.5.0] - 2026-02-18

### Added
- Initial `FranklinWHController` with pysunspec2 integration
- SunSpec model scanning (Models 1, 701-715)
- Battery charge/discharge via M704 WSetPct/WSetEna
- Extension register reading (15500-15509)
- CLI tool with `--status`, `--charge`, `--discharge`, `--stop`
- Basic alarm monitoring

[Unreleased]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.5...HEAD
[0.9.5]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.4...v0.9.5
[0.9.4]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.3...v0.9.4
[0.9.3]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.2...v0.9.3
[0.9.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/david2069/franklinwh-modbus/releases/tag/v0.5.0
