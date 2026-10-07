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
