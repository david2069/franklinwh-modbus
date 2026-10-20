# Virtual Mode Specifications & Validation Targets

> **Purpose**: Define what each mode does, power sources, load priorities, and validation targets for hardware testing.  
> **Last Updated**: 2026-03-12  
> **References**: [Understanding Operating Modes](https://service.franklinwh.com/en/support/solutions/articles/73000647816), [Emergency Backup](https://service.franklinwh.com/en/support/solutions/articles/73000649111), [Time of Use](https://service.franklinwh.com/en/support/solutions/articles/73000647820), [System Operation Mode](https://www.franklinwh.com/support/overview/system-operation-mode)

---

## ⚠️ Primary Constraint: FranklinWH Modbus TCP Implementation

Everything in this document is shaped by what the aGate actually exposes via Modbus TCP:

| Capability | Status | Detail |
|-----------|--------|--------|
| **Read battery state** | ✅ | SoC, power, voltage, temp, energy (M713, M714) |
| **Read grid/solar/inverter** | ✅ | Power, voltage, frequency, status (M701, M502) |
| **Read aGate native mode** | ✅ | Ext.15507 (Emergency/Self-Consumption/TOU/Manual) — read-only |
| **Write battery power** | ✅ | M704 WSetPct, WSet, WSetEna — the ONLY writable control |
| **Change operating mode** | ❌ | Ext.15507 is read-only; writes undocumented and not applied (V12R02B60D00, 2026-10-21) |
| **Control reserve SoC** | ❌ | Ext.15508-15509 are read-only; writes undocumented and not applied (V12R02B60D00, 2026-10-21) |
| **Control solar PV** | ❌ | No writable registers for PV curtailment or production |
| **Control smart circuits** | ❌ | Not exposed via Modbus TCP at all |
| **See generator/V2L** | ❌ | Not exposed via Modbus TCP |
| **Hardware reversion timer** | ❌ | WSetRvrtTms accepted but never executes (quirk) |
| **Hardware heartbeat** | ❌ | ControllerHb silently ignored (quirk) |

!!! caution
    **Our ONLY control lever is M704 battery power commands.** Everything else — mode, reserves, solar, smart circuits, load shedding — is either read-only or invisible. All virtual modes are constrained to: "tell the battery how many watts to charge or discharge." The aGate's native mode runs in parallel and resumes the instant we release control.

---

## FranklinWH aGate X — System Architecture

### Power Sources

| Source | On-Grid | Off-Grid | Modbus Visible | Controllable via M704 |
|--------|---------|----------|----------------|----------------------|
| **Solar PV (Proximal)** | ✅ | ✅ | ✅ `M502.OutPw`, `Ext.15502-15503` | ❌ (read-only) |
| **Solar PV (Remote via aPbox/aHub)** | ✅ | ✅ | ✅ `Ext.15504-15505` | ❌ (read-only) |
| **Grid** | ✅ | ❌ | ✅ `M701.W` | Indirect (via battery charge/discharge) |
| **Generator** | ❌ | ✅ | ❌ (not visible via Modbus TCP) | ❌ |
| **V2L (Vehicle-to-Load)** | ❌ | ✅ | ❌ (not visible via Modbus TCP) | ❌ |
| **Battery (aPower)** | ✅ | ✅ | ✅ `M714.DCW`, `M713.SoC` | ✅ M704 WSetPct/WSet |

### AC Input/Output Capacity

| Interface | Rating | Notes |
|-----------|--------|-------|
| **AC Input 1 (Solar/Grid)** | 63A / circuit | Proximal PV or grid |
| **AC Input 2 (Solar/Grid)** | 63A / circuit | Proximal PV or grid |
| **Max Inverter Power** | 5000W continuous | `M703.WRtg` |
| **Max Charge Rate** | 5000W | `M703.MaxChaRte` |
| **Max Discharge Rate** | 5000W | `M703.MaxDisChaRte` |
| **Smart Circuits** | 2–3 per aGate | ⚠️ NOT visible via Modbus TCP |

### Curtailment

| Scenario | Condition | What Happens |
|----------|-----------|--------------|
| **On-Grid: Battery Full** | SoC = 100%, excess solar | Excess exported to grid (if export allowed) |
| **On-Grid: Export Restricted** | Grid export disabled by utility | Solar production curtailed by aGate |
| **Off-Grid: Battery Full** | SoC = 100%, excess solar | aGate curtails solar (shuts down PV production) |
| **Off-Grid: Overload** | Home load > inverter + battery capacity | aGate load-sheds (Smart Circuits first) |
| **PV Capacity Limit** | Solar > 2× AC input (10kW+) | Hardware limit, not software-controllable |

> **Smart Circuits** are controlled by the aGate firmware and are NOT visible or controllable via Modbus TCP. They appear in the FranklinWH app only.

---

## Two Control Layers

The FranklinWH system has **two independent control layers** running in parallel:

| Layer | Source | Registers | Can We Change? |
|-------|--------|-----------|----------------|
| **aGate Native** | FranklinWH Cloud/App | Ext.15507 (OnGridMode) | ❌ Read-only (writes undocumented) |
| **Virtual (Ours)** | `modes.py` via M704 | WSetEna, WSetPct, WSet | ✅ Always writable |

Our virtual modes **override** the aGate's native battery behavior by sending M704 power commands every 5 seconds. The native mode keeps running in the background — when we release control (`--stop`), the aGate resumes its native mode immediately.

!!! important
    We can only control **battery charge/discharge power** via M704. We CANNOT:
    - Change the aGate's operating mode (Ext.15507): writes are undocumented and did not take effect on V12R02B60D00
    - Control Smart Circuit load shedding
    - Directly control solar PV production or curtailment
    - Control grid import/export limits (only indirect via battery)

---

## aGate Native Modes (Ext.15507 — Read Only)

These are what the FranklinWH app sets. We can READ them but not WRITE them. FranklinWH has never documented 15507 as writable.

### Mode 0: Emergency Backup

| Aspect | Behavior |
|--------|----------|
| **Intent** | Keep battery at 100% for outage resilience |
| **Load Priority** | 1. Solar → Home, 2. Grid → Home, 3. Solar → Battery, 4. Grid → Battery |
| **Battery** | Charges to 100% from solar + grid. Does NOT discharge for self-consumption. |
| **Grid (on-grid)** | Primary power source for home loads. Battery held in reserve. |
| **Off-Grid** | Battery powers home. Solar recharges battery (curtails if full). |
| **Ext.15507** | `0` |

### Mode 1: Self-Consumption

| Aspect | Behavior |
|--------|----------|
| **Intent** | Maximize solar self-use, minimize grid import |
| **Load Priority** | 1. Solar → Home, 2. Solar → Battery, 3. Battery → Home, 4. Grid → Home (last resort) |
| **Battery** | Charges from excess solar. Discharges to cover home load when solar insufficient. |
| **Grid (on-grid)** | Import only when battery depleted AND solar insufficient. Export excess when battery full. |
| **Off-Grid** | Battery + solar power home. Solar curtailed if battery full. |
| **Reserve** | User-configurable reserve % (Ext.15508). Battery won't discharge below reserve. |
| **Ext.15507** | `2` |

### Mode 2: Time-of-Use (TOU)

| Aspect | Behavior |
|--------|----------|
| **Intent** | Arbitrage — charge off-peak, discharge on-peak |
| **Load Priority (On-Peak)** | 1. Solar → Home, 2. Battery → Home, 3. Grid → Home (avoid) |
| **Load Priority (Off-Peak)** | 1. Solar → Home, 2. Solar → Battery, 3. Grid → Battery, 4. Grid → Home |
| **Battery (On-Peak)** | Discharges to power home, avoiding expensive grid import |
| **Battery (Off-Peak)** | Charges from solar + cheap grid power |
| **Grid** | Minimize import during peak. Allow import during off-peak. |
| **Schedule** | User defines: Super Off-Peak, Off-Peak, Mid-Peak, On-Peak periods |
| **Reserve** | User-configurable reserve % (Ext.15509). Battery won't discharge below. |
| **Ext.15507** | `1` |

### Mode 3: Manual

| Aspect | Behavior |
|--------|----------|
| **Intent** | User/API-directed battery behavior |
| **Ext.15507** | `3` |

---

## Virtual Modes: Battery Orchestration Plans

> **The Reality**: Native FranklinWH Operating Modes (set via the mobile app) are comprehensive ecosystem orchestration plans. They control battery behavior, grid import/export permissions, smart circuit load shedding, and generator triggers simultaneously. 
> 
> Because the Modbus TCP interface ONLY provides access to `M704` Battery Power, **our Virtual Modes are merely battery orchestration plans**. They emulate the core battery behavior of the native modes, but cannot touch the wider ecosystem. 

These modes run in our software (`modes.py`) and send continuous M704 power setpoints every 5 seconds. They **override** the aGate's native battery behavior but nothing else.

### Load Priority Reference

How each virtual mode prioritizes power sources for covering home load:

| Priority | Self-Consumption | Emergency Backup | Grid Zero | Peak Shave | TOU (On-Peak) | TOU (Off-Peak) | Manual |
|----------|------------------|------------------|-----------|------------|---------------|----------------|--------|
| 1st | Solar | Solar+Grid→Battery | Solar | Solar | Solar | Solar→Battery | User-set |
| 2nd | Battery discharge | Hold at target | Battery discharge | Idle (<threshold) | Battery discharge | Grid→Battery | — |
| 3rd | Grid import | Idle (no discharge) | — (target=0W grid) | Battery (>threshold) | Grid import | Grid→Home | — |
| 4th | — | — | — | Grid import | — | — | — |

---

### 1. `self_consumption` — Default Mode

**Emulation Target**: FranklinWH Native Self-Consumption (`Ext.15507=2`)  
**Emulation Fidelity**: **Partial**. We calculate net load and direct the battery to cover it, successfully minimizing grid import. However, if the home load exceeds inverter capacity off-grid, the native mode drops Smart Circuits; our virtual mode cannot, leading to an abrupt microgrid collapse.

**Power Flow (Our Implementation)**:
```
IF SoC >= target_soc + self_reserve:
    excess_solar = solar - home
    IF excess_solar > 0: charge from excess solar (up to max)
    IF excess_solar < 0: discharge to cover shortfall
    IF excess_solar = 0: idle
ELSE:
    FULL POWER CHARGE from grid+solar (to reach target ASAP)
```

**Validation Targets**:
- [ ] Night, SoC < target: charge at max from grid
- [ ] Night, SoC ≥ target: discharge to cover home load
- [ ] Day, excess solar: charge from excess only
- [ ] SoC at reserve: stop discharging

---

### 2. `emergency_backup` — Keep Battery Full

**Emulation Target**: FranklinWH Native Emergency Backup (`Ext.15507=0`)  
**Emulation Fidelity**: **Partial**. We successfully hold the battery at 100% and aggressively prevent discharging to the home. However, the native mode also triggers the Generator (if installed) during an outage to keep the battery topped up. We cannot trigger the generator via Modbus.

**Power Flow**:
```
IF SoC >= target: idle (0W) — do NOT discharge
ELSE: charge proportionally (higher power when further from target)
```

**Validation Targets**:
- [ ] SoC < target: charge at high power
- [ ] SoC ≥ target: idle (0W, no discharge even with home load)
- [ ] **Key**: battery never discharges to cover home load on-grid

---

### 3. `grid_zero` — Minimize Grid Interaction

**Emulation Target**: None (Custom Mode)  
**Emulation Fidelity**: **N/A**. This is a purely custom orchestration plan that tries to zero-out the grid meter by directly reacting to `M701.W` (Grid Power) rather than relying on solar projections. It has no native equivalent.

**Power Flow**:
```
net_load = home - solar
IF net_load > 0: discharge to cover (grid import → 0W)
IF net_load < 0 AND SoC < target: charge from excess (grid export → 0W)
IF net_load < 0 AND SoC >= target: idle (excess exports)
```

**Validation Targets**:
- [ ] Home > solar: `M701.W` near 0W (battery discharging)
- [ ] Solar > home: `M701.W` near 0W (battery absorbing excess)

---

### 4. `peak_shave` — Reduce Peak Grid Demand

**Emulation Target**: None (Custom Mode)  
**Emulation Fidelity**: **N/A**. This is a purely custom orchestration plan designed to shave utility demand-charge spikes. It has no native equivalent.

**Power Flow**:
```
IF home > threshold AND SoC > min + 5%:
    discharge = home - threshold (cap at max_discharge)
ELSE: idle (0W)
```

**Validation Targets**:
- [ ] Home < threshold: battery idle
- [ ] Home > threshold: battery discharges (threshold - home), grid caps at threshold

---

### 5. `time_of_use` — Schedule-Based Arbitrage

**Emulation Target**: FranklinWH Native TOU (`Ext.15507=1`)  
**Emulation Fidelity**: **Partial / Experimental**. We parse the TOU JSON schedule and force the battery to charge/discharge at the correct times. However, the native mode perfectly orchestrates solar curtailment and grid export limits during Peak periods. Our virtual mode must rely purely on aggressive battery discharging, which can sometimes "fight" the native grid topology.

**Power Flow**:
```
strategy = schedule.get_strategy()  // "charge", "discharge", "grid_zero", "solar_priority"

"charge":    charge at max (solar + grid)
"discharge": discharge to cover home load
"grid_zero": → grid_zero algorithm
"solar_priority": charge from solar only, else self_consumption
```

**Validation Targets**:
- [ ] During "charge" period: battery charges
- [ ] During "discharge" period: battery discharges
- [ ] Period transition: switches behavior at boundary

---

### 6. `manual` — Direct Power Control

**Emulation Target**: Cloud API Standby/Forced Charge/Discharge  
**Emulation Fidelity**: **Full**. This directly commands the battery at a specific wattage. It is the purest and most reliable Modbus mode, completely mirroring the Cloud API's manual overrides.

**Power Flow**: `return manual_power_w`

**Validation Targets**:
- [x] Positive → CHARGING (**validated 2026-03-12**)
- [x] Negative → DISCHARGING (**validated 2026-03-12**)
- [ ] Zero → IDLE

---

## Safety Systems (All Modes)

| Safety | Trigger | Action |
|--------|---------|--------|
| **SoC Hard Limit** | SoC ≥ 99.5% or ≤ 0.5% | Block command |
| **SoC Ramp** | Within 10% of limit | Linearly reduce power |
| **Inverter Limit** | Power > 5000W | Cap at rated max |
| **Load Safety** | Home > 90% of capacity | Reduce discharge |
| **Alarm Block** | Blocking alarms active | Stop operation |

---

## Hardware Validation Plan

### Tier 2 Tests (Pre-Approved, ≤500W, ≤30s)

| # | Test | CLI Command | Expect | Verify |
|---|------|-------------|--------|--------|
| 1 | Manual charge | `--charge 500` | CHARGING | M714.DCW positive ✅ |
| 2 | Manual discharge | `--discharge 500` | DISCHARGING | M714.DCW negative ✅ |
| 3 | Manual idle | `--mode manual --power 0` | IDLE | M714.DCW ~0W |
| 4 | Self-consumption (below target) | `--mode self_consumption --target-soc 99` | CHARGING max | Grid importing |
| 5 | Self-consumption (above target) | `--mode self_consumption --target-soc 50` | DISCHARGING | Grid reduced |
| 6 | Emergency backup (below target) | `--mode emergency_backup --target-soc 99` | CHARGING | Grid importing |
| 7 | Emergency backup (above target) | `--mode emergency_backup --target-soc 50` | IDLE (0W) | No discharge |
| 8 | Grid zero | `--mode grid_zero` | Varies | M701.W near 0W |
| 9 | Peak shave (below threshold) | `--mode peak_shave` | IDLE | No battery |

### Post-Each-Test (Mandatory)
```bash
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --stop
python3 tools/franklinwh_cli.py -i YOUR_AGATE_IP --healthcheck | grep zombie_state
```
