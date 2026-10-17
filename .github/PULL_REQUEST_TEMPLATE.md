## What changed

Brief description of the change and why it's needed.

Refs #  <!-- use "Refs", never "Fixes"/"Closes": the issue closes after the PyPI release is verified -->

## Severity and nature

- Severity: <!-- sev:S1-blocker / S2-high / S3-medium / S4-low -->
- Nature: <!-- code / device / doc / test-gap / design-risk -->
- Regression risk: <!-- low / medium / high — touches X, which could affect Y -->

## Evidence

<!-- Cite the source for every claim: vendor doc (revision, date), SunSpec model, a live read (time, firmware, request), or the code. Mark what is unverified. Quote output inline; do not cite tests/results/ or other local-only files. -->

## Mutation check

- [ ] I disabled the change and these tests failed: <!-- list them -->

## Gates (see `.agents/policies/release_policy.md`)

- [ ] **G0** — full suite passes, syntax check on changed files
- [ ] **G1** — Gateway Emulator run (or: not run — emulator not deployed)
- [ ] **G2** — real aGate, owner-coordinated (required for device writes, dispatch or safety changes): firmware ___
- Not run, and why:

## Checklist

- [ ] `CHANGELOG.md` updated under `[Unreleased]` (Upgrade notes for behaviour changes)
- [ ] Docstrings updated for changed public methods
- [ ] No site data in tracked files: no LAN IPs, serials, MACs or home paths (use `<AGATE_IP>`, 192.0.2.x, `~`)
