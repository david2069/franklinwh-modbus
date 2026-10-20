# Safety Controls & Development Rules

> **Purpose**: Protect system integrity and prevent catastrophic failures during development.
> **Project**: FranklinWH Modbus Battery Manager (`~/dev/modbus/`)
> **Inherited from**: fhp_demo controls, adapted for local Modbus project
> **Created**: 2026-02-18

---

## 🚨 CRITICAL RULE #1: Never Touch System Python

### ABSOLUTE PROHIBITION
**NEVER install packages to the system Python installation under ANY circumstances.**

#### ❌ FORBIDDEN Commands
```bash
pip install <package>
pip3 install <package>
sudo pip install <package>
```

#### ✅ REQUIRED Commands
```bash
python3 -m venv venv
source venv/bin/activate
pip install <package>
```

#### Exception: Docker containers and CI/CD pipelines only.

---

## 🔒 CRITICAL RULE #2: Backup Before Structural Changes

### Scope
Files >1000 lines or >50KB:
- `src/web_server.py` (107KB)
- `templates/dashboard.html` (141KB)
- `src/modbus_client.py` (59KB)
- `src/modbus_sunspec2_reader.py` (49KB)
- `src/mqtt_handler.py` (39KB)

### Protocol
1. **Create Timestamped Backup**: `cp <file> <file>.bak_$(date +%Y%m%d_%H%M%S)`
2. **Verify Backup**: `ls -lh <file>.bak*`
3. **Document Change**: Add comment with timestamp
4. **Get User Approval**: `SafeToAutoRun: false` for structural changes

---

## 🔄 CRITICAL RULE #3: Restart After Backend Changes

### When Required
After modifying any file in `src/` or `templates/`.

### Restart Command
```bash
# Kill THIS project only (port 8080):
lsof -ti:8080 | xargs kill 2>/dev/null; sleep 2; cd ~/dev/modbus && ./run.sh -q &

# NEVER use generic: pkill python  (kills fhp_demo on port 5000!)
```

### Verification
1. Server starts without errors
2. `tail -20 data/logs/franklinwh.log` — no errors
3. Browser at `http://localhost:8080` loads

---

## 📋 CRITICAL RULE #4: Version Control Discipline

### No Changes Without Git
**ALL file modifications MUST be in a git-tracked repository.**

Before editing:
```bash
git status  # Ensure repo is clean or changes are understood
```

After each working feature:
```bash
git add -A && git commit -m "feat: description"
```

### Pre-Commit Checklist
- [ ] Code runs without errors
- [ ] No console errors in browser
- [ ] No secrets in diff (`git diff | grep -i "password\|key\|secret"`)

---

## 🧪 RULE #5: Testing Protocol (3-Check Verification)

### Before declaring ANY task complete:

#### ✅ Check 1: Application Logs
```bash
tail -100 data/logs/franklinwh.log | grep -iE "error|exception|traceback"
# Must return EMPTY
```

#### ✅ Check 2: Browser Console
- Open `http://localhost:8080` → F12 → Console
- Must show **zero** JavaScript errors
- Check Network tab for failed requests

#### ✅ Check 3: Functional Testing
- **Actually use** the feature (click buttons, navigate)
- Test edge cases (empty data, missing connection)

### UNACCEPTABLE: "Implementation complete, should work now."
### REQUIRED: "Verified working — logs clean, console clean, feature tested."

---

## 🛡️ CRITICAL RULE #6: Project Boundary Enforcement

### This Project ONLY
**Path**: `~/dev/modbus/`
**Port**: `8080`

### Out of Bounds
| Path | What | Why |
|------|------|-----|
| `~/dev/ha/docker/fhp_demo/` | Cloud API dashboard | Separate project |
| `~/franklinwh-clean/` | Library PR repo | Separate repo |

### Before ANY File Write
1. Verify path starts with `~/dev/modbus/`
2. If not → **STOP**: "⚠️ Path is outside modbus project. Aborting."

### Before ANY Process Kill
- Use port-specific: `lsof -ti:8080 | xargs kill`
- **NEVER**: `pkill python`, `pkill -f app`, or any generic pattern

### Lesson Learned (2026-02-18)
Agent accidentally modified 3 files in fhp_demo while working on modbus. Required git rollback.

---

## 🤖 RULE #7: Agent Authorization (SafeToAutoRun)

#### ✅ SafeToAutoRun: true
- Viewing files, listing directories, grep, git status
- Reading logs, checking process status

#### ⚠️ SafeToAutoRun: false
- Installing packages
- Modifying/deleting files
- Killing processes, restarting services
- Git commits and pushes
- Writing to Modbus registers

---

## 📋 RULE #8: Execution Discipline & In-Flight Work Protection

### 8.1 Plan Lock-In
Once approved, the plan is the **governing document**:
1. Follow the plan **in order** — no skipping, no reordering
2. If deviation needed → STOP → document in `in_flight_work.md` → notify user
3. Human requests that conflict with plan → flag: "This diverges from step N. Proceed?"

