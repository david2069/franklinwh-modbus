import struct
import time
import sys
from franklinwh_modbus import FranklinWHController

AGATE_IP = "192.0.2.110"
UNIT_ID = 2  # The probe used Unit ID 2 per documentation
START_ADDR = 15000
COUNT = 40

def raw_read(sock, addr, count=1, unit_id=UNIT_ID):
    """Read holding registers via raw Modbus TCP (FC3)."""
    # Transaction ID (0), Protocol ID (0), Length (6), Unit ID, Function (3), Start, Count
    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, addr, count)
    sock.settimeout(5.0)
    sock.sendall(req)
    resp = sock.recv(256)
    if len(resp) < 9 or (resp[7] & 0x80):
        return None
    
    # Payload starts at byte 9
    payload = resp[9:]
    if count == 1:
        return struct.unpack('>H', payload[0:2])[0]
    else:
        return [struct.unpack('>H', payload[i*2:i*2+2])[0] for i in range(count)]

def raw_write(sock, addr, value, unit_id=UNIT_ID):
    """Write single holding register via raw Modbus TCP (FC6)."""
    # Transaction ID (0), Protocol ID (0), Length (6), Unit ID, Function (6), Start, Value
    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 6, addr, value)
    sock.settimeout(5.0)
    sock.sendall(req)
    resp = sock.recv(256)
    if len(resp) < 8 or (resp[7] & 0x80):
        exc = resp[8] if len(resp) > 8 else '?'
        return f"EXCEPTION_{exc}"
    return True

def main():
    print(f"--- [RE-PROBE 15000-15039] ---")
    print(f"Target: {AGATE_IP} (Unit {UNIT_ID})")
    
    ctrl = FranklinWHController(AGATE_IP)
    ctrl.connect()
    sock = ctrl.dev.client.socket
    
    # 1. Baseline Read
    print("\n[Phase 1] Reading baseline...")
    baseline = raw_read(sock, START_ADDR, COUNT)
    if baseline is None:
        print("❌ Failed to read baseline!")
        return
    
    for i, val in enumerate(baseline):
        addr = START_ADDR + i
        print(f"  {addr}: {val}")
        
    # 2. Write-back Test
    print("\n[Phase 2] Write-back test ( FC6 )...")
    for i, val in enumerate(baseline):
        addr = START_ADDR + i
        res = raw_write(sock, addr, val)
        if res is True:
            print(f"  {addr}: ✅ Accepted")
        else:
            print(f"  {addr}: ❌ {res}")
            
    # 3. Persistence Test
    print("\n[Phase 3] Persistence test ( value + 1 )...")
    results = []
    for i, val in enumerate(baseline):
        addr = START_ADDR + i
        test_val = (val + 1) % 65536
        
        # Write test value
        raw_write(sock, addr, test_val)
        time.sleep(0.5)
        
        # Re-read
        final_val = raw_read(sock, addr)
        
        status = "Silently ignored"
        if final_val == test_val:
            status = "✅ STICKY!"
        elif final_val != val:
            status = f"⚠️ Changed (was {val}, now {final_val})"
            
        print(f"  {addr}: Wrote {test_val}, Read {final_val} -> {status}")
        results.append((addr, val, test_val, final_val, status))
        
    print("\n--- [SUMMARY] ---")
    ignored = len([r for r in results if "ignored" in r[4]])
    changed = len([r for r in results if "Changed" in r[4]])
    sticky = len([r for r in results if "STICKY" in r[4]])
    
    print(f"  Silently Ignored: {ignored}")
    print(f"  Value Changed:    {changed}")
    print(f"  Sticky:           {sticky}")
    
    ctrl.disconnect()

if __name__ == "__main__":
    main()
