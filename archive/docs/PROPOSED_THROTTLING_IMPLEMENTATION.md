# Proposed Throttling Monitor Implementation

**Status:** PARKED - Ready for 1-hour PoC tomorrow  
**Last Updated:** 2026-02-24  
**Discovery Session:** Throttling register validation complete  

---

## 📋 Executive Summary

**Discovery:** FranklinWH aGate X implements **partial SunSpec2 throttling support**:

| Register | Address | Status | Value Found |
|----------|---------|--------|-------------|
| **ThrotPct** | 40180 | ✅ **WORKS** | 0% (no throttling currently) |
| **ThrotSrc** | 40181-2 | ❌ **NOT IMPLEMENTED** | 0xFFFFFFFF (uninitialized) |

**Decision:** Build minimal PoC adding ThrotPct to existing monitor (1 hour work).  
**ThrotSrc should be skipped** - FranklinWH firmware doesn't populate it.

---

## 🔍 Background: SunSpec2 Throttling Registers

### What Are These Registers?

From **Model 701: DERMeasureAC** (SunSpec2 standard), these registers show when/how much the inverter is limiting its output:

**ThrotPct (40180)** - uint16
- **Purpose:** Current throttling level (0-100%)
- **0%** = No throttling, full power available
- **50%** = Output reduced to half rated capacity  
- **100%** = Fully throttled, essentially zero output

**ThrotSrc (40181)** - bitfield32  
- **Purpose:** Bitfield indicating WHY throttling is active
- **Standard bits:** Grid command, thermal, frequency regulation, SOC limits, generator limit, etc.

### Standard SunSpec2 ThrotSrc Bitfield

| Bit | Name | Description | FranklinWH Context |
|-----|------|-------------|-------------------|
| 0 | GridCmd | 🔌 Utility/grid operator command | Export limits, demand response |
| 1 | FreqReg | 📊 Frequency regulation active | Grid frequency droop response |
| 2 | VoltReg | ⚡ Voltage regulation active | Local voltage ride-through |
| 3 | TempDerate | 🌡️ Temperature derating | aGate/aPower thermal protection |
| 4 | SOCLimit | 🔋 Battery SOC protection | Min/max SOC throttling |
| 5 | GenLimit | ⛽ Generator capacity limit | Generator input overload |
| 6 | IslandStab | 🏝️ Island mode stabilization | Blackstart/load matching |
| 7 | UserLimit | 👤 User/installer manual limit | Commissioning mode |
| 8 | PVLimit | ☀️ PV input limit | DC overvoltage or MPPT limit |
| 9 | CurrLimit | 🔒 Current/hardware limit | Internal protection |
| 10 | CommLoss | 📡 Communication loss | Fallback safe mode |
| 11-31 | Reserved | Vendor-specific / future use | FranklinHW proprietary (not implemented) |

---

## 🧪 Validation Test Results

### 10-Minute Test Completed (2026-02-24 22:48-22:58)

**Script:** `log_throttling_robust.py 192.0.2.110 2 10 30`

| Metric | Value |
|--------|-------|
| **Duration** | 10 minutes |
| **Total Samples** | 20 |
| **Sample Interval** | 30 seconds |
| **Read Success Rate** | 20/20 (100%) |
| **Connection Drops** | 0 (auto-reconnect prevented failures) |

**Data Collected:**

| Parameter | Start | End | Change |
|-----------|-------|-----|--------|
| **SoC** | 49.67% | 45.52% | ↓ 4.15% |
| **ThrotPct** | 0% | 0% | No change |
| **Power** | 1W | 1W | Idle |
| **Cabinet Temp** | 26.5°C | 26.4°C | Stable |
| **Inverter State** | Sleeping | Sleeping | Idle |

**Findings:**
1. ✅ **ThrotPct register readable** - Consistent 0% readings
2. ✅ **Connection stable** - Auto-reconnect logic working
3. ❌ **No throttling observed** - Battery sleeping, not charging
4. ❌ **ThrotSrc unimplemented** - Always 0xFFFFFFFF

### What This Proves

| Finding | Evidence | Value |
|---------|----------|-------|
| ThrotPct works | 20 successful reads | ✅ **YES** - Register is functional |
| ThrotPct changes with conditions | Remained 0% | ❌ **NOT TESTED** - need charging scenario |
| Auto-reconnect works | 0 failed reads | ✅ **YES** - WiFi handling robust |
| ThrotSrc works | Always 0xFFFFFFFF | ❌ **NO** - Not implemented |

---

## ✅ What's Useful (ThrotPct Only)

### Use Cases

| Scenario | ThrotPct Value | Action |
|----------|----------------|--------|
| Normal operation | 0% | No action needed |
| Grid export limiting | 20-80% | Alert: Export limit active |
| Hot day derating | 10-50% | Alert: Thermal protection active |
| Generator overload | 30-70% | Alert: Reduce load or upgrade generator |
| Blackstart forming | 100% | Info: Island mode ramping |

