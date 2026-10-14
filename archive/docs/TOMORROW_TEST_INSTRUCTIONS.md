# Tomorrow's Throttling Test - Instructions for Next Agent

**Date:** 2026-02-25 (or next sunny day)  
**Goal:** Capture ThrotPct > 0% during solar charging  
**Status:** Ready to execute

---

## 🎯 Test Objective

**Prove that ThrotPct changes during charging.**

Previous test showed ThrotPct = 0% while battery was sleeping (discharging).  
This test will catch throttling as battery approaches full during solar charging.

**Expected behavior:**
```
SoC 70-85%  → ThrotPct = 0%  (full speed charging)
SoC 90-95%  → ThrotPct = 10-30%  (tapering begins)
SoC 95-99%  → ThrotPct = 50-90%  (heavy throttling)
```

---

## ⏰ When to Run

### Prerequisites (ALL must be true)

| Check | Requirement | How to Verify |
|-------|-------------|---------------|
| ☀️ | **Sunny day** - Solar PV generating | Check FranklinWH app for solar production |
| 🔋 | **SoC < 90%** at start | FranklinWH app or previous evening charge level |
| ⬆️ | **Battery charging** | FranklinWH app shows "Charging" status |
| 📶 | **WiFi stable** | Can ping 192.0.2.110 |

### Ideal Start Time

**Morning:** 9:00-11:00 AM
- Solar production ramping up
- Battery likely charging from morning sun
- Time to reach 90%+ SoC

**OR Afternoon:** 1:00-3:00 PM  
- Peak solar production
- Battery may already be high SoC from morning

---

## 🚀 How to Run the Test

### Step 1: Check Current Conditions

Ask user to check FranklinWH app:
```
Is it sunny? ______
Is battery charging? ______
What is current SoC? ______%
Is WiFi working? ______
```

### Step 2: Start the Logger

```bash
cd ~/dev/modbus
source venv/bin/activate
python log_throttling_with_heartbeat.py 192.0.2.110 2 120
```

**Parameters:**
- `192.0.2.110` = aGate IP
- `2` = Unit ID
- `120` = Duration: 2 hours (should be enough to see SoC rise)

### Step 3: Monitor Progress

**Console will show:**
```
Time     SoC    Power  Throt  HB  Temp   State
--------------------------------------------------
09:00:00 72.0%  4200W   0%   OK  28.5°C Running
09:00:30 73.5%  4200W   0%   OK  28.8°C Running
09:01:00 75.1%  4150W   0%   OK  29.0°C Running
...
09:30:00 91.2%  3500W  15%🔥  OK  32.0°C Running  ← THROTTLING!
09:30:30 92.0%  3200W  20%🔥  OK  32.2°C Running
```

**Watch for:**
- ✅ SoC increasing (charging)
- ✅ ThrotPct = 0% initially
- 🔥 ThrotPct > 0% when SoC hits 90%+

### Step 4: Stop When Done

**Stop conditions (any of these):**
1. SoC reaches 98%+ and ThrotPct stabilizes
2. 2 hours elapsed
3. Solar production drops (cloudy)
4. User says stop

**To stop:** Ctrl+C

Script will:
- Release control (disable WSetEna)
- Close connection
- Show summary

---

## 📊 Expected Output

### Console Output

Real-time display:
```
💾 Logging to: throttling_heartbeat_20260225_090000.csv
⏱️  Duration: 120 minutes
💓 Heartbeat: Every 10s (WSetPct=0)
📝 Sampling: Every 30s

Time     SoC    Power  Throt  HB  Temp   State
--------------------------------------------------
09:00:00 72.0%  4200W   0%   OK  28.5°C Running
09:00:30 73.5%  4200W   0%   OK  28.8°C Running
...
09:30:00 91.2%  3500W  15%🔥  OK  32.0°C Running
09:30:30 92.0%  3200W  20%🔥  OK  32.2°C Running
09:31:00 93.1%  2800W  30%🔥  OK  32.5°C Running
...
```

### CSV Output

File: `throttling_heartbeat_YYYYMMDD_HHMMSS.csv`

```csv
Timestamp,UnixTime,ThrotPct,SoC_%,Power_W,TmpCab_C,InvState,Heartbeat_OK
2026-02-25T09:00:00,1772000000,0,72.0,4200,28.5,Running,True
2026-02-25T09:00:30,1772000030,0,73.5,4200,28.8,Running,True
...
2026-02-25T09:30:00,1772001800,15,91.2,3500,32.0,Running,True
```

---

## ✅ Success Criteria

### Minimum Success
- ✅ SoC increased from start to 90%+
- ✅ ThrotPct remained readable (no errors)
- ✅ CSV file created with data

### Full Success
- ✅ ThrotPct started at 0% (SoC < 90%)
- ✅ ThrotPct rose to > 10% (SoC > 90%)
- ✅ ThrotPct correlated with SoC (higher SoC = higher ThrotPct)

