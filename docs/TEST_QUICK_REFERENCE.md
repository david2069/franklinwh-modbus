# Hardware Test Quick Reference

## ⚡ One-Command Status Check

```bash
source venv/bin/activate && python franklinwh_cli.py -i 192.0.2.110 --status && python franklinwh_cli.py -i 192.0.2.110 --healthcheck
```

## 🧪 Running Tests

```bash
# 1. Read-only (safest)
python run_hardware_tests.py --read-only

# 2. Low-power writes (500W)
python run_hardware_tests.py --low-power

# 3. List available tests
python run_hardware_tests.py --list
```

## 🔒 Releasing Control (CRITICAL)

```bash
# Method 1: Runner script
python run_hardware_tests.py --release

# Method 2: CLI stop flag
python franklinwh_cli.py -i 192.0.2.110 --stop

# Method 3: Quick Python
python -c "import sys; sys.path.insert(0, 'src'); from franklinwh import FranklinWHController; c=FranklinWHController('192.0.2.110'); c.connect(); c.reset_control_state(); print('Released'); c.disconnect()"
```

## ✅ Post-Test Verification

```bash
# Check control released
python franklinwh_cli.py -i 192.0.2.110 --status | grep "Control Source"
# Expected: "Cloud API" or "Idle"

# Check zombie state
python franklinwh_cli.py -i 192.0.2.110 --healthcheck | grep zombie_state
# Expected: "OK (not in zombie state)"

# Check alarms
python franklinwh_cli.py -i 192.0.2.110 --status | grep -A2 "ALARMS"
# Expected: "No alarms active"
```

## 📊 Test Results

```bash
# Latest results file
ls -t data/test_results_*.json | head -1

# View summary
latest=$(ls -t data/test_results_*.json | head -1) && python -c "import json; d=json.load(open('$latest')); s=d['test_session']; print(f\"Passed: {s['passed']}/{s['total_tests']}\")"
```

## 🚨 Emergency Release (if stuck)

```bash
# Force control take then release
python franklinwh_cli.py -i 192.0.2.110 --mode manual --power 0 --duration 1
sleep 2
python franklinwh_cli.py -i 192.0.2.110 --stop
```

## 📁 File Locations

| File | Purpose |
|------|---------|
| `HARDWARE_TEST_GUIDE.md` | Full documentation |
| `run_hardware_tests.py` | Test runner script |
| `tests/hardware/test_live_battery_control.py` | Test suite |
| `data/test_results_*.json` | Test results |

---

**Remember: Always run `--stop` after testing and verify `zombie_state: OK`**
