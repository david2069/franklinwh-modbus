#!/usr/bin/env python3
"""
Robustness Re-Test v3: Fresh connection per INDIVIDUAL test.
Eliminates WiFi BrokenPipe entirely.
"""
import socket, struct, time, sys
import os
sys.path.insert(0, os.path.expanduser('~/dev/modbus/src'))

IP = '192.0.2.110'; PORT = 502; UID = 2; TO = 30

def do_test(addr, val, settle, use_fc16=False):
    """Single atomic test: connect, read, write, wait, read, close."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TO); s.connect((IP, PORT))

    # Read before
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, 1)
    s.sendall(req); r = s.recv(256)
    before = struct.unpack('>H', r[9:11])[0] if len(r) >= 11 and not (r[7] & 0x80) else 'ERR'

    time.sleep(0.2)

    # Write
    if use_fc16:
        header = struct.pack('>HHHBBHHB', 0, 0, 9, UID, 16, addr, 1, 2)
        data = struct.pack('>H', val)
        s.sendall(header + data)
    else:
        req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 6, addr, val)
        s.sendall(req)
    r = s.recv(256)
    wr_ok = not (len(r) < 8 or (r[7] & 0x80))
    if not wr_ok:
        exc = r[8] if len(r) > 8 else '?'
        wr_str = f"EXC_{exc}"
    else:
        wr_str = "OK"

    # Wait settle time
    time.sleep(settle)

    # Read after
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, 1)
    s.sendall(req); r = s.recv(256)
    after = struct.unpack('>H', r[9:11])[0] if len(r) >= 11 and not (r[7] & 0x80) else 'ERR'

    # Reset to 0
    time.sleep(0.2)
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 6, addr, 0)
    s.sendall(req); s.recv(256)

    s.close()
    return before, wr_str, after, (after == val)


def main():
    print("Robustness Re-Test v3 (atomic per-test)", flush=True)
    print("=" * 60, flush=True)

    settles = [0.5, 1.0, 2.0, 5.0]
    regs = [
        ("M704.WMaxLimPctEna", 310, [1, 2]),
        ("M704.VarSetEna",     331, [1, 2]),
        ("M715.ControllerHb",  1092,[1, 2, 100]),
        ("M702.WMax",          251, [5000, 1000, 100]),
    ]

    # ── PHASE 1: No VPP ──
    print("\nPHASE 1: No VPP", flush=True)
    p1_results = {}
    for name, addr, vals in regs:
        print(f"\n  {name} (addr {addr})", flush=True)
        results = []
        for val in vals:
            for settle in settles:
                for fc_label, fc16 in [("FC06", False), ("FC16", True)]:
                    before, wr, after, ok = do_test(addr, val, settle, fc16)
                    icon = "OK" if ok else "XX"
                    print(f"    [{icon}] {fc_label} val={val} wait={settle}s -> wr={wr} rb={after}", flush=True)
                    results.append(ok)
                    time.sleep(0.3)  # breathing room between connections
        p1_results[name] = results

    # ── PHASE 2: With VPP ──
    print("\nActivating VPP (500W charge)...", flush=True)
    from franklinwh_modbus import FranklinWHController
    from franklinwh_modbus.types import BatteryCommand, ControlMode
    ctrl = FranklinWHController(IP); ctrl.connect()
    ok, msg = ctrl.send_command(BatteryCommand(power_watts=500, mode=ControlMode.LIMIT_ABS))
    print(f"  {msg}", flush=True)
    ctrl.disconnect()
    print("  Waiting 8s...", flush=True); time.sleep(8)

    # Verify VPP
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TO); s.connect((IP, PORT))
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, 318, 1)
    s.sendall(req); r = s.recv(256)
    wse = struct.unpack('>H', r[9:11])[0]
    s.close()
    print(f"  WSetEna={wse}", flush=True)

    print("\nPHASE 2: VPP Active", flush=True)
    p2_results = {}
    for name, addr, vals in regs:
        print(f"\n  {name} (addr {addr}, VPP)", flush=True)
        results = []
        for val in vals:
            for settle in settles:
                for fc_label, fc16 in [("FC06", False), ("FC16", True)]:
                    before, wr, after, ok = do_test(addr, val, settle, fc16)
                    icon = "OK" if ok else "XX"
                    print(f"    [{icon}] {fc_label} val={val} wait={settle}s -> wr={wr} rb={after}", flush=True)
                    results.append(ok)
                    time.sleep(0.3)
        p2_results[name] = results

    # Cleanup
    print("\nCleanup: releasing VPP...", flush=True)
    ctrl2 = FranklinWHController(IP); ctrl2.connect()
    ctrl2.reset_control_state()
    bat = ctrl2.read_battery_status()
    ctl = ctrl2.read_control_status()
    mode = ctrl2.read_native_mode()
    print(f"  WSetEna={ctl.get('wset_enabled')} SoC={bat.get('soc')}% Mode={mode.get('mode_name')}", flush=True)
    ctrl2.disconnect()

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    total_pass = 0; total_tests = 0
    for phase, label in [(p1_results, "No VPP"), (p2_results, "VPP")]:
        for name in phase:
            passed = sum(1 for r in phase[name] if r)
            total = len(phase[name])
            total_pass += passed; total_tests += total
            print(f"  {name} ({label}): {passed}/{total}", flush=True)

    print(f"\n  TOTAL: {total_pass}/{total_tests} sticky", flush=True)
    print(f"  Test matrix: 4 registers x {len(settles)} settles x 2 FCs x 2 phases", flush=True)
    if total_pass == 0:
        print("  CONCLUSION: ALL tests failed", flush=True)
    print("DONE", flush=True)

if __name__ == '__main__':
    main()
