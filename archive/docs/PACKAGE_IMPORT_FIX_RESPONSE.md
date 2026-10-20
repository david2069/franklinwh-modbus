# Response: Package Import Defect Resolution

**Date:** 2026-03-01  
**To:** Energy Manager Integration Team  
**From:** Development Team  
**Subject:** FranklinWH Library Import Issue - RESOLVED

---

## Issue Summary

**Defect:** `from franklinwh import FranklinWHController` failed with:
```
NameError: name 'Layout' is not defined
```

**Impact:** Energy-manager and other consumers could not migrate from `franklinwh_control_standalone.py` to the new `franklinwh` library package.

**Status:** ✅ **RESOLVED**

---

## Root Cause

The `monitor.py` module (TUI dashboard) had type annotations referencing `Layout` from the `rich` library:

```python
# monitor.py - line 689 (before fix)
def create_layout(self) -> Layout:  # Layout from rich.layout
```

When `rich` was not installed, `Layout` was undefined at class definition time, causing `NameError` even though the TUI features weren't being used.

---

## Fix Applied

### 1. Postponed Type Annotation Evaluation

Added to `src/franklinwh/monitor.py` line 2:
```python
from __future__ import annotations  # Postpone type hint evaluation
```

**Effect:** Type annotations are stored as strings and evaluated lazily, preventing NameError at import time.

### 2. Graceful Degradation (Already in Place)

The `__init__.py` already handles missing `rich`:
```python
try:
    from .monitor import CLIMonitor, MonitorConfig
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    CLIMonitor = None
    MonitorConfig = None
```

---

## Migration Guide for Energy-Manager

### Before (Standalone Script)
```python
import sys
sys.path.insert(0, '/path/to/modbus')
from franklinwh_control_standalone import FranklinWHController

ctrl = FranklinWHController('192.0.2.110')
ctrl.connect()
```

### After (Library Package)
```python
import sys
sys.path.insert(0, '/path/to/modbus/src')
from franklinwh import FranklinWHController

ctrl = FranklinWHController('192.0.2.110')
ctrl.connect()
```

**Key Changes:**
1. Add `src/` to path (not just modbus root)
2. Import from `franklinwh` (not `franklinwh_control_standalone`)
3. Same API - no code changes needed

### Optional: Check Monitor Availability

```python
from franklinwh import FranklinWHController, HAS_MONITOR

# Core functionality always works
ctrl = FranklinWHController('192.0.2.110')

# Optional TUI features
if HAS_MONITOR:
    from franklinwh import CLIMonitor
    # Use TUI dashboard
else:
    # Fallback to console output
    pass
```

---

## Verification Steps

### Step 1: Test Import
```bash
cd /path/to/modbus
python3 -c "
import sys
sys.path.insert(0, 'src')
from franklinwh import FranklinWHController, HAS_MONITOR
print(f'✓ Import successful (HAS_MONITOR={HAS_MONITOR})')
"
```

### Step 2: Test Connection
```bash
python3 franklinwh_cli.py -i 192.0.2.110 --status
```

### Step 3: Run Test Suite
```bash
python3 tests/test_package_import.py
```

Expected output:
```
✓ Import core modules
✓ Monitor module no NameError
✓ HAS_MONITOR flag
✓ CLIMonitor availability
✓ Type annotations postponed
✓ Import in subprocess
All tests passed!
```

---

## Dependencies

### Required (Core Library)
- `pymodbus` - Modbus TCP communication
- `sunspec2` - SunSpec model parsing

### Optional (TUI Monitor)
- `rich` - Terminal UI dashboard
  - Install: `pip install rich`
  - Only needed for `--monitor` flag

### Testing
- `pytest` - Test framework
- Standard library: `threading`, `dataclasses`, etc.

---

## API Compatibility

| Feature | Standalone | Library | Notes |
|---------|------------|---------|-------|
| `FranklinWHController` | ✅ | ✅ | Identical API |
| `BatteryCommand` | ✅ | ✅ | Identical API |
| Virtual modes | ✅ | ✅ | `VirtualModeController` class |
| TOU schedules | ✅ | ✅ | `TOUSchedule` class |
| TUI Monitor | ❌ | ✅ | Library adds `--monitor` |
| Startup validation | ✅ | ✅ | Added to CLI |
| Auto-revert | ✅ | ✅ | Added to CLI |

**Breaking Changes:** None. Migration is drop-in replacement.

---

## Benefits of Migration

1. **Proper Package Structure** - Importable library, not just script
2. **Better Testing** - Unit tests, hardware test suite
3. **Active Development** - Standalone is deprecated
4. **New Features** - TUI monitor, conflict detection, auto-revert
5. **Documentation** - Comprehensive usage guide

---

## Support

- **Usage Guide:** See `USAGE_GUIDE.md`
- **API Reference:** See `USAGE_GUIDE.md` section 6
- **Test Suite:** `tests/test_package_import.py`
- **Hardware Tests:** `run_hardware_tests.py --read-only`

---

## Action Items

- [ ] Update energy-manager `MODBUS_LIB_PATH` to include `src/`
- [ ] Change import from `franklinwh_control_standalone` to `franklinwh`
- [ ] Run `tests/test_package_import.py` to verify
- [ ] Test connection to aGate hardware
- [ ] Remove standalone script dependency

---

**Questions?** Refer to `USAGE_GUIDE.md` or run `python franklinwh_cli.py --help`

*Fix verified 2026-03-01 by development team*
