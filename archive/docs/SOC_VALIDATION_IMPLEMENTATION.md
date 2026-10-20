# SoC Validation Implementation Summary

**Date:** 2026-03-01  
**Status:** GAP-1 and GAP-2 RESOLVED

---

## Overview

Implemented critical safety features for SoC validation to prevent operations that would conflict with FranklinWH aGate reserve settings.

## Implemented Features

### GAP-1: Reserve SoC Conflict Detection (FR-3) ✅

**Files Modified:**
- `src/franklinwh/controller.py`: Added validation methods
- `franklinwh_cli.py`: Integrated validation into all control paths

**New Methods in `controller.py`:**

```python
# Class constants
SAFETY_MARGIN_PCT = 5   # Minimum 5% buffer above reserve
ABSOLUTE_MIN_SOC = 5    # Absolute minimum SoC
ABSOLUTE_MAX_SOC = 99   # Absolute maximum SoC

def get_effective_reserve_level(self) -> Tuple[Optional[int], str]:
    """Get reserve level based on current OnGridMode.
    
    Returns:
        Tuple of (reserve_pct, source) where source is:
        - 'self': Self-Consumption reserve (reg 15508)
        - 'tou': TOU reserve (reg 15509)
        - 'none': Manual mode (no reserve)
        - 'unknown': Could not read
    """

def validate_target_soc(self, target_soc: float, operation: str) -> Tuple[bool, str, dict]:
    """Validate target SoC against reserve levels.
    
    Implements GAP-1 (reserve conflict) and GAP-2 (safety margin).
    
    Args:
        target_soc: Target SoC percentage
        operation: 'charge' or 'discharge'
        
    Returns:
        (is_valid, message, details_dict)
        
    Error Codes:
        E001: Target outside absolute safe range (5-99%)
        E002: Target conflicts with reserve + safety margin
        W001: Target below configured reserve (warning only)
    """

def validate_soc_safety(self, target_soc: float, current_soc: float, 
                        operation: str) -> Tuple[bool, str, dict]:
    """Comprehensive SoC safety validation.
    
    Combines reserve validation with current SoC sanity checks.
    Validates target vs current for charge/discharge direction.
    
    Error Codes:
        E003: Discharge target >= current SoC
        E004: Already at or below discharge target
        E005: Charge target <= current SoC
        E006: Already at or above charge target
        W002: Current SoC close to reserve boundary
    """
```

**CLI Integration:**
- Virtual modes (self_consumption, emergency_backup, peak_shave, time_of_use)
- Direct power control with `--target-soc-auto`
- Status display shows effective reserve level

### GAP-2: Safety Margin Enforcement (FR-4) ✅

**Implementation:**
- `SAFETY_MARGIN_PCT = 5` in controller class
- Minimum operational SoC = reserve + 5%
- Enforced for all discharge operations
- Warned for charge operations below reserve

**Example Validation:**
```python
# Self-Consumption mode with Self Reserve = 20%
reserve = 20
min_operational = reserve + SAFETY_MARGIN_PCT  # = 25%

# Discharge to 22% -> ERROR (only 2% above reserve)
# Discharge to 18% -> ERROR (below reserve)
# Discharge to 30% -> OK (10% margin)
```

### Status Display Updates

**Added to `check_state()` output:**
```python
{
    'effective_reserve': {
        'level': 20,          # Current reserve percentage
        'source': 'self',     # 'self', 'tou', 'none', or 'unknown'
        'min_operational': 25  # reserve + SAFETY_MARGIN_PCT
    },
    'self_reserve_pct': 20,   # From reg 15508
    'tou_reserve_pct': 20,    # From reg 15509
}
```

**Added to `healthcheck()` output:**
```python
{
    'effective_reserve': 20,
    'reserve_source': 'self',
    'min_operational_soc': 25,
}
```

**CLI Display:**
```
  Reserve Settings:
    Level:         20% (self)
    Min Operational: 25%
```

## Error Messages

### E-Series (Blocking Errors)
- **E001**: Target SoC outside absolute safe range (5-99%)
- **E002**: Target conflicts with reserve + safety margin
- **E003**: Discharge target must be below current SoC
- **E004**: Already at or below target SoC
- **E005**: Charge target must be above current SoC
- **E006**: Already at or above target SoC

### W-Series (Warnings)
- **W001**: Target below configured reserve (charge only)
- **W002**: Current SoC close to reserve boundary

## Testing Recommendations

1. **Test Reserve Reading:**
   ```bash
   python franklinwh_cli.py --ip 192.0.2.110 --status
   # Verify Reserve Settings section shows correct values
   ```

2. **Test Discharge Below Reserve:**
   ```bash
   # If Self Reserve = 20%, try discharge to 22%
   python franklinwh_cli.py --ip 192.0.2.110 --discharge 3000 --target-soc-auto 22
   # Expected: E002 error, operation blocked
   ```

3. **Test Charge Below Reserve:**
   ```bash
   # If Self Reserve = 20%, try charge to 15%
   python franklinwh_cli.py --ip 192.0.2.110 --charge 3000 --target-soc-auto 15
   # Expected: W001 warning, operation proceeds
   ```

4. **Test Virtual Mode Validation:**
   ```bash
   python franklinwh_cli.py --ip 192.0.2.110 --mode peak_shave --target-soc 22
   # If reserve + margin > 22, should fail with E002
   ```

## Remaining Gaps

| Gap | Description | Priority |
|-----|-------------|----------|
| GAP-3 | Virtual modes target vs current validation | Medium |
| GAP-4 | Library `auto_stop_at_soc()` method | Low |

GAP-3 and GAP-4 are lower priority as CLI validation covers the critical paths.

## Traceability

| Req | Description | Implementation | Status |
|-----|-------------|----------------|--------|
| FR-1 | Target SoC range validation | CLI args + controller | ✅ |
| FR-2 | Target vs current sanity | `validate_soc_safety()` | ✅ |
| FR-3 | Reserve SoC conflict | `validate_target_soc()` | ✅ |
| FR-4 | Safety margin (5%) | `SAFETY_MARGIN_PCT` | ✅ |
| FR-5 | aGate conflict detection | `check_state()` | ✅ |
| FR-6 | Off-grid safety | `--off-grid-permitted` | ✅ |
| FR-7 | SoC auto-stop | CLI `--target-soc-auto` | ✅ CLI only |

---

## Dry-Run Support Fix (2026-03-01)

**Issue:** `--dry-run` flag was not being respected in continuous control modes.

**Fix:** Added dry-run checks in three locations in `franklinwh_cli.py`:

1. **Virtual modes** (lines 899-910): Shows what mode would be set and exits
2. **Target-SoC-Auto mode** (lines 1027-1037): Shows monitoring loop parameters and exits  
3. **Duration/SoC limit mode** (lines 1087-1099): Shows run_continuous() parameters and exits

**Dry-Run Output Example:**
```
============================================================
  DRY RUN: Manual mode with SoC limits
  Power: 5000W
  Max charge SoC: 20%
  Min discharge SoC: 20%
============================================================

  Would run: vmc.run_continuous(
      duration_seconds=None,
      enable_safety_checks=False
  )

  ✓ Dry run complete - no commands sent
```

---

**Next Steps:**
1. Hardware test reserve validation with actual aGate
2. Add `auto_stop_at_soc()` to library if needed for programmatic use
3. Document validation behavior in user guide
