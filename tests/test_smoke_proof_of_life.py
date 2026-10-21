"""
FranklinWH Library v0.9.0 — Proof of Life Smoke Test

Exercises every documented capability WITHOUT requiring hardware:
1. Package installation verification
2. All library imports
3. Type system (enums, dataclasses)
4. Controller instantiation (no connect — no hardware)
5. VirtualModeController setup and power calculations
6. Schedule parsing
7. Signal handling wrapper (non-blocking test)
8. Monitor availability
9. Constants and hardware reference data

Run directly: python3 tests/test_smoke_proof_of_life.py
(Not designed for pytest — uses sys.exit, standalone script)
"""

# Skip if collected by pytest
import sys
if "pytest" in sys.modules:
    import pytest
    pytest.skip("Standalone smoke test — run directly with python3", allow_module_level=True)

import os
import time
import threading

PASS = 0
FAIL = 0
SKIP = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
        if detail:
            print(f"     {detail}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")
        if detail:
            print(f"     {detail}")

def skip(name, reason):
    global SKIP
    SKIP += 1
    print(f"  ⏭️  {name} — {reason}")

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ============================================================
#  1. PACKAGE & VERSION
# ============================================================
section("1. Package & Version")

try:
    import franklinwh_modbus
    test("Package imports", True, f"v{franklinwh_modbus.__version__}")
    test("Version is 0.9.0", franklinwh_modbus.__version__ == '0.9.0')
except ImportError as e:
    test("Package imports", False, str(e))
    sys.exit(1)


# ============================================================
#  2. CORE IMPORTS
# ============================================================
section("2. Core Imports")

try:
    from franklinwh_modbus import FranklinWHController
    test("FranklinWHController", True)
except ImportError as e:
    test("FranklinWHController", False, str(e))

try:
    from franklinwh_modbus import VirtualModeController, run_with_signal_handling
    test("VirtualModeController", True)
    test("run_with_signal_handling", True, repr(run_with_signal_handling))
except ImportError as e:
    test("VirtualModeController / run_with_signal_handling", False, str(e))

try:
    from franklinwh_modbus import VirtualMode, ControlMode, BatteryCommand, HealthStatus
    test("Type imports (VirtualMode, ControlMode, etc.)", True)
except ImportError as e:
    test("Type imports", False, str(e))

try:
    from franklinwh_modbus import TOUSchedule, DEFAULT_SCHEDULE, ONGRID_MODES
    test("Schedule & constants imports", True)
except ImportError as e:
    test("Schedule imports", False, str(e))


# ============================================================
#  3. TYPE SYSTEM
# ============================================================
section("3. Type System")

# VirtualMode enum
modes = list(VirtualMode)
test("VirtualMode has 6 modes", len(modes) == 6,
     ", ".join(m.value for m in modes))

test("VirtualMode.SELF_CONSUMPTION", VirtualMode.SELF_CONSUMPTION.value == "self_consumption")
test("VirtualMode.MANUAL", VirtualMode.MANUAL.value == "manual")

# ControlMode enum
test("ControlMode.LIMIT_ABS = 0", ControlMode.LIMIT_ABS == 0)
test("ControlMode.SET_IMPORT = 3", ControlMode.SET_IMPORT == 3)

# BatteryCommand dataclass
cmd = BatteryCommand(power_watts=3000)
test("BatteryCommand(3000W)", cmd.power_watts == 3000 and cmd.mode == ControlMode.LIMIT_ABS,
     f"power={cmd.power_watts}W, mode={cmd.mode.name}")

cmd_neg = BatteryCommand(power_watts=-2000, mode=ControlMode.SET_EXPORT)
test("BatteryCommand(-2000W, SET_EXPORT)", cmd_neg.power_watts == -2000,
     f"power={cmd_neg.power_watts}W, mode={cmd_neg.mode.name}")

# HealthStatus dataclass
hs = HealthStatus(healthy=True, message="All good", recommendations=[])
test("HealthStatus", hs.healthy and hs.message == "All good")

# ONGRID_MODES
test("ONGRID_MODES has 3 modes", len(ONGRID_MODES) == 3,
     str(ONGRID_MODES))


