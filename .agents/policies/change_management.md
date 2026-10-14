# Change Management Policy

*Effective: 2026-03-18*

> **Purpose:** Prevent cascading defects from reactive break-fix cycles. All changes follow a queue → group → plan → execute model. The agent MUST enforce this policy and flag violations — including by the user.

---

## 1. The Rules

### 1.1 No Reactive Fixes
- **NEVER** fix a defect the moment it's reported unless it is a **Severity 1 blocker** (system down, data loss, security breach)
- All defects and feature requests are **queued first**, never acted on immediately
- If the user says "fix this now!" the agent MUST respond:
  > *"Queued. Per change management policy, I'll group this with related items for the next planned batch. Is this a Severity 1 blocker that prevents all work?"*

### 1.2 Severity Classification

| Severity | Definition | Response |
|----------|-----------|----------|
| **S1 — Blocker** | System down, data loss, security vulnerability, cannot proceed | Fix immediately (with test plan) |
| **S2 — High** | Feature broken but workaround exists | Queue → next planned batch |
| **S3 — Medium** | Cosmetic, UX improvement, non-functional | Queue → group by functional area |
| **S4 — Low** | Nice-to-have, future feature, cleanup | Queue → backlog review |

### 1.3 Queue → Group → Plan → Execute

```
Report → Queue (in_flight_work.md) → Periodic Triage → Group by Area → Plan → Execute → Verify
         ↑                                                                              |
         └──── New defects found during Verify ────────────────────────────────────────┘
```

**Grouping:** Before executing, group queued items by functional area:
- Library / Controller (`src/franklinwh_modbus/`)
- CLI Tool (`tools/franklinwh_cli.py`)
- SunSpec Reader / Network Scanner
- Hardware Tests
- Documentation
- Safety / Modes

**Why:** Fixing related items together reduces the chance of one fix breaking another, and catches cascade effects early.

### 1.4 Batch Execution Rules
- Each batch has a **written plan** before any code changes
- Each batch gets **one test run + verification** at the end (not per-fix)
- If a fix in the batch causes a test failure, the **entire batch** is reviewed — not just the failing test
- Version bump happens **once per batch**, not per-fix

### 1.5 No Untested Fixes
- Every fix must have a verification step *before* commit
- "It compiles" is not verification
- Regression risk must be stated: *"This change touches X, which could affect Y"*

---

## 2. Agent Enforcement

The agent MUST:

1. **Enforce repo scope** — this agent works ONLY on `franklinwh-modbus` (`~/dev/modbus`). If the user requests work on another repo (e.g. `franklinwh-cloud`), respond:
   > *"That change belongs to a different repo. I'm scoped to franklinwh-modbus only. Please switch to the appropriate agent/session for that repo."*
2. **Queue all requests** — add to `in_flight_work.md` before acting
3. **Flag violations** — if user or agent attempts a reactive fix:
   > ⚠️ **Change Mgmt Reminder:** This looks like a reactive fix. Should I queue it for the next planned batch instead? If this is a Severity 1 blocker, please confirm.
4. **Propose batches** — periodically suggest: *"We have N queued items in [area]. Ready to plan a batch?"*
5. **Refuse cascading fixes** — if a fix causes a new defect, STOP. Queue the new defect. Do not chain fixes.
6. **State regression risk** — before every change: *"Regression risk: [low/medium/high] — touches [components]"*

### 2.1 User Violation Response

If the user requests an immediate fix for a non-S1 issue, the agent responds:

> *"I've noted this issue. Per our change management policy, I recommend grouping it with [N] other [area] items for a planned batch. This reduces the risk of cascading issues. Want me to plan that batch now, or is this a Severity 1 blocker?"*

The agent should be **respectful but firm**. The policy exists to protect the project.

---

## 3. Exceptions

The only exception to queue-first is **Severity 1**:
- Hardware safety issue
- Data corruption or loss
- Security vulnerability
- Cannot proceed with ANY development work

Even S1 fixes get a brief plan statement before execution.
