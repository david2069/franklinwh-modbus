# Approved Workarounds

The library sends each request through its own SunSpec point: percent through `WSetPct` (`WSetMod=0`) and watts through `WSet` (`WSetMod=1`). It never converts one into the other.

Anything that departs from plain SunSpec is listed here only when the owner has approved it. Each entry records the approval, the reason and the log line. Every time one of these runs, the library logs it with the tag `[approved workaround #114 …]`, so it can be found in the application log.

Approved by the owner on 2026-10-24 in [#114](https://github.com/david2069/franklinwh-modbus/issues/114) (items B3 and B4).

| Workaround | What it does | Reason | Log line (tag) |
|---|---|---|---|
| Standby handshake | `reset_control_state()`: if `WSetEna`=1, it writes 0 W (`WSetPct`=0, `WSet`=0) and waits `handshake_wait_s` (default 1 s) before `WSetEna`=0. `handshake_wait_s=0` skips it. | The battery gets a 0 W setpoint before control is released, instead of being released straight from a non-zero setpoint. | INFO `Performing standby handshake … [approved workaround #114 B3: standby handshake]` |
| Software timeout | `send_command(..., duration_s=N)` starts a timer that calls `reset_control_state()` after N seconds. It runs only when `duration_s` is set. | The aGate has no working hardware reversion: `WSetRvrtTms` doesn't revert per spec on V10 or V12R02B60D00, and `ControllerHb` is non-functional. See [SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md). | INFO `Software timeout set …`; WARNING `Software timeout (Ns) expired …` (`[approved workaround #114 B3: software timeout]`) |
| Power clamps | `BatteryCommand` clamps `power_watts` to ±10000 W. `send_command` clamps watts to the charge/discharge rating, keeping the direction. | The aGate accepts out-of-range setpoints without validation (PICS Issue 5). | WARNING `… clamped to … [approved workaround #114 B3: power clamp]` |
| Rating fallback | `discover_ratings()` uses 5000 W when M702 is missing or a rating (`WMaxRtg`, `WChaRteMaxRtg`, `WDisChaRteMaxRtg`) reads 0. The constructor overrides `max_charge_w` / `max_discharge_w` take precedence. | V12R02B60D00 reports `WMaxRtg` 0, so there is no rating to clamp against without it. | WARNING `M702 WMaxRtg reads 0; using 5000W [approved workaround #114 B3: rating fallback]` |
| WSetMod restore on a refused percent command | Percent commands are two frames (`WSetMod`, then `WSetPct`). If `WSetPct` is refused after `WSetMod` was accepted, `send_command` writes `WSetMod` back to its previous value. Approved 2026-10-28 (#114, "fix wsetmod"). | A refused command should change nothing. Live 2026-10-24: `WSetMod`=0 stayed after the `WSetPct` refusal. | WARNING `WSetPct=N refused: WSetMod restored from 0 to 1` |
| Home load from 16000 | `_read_extension_solar()` reads home load from extension register 16000 and falls back to 15506 if the read fails. | 16000 gives about 1 W resolution; 15506 is quantised to about 100 W. Neither is documented by FranklinWH. | INFO on every read, with the value used, its register and the 15506 value (`Home load 1234W from 16000 (15506 read 1200W) [approved workaround #114 B4: 16000 instead of 15506]`); WARNING when the 16000 read fails and 15506 is used |

## Removed (owner decision 2026-10-24, #114)

- **B1:** `dispatch()` converted "N%" to watts of the rating. It now sends `WSetPct`.
- **B2:** `tools/franklinwh_control_standalone.py` converted watts to `WSetPct`. It now sends `WSet`.
