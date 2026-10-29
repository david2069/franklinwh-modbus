# Firmware Quirks Record

`src/franklinwh_modbus/firmware_quirks.json` records how each aGate firmware (M1 `Vr`) behaves over Modbus, across firmware and library releases ([#91](https://github.com/david2069/franklinwh-modbus/issues/91)). It ships with the package. Nothing is fetched at runtime.

## Layout

- **Behaviours** are keyed by a stable id (for example `m704_wset_sign`). An id is never reused or renamed.
- Each behaviour has:
  - `point`: the register or point, with raw type and scale where they matter;
  - `description`;
  - `our_assessment`, with its `basis`;
  - `vendor_position`;
  - `library_handling`, keyed by repo. Each repo adds its own text by PR to this repo.
  - Behaviours that a read can tell apart also have `detectable_by_read`.
- Each behaviour lists **observations**, one per firmware. Each observation gives the value, `status`, `date`, `site_count` and full `refs`. A firmware change adds an observation; old ones stay.

## Rules

- **Status.** The status is one of `documented`, `measured`, `reported`, `inferred` or `speculation`. Code and emulator profiles act only on `documented` or `measured`.
- **Unknown firmware.** It is unknown, not "no quirks": `quirks_for()` returns `None`.
- **Public facts only.** Every observation cites a public issue (`david2069/<repo>#N`) or a doc in this repo. Nothing comes from `private/` or `tests/results/`, and no site identifiers are included.
- **Updates.** Changes come only by PR to this repo, after the measurement is on a public issue. A message relayed between sessions is not a source.
- **No writability claims.** FranklinWH has not documented any extension register as writable. The file records only what writes did.

## Use

```python
from franklinwh_modbus.firmware_quirks import quirks_for

q = quirks_for("V12R02B60D00", actionable_only=True)
q["m704_wset_sign"]["value"]        # 'positive = discharge'
quirks_for("V99R00B00D00")          # None: unknown firmware
```

The controller doesn't act on this file yet.
