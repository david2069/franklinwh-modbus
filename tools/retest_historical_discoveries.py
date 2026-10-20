import struct
import time
import sys
import json
from datetime import datetime
from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.types import BatteryCommand

AGATE_IP = "192.0.2.110"

def raw_read(sock, addr, count=1, unit_id=1):
    """Read holding registers via raw Modbus TCP (FC3)."""
    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, addr, count)
    sock.settimeout(5.0)
    sock.sendall(req)
    resp = sock.recv(256)
    if len(resp) < 9 or (resp[7] & 0x80):
        return None
    payload = resp[9:]
    if count == 1:
        return struct.unpack('>H', payload[0:2])[0]
    else:
        return [struct.unpack('>H', payload[i*2:i*2+2])[0] for i in range(count)]

def raw_write(sock, addr, value, unit_id=1):
    """Write single register via raw Modbus TCP (FC6)."""
    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 6, addr, value)
    sock.settimeout(5.0)
    sock.sendall(req)
    resp = sock.recv(256)
    if len(resp) < 8 or (resp[7] & 0x80):
        return False
    return True

def log_test(name, result, notes=""):
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"[{status}] {name} | {notes}")

def main():
    print(f"--- [HISTORICAL RE-TEST SUITE] ---")
    print(f"Target: {AGATE_IP}")
    print(f"Date:   {datetime.now().isoformat()}")
    
    ctrl = FranklinWHController(AGATE_IP, unit_id=1)
    ctrl.connect()
    sock = ctrl.dev.client.socket
    
    # 1. Unit ID Aliasing Check (2026-03-15)
    print("\n[1] UID Aliasing (UID 1 vs 2)...")
    val1 = raw_read(sock, 0, 2, unit_id=1) # "SunS"
    val2 = raw_read(sock, 0, 2, unit_id=2)
    aliased = (val1 == val2)
    log_test("UID Aliasing", aliased, f"UID1={val1}, UID2={val2}")
    
    # 2. M801 Scan (2026-03-15)
    print("\n[2] M801 Battery Model Presence...")
    m801 = ctrl.dev.models.get(801)
    log_test("M801 Absence", m801 is None, "Model 801 not found in chain")
    
    # 3. Discard Probes (P1-P4)
    print("\n[3] Discard Probes (P1-P4 Registers)...")
    tests = [
        ("ControllerHb (1092)", 1092, 123),
        ("WMaxLimPct (311)", 311, 500),
        ("VarSet (334)", 334, 100),
        ("WMax (251)", 251, 5000),
    ]
    for label, addr, test_val in tests:
        baseline = raw_read(sock, addr)
        raw_write(sock, addr, test_val)
        time.sleep(0.5)
        after = raw_read(sock, addr)
        discarded = (after == baseline)
        log_test(label, discarded, f"Base={baseline}, Wrote={test_val}, After={after} (Discarded)")
        
    # 4. PFWInjEna (Power Factor) - The only writable one besides M704
    print("\n[4] PFWInjEna (Power Factor) Writability...")
    pf_ena = raw_read(sock, 298)
    if pf_ena is not None:
        new_val = 1 if pf_ena == 0 else 0
        raw_write(sock, 298, new_val)
        time.sleep(0.5)
        after = raw_read(sock, 298)
        sticky = (after == new_val)
        log_test("PFWInjEna Sticky", sticky, f"Base={pf_ena}, Wrote={new_val}, After={after}")
        # Restore
        raw_write(sock, 298, pf_ena)
        
    # 5. Reversion Efficacy (2026-05-14)
    print("\n[5] Reversion Efficacy (30s Dead-man Test)...")
    print("  Activating Remote Control (500W standby)...")
    ctrl.send_command(BatteryCommand(power_watts=0), duration_s=60) # duration_s=60 is software timeout
    
    # Set hardware timer
    raw_write(sock, 327, 30) # WSetRvrtTms = 30s
    raw_write(sock, 326, 1)  # WSetEnaRvrt = 1
    
    time.sleep(5)
    rem = raw_read(sock, 329)
    print(f"  T+5s: WSetEna={raw_read(sock, 318)}, WSetRvrtRem={rem}")
    
    print("  Waiting 40s for expiry...")
    time.sleep(35)
    
    final_ena = raw_read(sock, 318)
    final_rem = raw_read(sock, 329)
    
    efficacy_fail = (final_ena == 1 and final_rem == 0)
    log_test("Reversion Cosmetic", efficacy_fail, f"Final Ena={final_ena}, Rem={final_rem} (DID NOT STOP)")
    
    # Cleanup
    ctrl.reset_control_state()
    print("  Cleaned up.")
    
    # 6. 15000 Correlation (SoC vs SoH)
    print("\n[6] 15000 Correlation (SoC vs SoH)...")
    soc_hr = raw_read(sock, 15035) # High-res SoC
    soh_raw = raw_read(sock, 15036) # SoH
    
    # Get standard SoC from controller
    status = ctrl.read_battery_status()
    std_soc = status.get('soc', 0)
    
    match = (abs(std_soc - soc_hr/10) < 5.0)
    log_test("SoC Correlation", match, f"StdSoC={std_soc}%, HighRes={soc_hr/10}%")
    log_test("SoH Readback", (soh_raw > 900 and soh_raw < 1000), f"SoH={soh_raw/10}%")
    
    ctrl.disconnect()
    print("\n--- [RE-TEST COMPLETE] ---")

if __name__ == "__main__":
    main()
