#!/usr/bin/env python3
"""
SunSpec 6-Phase Sequencing Re-Test Suite
========================================

Re-tests all previously "non-functional" registers using proper SunSpec
phased protocol with correct timing:

  Phase 0: Pre-flight reads (scale factors, limits, current state)
  Phase 1: Configure mode (200ms settle)
  Phase 2: Safety / reversion (100ms between writes)
  Phase 3: Write setpoint
  Phase 4: Enable — "go" trigger (200ms before, 500ms after)
  Phase 5: Verify readback

Groups tested:
  A: VarSet (reactive power) — validation baseline
  B: WMaxLimPct (max power limit)
  C: WSetRvrtTms + ControllerHb (lifecycle, requires VPP active)
  D: WChaRteMax / WDisChaRteMax (PCS rate limits)

SAFETY: Uses safe values (0 Var, 100% max, nameplate rates).
        500W charge for VPP activation (Tier 2).
"""

import sys
import struct
import time
import json
from datetime import datetime

import os
sys.path.insert(0, os.path.expanduser('~/dev/modbus/src'))
from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.types import BatteryCommand, ControlMode

AGATE_IP = sys.argv[1] if len(sys.argv) > 1 else '192.0.2.110'
UNIT_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 1

# Timing constants (ms → seconds)
SETTLE_MODE = 0.3       # After mode register writes
SETTLE_SAFETY = 0.2     # Between reversion writes
SETTLE_PRE_ENA = 0.3    # Before enable (go trigger)
SETTLE_POST_ENA = 0.8   # After enable (device processing)
SETTLE_INTER_OP = 0.2   # Between individual register R/W
SETTLE_GROUP = 3.0       # Between test groups
SETTLE_VPP = 6.0         # After VPP activation


def raw_read(sock, addr, count=1, unit_id=UNIT_ID):
    """Read register(s) via raw Modbus TCP at base-1 address."""
    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, addr, count)
    sock.settimeout(10)
    sock.sendall(req)
    resp = sock.recv(256)
    if len(resp) < 9 or (resp[7] & 0x80):
        return None
    byte_count = resp[8]
    if count == 1:
        return struct.unpack('>H', resp[9:11])[0]
    else:
        vals = []
        for i in range(count):
            vals.append(struct.unpack('>H', resp[9 + i*2:11 + i*2])[0])
        return vals


def raw_write(sock, addr, value, unit_id=UNIT_ID):
    """Write single register via raw Modbus TCP at base-1 address."""
    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 6, addr, value)
    sock.settimeout(10)
    sock.sendall(req)
    resp = sock.recv(256)
    if len(resp) < 8 or (resp[7] & 0x80):
        exc = resp[8] if len(resp) > 8 else '?'
        return f"EXCEPTION_{exc}"
    return True


def raw_write_multi(sock, addr, values, unit_id=UNIT_ID):
    """Write multiple registers via FC16 at base-1 address."""
    count = len(values)
    byte_count = count * 2
    # FC16: unit, func=16, start_addr, count, byte_count, then data
    header = struct.pack('>HHHBBHHB', 0, 0, 7 + byte_count, unit_id, 16, addr, count, byte_count)
    data = b''.join(struct.pack('>H', v) for v in values)
    sock.settimeout(10)
    sock.sendall(header + data)
    resp = sock.recv(256)
    if len(resp) < 8 or (resp[7] & 0x80):
        exc = resp[8] if len(resp) > 8 else '?'
        return f"EXCEPTION_{exc}"
    return True


def phase_log(phase, msg):
    """Log with phase prefix."""
    print(f"   [{phase}] {msg}")


def separator(title):
    print(f"\n{'━'*70}")
    print(f"  {title}")
    print(f"{'━'*70}")


