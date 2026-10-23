# Model 704 Conformance Results — Firmware V12R02B60D00

Tests of SunSpec Model 704 (DER AC Controls) active-power control on an aGate
running V12R02B60D00, recorded on 2026-10-22.

- **Test files:** `examples/sequencer/v12_conformance/` (c0–c6, plus `v12c_restore.json`).
- **Runs:** each test ran 3 times — rounds 1 and 3 at base address 0, round 2 at base 40000. All three rounds agreed.
- **Evidence:** every result below is decoded from the raw Modbus frames
  (pysunspec2 `trace_func`), not from the library's own read-back.
- **Reference:** SunSpec DER Information Model Specification v1.2, §3.3.

## Summary

| # | What was tested | Result (3 of 3 runs) |
|---|---|---|
| c1 | Spec order: set `WSetPct`, then `WSetEna=1`; change value while enabled | ✅ Matches §3.3. 10 % → `714.DCW` 500 W; change while enabled applies without rewriting the enable; 0 % holds 0 W |
| c2 | `702.WMax` as the percentage reference | ⚠️ Writes acknowledged but ignored (`WMax` stays 0). 10 % stays 500 W, so the reference is 5000 W |
| c3 | Watts path: `WSetMod=1`, `WSet` 500 → 1000 W | ✅ Works. 1000 W is above the 10 % `WSetPct` cap |
| c8 | Full-rate watts path: `WSetMod=1`, `WSet=5000`, `WSetEna=1` (2026-10-23) | ✅ `714.DCW` 4900–5000 W, `701.W` about −4710 W, within 5–10 s; after cleanup back to about 200 W (house load) |
| c4, c4b | Reversion (`WSetRvrtTms`, `WSetPctRvrt`) | ❌ Behaves opposite to the spec (see below) |
| c5 | **Charge by percentage:** `WSetPct = −5 %` | ❌ Rejected, Modbus exception 3 |
| c6 | **Charge by watts:** `WSetMod=1`, `WSet = −500 W` | ❌ Rejected, Modbus exception 3 |

## Charging: what "both routes" means

Model 704 offers two ways to set active power, and a negative value means
charge in both:

1. **Percentage route** — `WSetMod=0`, `WSetPct` (int16, scale −1). Tested with −5 %.
2. **Watts route** — `WSetMod=1`, `WSet` (int32, scale 0). Tested with −500 W.

The positive (discharge) value worked on both routes. The negative (charge)
value was refused on both:

| Test | Frame sent | Encoding check | Response |
|---|---|---|---|
| c5 | FC06 `WSetPct` = `0xFFCE` | −50 raw = −5.0 % at scale −1; int16 is 1 register ✔ | exception 3 (×3) |
| c6 | FC16 `WSet` = `0xFFFF FE0C` | −500 as int32, 2 registers ✔ | exception 3 (×3) |

Exception 3 is *Illegal Data Value*: the aGate refused the value at write
time. It is not a battery limit, because state of charge was 88–90 %
during these tests, leaving room to charge.

### Limits of this result

These results show that the aGate refused these two writes. They do **not** prove
that V12 cannot charge through Model 704. The following were not tested:

- Only one magnitude per route (−5 %, −500 W).
- Both negative writes were made while `WSetEna=0`. A negative write while
  enabled was not tried.
- Other charge paths outside Model 704 were not tested here.

## Reversion (c4, c4b)

What the spec says: when the reversion timer (`WSetRvrtTms`) expires, the
controller reverts to the reversion values (`WSetPctRvrt` and the others).

What V12 does, 3 of 3 runs:

- The countdown starts when `WSetRvrtTms` is **written**, not when the enable is set.
- **During** the countdown the reversion value applies (0 W with
  `WSetPctRvrt=0`, about 250 W with `WSetPctRvrt=5`).
- **After** expiry the setpoint applies (10 % → 500 W). `WSetEna` stays 1.

That is the reverse of the spec. Don't rely on reversion as a fail-safe on V12.

## Full-rate discharge (c8)

Run 2026-10-23, 3 rounds, raw frames: `FC16 @320 n=2` = `0x0000 1388` (5000 W).
Every write was acknowledged. `714.DCW` reached 4900–5000 W within 5–10 s of
`WSetEna=1` and held for the 30 s window. After cleanup (`WSetEna=0`, `WSet=0`,
`WSetMod=0`) it returned to about 200 W within 6 s.

The same request through the percentage route (`WSetPct` raw 1000 = 100 %)
is refused with exception 3. A bridge log from 2026-10-23 recorded 116
such refusals in one hour. So on V12, **watts requests must use `WSet`**.

## Measurement notes

- `714.DCW` reports in 100 W steps, and the house load was about 200–300 W. So
  the 5 % step (about 250 W) couldn't be told apart from load and is recorded
  as inconclusive.
- Base address 0 and 40000 produced identical reads. The controller currently
  ignores the configured base (#103), so this does not yet show that both bases work.

## Effect on the library

`FranklinWHController.send_command` departs from §3.3:

- It cycles `WSetEna` 0 → 1 around each change, which the spec says is not required.
- It scales `WSetPct` from the battery rate, not from `WMax`/`WMaxRtg`.

Changing it needs the owner's sign-off (it affects hardware) and is tracked separately.