### Limitations

Without ThrotSrc, **we cannot determine WHY throttling is happening**:
- ❌ Can't tell if it's thermal, grid command, or generator limit
- ❌ Can't provide specific diagnostic guidance
- ✅ Can only alert "throttling detected: X%"

**Workaround:** Cross-reference with other telemetry:
- Check `TmpCab` (cabinet temp) - if high, likely thermal
- Check grid power vs limits - if at export limit, likely grid command
- Check generator input status - if active, likely GenLimit

---

## 🛠️ Proposed 1-Hour PoC

### Goal
Add ThrotPct monitoring to existing monitor/dashboard.

### Files to Modify

#### 1. `src/franklinwh/monitor.py`

Add to `SystemData` class:
```python
@dataclass
class SystemData:
    # ... existing fields ...
    throttle_pct: float = 0.0  # NEW: Throttling percentage (0-100)
```

Add to `MonitorConfig`:
```python
@dataclass  
class MonitorConfig:
    # ... existing ...
    throttle_alert_threshold: float = 5.0  # Alert if > 5% throttled
```

Add to `Monitor._read_system_data()`:
```python
def _read_system_data(self) -> Optional[SystemData]:
    # ... existing reads ...
    
    # Read throttling register (Model 701, register 40180)
    try:
        result = self.client.read_holding_registers(40180 - 40001, 1, device_id=self.config.unit_id)
        if not result.isError() and result.registers[0] != 0xFFFF:
            data.throttle_pct = result.registers[0]  # uint16, 0-100
    except Exception:
        data.throttle_pct = 0.0  # Default to 0 on error
    
    return data
```

Add to `Monitor._create_dashboard()` layout:
```python
# In system info panel or as separate indicator
# Show: "Throttle: 0%" (green) or "Throttle: 25%" (yellow/red)
```

Add throttling display to `_update_display()`:
```python
# Add to appropriate panel
throttle_color = "green" if data.throttle_pct == 0 else "yellow" if data.throttle_pct < 50 else "red"
self.throttle_display.update(f"Throttle: {data.throttle_pct:.0f}%", style=throttle_color)
```

#### 2. Add Alert Logic

```python
def check_throttling(self, data: SystemData):
    """Alert if throttling detected."""
    if data.throttle_pct > self.config.throttle_alert_threshold:
        self.show_alert(
            f"⚠️ Throttling Active: {data.throttle_pct:.0f}%",
            severity="warning" if data.throttle_pct < 50 else "critical"
        )
```

### UI Placement Options

**Option A: System Info Panel** (Recommended - minimal change)
```
┌─ System Info ──────────────────────┐
│ Mode: Self-consumption             │
│ SoC: 94%                           │
│ Throttle: 0%  ✅                   │  ← Add here
└────────────────────────────────────┘
```

**Option B: Power Flow Panel** (Alternative)
```
┌─ Power Flow ───────────────────────┐
│ ⚡ Solar → [Battery] → Grid        │
│ Throttle: 25% ⚠️                   │  ← Warning indicator
└────────────────────────────────────┘
```

---

## 📚 Code Reference: Existing Patterns

### Modbus Read Pattern (from `franklinwh_control_standalone.py`)

```python
# Pattern: Direct register read with error handling
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient(host, port=502, timeout=10)

# Model 701 registers are at base 40070
# ThrotPct is at 40180 = offset 110 from base
# pymodbus uses 0-based addressing: 40180 - 40001 = 179

result = client.read_holding_registers(
    address=40180 - 40001,  # = 179
    count=1,
    device_id=unit_id  # Usually 2 for FranklinWH
)

if not result.isError():
    throt_pct = result.registers[0]  # 0-100, or 0xFFFF if not implemented
    if throt_pct != 0xFFFF:
        print(f"Throttling: {throt_pct}%")
```

### Bitfield Decode Pattern (from `enum_alarms.py`)

```python
def decode_bitfield(value: int, bit_definitions: dict) -> list:
    """Generic bitfield decoder."""
    active = []
    for bit, (name, description) in bit_definitions.items():
        if value & (1 << bit):
            active.append({"bit": bit, "name": name, "desc": description})
    return active

# Example usage (not useful for ThrotSrc since it's not implemented)
THROT_SOURCES = {
    0: ("GridCmd", "Utility/grid operator command"),
    1: ("FreqReg", "Frequency regulation"),
    3: ("TempDerate", "Temperature derating"),
    # ... etc
}
```

### Dashboard Update Pattern (from `monitor.py`)

```python
# Pattern: Update Rich panel with new data
def _update_display(self, data: SystemData):
    # Existing updates...
    
    # Add throttling indicator
    if hasattr(self, 'throttle_panel'):
        color = "green" if data.throttle_pct == 0 else "yellow" if data.throttle_pct < 50 else "red"
        emoji = "✅" if data.throttle_pct == 0 else "⚠️" if data.throttle_pct < 50 else "🔥"
        self.throttle_panel.update(
            Panel(f"{emoji} Throttle: {data.throttle_pct:.0f}%", border_style=color)
        )
```