# ═══════════════════════════════════════════════════════════════════
# GROUP A: VarSet (Reactive Power) — Validation Baseline
# ═══════════════════════════════════════════════════════════════════
def test_group_a(sock):
    """Test VarSet group following 6-phase protocol."""
    separator("GROUP A: VarSet (Reactive Power) — Validation Baseline")
    results = {}

    # Phase 0: Pre-flight reads
    phase_log("P0", "Pre-flight reads...")
    time.sleep(SETTLE_INTER_OP)
    var_sf = raw_read(sock, 273)  # Var_SF
    time.sleep(SETTLE_INTER_OP)
    var_max_inj = raw_read(sock, 257)  # VarMaxInj
    time.sleep(SETTLE_INTER_OP)
    var_max_abs = raw_read(sock, 258)  # VarMaxAbs
    time.sleep(SETTLE_INTER_OP)
    var_set_ena = raw_read(sock, 331)  # VarSetEna
    time.sleep(SETTLE_INTER_OP)
    var_set_mod = raw_read(sock, 332)  # VarSetMod
    time.sleep(SETTLE_INTER_OP)
    var_set_pri = raw_read(sock, 333)  # VarSetPri
    time.sleep(SETTLE_INTER_OP)
    var_set = raw_read(sock, 334, 2)  # VarSet (int32, 2 regs)

    phase_log("P0", f"Var_SF={var_sf}  VarMaxInj={var_max_inj}  VarMaxAbs={var_max_abs}")
    phase_log("P0", f"VarSetEna={var_set_ena}  VarSetMod={var_set_mod}  VarSetPri={var_set_pri}")
    phase_log("P0", f"VarSet(raw)={var_set}")
    results['phase0'] = {
        'Var_SF': var_sf, 'VarMaxInj': var_max_inj, 'VarMaxAbs': var_max_abs,
        'VarSetEna': var_set_ena, 'VarSetMod': var_set_mod, 'VarSetPri': var_set_pri,
        'VarSet': var_set
    }

    # Phase 1: Configure mode
    phase_log("P1", "Configure mode: VarSetMod=1(abs), VarSetPri=2...")
    time.sleep(SETTLE_INTER_OP)
    r1 = raw_write_multi(sock, 332, [0x0001, 0x0002])  # VarSetMod=1, VarSetPri=2
    phase_log("P1", f"Write VarSetMod+VarSetPri: {r1}")
    time.sleep(SETTLE_MODE)

    # Read back mode
    mod_rb = raw_read(sock, 332)
    time.sleep(SETTLE_INTER_OP)
    pri_rb = raw_read(sock, 333)
    phase_log("P1", f"Readback: VarSetMod={mod_rb} VarSetPri={pri_rb}")
    results['phase1'] = {'VarSetMod_write': r1, 'VarSetMod_rb': mod_rb, 'VarSetPri_rb': pri_rb}

    # Phase 2: Safety — skip reversion for this baseline test (write 0 Var setpoint = safe)

    # Phase 3: Write setpoint (0 Var = safe/neutral)
    phase_log("P3", "Write VarSet=0 (safe, 0 Var)...")
    time.sleep(SETTLE_INTER_OP)
    r3 = raw_write_multi(sock, 334, [0x0000, 0x0000])  # VarSet=0 (int32)
    phase_log("P3", f"Write VarSet=0: {r3}")
    time.sleep(SETTLE_PRE_ENA)

    # Read back setpoint
    vs_rb = raw_read(sock, 334, 2)
    phase_log("P3", f"VarSet readback: {vs_rb}")
    results['phase3'] = {'VarSet_write': r3, 'VarSet_rb': vs_rb}

    # Phase 4: Enable (the "go" trigger — LAST)
    phase_log("P4", "ENABLE: VarSetEna=1 (go trigger)...")
    time.sleep(SETTLE_PRE_ENA)
    r4 = raw_write(sock, 331, 1)  # VarSetEna=1
    phase_log("P4", f"Write VarSetEna=1: {r4}")
    time.sleep(SETTLE_POST_ENA)

    # Phase 5: Verify
    phase_log("P5", "Verify readback...")
    time.sleep(SETTLE_INTER_OP)
    ena_rb = raw_read(sock, 331)
    time.sleep(SETTLE_INTER_OP)
    vs_rb2 = raw_read(sock, 334, 2)
    phase_log("P5", f"VarSetEna readback: {ena_rb} {'✅ ACCEPTED!' if ena_rb == 1 else '❌ NOT ACCEPTED'}")
    phase_log("P5", f"VarSet readback: {vs_rb2}")
    results['phase5'] = {'VarSetEna_rb': ena_rb, 'VarSet_rb': vs_rb2}

    # Cleanup: disable VarSet
    phase_log("--", "Cleanup: VarSetEna=0...")
    time.sleep(SETTLE_INTER_OP)
    raw_write(sock, 331, 0)
    time.sleep(SETTLE_MODE)
    ena_final = raw_read(sock, 331)
    phase_log("--", f"VarSetEna final: {ena_final}")
    results['cleanup'] = {'VarSetEna_final': ena_final}

    accepted = (ena_rb == 1)
    print(f"\n   GROUP A RESULT: {'✅ VarSetEna ACCEPTED' if accepted else '❌ VarSetEna NOT ACCEPTED'}")
    results['accepted'] = accepted
    return results


