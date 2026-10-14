#!/usr/bin/env python3
"""
EXTENDED REVERSION TEST — NO FORCED CLEANUP
Polls 3 minutes post-expiry to observe if device eventually auto-releases.
"""
import socket, struct, time, sys
import os
sys.path.insert(0, os.path.expanduser('~/dev/modbus/src'))

IP = '192.0.2.110'; PORT = 502; UID = 1; TO = 30

def conn():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TO); s.connect((IP, PORT)); return s

def rd(s, addr, n=1):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, n)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    if len(r) < 9 or (r[7] & 0x80): return 'ERR'
    if n == 1: return struct.unpack('>H', r[9:11])[0]
    return [struct.unpack('>H', r[9+i*2:11+i*2])[0] for i in range(n)]

def rd_s16(s, addr):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, 1)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    if len(r) < 9 or (r[7] & 0x80): return 'ERR'
    return struct.unpack('>h', r[9:11])[0]

def wr(s, addr, val):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 6, addr, val & 0xFFFF)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    return 'OK' if not (len(r) < 8 or (r[7] & 0x80)) else 'ERR'

def wr32(s, addr, val):
    hi = (val >> 16) & 0xFFFF; lo = val & 0xFFFF
    header = struct.pack('>HHHBBHHB', 0, 0, 11, UID, 16, addr, 2, 4)
    s.settimeout(TO); s.sendall(header + struct.pack('>HH', hi, lo)); r = s.recv(256)
    return 'OK' if not (len(r) < 8 or (r[7] & 0x80)) else 'ERR'

def poll(t0):
    """Single atomic poll — fresh connection."""
    try:
        s = conn()
        time.sleep(0.15); we = rd(s, 318)
        time.sleep(0.15); wp = rd_s16(s, 324)
        time.sleep(0.15); rr = rd(s, 329, 2)
        s.close()
        rr_val = rr[1] if isinstance(rr, list) else rr
        return we, wp, rr_val
    except Exception as e:
        return f'ERR', f'ERR', f'ERR'

print("EXTENDED REVERSION TEST — 3 min post-expiry, NO forced cleanup", flush=True)
print("=" * 65, flush=True)

# Step 1: VPP via library
print("\n[1] Activate VPP...", flush=True)
from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.types import BatteryCommand, ControlMode
ctrl = FranklinWHController(IP); ctrl.connect()
ctrl.send_command(BatteryCommand(power_watts=500, mode=ControlMode.LIMIT_ABS))
ctrl.disconnect()
print("  Waiting 8s...", flush=True); time.sleep(8)

# Step 2: Configure reversion
print("[2] Configure reversion...", flush=True)
s = conn()
time.sleep(0.3); print(f"  WSetEna={rd(s, 318)}", flush=True)
time.sleep(0.3); wr32(s, 322, 0)       # revert to 0W
time.sleep(0.3); wr(s, 326, 1)         # enable reversion
time.sleep(0.3); wr32(s, 327, 30)      # 30s countdown
time.sleep(0.5)
rrem = rd(s, 329, 2)
print(f"  WSetRvrtRem={rrem}", flush=True)
s.close()

# Step 3: Poll — every 5s during countdown, then every 10s for 3 min
print(f"\n{'━'*65}", flush=True)
print(f"  {'T':>5s}  {'WSetEna':>8s}  {'WSetPct':>8s}  {'RvrtRem':>8s}  Notes", flush=True)
print(f"  {'─'*5}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*25}", flush=True)

t0 = time.time()
# Phase A: countdown (every 5s for 35s)
for i in range(8):
    target = t0 + i * 5
    now = time.time()
    if now < target: time.sleep(target - now)
    we, wp, rr = poll(t0)
    elapsed = time.time() - t0
    note = "countdown" if isinstance(rr, int) and rr > 0 else "expired" if isinstance(rr, int) and rr == 0 else ""
    if elapsed > 30 and isinstance(we, int) and we == 0: note += " AUTO-RELEASED ✅"
    elif elapsed > 30 and isinstance(we, int) and we == 1: note += " still active ⚠️"
    print(f"  {elapsed:5.0f}s  {we!s:>8s}  {wp!s:>8s}  {rr!s:>8s}  {note}", flush=True)

# Phase B: post-expiry (every 10s for 3 minutes = 18 polls)
for i in range(18):
    target = t0 + 35 + (i + 1) * 10
    now = time.time()
    if now < target: time.sleep(target - now)
    we, wp, rr = poll(t0)
    elapsed = time.time() - t0
    note = ""
    if isinstance(we, int) and we == 0: note = "AUTO-RELEASED ✅ ✅ ✅"
    elif isinstance(we, int) and we == 1: note = "still active ⚠️"
    print(f"  {elapsed:5.0f}s  {we!s:>8s}  {wp!s:>8s}  {rr!s:>8s}  {note}", flush=True)
    # If auto-released, stop early
    if isinstance(we, int) and we == 0:
        print(f"\n  DEVICE AUTO-RELEASED at ~{elapsed:.0f}s ({elapsed-30:.0f}s post-expiry)!", flush=True)
        break

# Final state — NO cleanup
print(f"\n{'━'*65}", flush=True)
sf = conn()
time.sleep(0.3); f_wse = rd(sf, 318)
time.sleep(0.3); f_wpct = rd_s16(sf, 324)
time.sleep(0.3); f_rrem = rd(sf, 329, 2)
sf.close()
print(f"  Final: WSetEna={f_wse}  WSetPct={f_wpct}  RvrtRem={f_rrem}", flush=True)

print(f"\n{'═'*65}", flush=True)
if isinstance(f_wse, int) and f_wse == 0:
    print("  VERDICT: ✅ Device auto-released VPP", flush=True)
else:
    print("  VERDICT: ❌ Device did NOT auto-release VPP after 3+ min", flush=True)
    print("  Forcing cleanup now...", flush=True)
    ctrl2 = FranklinWHController(IP); ctrl2.connect()
    ctrl2.reset_control_state()
    ctrl2.disconnect()
    print("  Cleanup done.", flush=True)
print("DONE", flush=True)
