# Test and Proof Plan: M704 `WSetPct` Limit on V12R02B60D00

**Status:** phases 0.5–3 complete, 2026-10-21; phase 4 open. Owner sign-off is needed before any step that writes to the aGate.
**Issue:** [#92](https://github.com/david2069/franklinwh-modbus/issues/92)
**Tool:** [`tools/m704_setpoint_probe.py`](https://github.com/david2069/franklinwh-modbus/blob/develop/tools/m704_setpoint_probe.py)

## 1. The question

After the aGate's firmware moved from V10R01B04D00 to V12R02B60D00, Modbus battery commands above about 500 W stopped taking effect. This plan sets out what we need to show before we say anything firm about it, to ourselves or to FranklinWH:

1. Which raw `WSetPct` values does V12 accept, and which does it refuse? With which Modbus reply?
2. Is the boundary the same on the charge side as on the discharge side?
3. Does it survive a reboot of the aGate X?
4. How does it compare with what V10 did, with the SunSpec specification and with FranklinWH's PICS?

## 2. What we have so far

Each item is graded by its evidence: **Measured** (read directly by us from the device), **Reported** (a bridge log or UI message we haven't seen the raw data for), or **Documented** (from our older docs; the underlying record has not been re-examined).

| # | Finding | Grade | Source |
|---|---|---|---|
| E1 | `WSetPct_SF` = −1 on V10R01B04D00 and on V12R02B60D00 | Measured | 2026-05-14 V10 scan (`docs/AGATE_FULL_SCAN_2026-05-14.txt`); 2026-10-20 V12 re-scan |
| E2 | V12: raw +100 latched (`WSetEna` 1, `WSetPct` 100) and delivered +500 W `DCW` within about 8 s; released cleanly | Measured, once | Read-only poll, 2026-10-21 04:50:01–04:51:05Z |
| E3 | V12: raw +110 and +200 did not take effect (`WSetEna` stayed 0, `WSetPct` stayed 0) | Measured, once each | Same poll, 04:53–04:54Z and 04:56–04:57Z |
| E4 | V12: raw +10 latched; battery power did not change | Measured, once | Same poll, 04:26:14Z; read-back 04:27:18Z |
| E5 | V12: raw +500 refused with Modbus exception 3 | Reported | Bridge UI message, 2026-10-21 15:27:18 AEDT; also reported earlier that morning |
| E6 | V12: whether +110 and +200 got exception 3 or were never sent | **Unknown** | Bridge audit log requested |
| E7 | V10: a 5000 W discharge (raw 1000) delivered about 4.8 kW, 2026-10-20 18:00–19:03 AEDT | Reported, plus measured power history; firmware confirmed by E8 | Bridge activity log; the bridge's 24 h power history shows about +4.9 kW battery and −4.7 kW grid |
| E8 | The firmware changed to V12R02B60D00 at 21:11 AEDT on 2026-10-20, after E7 | Measured | Direct Connect bridge log: aGate unreachable 10:10:59Z, then "firmware changed: V12R02B30D06_260304 → V12R02B60D00_260924" at 10:11:39Z (local-API version strings); matches the GridDisconnect event at 21:07:32 AEDT. E7 ran 07:00:59–08:04:00Z |
| E9 | V10 accepted `WSetPct` = 1500 without exception 3 | Documented | `docs/NON_COMPLIANCE_ASSESSMENT.md` (2026-05-14) |
| E10 | Raw −500 latched for 216 s (firmware not recorded) | Documented | `docs/PICS_CONFORMANCE_CROSS_REFERENCE.md`, test of 2026-03-13 |

### Phase 1 results (2026-10-21 06:34–06:45Z, two passes, measured)

| Raw | Result, both passes | `DCW` |
|---|---|---|
| +10, +50, +100 | accepted, latched | 0, +200, +500 W |
| +101, +110, +200, +500, +1000 | exception 3 at the `WSetPct` write | — |
| −10, −100, −101, −110, −500 | exception 3 at the `WSetPct` write | — |

V12R02B60D00 accepts `WSetPct` only in raw 0…+100: discharge up to 10 %, no charge. This matches the PICS range read as raw values. On V10R01B04D00, `WSetPct` ±1500 was accepted (2026-03-13). Writing M702 `WMax`, `VAMax`, `WChaRteMax` or `WDisChaRteMax` didn't change the result.

### Phases 2–3 results (2026-10-21, measured)

**Phase 2:** the owner rebooted the aGate X at 17:59:18 AEDT (06:59:18Z). A read-only re-scan afterwards showed the same firmware (`Vr` V12R02B60D00), the same 17-model map, the 40000 mirror, `WSetPct_SF` −1 and `WSetEna` 0.

**Phase 3** (07:07:40–07:19:08Z, two passes, same command as phase 1):

| Raw | Phase 1 (×2) | Phase 3, after reboot (×2) | `DCW` median |
|---|---|---|---|
| +10, +50, +100 | accepted, latched | accepted, latched | 0, +200, +500 W |
| +101, +110, +200, +500, +1000 | exception 3 | exception 3 | — |
| −10, −100, −101, −110, −500 | exception 3 | exception 3 | — |

Every step ended released. The final state was `WSetEna` 0, `WSetPct` 0, `DCW` 0, SoC 99.0 %, with no read errors. Phase 3 matches phase 1 in all 26 steps, so H1–H4 hold on this unit: the limit survives a reboot.

**Still not shown:** the `WSet` (watts) path (phase 4).

## 3. Standards and declarations we will measure against

| Source | What it says |
|---|---|
| SunSpec Information Model Specification #12041, v1.9, *Error Handling: Invalid Setting Value* | "When a setting is written with an unsupported value for the implementation … An exception "3" Illegal Data Value must be returned and processing of the write operation must terminate. … Such limitations must be documented in the PICS." |
| #12041, *Data point implementation* | "Implementations that implement a setting must indicate the supported setting values … or valid range (scalar) and default value in the PICS document." |
| SunSpec DER Information Model Specification v1.2, Model 704 | `WSetMod`: `W_MAX_PCT` (0) = Active Power as Max Percent; `WATTS` (1). `WSetPct`: scale factor `WSetPct_SF`, units Pct, "Active power setting value as a percent." No numeric range: the PICS supplies it. |
| FranklinWH PICS SM-000028, sheet 704 | `WSetPct` (PDU 324): supported, RW, Min 0, Max 100. `WSetPct_SF` (352): −1. `WSet` (320): RW, Min 0, Max 10000 |

**Open interpretation:** none of the SunSpec documents we have read says whether a PICS Min/Max is in raw register units or in scaled engineering units. If 0–100 means percent, raw 1000 is declared supported. If it means raw, 10 % is the declared maximum. The plan records this; it doesn't assume an answer.

## 4. Hypotheses

| | Hypothesis | Settled by |
|---|---|---|
| H1 | V12 refuses `WSetPct` writes above raw +100 with exception 3 | Phase 1, discharge values around and above 100 |
| H2 | The same limit applies to negative (charge) values | Phase 1, charge values |
| H3 | The boundary is exactly raw 100 (101 is refused) | Phase 1, raw 101 and −101 |
| H4 | The limit is persistent firmware behaviour, not a transient state | Phase 3 (after reboot) matches Phase 1 |
| H5 | The watts path (`WSetMod` = 1, `WSet` in W) is not limited the same way | Phase 4, optional |

## 5. Preconditions

- **Owner present** for every write phase (gate G2). Times outside 17:30–20:00 local.
- **No other writer.** All bridge schedules and automations that command the battery are disabled. The bridge may keep polling.
- **No command active:** `WSetEna` = 0 before starting. The probe refuses to start otherwise.
- **Scale factor −1.** The probe refuses to start otherwise.
- **SoC.** Discharge steps are skipped below 20 %. At high SoC a charge command can be accepted without being delivered, so charge results show acceptance, not delivered power, unless SoC is below about 90 %.
- **App mode** is noted before and after: it affects how the aGate treats a released battery.

## 6. Procedure

| Phase | What | Who | Writes? |
|---|---|---|---|
| 0 | Bridge exports its command audit trail (every M704 write with register, raw value, reply, initiator), its firmware history and its connection events, 2026-10-14 to now | Bridge session; the owner hands over the file | No |
| 0.5 | G1 check against the Gateway Emulator, with its `v12-candidate` profile: the same probe command, once with the `wsetpct_max_abs_raw` quirk off and once with it set to 100. This confirms the probe handles both acceptance and exception 3, and always releases, before it touches the aGate | Library session, against an emulator instance | No (emulator only) |
| 1 | Baseline on V12: `m704_setpoint_probe.py probe --values 10,50,100,101,110,200,500,1000,-10,-100,-101,-110,-500 --repeat 2 --hold 30 --gap 15 --execute` (about 20 minutes) | Library session runs it; owner watches | **Yes** |
| 2 | Owner reboots the aGate X. Then a read-only re-scan: firmware string, model map, scale factors | Owner, then the library session | No |
| 3 | Phase 1 repeated exactly | As phase 1 | **Yes** |
| 4 | Optional: one `WSetMod` = 1, `WSet` = 1000 W write, held 30 s, then released | Owner decides | **Yes** |

Each write phase starts and ends with `observe` for 2 minutes, so the before and after states are on record.

## 7. What is collected, and why

Collected every `--interval` seconds (default 1 s) during holds and gaps, and around every write:

| Data | Register (PDU) | Why |
|---|---|---|
| The write itself: register, value written, the aGate's reply (OK, exception code, or connection error), UTC time in ms | 318, 319, 324 | The core proof: what the device said to each write. This is missing for E3 and E5 today |
| `WSetEna` | 318 | Whether remote control is actually on. Latching is the test of acceptance |
| `WSetMod` | 319 | Confirms percent mode (0) |
| `WSet` | 320–321 | Confirms the watts setpoint is untouched in percent mode |
| `WSetPct` (raw, signed) | 324 | Read-back: did the value written stick? |
| `WSetEnaRvrt`, `WSetRvrtTms`, `WSetRvrtRem` | 326–330 | Any timer state that could end a command early |
| `WSetPct_SF` | 352 | The scale factor every conclusion depends on; checked at the start |
| M714 `DCW` | 1048 | Delivered battery power: the difference between accepted and actually done |
| M713 SoC (raw) | 1037 | The SoC guard, and a reason a command might not be delivered |
| M1 `Vr` | 44–51 | The firmware every result belongs to |

**Derived for each step:** accepted (every write OK), latched (read-back shows `WSetEna` 1 and the value written), the exception code if refused, and the median `DCW` over the second half of the hold.

**Caps:** each run stops at `--max-duration` (default 30 minutes) or `--max-bytes` (default 5 MB), whichever comes first, and records which cap ended it. Ctrl-C and any error trigger an immediate release.

**Not collected:** the aGate's IP address and serial number are never written to the output.

## 8. How results are read

| Phase 1 and 3 show… | Conclusion |
|---|---|
| +100 accepted and latched, +101 refused with exception 3, every time | H1 and H3 confirmed: the limit is raw 100 |
| −100 accepted, −101 refused with exception 3 | H2 confirmed: a symmetrical limit |
| Charge values accepted beyond −100 | H2 rejected: the limit is discharge-only |
| Phase 3 matches phase 1 | H4 confirmed: firmware behaviour, not a transient |
| Phase 3 differs | A transient state. Report what changed and when |
| A value refused without exception 3 (e.g. silently ignored) | A separate finding: the refusal doesn't follow #12041 |
| Results differ between the two repeats | Inconclusive for that value; repeat before claiming anything |

Each conclusion is stated as **measured, one site, firmware V12R02B60D00, date**. Anything beyond the data, such as *why* the device limits the value, is labelled speculation.

## 9. Where the data goes

| File | Content | Shared? |
|---|---|---|
| `tests/results/m704_probe_<UTC>.jsonl` | Every write, reply and sample | Local (gitignored). The owner decides on sharing |
| `tests/results/m704_observe_<UTC>.jsonl` | Before and after observation | Same |
| A summary table per phase | One row per step: raw, %, accepted, latched, exception, median `DCW` | Goes into this repo's docs and the evidence package (§10) |
| The bridge's audit export (phase 0) | The bridge's record of its writes | The owner decides |

## 10. Reporting to FranklinWH

Whether, when and through which channel to report is **the owner's decision**, and the owner sends it. The library and bridge sessions prepare the package; they don't contact FranklinWH.

**The package:**

1. **Summary**, one paragraph: on firmware V12R02B60D00, M704 `WSetPct` writes above raw N are refused with exception X. On V10R01B04D00, raw 1000 was accepted and delivered. Measured on one aGate X, dates.
2. **Device and firmware:** model, M1 `Vr` before and after, the update date as known to the owner, and the reboot in phase 2.
3. **Reproduction:** the exact write sequence (registers, values, order, timing) so FranklinWH can run it on their own unit, plus the probe command line.
4. **Results table** from phases 1 and 3, with the exception code for every refused write and the delivered power for every accepted one.
5. **The comparison:** the V10 evidence (E7, E9, with their grades as in §2) and the V12 results side by side.
6. **References:** the SunSpec text in §3 and the PICS SM-000028 `WSetPct` row, with the open interpretation stated plainly. The report asks FranklinWH to confirm the intended `WSetPct` range on V12.
7. **The questions,** stated neutrally:
   - Is the limit intended?
   - If it is, what is the supported range, and will the PICS be updated?
   - If it isn't, is a fix planned?
   - Is the `WSet` (watts) path supported as an alternative?

**Wording rules:**

- Measured facts only, with date, firmware and the number of trials. No "always", no "every unit".
- Inferences are labelled as such. No speculation about FranklinWH's code.
- Nothing from private correspondence, and no claims about any register not covered by the SunSpec models.
- Site data: the serial number only if FranklinWH asks for it, sent privately by the owner. Never the LAN IP or account details.
- Neutral tone: a defect report with evidence, not a complaint.