# ═══════════════════════════════════════════════════════════════════
# GROUP B: WMaxLimPct (Max Power Limit)
# ═══════════════════════════════════════════════════════════════════
def test_group_b(sock):
    """Test WMaxLimPct following 6-phase protocol."""
    separator("GROUP B: WMaxLimPct (Max Power Limit)")
    results = {}

    # Phase 0: Pre-flight
    phase_log("P0", "Pre-flight reads...")
    time.sleep(SETTLE_INTER_OP)
    sf = raw_read(sock, 350)  # WMaxLimPct_SF
    time.sleep(SETTLE_INTER_OP)
    pct = raw_read(sock, 311)  # WMaxLimPct
    time.sleep(SETTLE_INTER_OP)
    ena = raw_read(sock, 310)  # WMaxLimPctEna
    time.sleep(SETTLE_INTER_OP)
    rvrt = raw_read(sock, 312)  # WMaxLimPctRvrt
    time.sleep(SETTLE_INTER_OP)
    rvrt_ena = raw_read(sock, 313)  # WMaxLimPctEnaRvrt

    phase_log("P0", f"WMaxLimPct_SF={sf}  WMaxLimPct={pct}  WMaxLimPctEna={ena}")
    phase_log("P0", f"WMaxLimPctRvrt={rvrt}  WMaxLimPctEnaRvrt={rvrt_ena}")
    results['phase0'] = {'SF': sf, 'Pct': pct, 'Ena': ena, 'Rvrt': rvrt, 'RvrtEna': rvrt_ena}

    # Phase 1: No separate mode register for this group

    # Phase 2: Safety — write reversion values
    phase_log("P2", "Safety: WMaxLimPctRvrt=1000 (100%), WMaxLimPctEnaRvrt=1...")
    time.sleep(SETTLE_INTER_OP)
    r2a = raw_write(sock, 312, 1000)  # 100% with SF=-1 → safe
    phase_log("P2", f"Write WMaxLimPctRvrt=1000: {r2a}")
    time.sleep(SETTLE_SAFETY)
    r2b = raw_write(sock, 313, 1)  # Enable reversion
    phase_log("P2", f"Write WMaxLimPctEnaRvrt=1: {r2b}")
    time.sleep(SETTLE_MODE)

    # Readback reversion
    rvrt_rb = raw_read(sock, 312)
    time.sleep(SETTLE_INTER_OP)
    rvrt_ena_rb = raw_read(sock, 313)
    phase_log("P2", f"Readback: Rvrt={rvrt_rb}  RvrtEna={rvrt_ena_rb}")
    results['phase2'] = {'Rvrt_write': r2a, 'RvrtEna_write': r2b, 'Rvrt_rb': rvrt_rb, 'RvrtEna_rb': rvrt_ena_rb}

    # Phase 3: Setpoint — 100% (safe, no actual limiting)
    phase_log("P3", "Setpoint: WMaxLimPct=1000 (100%, safe)...")
    time.sleep(SETTLE_INTER_OP)
    r3 = raw_write(sock, 311, 1000)  # 100%  (SF=-1 → 100.0%)
    phase_log("P3", f"Write WMaxLimPct=1000: {r3}")
    time.sleep(SETTLE_PRE_ENA)

    pct_rb = raw_read(sock, 311)
    phase_log("P3", f"WMaxLimPct readback: {pct_rb}")
    results['phase3'] = {'WMaxLimPct_write': r3, 'WMaxLimPct_rb': pct_rb}

    # Phase 4: Enable
    phase_log("P4", "ENABLE: WMaxLimPctEna=1...")
    time.sleep(SETTLE_PRE_ENA)
    r4 = raw_write(sock, 310, 1)
    phase_log("P4", f"Write WMaxLimPctEna=1: {r4}")
    time.sleep(SETTLE_POST_ENA)

    # Phase 5: Verify
    phase_log("P5", "Verify readback...")
    time.sleep(SETTLE_INTER_OP)
    ena_rb = raw_read(sock, 310)
    time.sleep(SETTLE_INTER_OP)
    pct_rb2 = raw_read(sock, 311)
    phase_log("P5", f"WMaxLimPctEna readback: {ena_rb} {'✅ ACCEPTED!' if ena_rb == 1 else '❌ NOT ACCEPTED'}")
    phase_log("P5", f"WMaxLimPct readback: {pct_rb2}")
    results['phase5'] = {'Ena_rb': ena_rb, 'Pct_rb': pct_rb2}

    # Cleanup
    phase_log("--", "Cleanup: WMaxLimPctEna=0...")
    time.sleep(SETTLE_INTER_OP)
    raw_write(sock, 310, 0)
    time.sleep(SETTLE_MODE)
    ena_final = raw_read(sock, 310)
    phase_log("--", f"WMaxLimPctEna final: {ena_final}")
    results['cleanup'] = {'Ena_final': ena_final}

    accepted = (ena_rb == 1)
    print(f"\n   GROUP B RESULT: {'✅ WMaxLimPctEna ACCEPTED' if accepted else '❌ WMaxLimPctEna NOT ACCEPTED'}")
    results['accepted'] = accepted
    return results


