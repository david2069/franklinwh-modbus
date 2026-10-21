# V12 SunSpec Modbus TCP Conformance Re-test Plan

**Status:** draft, 2026-10-21. Nothing in this plan writes to the aGate without the owner's sign-off for that step.
**Firmware under test:** V12R02B60D00 (one site).
**Related:** [#92](https://github.com/david2069/franklinwh-modbus/issues/92) (the `WSetPct` limit), the V12 `WSetPct` test plan (`docs/V12_WSETPCT_TEST_PLAN.md`, in PR #93).

## 1. Why re-test

V12R02B60D00 refuses M704 `WSetPct` values that V10R01B04D00 accepted, with exception 3 (#92, measured in four passes). Our earlier compliance documents were written against V10, and some of their statements can't be traced to a SunSpec source (§7). So we are re-testing V12 from the start against SunSpec's own conformance procedure, rather than re-running our own checks.

**Scope:** SunSpec Modbus over TCP, the 700-series DER models (SunSpec 2) and Model 1, as declared in FranklinWH's PICS. FranklinWH's non-SunSpec extension registers are out of scope: SunSpec certification considers only standardised models.

## 2. The basis: SunSpec's own procedure

We follow the **SunSpec Modbus Conformance Test Procedures, v1.4 (Approved)** test by test. Its test IDs and labels are used unchanged (for example `MOD-1.704`), so our results can be compared with a certification lab's.

Supporting documents:

| Document | Used for |
|---|---|
| SunSpec Modbus Conformance Test Procedures v1.4 | The test cases and procedures (§3) |
| SunSpec Information Model Specification #12041 | Discovery, error handling, multi-write procedure |
| SunSpec DER Information Model Specification v1.2 | 700-series semantics: enable (§3.3), reversion timers (§3.2), `WSetMod` |
| SunSpec Modbus IEEE 1547-2018 Profile Specification v1.1 | Required points per model for the 1547 profile |
| FranklinWH PICS, certificate SM-000028 | What FranklinWH declares: models, points, R/RW, Min/Max (§4) |
| MODBUS Application Protocol V1.1b3; MODBUS Messaging on TCP/IP V1.0b | Function codes, exception codes, MBAP framing |

### Other people's work we cross-referenced

| Source | What it is | How we use it |
|---|---|---|
| [`sunspec/models`](https://github.com/sunspec/models) | SunSpec's normative model definitions (JSON) | Expected model lengths, mandatory points, access (R/RW), enum values, scale factor names |
| [`sunspec/pysunspec2`](https://github.com/sunspec/pysunspec2) | SunSpec's Python client, built from `sunspec/models` | An independent reader for DEV and MOD tests, so we don't grade the device with our own library |
| [`sunspec/svp`](https://github.com/sunspec/svp), [`sunspec/svp_energy_lab`](https://github.com/sunspec/svp_energy_lab) | SunSpec System Validation Platform and its device drivers (`der1547_sunspec.py`) | Reference for how SunSpec's tooling reads and writes 700-series points. The SVP Dashboard, which automates the conformance tests, is available only to SunSpec members; we have not used it |
| [`sandialabs/svp_1547.1`](https://github.com/sandialabs/svp_1547.1) | Sandia's open IEEE 1547.1 test scripts; `IOP.py` covers interoperability | Pattern for settings tests: read, write, read back, restore. Most of `IOP.py` needs a grid simulator and lab meters, which we don't have |

We found no public, open-source implementation of the SunSpec Modbus conformance tests themselves. If one turns up, it replaces our harness for the tests it covers.

## 3. Test catalogue for this device

**Risk classes:**
- **R:** read-only, or a protocol test that writes nothing.
- **W1:** writes that should not change operation (writing back the current value).
- **W2:** writes that change battery power. Always released afterwards.
- **W3:** writes to grid-protection, connect/disconnect or curve settings. Not run on a live home site unless the owner decides per item (§5).

| Test | What SunSpec checks | Applies here | Class | Already known |
|---|---|---|---|---|
| DEV-1 | Discovery: `SunS` at 0, 40000 or 50000; end model 65535 with length 0 | Yes | R | V12 re-scan 2026-10-20: 17 models, a mirror at 40000. To be repeated with pysunspec2 |
| DEV-2 | Model 1 present, matching the PICS | Yes | R | — |
| MOD-1.*n* | Model present; correct length; mandatory points implemented; points match the PICS; each point read singly and within its PICS range | 1, 701–715 | R | — |
| MOD-2.*n* | Model readable in one read (≤125 registers per read) | 1, 701–715 | R | — |
| MOD-3.*n* | Every adjustable point written at min, max and three intermediate values, individually and as a group; read back must match; every supported enum value written | 702, 703, 704, 705–712, 715 | W2 or W3 by point (§5) | 704 `WSetPct`: only raw 0…+100 accepted (#92) |
| CRV-1/2/3 | Curve 1 read-only; adopting curves; adopt error | 705, 706, 707–710, 712 | W3 | — |
| REV-1/2/3 | Reversion: remaining time within 2 s of expected during countdown; times out within 2 s; update and cancel | 704 (`WSet`, `WMaxLimPct`, `PFWInj`, `PFWAbs`, `VarSet` reversion groups); 705, 706, 711, 712 (`RvrtTms`) | W2 for 704 `WSet`; W3 otherwise | — |
| TCP-1 | All tests run over Modbus TCP | Yes | — | Applies to every test here |
| TCP-2 | A partial request is ignored; the next complete request is answered | Yes | R | — |
| TCP-3 | A request split across two TCP frames is answered | Yes | R | — |
| MB-1 | Two consecutive RW points written with FC16, then each with FC06 | Yes | W1 (write the current values back) | The library already writes M704 with FC06 |
| MB-2 | Single-register FC03 reads, three registers | Yes | R | — |
| EXC-1 | An invalid value per model (an out-of-range value, or an undefined enum) gets exception 2, 3 or 4, and isn't written | 702–712, 715 | W2 for 704; W3 otherwise | 704 `WSetPct`: exception 3 above raw 100, and on every negative value (#92) |
| EXC-2 | Writes to three or more read-only registers get exception 2, 3 or 4, and aren't written | Yes | W1/W2 by register (§5) | Writing 702 `WMax` (RW) changed 702 `WMaxRtg` (R) from 0 to 5000, and the change persisted through a reboot (measured 2026-10-21; #92 comments) |
| EXC-3 | An undefined function code (for example 50) sent to a RW register gets exception 1 | Yes | R | — |
| RTU-1…5 | Modbus RTU | **No:** the aGate is tested over TCP only | — | — |

## 4. What the PICS declares

From FranklinWH's PICS (SunSpec certificate SM-000028, issued 2023-05-01; the 1547 certificate is archived at sunspec.org):

| Model | RW points declared | Of which have a Min/Max |
|---|---|---|
| 701, 713, 714 | 0 | — |
| 702 | 19 (for example `WMax` 0–10000, `VAMax` 0–11000) | 2 |
| 703 | 8 (`ES` and the enter-service limits) | 7 |
| 704 | 40 (`WSet`/`WSetPct` groups, `WMaxLimPct`, PF, Var, ramps, `AntiIslEna`) | 6 |
| 705, 706, 711, 712 | 49, 18, 16, 34 (volt-var, volt-watt, freq-droop, watt-var) | curve 1 only |
| 707–710 | 68 each (voltage and frequency trip curves) | curve 1 only |
| 715 | 3 (`ControllerHb`, `AlarmReset`, `OpCtl`) | 0 |

**The PICS Min/Max are in engineering units, not raw register values.** Several rows have non-integer limits that a raw register could not hold: 704 `PFWInj.PF` 0.85–1, 703 `ESHzHi` 60.1–61, 708 `MustTrip.Pt.1.Tms` 0.16. Read the same way, 704 `WSetPct` Max 100 means 100 %, which is raw 1000 at `WSetPct_SF` −1.

That is an inference from the PICS's own content, not a statement in it. If it holds, V12 refuses `WSetPct` values that its PICS declares supported (#92). The PICS has no conformance notes recording a limit, which #12041 requires for such limitations.

**PICS gaps to record:** most RW points have no Min/Max. Some 712 rows have Min greater than Max (for example `Crv.1.Pt.1.W` −50 to −100). For points without a range, MOD-3 can only use the model's datatype range, and EXC-1 has no defined "invalid" value.

## 5. Safety and order of work

1. **G1 first.** Every write test runs against the Gateway Emulator before the aGate, as the `WSetPct` probe did.
2. **Read-only pass (class R) on the aGate.** DEV, MOD-1, MOD-2, MB-2, TCP-2, TCP-3, EXC-3. No other client polls the aGate during it.
3. **W1 and W2 on the aGate, owner present.** Limited to 704's `WSet` group and its reversion timer, plus MB-1 and EXC-2 on registers the owner approves. The same guards as the `WSetPct` probe: dry run by default, refuse if a command is already active, release on every exit path, stop after three failed reads.
4. **W3 is not run on a live home site by default.** These points set grid-protection trip curves, enter-service limits, anti-islanding and grid-support curves. A wrong value can disconnect the system or change how it behaves on the grid. For each W3 test the report says "not run (safety)", unless the owner decides otherwise for that item.
5. **Restore.** Every write test records the value before it starts and writes it back at the end. Any value that doesn't come back is reported, as `WMaxRtg` was.

## 6. Recording results

Each test instance gets one row: label (for example `MOD-3.704`), date and firmware, pass / fail / not run, the evidence (log file in `tests/results/`), and the grade (measured, reported, inferred). Where SunSpec documents disagree with each other (§7), the row says which document the result was judged against.

SunSpec publishes a *Results Reporting Specification v1.0* for certification labs. We haven't read it yet. If it is followed, our report can be laid out the same way.

## 7. Conflicts and errors found while preparing

**Between SunSpec documents:**
- **Writing a read-only register.** #12041 (Error Handling) says: "WRITE to R: The written value is ignored. No exception is generated." The Conformance Test Procedures v1.4 (EXC-2) require exception 2, 3 or 4. We report EXC-2 against v1.4, the procedure certification uses, and note the #12041 behaviour alongside.
- **Changing settings while enabled.** #12041 (Procedures for Multi-Write Operations) says changes "do NOT take effect, even if the activation field is already enabled, until the activation field is enabled." The DER Information Model v1.2 §3.3 says: "Rewriting the enable is not required for the changes to be applied." For 700-series models we use DER v1.2.
- **Version numbering.** The Conformance Test Procedures cover page says version 1.4, but its revision history ends at 1.3 (2025-10-15). We cite it as v1.4.

**In our own docs** (to be fixed separately, not relied on here):
- `docs/SUNSPEC_COMPLIANCE_BASIS.md` quotes "SunSpec 704, Section 3.1.1": "The DER must not react to changes in setpoint registers until the Enable register is transitioned from 0 to 1." We couldn't find this text in #12041 or DER v1.2, and DER v1.2 §3.3 says the opposite.
- The same doc gives `WSetPct_SF` = −2 in its worked example. The device reports −1 on V10 and on V12.

## 8. Open items

- The owner decides which W1/W2 registers may be used for MB-1 and EXC-2, and whether any W3 test is run.
- The harness: pysunspec2 for the read-only pass; a write harness built on the `WSetPct` probe's guards. It will be drafted after this plan is agreed.
- Whether to report results to FranklinWH is the owner's decision, as in the `WSetPct` plan §10.