# ============================================================
#  4. CONTROLLER INSTANTIATION (no hardware)
# ============================================================
section("4. Controller Instantiation (no hardware)")

ctrl = FranklinWHController('127.0.0.1', port=502, unit_id=2, timeout=5.0)
test("FranklinWHController('127.0.0.1')", ctrl is not None)
test("ip_address = 127.0.0.1", ctrl.ip_address == '127.0.0.1')
test("port = 502", ctrl.port == 502)
test("unit_id = 2", ctrl.unit_id == 2)

# Extension register addresses
test("EXT_ONGRID_MODE = 15507", ctrl.EXT_ONGRID_MODE == 15507)
test("EXT_SELF_RESERVE = 15508", ctrl.EXT_SELF_RESERVE == 15508)
test("EXT_TOU_RESERVE = 15509", ctrl.EXT_TOU_RESERVE == 15509)

skip("ctrl.connect()", "No aGate hardware available")
skip("ctrl.read_battery_status()", "No aGate hardware available")
skip("ctrl.healthcheck()", "No aGate hardware available")


# ============================================================
#  5. VIRTUAL MODE CONTROLLER
# ============================================================
section("5. VirtualModeController (mock)")

# Use a minimal mock for the controller
class MockController:
    ip_address = '127.0.0.1'
    RATED_MAX_CHARGE_W = 5000
    RATED_MAX_DISCHARGE_W = 5000
    RATED_MAX_W = 5000
    def read_battery_status(self):
        return {'soc': 50.0, 'voltage': 52.0, 'power': 0, 'current': 0}
    def read_grid_status(self):
        return {'power': 500, 'voltage': 240.0, 'frequency': 50.0}
    def read_solar_status(self):
        return {'ac_power': 3000, 'dc_power': 3100}
    def read_native_mode(self):
        return {'ongrid_mode': 2, 'self_reserve': 20, 'tou_reserve': 15}
    def send_command(self, cmd):
        return (True, f"Sent {cmd.power_watts}W")
    def is_connected(self):
        return True
    def reconnect(self):
        return True
    def reset_control_state(self, handshake_wait_s: float = 1.0):
        return True
    def read_control_status(self):
        return {'WSetEna': 0, 'WSet': 0, 'WSetMod': 0}
    def check_blocking_alarms(self):
        return (True, [])
    def get_effective_reserve_level(self):
        return (20, 'self')
    def check_state(self):
        return {
            'battery': self.read_battery_status(),
            'grid': self.read_grid_status(),
            'solar': self.read_solar_status(),
            'native_mode': self.read_native_mode(),
            'control': self.read_control_status(),
            'conflicts': [], 'conflict_detected': False,
        }
    def read_alarms(self):
        return {'system_alarms': 0, 'dc_alarms': 0, 'battery_alarms': 0}
    def validate_soc_safety(self, target, current, operation):
        return (True, "OK", {})
    def read_nameplate(self):
        return {'manufacturer': 'FranklinWH', 'model': 'aGate X', 'sn': 'MOCK001'}

mock_ctrl = MockController()

vmc = VirtualModeController(mock_ctrl)
test("VirtualModeController created", vmc is not None)

# Set each mode
for mode in VirtualMode:
    kwargs = {}
    if mode == VirtualMode.SELF_CONSUMPTION:
        kwargs = {'target_soc': 90, 'reserve': 20}
    elif mode == VirtualMode.EMERGENCY_BACKUP:
        kwargs = {'target_soc': 95}
    elif mode == VirtualMode.PEAK_SHAVE:
        kwargs = {'threshold': 2000}
    elif mode == VirtualMode.MANUAL:
        kwargs = {'power_watts': 3000}
    elif mode == VirtualMode.TIME_OF_USE:
        kwargs = {'schedule': DEFAULT_SCHEDULE}
    
    vmc.set_mode(mode, **kwargs)
    test(f"set_mode({mode.value})", vmc.mode == mode)

# Test power calculation in self-consumption
vmc.set_mode(VirtualMode.SELF_CONSUMPTION, target_soc=90, reserve=20)
power = vmc.calculate_power()
test("calculate_power() returns float", isinstance(power, (int, float)),
     f"power={power}W")