# ═══════════════════════════════════════════════════════════════════
# GROUP C: WSetRvrtTms + ControllerHb (Lifecycle — requires VPP)
# ═══════════════════════════════════════════════════════════════════
def test_group_c(ctrl, sock):
    """Test WSetRvrtTms and ControllerHb with VPP active."""
    separator("GROUP C: Lifecycle (WSetRvrtTms + ControllerHb) — VPP Required")
    results = {}

    # Phase 0: Pre-flight
    phase_log("P0", "Pre-flight reads...")
    time.sleep(SETTLE_INTER_OP)
    wset_ena = raw_read(sock, 318)       # WSetEna
    time.sleep(SETTLE_INTER_OP)
    wset_rvrt_tms = raw_read(sock, 327, 2)  # WSetRvrtTms (uint32)
    time.sleep(SETTLE_INTER_OP)
    wset_rvrt_rem = raw_read(sock, 329, 2)  # WSetRvrtRem (uint32)
    time.sleep(SETTLE_INTER_OP)
    ctrl_hb = raw_read(sock, 1092)       # ControllerHb (M715, base-1)
    time.sleep(SETTLE_INTER_OP)
    der_hb = raw_read(sock, 1093)        # DERHb (M715, base-1)

    phase_log("P0", f"WSetEna={wset_ena}  WSetRvrtTms={wset_rvrt_tms}  WSetRvrtRem={wset_rvrt_rem}")
    phase_log("P0", f"ControllerHb={ctrl_hb}  DERHb={der_hb}")
    results['phase0'] = {
        'WSetEna': wset_ena, 'WSetRvrtTms': wset_rvrt_tms,
        'WSetRvrtRem': wset_rvrt_rem, 'ControllerHb': ctrl_hb, 'DERHb': der_hb
    }

    # Activate VPP with 500W charge (Tier 2)
    phase_log("VPP", "Activating VPP Mode: 500W charge...")
    cmd = BatteryCommand(power_watts=500, mode=ControlMode.LIMIT_ABS)
    success, msg = ctrl.send_command(cmd)
    phase_log("VPP", f"send_command(500W): {'✅' if success else '❌'} {msg}")
    phase_log("VPP", f"Waiting {SETTLE_VPP}s for VPP activation...")
    time.sleep(SETTLE_VPP)

    time.sleep(SETTLE_INTER_OP)
    wset_ena2 = raw_read(sock, 318)
    phase_log("VPP", f"WSetEna={wset_ena2} {'✅ VPP active' if wset_ena2 == 1 else '❌ NOT active'}")
    results['vpp'] = {'WSetEna': wset_ena2, 'cmd_ok': success}

    if wset_ena2 != 1:
        phase_log("VPP", "❌ VPP not active — skipping lifecycle tests")
        ctrl.reset_control_state()
        results['accepted_rvrt'] = False
        results['accepted_hb'] = False
        return results

    # Phase 1: Mode is already set via send_command (WSetMod, WSetPct)
    # Phase 2: Write WSetRvrtTms (the reversion timer)
    phase_log("P2", "Safety: WSetRvrtTms=60 (60 seconds timeout)...")
    time.sleep(SETTLE_INTER_OP)
    r_tms = raw_write_multi(sock, 327, [0x0000, 60])  # uint32 = 60 seconds
    phase_log("P2", f"Write WSetRvrtTms=60: {r_tms}")
    time.sleep(SETTLE_SAFETY)

    # Readback
    tms_rb = raw_read(sock, 327, 2)
    phase_log("P2", f"WSetRvrtTms readback: {tms_rb}")
    tms_accepted = (tms_rb is not None and (tms_rb == [0, 60] or tms_rb == [0x0000, 60]))

    # Phase 2b: Enable reversion (WSetEnaRvrt)
    phase_log("P2", "Enable reversion: WSetEnaRvrt=1...")
    time.sleep(SETTLE_INTER_OP)
    r_rvrt_ena = raw_write(sock, 326, 1)  # WSetEnaRvrt
    phase_log("P2", f"Write WSetEnaRvrt=1: {r_rvrt_ena}")
    time.sleep(SETTLE_SAFETY)

    rvrt_ena_rb = raw_read(sock, 326)
    phase_log("P2", f"WSetEnaRvrt readback: {rvrt_ena_rb}")
    results['phase2_rvrt'] = {
        'RvrtTms_write': r_tms, 'RvrtTms_rb': tms_rb, 'RvrtTms_accepted': tms_accepted,
        'RvrtEna_write': r_rvrt_ena, 'RvrtEna_rb': rvrt_ena_rb
    }

    # Now check WSetRvrtRem — is it counting down?
    phase_log("P5", "Checking WSetRvrtRem countdown...")
    time.sleep(2.0)  # Wait 2 seconds
    time.sleep(SETTLE_INTER_OP)
    rem1 = raw_read(sock, 329, 2)
    phase_log("P5", f"WSetRvrtRem (after 2s): {rem1}")
    time.sleep(3.0)  # Wait 3 more seconds
    time.sleep(SETTLE_INTER_OP)
    rem2 = raw_read(sock, 329, 2)
    phase_log("P5", f"WSetRvrtRem (after 5s): {rem2}")

    counting = (rem1 is not None and rem2 is not None and rem1 != rem2 and rem1 != [0, 0])
    phase_log("P5", f"Countdown active: {'✅ YES!' if counting else '❌ NO'}")
    results['phase5_rvrt'] = {'rem_2s': rem1, 'rem_5s': rem2, 'counting': counting}

    # Test ControllerHb
    phase_log("HB", "Testing ControllerHb write (M715 base-1 addr 1092)...")
    time.sleep(SETTLE_INTER_OP)
    hb_before = raw_read(sock, 1092)
    phase_log("HB", f"ControllerHb before: {hb_before}")
    time.sleep(SETTLE_INTER_OP)
    hb_write = raw_write(sock, 1092, 1)  # Write heartbeat = 1
    phase_log("HB", f"Write ControllerHb=1: {hb_write}")
    time.sleep(SETTLE_POST_ENA)

    hb_after = raw_read(sock, 1092)
    hb_sticky = (hb_after == 1)
    phase_log("HB", f"ControllerHb after: {hb_after} {'✅ ACCEPTED!' if hb_sticky else '❌ discarded'}")

    # Check DERHb response
    time.sleep(SETTLE_INTER_OP)
    der_hb2 = raw_read(sock, 1093)
    phase_log("HB", f"DERHb after: {der_hb2} (was {der_hb})")
    results['heartbeat'] = {
        'before': hb_before, 'write': hb_write, 'after': hb_after,
        'sticky': hb_sticky, 'DERHb_after': der_hb2
    }

    # Cleanup: release VPP
    phase_log("--", "Cleanup: releasing VPP...")
    ctrl.reset_control_state()
    time.sleep(SETTLE_GROUP)
    time.sleep(SETTLE_INTER_OP)
    wset_ena_final = raw_read(sock, 318)
    phase_log("--", f"WSetEna final: {wset_ena_final}")

    results['accepted_rvrt'] = tms_accepted
    results['accepted_hb'] = hb_sticky
    print(f"\n   GROUP C RESULTS:")
    print(f"     WSetRvrtTms: {'✅ ACCEPTED' if tms_accepted else '❌ NOT ACCEPTED'}")
    print(f"     Countdown:   {'✅ ACTIVE' if counting else '❌ NOT COUNTING'}")
    print(f"     ControllerHb: {'✅ ACCEPTED' if hb_sticky else '❌ NOT ACCEPTED'}")
    return results


