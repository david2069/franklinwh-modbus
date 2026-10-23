# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.1] - 2026-10-24

### Upgrade notes
- **`send_command` now writes `WSetMod=1` + `WSet` (watts), not `WSetPct`.** It no longer writes `WSetEna=0` before each command, and it returns `(False, "Command not applied: …")` if the read-back differs. Anything that read `WSetPct` to see the active command should read `WSet`/`WSetMod` (or `read_control_status()['wset_mode']`/`['wset_watts']`).
- **A refused write now fails at once** with "Rejected by the aGate (…)", instead of reconnecting and resending (#96).
- **Charging is still refused by V12R02B60D00** (negative `WSet` and `WSetPct`, exception 3); a charge command returns that rejection.

### Fixed
- **Sequencer raw-address reads and writes did nothing** after the scan, because the socket was closed and `write_value` called a missing method (#99). They now reconnect first and handle FC06/FC16.
- **Sequencer: a rejected write aborted the sequence and skipped restore steps** (#101). Steps take `on_error` (abort / continue / retry; transport errors only), and a `{"steps", "cleanup"}` form whose cleanup always runs.
- **`send_command` now sends watts through `WSet` (`WSetMod=1`), not `WSetPct`.** V12R02B60D00 refuses `WSetPct` above 10 % with exception 3, so a 5000 W Force Discharge (sent as 100 %) never ran; one bridge log recorded 116 refusals in an hour. The watts path delivered 5000 W, 3 of 3 runs. `WSetEna` is no longer cycled to 0 before each change (DER v1.2 §3.3), `WSetMod`+`WSet` go in one write, and the result is read back. Charging through `WSet` is still refused by V12.
- **A Modbus exception response is no longer treated as a connection fault** (#96). `_with_retry` reconnected and resent on exception 3; it now returns "Rejected by the aGate" at once.

### Changed
- **Docs: reserve and mode readings on V12R02B60D00.** **16001 holds the reserve for the active mode** (8 in Self-Consumption, 15 in TOU); it was documented as a mirror of 15508. 15507 is confirmed as 1 = Emergency Backup, 2 = Self-Consumption and 3 = TOU by reads in each mode; 4 is still unread (#75). In Emergency Backup, 16001 reads 100. 16002 reads 20 in both modes. (#63)

### Changed
- **Docs: aGate firmware V12R02B60D00.**
  - A new dated snapshot (`docs/SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md`): the SunSpec map is unchanged from 2026-05-14, as are the scale factors.
  - **Read-only re-scan (2026-10-20T20:17Z):**
    - On V12R02B60D00 the **SunSpec map is also served at PDU 40000** (it returned exception 2 on V10). Pysunspec2's scan, and this library (#84), bind to that mirror; writes to it are unverified.
    - M714's per-port block reads all zero on V12, so battery DC voltage and temperature aren't available from it.
    - 15500 = 1; 15040 and 15043 are newly seen.
  - The docs that said "40000+ returns exception 2" now give the result per firmware.
  - **15509 now holds the TOU reserve.** The V10R01B04D00 defect, where it repeated 15508, is fixed on V12 (#63). The extension page, QUIRKS, the HA guide (add a TOU reserve sensor on V12+) and the cloud comparison now say this per firmware.
- **HA Modbus YAML guide: "everything the TUI shows" (§2b).** It adds 18 optional sensors: battery SoH, energy available and rating, voltage and temperature; AC voltage, current, frequency, PF, VA and VAR; ambient and cabinet temperature; solar proximal and remote 1/2; model and firmware. It adds **description templates** for inverter state, battery state (Charging / Discharging / Idle), grid mode (Grid Forming / Grid Following), operating mode (provisional, #75), battery current, active alarm names and PV clipped. Also a TUI panel → entity map and a TUI-style card. The battery voltage and temperature addresses are computed from SunSpec model 714 and were confirmed against the gateway emulator. They may read 0 on V10R01B04D00, which is unresolved and noted in the guide. Tested 2026-10-20 against the emulator (34 sensors, 9 templates, on-grid and off-grid), with screenshots. Active Alarms shows "No alarms" instead of a value HA reads as unknown.

### Added
- **Home Assistant: Monitoring with Modbus YAML** (`docs/HOME_ASSISTANT_MODBUS_YAML.md`): a monitor-only proof of concept using Home Assistant's built-in Modbus integration. It covers 16 sensors (SoC, battery, grid, solar, home, reserve, mode, lifetime grid, battery and solar energy, and M701 grid connection, inverter state, DER mode and alarm bits), plus template sensors for **grid status** (on grid / backup (off-grid) / disconnected) and **grid connected**, Energy dashboard mapping, a built-in-cards dashboard, a scale-factor check, verification against the CLI, troubleshooting, and pros and cons. Tested against the gateway emulator in HA 2026.10.1, with screenshots; not yet tested against a real aGate.

### Changed
- **"What is Modbus TCP?" rewritten** with sourced background:
  - Modbus origins (Modicon 1979, Modbus Organization 2004, TCP/IP 1999) and its specifications;
  - the SunSpec Alliance, the "SunS" model chain, the 700-series DER models and IEEE 1547-2018;
  - SunSpec publications;
  - what a PICS is and how certification works, plus FranklinWH's PICS;
  - where the FranklinWH extension registers sit in that context: outside the SunSpec chain, not vendor models, and not covered by certification.

  It also corrects "TOU schedules: read-only (extension registers)": TOU schedules aren't available over Modbus.
- **Removed the remaining "SPAN unlock" claims** from the docs, the bug template, the sequencer example, the compliance report and tool messages. These said extension register writes need a "SPAN Modbus" (or "SPAN/Lumin") installer unlock or provisioning. FranklinWH has not documented the extension registers and has never documented any of them as writable; whether it must authorise a Modbus client to write them is unknown. On `V12R02B60D00` (owner observation, 2026-10-21) writes to 15507–15509 did not take effect. Access columns for 15507–15509 now read "R (writes undocumented)", and the raw reader labels them `R`. Earlier `RW` labels are marked as speculation. SPAN is a third-party company; no relationship is implied.

### Added
- **Modbus Client Libraries** (`docs/MODBUS_CLIENT_LIBRARIES.md`), every claim sourced. It covers:
  - this library's dependencies;
  - the Python Modbus client libraries, with PyPI facts;
  - the pros and cons of raw register reads;
  - worked pysunspec2 examples;
  - the Open Home Foundation's modbus-connection, its pros, cons and boundary;
  - whether a FranklinWH-specific library is needed.
  - the API 2.0 decision record and the read-only spike plan, folded in from PR #32's evaluation, which this page supersedes.

### Added
- **FranklinWH Extension Registers** page (`docs/FRANKLINWH_MODBUS_EXTENSIONS.md`): one table of every extension register (15000–15043, 15500–15513, 16000–16002), with access, type and unit, meaning, library accessor and evidence, plus how to read and write them. QUIRKS and the cookbook now point to it instead of keeping their own copies. The Extensions Manifest is marked as raw scan evidence, with its correlation guesses flagged as speculative.
- **API Cookbook** (`docs/API_COOKBOOK.md`): worked examples for connecting, a full status snapshot, every TUI panel and key mapped to its API call, each CLI command with its Python equivalent, battery control, virtual modes, alarms, the FranklinWH extension registers (what they are, how to read and write them, quirks), and a link to the cloud comparison.
- **Modbus vs Cloud API comparison** (`docs/MODBUS_CLOUD_COMPARISON.md`): a field-by-field map of the Modbus client and the FranklinWH cloud API, covering units, signs, the 3 vs 4 grid states, energy and evidence labels. It's kept in step with franklinwh-cloud's own copy.

### Changed
- **Docs: Modbus addressing uses modbus.org terms.** Every register address in the docs is now a Modbus **PDU address** (0-based, as sent on the wire, as in the FranklinWH PICS: ControllerHb is 1092). The "base-1" and "base-40000" labels, which wrongly called PDU addresses base-1, are gone. QUIRKS now separates what Modbus defines (PDU address, register number, holding registers, the Modicon 4xxxx reference) from what SunSpec adds (the "SunS" marker at PDU 0, 40000 or 50000). The aGate's map starts at PDU 0. Device snapshot sections and glossary columns say which notation they print. Dead links to the proprietary PICS spreadsheet, which is not distributed here, now cite it by name. (#43)

## [0.10.0] - 2026-10-17

> **Alarms are reported, not decided.** The library now names every active alarm from the SunSpec models and leaves the decision to the caller. `check_blocking_alarms()` is deprecated, and `healthcheck()` no longer turns unhealthy on alarms. A failed alarm read is never reported as "no alarms". Read the upgrade notes if you use `healthcheck()`, `--check-alarms` or `check_blocking_alarms()`.

### Upgrade notes
- **The library no longer decides what an alarm means; the client does.** (#40, #46)
  - `check_blocking_alarms()` is deprecated (it warns, and will be removed). Use `read_alarms()` or the new `active_alarms()` and apply your own rule.
  - `healthcheck()` lists active alarms in `details['alarms']` and in its recommendations, but they no longer affect `healthy` or `message`. `details['blocking_alarms']` and `details['can_operate']` are gone.
  - The conflict check's `result['alarms']` is now `{'active', 'system_alrm', 'decoded'}`; `can_operate` and `blocking` are gone.
  - `VirtualModeController.run_continuous(enable_safety_checks=True)` no longer stops after two alarm checks. Its SoC-limit and dispatch-verification checks are unchanged.
  - A failed alarm read is never "no alarms": `active_alarms()` returns `["Alarm read failed: …"]`, so `--check-alarms` exits 1, and the deprecated `check_blocking_alarms()` returns `(False, ["ALARM_READ_FAILED: …"])`. Its `CRITICAL_BITS` are still the set that is one bit off from model 701 (#46); it's kept unchanged until the function is removed.
  - `--check-alarms` exits 1 if **any** alarm is active (before: only the fixed "critical" set). `--healthcheck` and `--status` print "ACTIVE ALARMS".
- `read_alarms()` now reads models 701, 713, 714 and 502 itself (pass `refresh=False` if you read them in the same poll), and it fills `decoded`. DC ports in `decoded['dc_port']` are numbered from 1, the same as `read_battery_status()['individual_batteries']`. (#39)
- If `read_alarms()` fails, the result has an `error` key and the failure is logged at warning level. It used to return zeros at debug level, which looked like "no alarms". Check `error` before trusting an empty alarm list. (#39)

### Added
- `FranklinWHController.active_alarms(alarms=None)`: every active alarm by name (system, DC port, solar, and the battery when not OK), from `read_alarms()`. Reports only. (#46)

### Fixed
- `--status --detail` labels AC Type `(derived from M701.LNV)`. It said `(M701.ACType)`, a point the library doesn't read; the value comes from the voltage band. (#42)
- **`read_alarms()` reads the device and names every active alarm.** It returned whatever another call had last loaded into the models (it never read them itself) and left `decoded` empty, so `--check-alarms` printed `Battery Status: UNKNOWN` and empty lists. It now reads models 701, 713, 714 and 502 first (pass `refresh=False` if you read them moments ago) and lists every set bit, named from the SunSpec model definitions in pysunspec2: M701 `Alrm`, M502 `Evt` (new: `solar_evt`, `decoded['solar']`), M713 `Sta` (OK / WARNING / ERROR), M701 `MnAlrmInfo` (new: `vendor_info`), and per DC port the `DCAlrm` bits plus a WARNING/ERROR `DCSta`. M714 `PrtAlrms` only flags which ports have an alarm; it is not an alarm-type field. The standalone tool's name tables were not ported: its system-alarm names are shifted by one bit from model 701, and its DC-port names are not in model 714. (#39)

## [0.9.6] - 2026-10-17

> **Upgrade advisory: all 0.9.5 users should upgrade.** 0.9.5 has two S1 defects that act on the battery. `connect()` writes the operating mode and reserves (15507–15509) on every connection (#24), and a charge or discharge above the device rating is clamped to full power in the **opposite** direction (#28). 0.9.6 also fixes the battery ERROR status, which was never recognised (#38). Read the upgrade notes below before upgrading: several behaviours changed.

### Upgrade notes
Behaviour changes that can affect code built on the library:
- `connect()` no longer runs the extension writability test, so `_extension_writable` stays `None` after connecting. Call `test_extension_writability()` explicitly if you need it. **That call writes 15507–15509.** (#24)
- `VirtualModeController` calculators (`_calc_*`) return the opposite sign from before: positive = charge, negative = discharge, matching `BatteryCommand`. Subclasses or direct callers must follow. (#20)
- Self-consumption grid-charges only below `self_reserve_pct` (default 20%), not below `target_soc`, and no longer refuses to start with a full battery. (#20)
- `verify_command_execution()` returns `ok=False` when the readback fails. It used to assume success. (#21)
- Failed status reads log at **warning** level (first failure, then at most once a minute, then on recovery) instead of debug. (#22)
- When one model fails inside `read_battery_status()` or `read_solar_status()`, the result now carries `partial` (e.g. `['714']`) and **leaves that model's keys out**. `read_solar_status()` used to report them as `0`. Use `.get()` on `ac_power_w`, `dc_power_w` and `battery_dc_power_w`, and treat a present `partial` as an incomplete sample. (#52)

### Fixed
- **Partial read failures are no longer silent.** A model 714 (or 502) read that failed inside an otherwise successful `read_battery_status()` or `read_solar_status()` was logged at debug level only. Battery power, state, current and temperature disappeared without trace, and `read_solar_status()` reported `0` W, which looks the same as an idle battery or no solar. It now logs a warning (first failure, then at most once a minute per model, then on recovery), updates `last_error`, and lists the model in `partial`. A failed M502 still falls back to the extension solar total when one is available. `consecutive_failures` keeps counting whole-read failures only. (#52)
- **Battery status is read with the SunSpec values.** Model 713 defines `Sta` as 0 OK, 1 WARNING, 2 ERROR (pysunspec2 1.3.3 `model_713.json`); the library tested for 6, which SunSpec does not define, so a battery ERROR was never recognised. `--status` now prints ERROR or WARNING, and `check_blocking_alarms()` reports `BATTERY_FAULT` on 2 instead of 6. A WARNING, or a value SunSpec does not define, is logged. Only `Sta = 0` has been observed on the aGate. (#38)
- **`connect()` no longer writes to the device.** It ran the extension writability test on every connection: it wrote 15507 (operating mode), 15508 and 15509 (reserves) with test values and restored them only if the readback matched. On a unit where those registers are writable, every connect (including every bridge reconnect) briefly changed the mode and reserves, and a dropped link could leave them changed (a 100% reserve was tested as 0%). The test is now the explicit `test_extension_writability()`, still run by `--test-extension-write`. (#24)
- **The rating clamp no longer reverses the direction of over-limit commands.** `send_command()` clamped a charge above the device rating to a full-rate discharge, and a discharge above it to a full-rate charge (e.g. `--power 6000` on a 5 kW unit discharged at 5 kW). It now clamps to the rating in the requested direction. The same fix is in `tools/franklinwh_control_standalone.py`. (#28)
- Virtual-mode calculators now return the `BatteryCommand` convention (positive = charge, negative = discharge) that the SoC limiter and `send_command()` expect. Self-consumption, peak-shave and the TOU `discharge` strategy returned the opposite sign, so the limiter ramped and blocked the wrong direction (a charge near the discharge floor was cut back or blocked without any log), and the inverted setpoint went out as a positive `WSetPct`, which the device ignores. Reported by @balloobbot in #12. (#20)
- Self-consumption grid-charges at full power only below `self_reserve_pct` (`--reserve`, previously accepted but unused). Between the reserve and `target_soc` it covers home load from the battery and charges from excess solar. Before, it charged whenever SoC was below `target_soc`, which defaults to 100. Starting self-consumption with a full battery is no longer refused. (#20)
- `--power`/`--duration` honours `--min-discharge-soc 0` instead of coercing it to 20. The 20% default on that path is unchanged. (#20)
- `VirtualModeController.verify_command_execution()` compared the never-written `M704.WSet` with battery power, so it always passed. It now reads the setpoint back from `WSetPct` and reports a failed readback instead of assuming success. (#21)

### Added
- `FranklinWHController.verify_dispatch(expected_w, tolerance_pct=20, timeout_s=0)` reads back `WSetEna`/`WSetPct` and `M714.DCW`, compares them in the `BatteryCommand` convention, and returns `ok`, `dispatched`, `commanded_w`, `actual_w` and `reason`. It detects a dispatch the device accepted but did not act on. With `timeout_s` it polls while the battery ramps. Tolerance has a 100 W floor (M714.DCW reads in 100 W steps), and commands under 150 W are verified on the setpoint only. (#21)
- Controller I/O health: `last_success_ts`, `last_error`, `last_error_ts`, `consecutive_failures` and `data_age_s`, so callers can tell a dead link from an empty read. (#22)
- The SoC limiter logs when it ramps a command (once per distinct value), not only when it blocks one. (#20)

### Changed
- `send_command(duration_s=…)` documents that its timeout runs `reset_control_state()` on a timer thread without the caller's lock. Callers that share the controller across threads should release from their own watchdog instead. A lock fix is tracked in #54.
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

[Unreleased]: https://github.com/david2069/franklinwh-modbus/compare/v0.10.1...HEAD
[0.10.1]: https://github.com/david2069/franklinwh-modbus/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.6...v0.10.0
[0.9.6]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.5...v0.9.6
[0.9.5]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.4...v0.9.5
[0.9.4]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.3...v0.9.4
[0.9.3]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.2...v0.9.3
[0.9.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/david2069/franklinwh-modbus/releases/tag/v0.5.0