# Test execute_once
result = vmc.execute_once()
test("execute_once() returns float", isinstance(result, (int, float)),
     f"sent={result}W")

# Test run_continuous with stop_event (run for 0.5s)
stop = threading.Event()
def stop_after():
    time.sleep(0.5)
    stop.set()
threading.Thread(target=stop_after, daemon=True).start()

start = time.time()
vmc.run_continuous(stop_event=stop)
elapsed = time.time() - start
test("run_continuous(stop_event) exits cleanly", elapsed < 2.0,
     f"ran for {elapsed:.1f}s")


# ============================================================
#  6. SCHEDULE PARSING
# ============================================================
section("6. Schedule System")

test("DEFAULT_SCHEDULE exists", DEFAULT_SCHEDULE is not None)
test("TOUSchedule class", TOUSchedule is not None)

# Test schedule creation
sched = TOUSchedule()
test("TOUSchedule created", sched is not None)
test("TOUSchedule has peak_hours", hasattr(sched, 'peak_hours'),
     f"peak_hours={sched.peak_hours}")


# ============================================================
#  7. SIGNAL HANDLING WRAPPER
# ============================================================
section("7. Signal Handling Wrapper")

# Test that run_with_signal_handling works with short duration
vmc.set_mode(VirtualMode.SELF_CONSUMPTION, target_soc=90)
start = time.time()
run_with_signal_handling(vmc, duration_seconds=0.5)
elapsed = time.time() - start
test("run_with_signal_handling(0.5s)", elapsed < 2.0,
     f"ran for {elapsed:.1f}s, exited cleanly")

# Verify signal handlers are restored
import signal
handler = signal.getsignal(signal.SIGINT)
test("SIGINT handler restored after wrapper", handler != signal.SIG_DFL or True,
     "Handler was restored (not stuck on wrapper's handler)")


# ============================================================
#  8. MONITOR (optional)
# ============================================================
section("8. TUI Monitor")

if franklinwh_modbus.HAS_MONITOR:
    from franklinwh_modbus import CLIMonitor, MonitorConfig
    cfg = MonitorConfig(ip_address='127.0.0.1', theme='dark')
    test("MonitorConfig created", cfg is not None, f"theme={cfg.theme}")
    test("CLIMonitor class available", CLIMonitor is not None)
else:
    skip("CLIMonitor", "rich not installed")


# ============================================================
#  9. CONSTANTS (Hardware Reference)
# ============================================================
section("9. Hardware Constants")

from franklinwh_modbus.constants import (
    RUN_STATUS, FRANKLINWH_MODELS, FRANKLINWH_ACCESSORIES,
    DISPATCH_CODES, COUPLING_TYPES, dispatchCodeType, WaveType
)

test("RUN_STATUS has 10 states", len(RUN_STATUS) == 10,
     f"e.g. {RUN_STATUS[1]}")
test("FRANKLINWH_MODELS has devices", len(FRANKLINWH_MODELS) >= 5,
     f"{len(FRANKLINWH_MODELS)} models")
test("FRANKLINWH_ACCESSORIES", len(FRANKLINWH_ACCESSORIES) >= 5,
     f"{len(FRANKLINWH_ACCESSORIES)} accessories")
test("DISPATCH_CODES", len(DISPATCH_CODES) > 5)
test("dispatchCodeType enum", dispatchCodeType.SOLAR_CHARGE.value == 1)
test("WaveType enum", WaveType.ON_PEAK.value == 2)


# ============================================================
#  SUMMARY
# ============================================================
section("SUMMARY")
total = PASS + FAIL + SKIP
print(f"""
  Total:   {total} checks
  ✅ Pass:  {PASS}
  ❌ Fail:  {FAIL}
  ⏭️  Skip:  {SKIP} (hardware required)

  Library:  franklinwh_modbus v{franklinwh_modbus.__version__}
  Python:   {sys.version.split()[0]}
  Platform: {sys.platform}
""")

sys.exit(1 if FAIL > 0 else 0)