# ═══════════════════════════════════════════════════════════════════
# GROUP D: WChaRteMax / WDisChaRteMax (PCS Rate Limits)
# ═══════════════════════════════════════════════════════════════════
def test_group_d(ctrl, sock):
    """Test PCS rate registers with VPP active and proper sequencing."""
    separator("GROUP D: WChaRteMax / WDisChaRteMax (PCS Rate Limits)")
    results = {}

    # Phase 0: Pre-flight
    phase_log("P0", "Pre-flight reads...")
    time.sleep(SETTLE_INTER_OP)
    w_sf = raw_read(sock, 270)  # W_SF (M702)
    time.sleep(SETTLE_INTER_OP)
    cha_rtg = raw_read(sock, 235)  # WChaRteMaxRtg
    time.sleep(SETTLE_INTER_OP)
    dis_rtg = raw_read(sock, 236)  # WDisChaRteMaxRtg
    time.sleep(SETTLE_INTER_OP)
    cha_max = raw_read(sock, 259)  # WChaRteMax
    time.sleep(SETTLE_INTER_OP)
    dis_max = raw_read(sock, 260)  # WDisChaRteMax
    time.sleep(SETTLE_INTER_OP)
    wmax = raw_read(sock, 251)  # WMax (M702 capacity setting)

    phase_log("P0", f"W_SF={w_sf}  WChaRteMaxRtg={cha_rtg}  WDisChaRteMaxRtg={dis_rtg}")
    phase_log("P0", f"WChaRteMax={cha_max} (0x{cha_max:04X})" if cha_max else f"WChaRteMax={cha_max}")
    phase_log("P0", f"WDisChaRteMax={dis_max} (0x{dis_max:04X})" if dis_max else f"WDisChaRteMax={dis_max}")
    phase_log("P0", f"WMax={wmax}")
    results['phase0'] = {
        'W_SF': w_sf, 'ChaRtg': cha_rtg, 'DisRtg': dis_rtg,
        'ChaMax': cha_max, 'DisMax': dis_max, 'WMax': wmax
    }

    # First activate VPP
    phase_log("VPP", "Activating VPP Mode: 500W charge...")
    cmd = BatteryCommand(power_watts=500, mode=ControlMode.LIMIT_ABS)
    success, msg = ctrl.send_command(cmd)
    phase_log("VPP", f"send_command(500W): {'✅' if success else '❌'} {msg}")
    time.sleep(SETTLE_VPP)

    time.sleep(SETTLE_INTER_OP)
    wset_ena = raw_read(sock, 318)
    phase_log("VPP", f"WSetEna={wset_ena}")

    # Phase 1: Set WMax capacity first (may be a prerequisite)
    phase_log("P1", "Configure: WMax=5000 (capacity setting)...")
    time.sleep(SETTLE_INTER_OP)
    r1 = raw_write(sock, 251, 5000)
    phase_log("P1", f"Write WMax=5000: {r1}")
    time.sleep(SETTLE_MODE)
    wmax_rb = raw_read(sock, 251)
    phase_log("P1", f"WMax readback: {wmax_rb}")
    results['phase1'] = {'WMax_write': r1, 'WMax_rb': wmax_rb}

    # Phase 3: Write setpoints (safe = nameplate values)
    phase_log("P3", "Setpoints: WChaRteMax=5000, WDisChaRteMax=5000...")
    time.sleep(SETTLE_INTER_OP)
    r3a = raw_write(sock, 259, 5000)  # WChaRteMax
    phase_log("P3", f"Write WChaRteMax=5000: {r3a}")
    time.sleep(SETTLE_INTER_OP)
    r3b = raw_write(sock, 260, 5000)  # WDisChaRteMax
    phase_log("P3", f"Write WDisChaRteMax=5000: {r3b}")
    time.sleep(SETTLE_POST_ENA)

    # Phase 5: Verify
    phase_log("P5", "Verify readback...")
    time.sleep(SETTLE_INTER_OP)
    cha_rb = raw_read(sock, 259)
    time.sleep(SETTLE_INTER_OP)
    dis_rb = raw_read(sock, 260)
    cha_sticky = (cha_rb == 5000)
    dis_sticky = (dis_rb == 5000)
    phase_log("P5", f"WChaRteMax: {cha_rb} {'(0x{:04X})'.format(cha_rb) if cha_rb else ''} {'✅ STICKY!' if cha_sticky else '❌ discarded'}")
    phase_log("P5", f"WDisChaRteMax: {dis_rb} {'(0x{:04X})'.format(dis_rb) if dis_rb else ''} {'✅ STICKY!' if dis_sticky else '❌ discarded'}")
    results['phase5'] = {'ChaMax_rb': cha_rb, 'DisMax_rb': dis_rb, 'cha_sticky': cha_sticky, 'dis_sticky': dis_sticky}

    # Cleanup
    phase_log("--", "Cleanup: releasing VPP + restoring WMax...")
    time.sleep(SETTLE_INTER_OP)
    raw_write(sock, 251, 0)  # Restore WMax
    ctrl.reset_control_state()
    time.sleep(SETTLE_GROUP)

    accepted = cha_sticky or dis_sticky
    print(f"\n   GROUP D RESULT: {'✅ PCS REGISTERS WRITABLE!' if accepted else '❌ PCS registers still NOT writable'}")
    results['accepted'] = accepted
    return results


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    print(f"{'═'*70}")
    print(f"  SunSpec 6-Phase Sequencing Re-Test Suite")
    print(f"  Device: {AGATE_IP}  Unit ID: {UNIT_ID}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S AEDT')}")
    print(f"{'═'*70}")

    ctrl = FranklinWHController(AGATE_IP)
    ctrl.connect()
    sock = ctrl.dev.client.socket
    fw = ctrl.firmware_version if hasattr(ctrl, 'firmware_version') else 'unknown'
    print(f"  Firmware: {fw}")

    all_results = {'date': datetime.now().isoformat(), 'device': AGATE_IP, 'firmware': fw}

    # ── GROUP A ──
    all_results['group_a'] = test_group_a(sock)
    time.sleep(SETTLE_GROUP)

    # ── GROUP B ──
    all_results['group_b'] = test_group_b(sock)
    time.sleep(SETTLE_GROUP)

    # ── GROUP C ── (needs VPP)
    all_results['group_c'] = test_group_c(ctrl, sock)
    time.sleep(SETTLE_GROUP)

    # ── GROUP D ── (needs VPP)
    all_results['group_d'] = test_group_d(ctrl, sock)
    time.sleep(SETTLE_GROUP)

    # ── FINAL SAFETY CHECK ──
    separator("FINAL SAFETY CHECK")
    time.sleep(SETTLE_INTER_OP)
    ctrl.reset_control_state()
    time.sleep(2)
    bat = ctrl.read_battery_status()
    ctl_status = ctrl.read_control_status()
    mode = ctrl.read_native_mode()
    print(f"  WSetEna:       {ctl_status.get('wset_enabled')} (expect 0)")
    print(f"  Battery SoC:   {bat.get('soc')}%")
    print(f"  Battery State: {bat.get('battery_state')}")
    print(f"  Native Mode:   {mode.get('mode_name')}")

    ctrl.disconnect()

    # ── SUMMARY ──
    print(f"\n{'═'*70}")
    print(f"  SUMMARY — SunSpec 6-Phase Sequencing Results")
    print(f"{'═'*70}")
    summary = [
        ('A: VarSetEna (reactive power)', all_results['group_a'].get('accepted', False)),
        ('B: WMaxLimPctEna (max power limit)', all_results['group_b'].get('accepted', False)),
        ('C: WSetRvrtTms (reversion timer)', all_results['group_c'].get('accepted_rvrt', False)),
        ('C: ControllerHb (heartbeat)', all_results['group_c'].get('accepted_hb', False)),
        ('D: WChaRteMax (PCS charge rate)', all_results['group_d'].get('accepted', False)),
    ]
    for label, accepted in summary:
        print(f"  {'✅' if accepted else '❌'} {label}")

    any_new = any(accepted for _, accepted in summary)
    if any_new:
        print(f"\n  🚨 NEW FINDINGS — some registers work with proper sequencing!")
    else:
        print(f"\n  ❌ No change — all registers remain non-functional even with proper protocol")

    # Save results
    results_path = '/tmp/sunspec_phased_retest_results.json'
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved: {results_path}")


if __name__ == '__main__':
    main()