### 8.2 Zero-Error Gate
No item marked complete unless:
1. Application logs: zero errors from this change
2. Browser console: zero JS errors on affected pages
3. Functional test: feature tested and working

### 8.3 In-Flight Work Tracking
`in_flight_work.md` is the **single source of truth**. Update after **each** completed item.

### 8.4 Crash-Resilient Evidence
All test evidence persisted to disk immediately:
- Browser recordings saved as artifacts
- Log excerpts saved to `in_flight_work.md`
- Never rely on agent session memory

### 8.5 Session Handoff
**Start of session**: Read `in_flight_work.md` FIRST, resume where previous agent left off.
**End of session**: Update `in_flight_work.md`, ensure evidence is persisted.

---

## 🔌 RULE #9: Library Boundaries

### `franklinwh_control_standalone.py` is the battery control library
- All direct Modbus battery control goes through this library
- `src/web_server.py` is the **integration layer** — orchestrates, doesn't reimplement
- If the library has a bug → fix the library, don't bypass it in web_server

### `src/modbus_client.py` is the Modbus communication layer
- All raw register reads/writes go through this module
- Never bypass it with direct pymodbus calls from web_server

---

## 📊 RULE #10: Monitoring & Error Tracking

### See also: `AGENT_ERROR_TRACKING.md`

### After every change:
```bash
tail -100 data/logs/franklinwh.log | grep -c "ERROR"
# Must be 0 (or same count as documented pre-existing errors)
```

### Session sign-off checklist (from AGENT_ERROR_TRACKING.md):
- [ ] Checked logs for errors
- [ ] Error count documented
- [ ] Server running cleanly
- [ ] `in_flight_work.md` updated

---

## 🔄 Review Schedule

- After major incidents
- Before onboarding new agents
- Quarterly (minimum)

**Created**: 2026-02-18
**Next Review**: 2026-05-18

---

## ⚡ OPERATIONAL SAFETY: Conflict Detection

### Purpose
Prevent the script from fighting with aGate Cloud API or native operating modes.

### How It Works

The script detects conflicts in two ways:

1. **Modbus Control Detection** (`WSetEna=1`)
   - Another controller (previous script run, VPP aggregator) is active
   - We can take over with `--reset-on-start`

2. **Cloud API Detection** (`WSetEna=0` but battery active)
   - aGate is controlling via FranklinWH Cloud/APP
   - Battery DC power > 500W (charging or discharging)
   - Script exits to prevent conflicts

### Conflict Messages

```
🚨 CONFLICTS DETECTED - aGate is actively controlling:
   • aGate Self-Consumption actively CHARGING at 5000W

⚠️  Use --reset-on-start to force takeover
⚠️  Or change aGate mode in vendor app first
⚠️  Exiting to avoid fighting with aGate control!
```

### Resolution Options

| Situation | Resolution |
|-----------|------------|
| Testing/debugging | Use `--reset-on-start` to force takeover |
| Production use | Change aGate mode in vendor app first, then run script |
| VPP/active contract | Do NOT use `--reset-on-start` - may violate contract |

### Target SoC Validation

Script exits with error if target already reached:

```
❌ CONFIGURATION ERROR: Target SoC 40.0% already reached (current: 48.0%)

Options:
  1. Lower --target-soc below current SoC
  2. Wait for battery to discharge naturally
  3. Use discharge mode to reduce SoC first
```

This prevents unnecessary grid charging when battery is already above target.

---

## 🔋 BATTERY SAFETY: Alarm Monitoring

### Monitored Alarms

| Source | Register | Critical Alarms |
|--------|----------|-----------------|
| System (M701) | 40076 | Ground fault, over temp, grid disconnect |
| DC Port (M714) | 41044 | Over voltage, under voltage, contactor fault |
| Battery (M713) | 41039 | FAULT status |
| Solar (M502) | 41104 | Input over voltage |

### Blocking Behavior

If critical alarms detected:
- Script prevents operation
- Logs alarm details
- Suggests using `--clear-alarms` after resolving faults

### Clearing Alarms

```bash
# After resolving fault conditions
python3 franklinwh_cli.py -i 192.0.2.110 --clear-alarms
```

---

## 🌐 CONNECTION SAFETY: Auto-Reconnection

### Behavior

When connection drops ("Broken pipe", timeout):
1. Log warning with attempt count
2. Disconnect and reconnect
3. Rescan SunSpec models
4. Resume operation

### Failure Limits

After 5 consecutive failures:
```
ERROR - Too many consecutive failures, stopping
```

Script exits cleanly to prevent endless retry loops.

### Graceful Shutdown

On Ctrl+C (SIGINT):
1. Attempt to reconnect if connection lost
2. Reset control state (WSetEna=0)
3. Log result
4. Exit cleanly

---

*Last Updated: February 22, 2026*
