# Backlog

> **Purpose**: The formal queue for all deferred defects, features, and improvements.  
> All items must be logged here **before** any work begins (per the [Change Management Policy](https://github.com/david2069/franklinwh-modbus/blob/develop/.agents/policies/change_management.md)).  
> Items flow: **Queue (here) → Group → Plan → Execute → Remove from backlog**

---

## CI / Release Pipeline

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| DEF-CI-TESTPYPI | `publish.yml` — `environment: name: testpypi` triggers linter error *"Value 'testpypi' is not valid"* in GitHub Actions | S3 | `continue-on-error: true` means it doesn't block PyPI release, but the warning is noisy. Fix: add the `testpypi` environment in GitHub repo Settings → Environments. |

---

## CLI Tool / Network Scanner

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| ~~DEF-SCANNER-SPAN~~ | ~~SPAN Panel detection false positives~~ | ~~S3~~ | **RESOLVED** `07de71f`. Both `192.0.2.118` (AWTRIX 3 LED display) and `192.0.2.35` were false positives — neither is a SPAN Panel. No real SPAN Panel exists on this network. Fix: `probe_span()` now requires strict JSON schema from `/api/v1/status` or `/api/v1/circuits` instead of HTML content matching. **Investigation also revealed:** HA, Modbus, and SSH disappearing on second scan run was a thread-race at `--threads 100` (probers work correctly when called directly). |

---

## Library / Controller

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| DEF-HW-M713-STA | `M713.Sta` always returns `0` (IDLE) regardless of actual battery state | S3 | Hardware defect. Workaround: derive battery state from `WSetPct` and DC power. Already implemented — needs to be explicitly documented in `FRANKLINWH_SUNSPEC_QUIRKS.md`. |
| DEF-HW-HEARTBEAT | Hardware heartbeat (PICS timeout) non-functional | S3 | DC voltage is not populated; extension writes are undocumented and unconfirmed. Documented in quirks but no software workaround yet. |
| FEAT-LIB-CHARGE-MAX | Add `--charge-max` / `--discharge-max` CLI flags using nameplate rated power | S4 | Deferred from 2026-02-23 after `--charge`/`--discharge` explicit flags were added. Effort: ~30 min. |

---

## CLI Tool

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| FEAT-CLI-TUI-SPARKLINE | TUI Monitor: add timeline / sparkline panel (Stage 6 of original TUI plan) | S4 | Low priority visual enhancement. |
| FEAT-CLI-TUI-SOC-ETA | TUI Monitor: enhanced SoC bar with embedded reserve marker and ETA to target/reserve | S4 | Deferred from 2026-03-01 TUI monitor work. Spec in `TODO_TUI_TERMINAL_MONITOR.md` (archived). |
| FEAT-CLI-TUI-HELP | TUI Monitor: help screen missing `+/-`, `R`, `1–9` key documentation | S3 | Noted during Feb 2026 TUI fixes. Quick fix — update help panel text. |

---

## Hardware / Register Map

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| FEAT-HW-M701-LIFETIME | M701 Grid Lifetime Energy Metrics — not yet exposed in CLI or library | S4 | Known gap. Registers exist but not wired to any output. |
| DEF-HW-EXT-READONLY | Extension registers 15507–15509 (OnGridMode, SelfReserve, TOUReserve) are read-only via Modbus | S3 | Cannot control native mode via Modbus. Documented in quirks. Writes are undocumented; on V12R02B60D00 (2026-10-21) they did not take effect. No workaround. |
| FEAT-HW-MAC1-DISCOVERY | Hidden Register Scan for MAC-1 (Meter Adaptor Collar) | S3 | Search for grid metrics aliasing and new Unit ID (DA) profiles. |
| FEAT-HW-APOWER-S-DC | Registry Discovery for aPower S DC Hybrid | S3 | Identify new SunSpec models or extensions for DC-coupled storage telemetry. |

---

## Documentation

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| DOC-VIRTUAL-MODES-VALIDATION | `VIRTUAL_MODE_SPECIFICATIONS.md` validation targets are all `[ ]` — none have been hardware-verified | S3 | Fill in as modes are tested on live hardware. |
| DOC-MKDOCS-GETTING-STARTED | `GETTING_STARTED.md` contains an old reference to `GETTING_STARTED.md` at the bottom — dead link | S4 | Minor cleanup. |

---

## Safety / Modes

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| FEAT-SAFETY-INTENT-CONFLICT | Intent-based conflict detection (Phase 3) — deferred pending virtual mode testing | S3 | Decision recorded: selected Option 2 (Intent-Based). Band-aid detection is active. |

---

## Deferred / Low Priority

| ID | Item | Severity | Notes |
|----|------|----------|-------|
| FEAT-ACCESSORY-GEN | Generator module control via Modbus — not exposed | S4 | Hardware constraint. No Modbus registers available for generator. |
| FEAT-ACCESSORY-SMART-CIRCUITS | Smart Circuits control via Modbus — not exposed | S4 | Hardware constraint. Only available via Cloud API. |
| FEAT-ACCESSORY-V2L | V2L mode visibility via Modbus — not exposed | S4 | Hardware constraint. |

---

*Last updated: 2026-04-04 by agent (initial population from session history)*