---

## 🔧 Logger Scripts for Testing

### Option A: Simple Read-Only Logger
**File:** `log_throttling_simple.py`
- 5-second polling
- JSON output
- No heartbeat
- Use for: Quick tests, minimal overhead

```bash
python log_throttling_simple.py 192.0.2.110 2 60
```

### Option B: WSetPct Heartbeat Logger ⭐ RECOMMENDED
**File:** `log_throttling_with_heartbeat.py`
- Sends WSetPct(0) every 10s to maintain VPP mode
- 30-second sampling
- CSV output with heartbeat status
- Use for: Extended monitoring, stable connection

```bash
python log_throttling_with_heartbeat.py 192.0.2.110 2 60
```

**Why Heartbeat:**
- Your monitor uses WSetPct writes to keep connection alive
- ControllerHb (41092) doesn't work on FranklinWH
- WSetPct(0) acts as "keepalive" without changing battery behavior

### Option C: Full Control Test
**File:** `throttling_charge_test.py`
- Shows full system state (mode, reserve, temps)
- Can optionally set MAX CHARGE mode
- Monitors until target SoC reached

```bash
python throttling_charge_test.py 192.0.2.110 2 95
```

---

## 🧪 Testing Plan

### Phase 1: Validate Register (COMPLETED ✅)
- ✅ Run `log_throttling_robust.py` for 10 minutes
- ✅ Confirmed ThrotPct readable and stable
- ✅ Verified auto-reconnect handles WiFi drops
- Result: **20/20 samples successful, ThrotPct = 0%**

### Phase 2: Catch Throttling in Action (NEXT)
**When:** Sunny morning/afternoon with solar charging  
**Start:** SoC ~70%, will rise to 95%+  
**Expected:** ThrotPct increases as SoC approaches 100%

```bash
python log_throttling_with_heartbeat.py 192.0.2.110 2 120
```

**Success Criteria:**
- ThrotPct stays at 0% during 70-85% SoC
- ThrotPct rises to 10-30% at 90-95% SoC
- ThrotPct reaches 50%+ at 98%+ SoC

### Phase 3: Integration (AFTER validation)
- Add ThrotPct to existing monitor
- Add alert when ThrotPct > threshold
- Log throttling events for analysis

---

## 🤔 Decision Points

### Question 1: Proceed with PoC?

**Option A: YES** ⭐ RECOMMENDED
- Evidence: ThrotPct register confirmed working
- Effort: 1 hour to add to monitor
- Risk: Low - read-only, can't break anything

**Option B: NO**
- Reason: Haven't seen ThrotPct > 0 yet
- Alternative: Wait for Phase 2 validation first

### Question 2: Which Logger for Phase 2?

**Option A:** `log_throttling_simple.py` - Quick test  
**Option B:** `log_throttling_with_heartbeat.py` - Stable, extended test ⭐  
**Option C:** `throttling_charge_test.py` - Full system state

### Question 3: Alert Threshold?

- **5%** - Very sensitive (might alert on normal operation)
- **10%** - Moderate ⭐  
- **25%** - Only significant throttling

---

## 📁 Related Files

| File | Purpose |
|------|---------|
| `test_throttling_registers.py` | Initial 30-second validation |
| `log_throttling_1hour.py` | Original buggy logger (deprecated) |
| `log_throttling_robust.py` | Fixed version with reconnections |
| `log_throttling_simple.py` | Quick 5s polling logger |
| `log_throttling_with_heartbeat.py` | WSetPct heartbeat logger ⭐ |
| `throttling_charge_test.py` | Full control/state monitor |
| `PROPOSED_THROTTLING_IMPLEMENTATION.md` | This document |
| `enum_alarms.py` | Bitfield decoding patterns |
| `franklinwh_control_standalone.py` | Working Modbus patterns |
| `Modbus_Throttling_Kimi_K2.5_via_T3chat.txt` | Original SunSpec2 analysis |

---

## 📝 Critical Notes

### What We Know FOR CERTAIN
1. ✅ **ThrotPct (40180) is READABLE** - Returns valid 0-100%
2. ✅ **ThrotSrc (40181) is BROKEN** - Always 0xFFFFFFFF
3. ✅ **Auto-reconnect works** - Handles WiFi drops
4. ❌ **ControllerHb doesn't work** - Write rejected
5. ✅ **WSetPct works** - Use for heartbeat instead

### What We DON'T Know Yet
1. ❓ Does ThrotPct ever go above 0%?
2. ❓ Does it correlate with SoC during charging?
3. ❓ Does it work during thermal throttling?

### Next Steps
1. **Run Phase 2 test** during solar charging (SoC > 90%)
2. **Confirm ThrotPct changes** with battery conditions
3. **Decide on integration** based on results

---

**End of Document**  
*Last Updated: 2026-02-24*  
*Status: Phase 1 Complete, Phase 2 Ready*
