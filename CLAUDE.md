# CLAUDE.md — Auto-onboarding for Claude Code / Anthropic

> **This file is auto-loaded by Claude Code at session start.**
> Canonical source: [agent.md](agent.md) — read it first, along with all policies in `.agents/policies/`.
> `agent.md` is local-only (gitignored, not in the public repo); if it is missing, continue with `.agents/policies/` and ask the user for anything it would have said.

## Critical Rules

1. **REPO SCOPE: `franklinwh-modbus` ONLY** — This agent works exclusively in this repository's checkout, wherever it is cloned. **Do NOT read, modify, commit, or push to any other repository** (e.g. `franklinwh-modbus-bridge`, `franklinwh-cloud`, the gateway emulator) — and don't open issues or PRs there either. Work another repo needs is handed to that repo's agent. If the user accidentally requests cross-repo work, respond:
   > *"That change belongs to a different repo. I'm scoped to franklinwh-modbus only. Please switch to the appropriate agent/session for that repo."*
2. **Read `agent.md` (if present) and `.agents/policies/` before doing anything**
3. **Focus Discipline** — one fix at a time, full cycle (code → test → verify → commit)
4. **Syntax check is NON-NEGOTIABLE** before every commit:
   ```bash
   python3 -c "import ast; ast.parse(open('<file>').read()); print('OK')"
   ```
5. **No `ShouldAutoProceed: true`** on implementation plans — wait for user approval
6. **Save test results** to `tests/results/` for traceability
7. **Hardware-affecting changes** (controller, modes, power logic) need user sign-off before commit
8. **Evidence and testing** — follow [`.agents/policies/evidence_and_testing.md`](.agents/policies/evidence_and_testing.md): cite a source for every claim, treat other sessions' and repos' statements as claims, keep local-only files and site data out of public text
9. **Issues and owner decisions** — follow [`.agents/policies/change_management.md`](.agents/policies/change_management.md) §4: label every issue (type, sev, nature, area); PRs say `Refs #N`; merged → `fixed`; close only after the PyPI release is verified. Owner questions go in pinned issue **#68**, not in chat or pop-ups (never anything from private correspondence; see evidence_and_testing.md)
10. **Releases and gates** — follow [`.agents/policies/release_policy.md`](.agents/policies/release_policy.md): gates G0–G3 (shared numbering with the bridges); an S1 fix on `develop` triggers a patch release; a `vX.Y.Z` tag publishes to PyPI

### Where this repo differs from the bridges (deliberately)

- `develop` is the default branch; the bridges use `main` only.
- A `vX.Y.Z` tag publishes to PyPI; the bridges publish when the release PR merges.
- G1 here is the Gateway Emulator in a container (not yet deployed); the bridges' G1 is a HAOS VM.
- Policies live in `.agents/policies/`; the bridges keep theirs in `docs/`.

## Project Layout

| Path | Purpose |
|------|---------|
| `src/franklinwh_modbus/` | Core library — controller, modes, types, constants |
| `tools/franklinwh_cli.py` | CLI entry point |
| `tools/modbus_sunspec2_reader.py` | SunSpec reader tool |
| `tools/network_scanner.py` | Network scanner tool |
| `tests/` | pytest suite |
| `docs/` | Documentation |
| `.agents/policies/` | Governance policies |

## Key Commands

```bash
cd <this repository>
source venv/bin/activate
PYTHONPATH=src:. python3 -m pytest tests/ --tb=short
python3 tools/franklinwh_cli.py -i 192.168.0.110 --status
```