### Failure Modes

| Scenario | Cause | Action |
|----------|-------|--------|
| ThrotPct always 0% | SoC never reached 90% | Try again tomorrow with longer duration |
| ThrotPct always 0% | FranklinWH doesn't throttle | Check if different behavior with generator |
| Connection errors | WiFi issues | Check ping to 192.0.2.110 |
| "HB = ERR" | WSetPct write failing | Check if LocRemCtl changed |

---

## 🛠️ Troubleshooting

### If WSetPct Heartbeat Fails

**Symptom:** HB column shows "ERR"

**Check:**
```bash
# Test if WSetPct still works
python -c "
from pymodbus.client import ModbusTcpClient
c = ModbusTcpClient('192.0.2.110', port=502)
c.connect()
# Read LocRemCtl first
result = c.read_holding_registers(41089-40001, 1, device_id=2)
print(f'LocRemCtl: {result.registers[0]}')
c.close()
"
```

- LocRemCtl = 0: Local mode (WSetPct may not work)
- LocRemCtl = 1: Remote mode (should work)

**Fallback:** If heartbeat fails, use simple logger instead:
```bash
python log_throttling_simple.py 192.0.2.110 2 120 30
```

### If SoC Not Increasing

**Check FranklinWH app:**
- Is solar producing? (needs > 1kW to charge battery + supply home)
- Is battery in "Self-Consumption" or "TOU" mode?
- Is there a self-reserve limit blocking charge?

**May need to:**
- Wait for sunnier conditions
- Or set MAX CHARGE mode (see `throttling_charge_test.py`)

---

## 📋 After Test Completes

### Step 1: Verify CSV File

```bash
ls -la throttling_heartbeat_*.csv
wc -l throttling_heartbeat_*.csv
```

Should have ~240 lines (2 hours × 30s interval + header).

### Step 2: Quick Analysis

```bash
python3 -c "
import csv
with open('throttling_heartbeat_YYYYMMDD_HHMMSS.csv') as f:
    rows = list(csv.DictReader(f))

socs = [float(r['SoC_%']) for r in rows if r['SoC_%']]
throts = [int(r['ThrotPct']) for r in rows if r['ThrotPct']]

print(f'Samples: {len(rows)}')
print(f'SoC: {min(socs):.1f}% → {max(socs):.1f}%')
print(f'ThrotPct: {min(throts)}% → {max(throts)}%')

if max(throts) > 0:
    print(f'✅ SUCCESS! Throttling detected: {max(throts)}%')
else:
    print(f'❌ No throttling observed')
"
```

### Step 3: Update Documentation

Add results to `PROPOSED_THROTTLING_IMPLEMENTATION.md`:
- Test date and duration
- SoC range observed
- Max ThrotPct observed
- Conclusion (useful / not useful)

### Step 4: Hand Off to User

Show user:
1. CSV file location
2. Summary of findings
3. Recommendation (implement monitor / skip feature)

---

## 📁 Files to Use

| File | Purpose | When to Use |
|------|---------|-------------|
| `log_throttling_with_heartbeat.py` | **PRIMARY** - WSetPct heartbeat | ☀️ Sunny day, battery charging |
| `log_throttling_simple.py` | Fallback - no heartbeat | If heartbeat fails |
| `throttling_charge_test.py` | Force charge mode | If battery not charging naturally |
| `PROPOSED_THROTTLING_IMPLEMENTATION.md` | Reference | Read for context |
| `TOMORROW_TEST_INSTRUCTIONS.md` | This file | Your instructions |

---

## 🎯 Decision Tree for Next Agent

```
Is it sunny and battery charging?
├── NO → Wait or use throttling_charge_test.py to force charge
└── YES → Start log_throttling_with_heartbeat.py
    └── Monitor for 2 hours or until SoC > 95%
        └── Did ThrotPct go above 0%?
            ├── YES → Feature is useful! Recommend implementing monitor
            └── NO → May need longer test or different conditions
```

---

## 📞 Questions for User

When you start, ask the user:

1. "What's the current SoC?" (Need < 90% to see the rise)
2. "Is the battery currently charging?" (Should show in app)
3. "How's the solar production today?" (Need > 2kW ideally)
4. "How long can we run the test?" (Recommend 2 hours)

---

## ✅ Checklist Before Starting

- [ ] Sunny conditions confirmed
- [ ] Battery charging or will charge soon
- [ ] SoC currently < 90% (room to grow)
- [ ] WiFi connection stable
- [ ] User available for 2 hours (or ok to run unattended)
- [ ] `log_throttling_with_heartbeat.py` exists and is executable

---

**Good luck!** The goal is to finally see ThrotPct > 0% and prove the feature is worth implementing.

---

*Document created: 2026-02-24*  
*For: Next Kimi Agent*  
*Mission: Prove ThrotPct monitoring is valuable*
