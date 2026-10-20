# TODO: Native Mode Switching (Register 15507)

**Status:** Approved (pending implementation)  
**Approved:** 2026-05-15  
**Priority:** S2 — High  
**Estimated Effort:** Medium

## Description
Repurpose the existing CLI `--mode` flag to control the native FranklinWH Operating Mode via Modbus Extension Register 15507 (`OnGridMode`). Introduce a new `--vmode` flag to handle the virtual (software-emulated) operating modes.

## Requirements (as approved)
- Update `tools/franklinwh_cli.py` argument parsing:
    - `--mode` -> Writes to Register 15507.
    - `--vmode` -> Uses existing virtual mode logic.
- Supported Native Modes (Register 15507):
    - 1: Backup
    - 2: Self-Consumption
    - 3: TOU
    - 4: Manual (Wait for standby/handoff)
- Maintain backward compatibility where possible or document the breaking change.

## Implementation Notes
- Register 15507 is 1-indexed for modes.
- Hardware transition times may apply; status should reflect the "Target Mode" vs "Actual Mode" if available.

## Related
- GitHub Issue: [#9](https://github.com/david2069/franklinwh-modbus/issues/9)
- Original approval context: [in_flight_work.md](/in_flight_work.md)
