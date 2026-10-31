# Alarms, Errors and Exceptions

What the aGate reports when something is wrong, per firmware (M1 `Vr`). There are three kinds:

- **Alarm and status points:** registers that should change when the device has a fault.
- **Modbus exceptions:** the aGate refuses a request with an exception code.
- **Silent discards:** the aGate acknowledges a write without an exception, but the value doesn't stick or has no effect. No alarm or exception reports these.

Every row cites its source. Firmware columns: **V10** = V10R01B04D00, **V12** = V12R02B60D00. "—" = not on record. Re-check every row when the firmware changes, and add a column for the new firmware rather than overwriting.

## Alarm and status points

No alarm or status point has ever been seen in a fault state, so whether the aGate raises any alarm over Modbus is **unknown**. All captures on record are from normal operation at one site.

| Point (PDU) | Meaning (SunSpec) | V10 | V12 | Library |
|---|---|---|---|---|
| M701 `Alrm` (76) | DER alarm bitfield | 0 (2026-03-13 probe under out-of-range writes; 2026-05-14 scan) | 0 (2026-10-20) | `read_alarms()['system_alrm']`, named in `decoded` |
| M701 `St` (73) | Operating state | 1 (2026-05-14) | 1 (2026-10-20) | — |
| M701 `InvSt` (74) | Inverter state | 3 = RUNNING (2026-05-14) | 3 (2026-10-20) | — |
| M701 `ConnSt` (75) | Grid connection state | 1 (2026-05-14) | 1 (2026-10-20) | — |
| M701 `DERMode` (78) | DER mode bitfield | 1 (2026-05-14) | 1 (2026-10-20) | — |
| M701 `ThrotPct` (180) | Throttle % | not implemented (2026-05-14 scan). An undated QUIRKS row says "readable, always 0 %"; it conflicts with the scan and has no raw read behind it | not implemented (2026-10-20) | — |
| M701 `ThrotSrc` (181) | Throttle source bitfield | not implemented (0xFFFFFFFF) | not implemented (2026-10-20) | — |
| M701 `MnAlrmInfo` (193) | Manufacturer alarm text | **"Manufacturer custom error info"**, a fixed placeholder (2026-03-13; 2026-05-14) | same placeholder (2026-10-20) | `read_alarms()['vendor_info']`: empty when the value is the placeholder; `vendor_info_raw` has the string as read ([#136](https://github.com/david2069/franklinwh-modbus/issues/136)) |
| M713 `Sta` (1039) | Storage status: 0 OK, 1 WARNING, 2 ERROR | 0, including while charging at 400 W (2026-03-10) | 0 (2026-10-20) | `read_alarms()['battery_sta']`; also `read_battery_status()['status_raw']` |
| M714 `PrtAlrms` (1044) | Which DC ports have an alarm | 0 (2026-03-13 probe; 2026-05-14) | 0 (2026-10-20) | `read_alarms()['dc_port_alrm']` |
| M714 `Prt.1.DCAlrm` (1085) | Port alarm bitfield | — (port block not read) | 0, with the whole port block 0 ([#129](https://github.com/david2069/franklinwh-modbus/issues/129)) | named in `read_alarms()['decoded']` |
| M714 `Prt.1.DCSta` (1084) | Port state | — | **0 = OFF while the battery moves 600 W** (#129) | WARNING/ERROR named in `decoded` |
| M502 `Stat`, `StatVend`, `Evt`, `EvtVend` | Solar module status and events | 0 (2026-05-14) | 0 (2026-10-20) | `read_alarms()['solar_evt']` (`Evt`) |
| M715 `DERHb` (1090) | DER heartbeat | 0 (2026-05-14) | 0, does not advance (2026-10-23, [#107](https://github.com/david2069/franklinwh-modbus/issues/107)) | — |
| M715 `AlarmReset` (1094) | Alarm reset | write accepted, reads back 0, no latched alarms (2026-03-13) | 0 (2026-10-20) | — |
| M715 `OpCtl` (1095) | Operation control | 0 (2026-03-13); write not tested | 0 (2026-10-20) | — |
| Extension 15016 | Status code (undocumented) | 2 on-grid; 6 during a WSet dispatch; 3 off-grid (bridge reports, 2026-10-09/15) | 2 on-grid; 1 for ~2 min after the aGate was unreachable (bridge report, 2026-10-21) | not read; see `ext_15016_status` |

Sources: V10, `docs/AGATE_FULL_SCAN_2026-05-14.txt` and the 2026-03-13 alarm probe in [PICS Conformance Cross-Reference](PICS_CONFORMANCE_CROSS_REFERENCE.md#alarm-observability-2026-03-13-2330-aedt). V12, the 2026-10-20 re-scan behind the [V12 snapshot](SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md), with values listed in #136. Extension 15016: `firmware_quirks.json`.

## Modbus exceptions

| Request | V10 | V12 | Library |
|---|---|---|---|
| Read at PDU 40000+ (the SunSpec map's conventional base) | **exception 2** (2026-03-15) | served: the map is mirrored at 40000 (2026-10-20, [#84](https://github.com/david2069/franklinwh-modbus/issues/84)) | binds to whichever base answers (#84) |
| Read at PDU 50000 | — | exception 2 (2026-10-20) | — |
| M704 `WSetPct` above +100 raw (10.0 %) | accepted, e.g. raw 1500 (2026-05-14) | **exception 3** (2026-10-24, [#92](https://github.com/david2069/franklinwh-modbus/issues/92), [#104](https://github.com/david2069/franklinwh-modbus/issues/104)) | logged "Refused by the aGate", raised as `ModbusClientException("Rejected by the aGate (…)")`, not retried (#96, #114 A4) |
| M704 `WSetPct` negative (charge) | accepted (2026-03-13 probe, raw −1500) | **exception 3** for every negative value (2026-10-24, #104) | as above |
| M704 `WSet` negative (charge) | — | **exception 3** (2026-10-22, #104) | as above |
| Extension 15000–15043, 15500–15513, 16000–16002 reads | none | none; 15044–15099, 15514–15599, 16003–16099 also read without an exception (all 0) | — |

A refused write leaves the earlier setpoint in place. Every refusal is logged with the register, the raw values and the firmware.

## Silent discards (acknowledged, not applied)

These writes get a normal response, with no exception and no alarm. Only a read-back shows that nothing happened.

| Write | V10 | V12 | Library |
|---|---|---|---|
| M702 `WMax` | reads back 0 (2026-03-13) | WMax stays 0 (2026-10-22, #104) | not written in normal use |
| M715 `ControllerHb` | reads back 0 | reads back 0, and `DERHb` stays 0 (2026-10-23, #107) | — |
| M704 `WMaxLimPctEna` | reads back 0 (2026-03-13) | — | — |
| M704 `VarSetEna` | reads back 0 (2026-03-13) | — | — |
| M702 `WChaRteMax`, `WDisChaRteMax`, `VAChaRteMax`, `VADisChaRteMax` | 0xFFFF (not implemented); writes discarded (2026-03-13) | — | — |
| Extension 15507 mode, 15508/15509 reserves | — | normal FC06 echo; values unchanged after 30–90 s (2026-10-23, #107) | `set_native_mode()` etc. return the read-back result; a failed write is reported |
| M704 `WSetRvrtTms` reversion | countdown runs, power not reverted at expiry (2026-03-13) | inverted: the reversion value applies during the countdown and the setpoint after it (2026-10-22, #104) | software timer + `reset_control_state()` |

Sources: [SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md) deviation table (2026-03-13 tests), [PICS Conformance Cross-Reference](PICS_CONFORMANCE_CROSS_REFERENCE.md), `firmware_quirks.json` (`m702_wmax_write`, `m715_controller_heartbeat`, `ext_15507_15509_writes`, `m704_wsetrvrttms_reversion`).

## Not reported (reads 0 instead of "not implemented")

Model 714 `DCA` and the whole port 1 block read plain 0 on V12. The PICS declares them supported. From the next release the library reports these as `None` ([#129](https://github.com/david2069/franklinwh-modbus/issues/129), [#130](https://github.com/david2069/franklinwh-modbus/issues/130)). See [SunSpec Quirks, Model 714](FRANKLINWH_SUNSPEC_QUIRKS.md#model-714-battery-dc-measurements).

## Open

- No alarm has been observed in a fault state. Reading the alarm points during a real event (grid outage, over-temperature, battery fault) would show whether any of them is wired up. Record the date, firmware and every point above.
- The V10 rows from 2026-03-13 have no raw capture on record except where a scan is cited.
