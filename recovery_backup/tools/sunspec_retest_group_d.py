#!/usr/bin/env python3
"""Group D: PCS Rate Limits re-test with proper SunSpec sequencing.

Run with: python3 -u tools/sunspec_retest_group_d.py
Pre-req: python3 tools/franklinwh_cli.py -i 192.0.2.110 --stop
"""
import socket, struct, time, sys
import os
sys.path.insert(0, os.path.expanduser('~/dev/modbus/src'))

print("Group D: PCS Rate Limits (raw socket, 30s timeout)", flush=True)
print("=" * 60, flush=True)

IP = '192.0.2.110'
PORT = 502
UID = 2
TO = 30

def connect():
    print(f"Connecting to {IP}:{PORT}...", flush=True)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TO)
    s.connect((IP, PORT))
    print("Connected!", flush=True)
    return s

def rd(s, addr, n=1):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, n)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    if len(r) < 9 or (r[7] & 0x80): return None
    if n == 1: return struct.unpack('>H', r[9:11])[0]
    return [struct.unpack('>H', r[9+i*2:11+i*2])[0] for i in range(n)]

def wr(s, addr, val):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 6, addr, val)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    return not (len(r) < 8 or (r[7] & 0x80))

# Phase 0: Pre-flight (raw socket, no library overhead)
s = connect()
print("[P0] Reading PCS registers...", flush=True)
time.sleep(0.5); cha = rd(s, 259)
time.sleep(0.5); dis = rd(s, 260)
time.sleep(0.5); wmax = rd(s, 251)
if cha is not None:
    print(f"  WChaRteMax={cha} (0x{cha:04X})", flush=True)
else:
    print(f"  WChaRteMax={cha}", flush=True)
if dis is not None:
    print(f"  WDisChaRteMax={dis} (0x{dis:04X})", flush=True)
else:
    print(f"  WDisChaRteMax={dis}", flush=True)
print(f"  WMax={wmax}", flush=True)
s.close()

# VPP activation via library (handles SunSpec model scan)
print("[VPP] Activating 500W charge via library...", flush=True)
from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.types import BatteryCommand, ControlMode
ctrl = FranklinWHController(IP)
ctrl.connect()
cmd = BatteryCommand(power_watts=500, mode=ControlMode.LIMIT_ABS)
ok, msg = ctrl.send_command(cmd)
print(f"  {msg}", flush=True)
ctrl.disconnect()

print("  Waiting 8s for VPP settling...", flush=True)
time.sleep(8)

# Phase 1-5: Fresh socket for register tests
s2 = connect()
time.sleep(0.5); wse = rd(s2, 318)
print(f"  WSetEna={wse}", flush=True)

print("[P1] WMax=5000...", flush=True)
time.sleep(0.5); wr(s2, 251, 5000)
time.sleep(0.5); print(f"  WMax rb: {rd(s2, 251)}", flush=True)

print("[P3] WChaRteMax=5000...", flush=True)
time.sleep(0.5); wr(s2, 259, 5000)
print("[P3] WDisChaRteMax=5000...", flush=True)
time.sleep(0.5); wr(s2, 260, 5000)
time.sleep(1.0)

print("[P5] Readback...", flush=True)
time.sleep(0.5); c = rd(s2, 259)
time.sleep(0.5); d = rd(s2, 260)
if c is not None:
    print(f"  WChaRteMax: {c} (0x{c:04X})", flush=True)
else:
    print(f"  WChaRteMax: {c}", flush=True)
if d is not None:
    print(f"  WDisChaRteMax: {d} (0x{d:04X})", flush=True)
else:
    print(f"  WDisChaRteMax: {d}", flush=True)
print(f"  ChaRte sticky: {'YES!' if c == 5000 else 'NO'}", flush=True)
print(f"  DisRte sticky: {'YES!' if d == 5000 else 'NO'}", flush=True)

print("[P3b] VAChaRteMax=5800, VADisChaRteMax=5800...", flush=True)
time.sleep(0.5); wr(s2, 261, 5800)
time.sleep(0.5); wr(s2, 262, 5800)
time.sleep(1.0)
time.sleep(0.5); va_c = rd(s2, 261)
time.sleep(0.5); va_d = rd(s2, 262)
if va_c is not None:
    print(f"  VAChaRteMax: {va_c} (0x{va_c:04X})", flush=True)
else:
    print(f"  VAChaRteMax: {va_c}", flush=True)
if va_d is not None:
    print(f"  VADisChaRteMax: {va_d} (0x{va_d:04X})", flush=True)
else:
    print(f"  VADisChaRteMax: {va_d}", flush=True)
s2.close()

# Cleanup via library
print("[--] Cleanup: releasing VPP...", flush=True)
ctrl2 = FranklinWHController(IP)
ctrl2.connect()
ctrl2.reset_control_state()
sock3 = ctrl2.dev.client.socket
time.sleep(0.5); wr(sock3, 251, 0)
bat = ctrl2.read_battery_status()
ctl = ctrl2.read_control_status()
mode = ctrl2.read_native_mode()
print(f"  WSetEna: {ctl.get('wset_enabled')}", flush=True)
print(f"  SoC: {bat.get('soc')}%  State: {bat.get('battery_state')}  Mode: {mode.get('mode_name')}", flush=True)
ctrl2.disconnect()
print("DONE", flush=True)
