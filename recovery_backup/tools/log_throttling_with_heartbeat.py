#!/usr/bin/env python3
"""
Throttling Logger WITH WSetPct Heartbeat - Keeps connection alive like your monitor
Uses periodic WSetPct(0) writes to maintain VPP/control mode

Usage: python log_throttling_with_heartbeat.py <agate_ip> [unit_id] [duration_min]
"""

import sys
import csv
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

TIMEOUT = 30
UNIT_ID = 2
INTERVAL = 30  # seconds between samples
HEARTBEAT_INTERVAL = 10  # seconds between WSetPct writes

# Register addresses
REG_THROTPCT = 40180
REG_THROTSRC = 40181
REG_W = 40080
REG_SOC = 41037
REG_TMPCAB = 40106
REG_TMPSW = 40109
REG_ST = 40073
REG_INVST = 40074
REG_WSETPCT = 40301  # WSetPct - for heartbeat
REG_WSETENA = 40299  # WSetEna - enable control

# State mappings
INV_STATES = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running', 
              4: 'Throttled', 5: 'ShuttingDown', 6: 'Fault', 7: 'Standby'}
OP_STATES = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault', 
             4: 'ShuttingDown', 5: 'Starting', 6: 'Maintenance'}

stop_requested = False
control_was_enabled = False


def signal_handler(signum, frame):
    global stop_requested
    print("\n⛔ Stopping...")
    stop_requested = True


def read_registers(client, address, count):
    """Read holding registers."""
    try:
        result = client.read_holding_registers(address=address - 40001, count=count, device_id=UNIT_ID)
        if result.isError():
            return None
        return result.registers
    except Exception as e:
        return None


def write_register(client, address, value):
    """Write single register."""
    try:
        result = client.write_register(address=address - 40001, value=value, device_id=UNIT_ID)
        return not result.isError()
    except Exception as e:
        return False


def send_heartbeat(client):
    """Send WSetPct(0) heartbeat to keep connection alive."""
    global control_was_enabled
    
    try:
        # Enable control if not already
        if not control_was_enabled:
            write_register(client, REG_WSETENA, 1)
            control_was_enabled = True
        
        # Write 0% setpoint (no change, but keeps VPP mode active)
        write_register(client, REG_WSETPCT, 0)
        return True
    except Exception as e:
        return False


def release_control(client):
    """Release control by disabling WSetEna."""
    global control_was_enabled
    try:
        write_register(client, REG_WSETPCT, 0)
        write_register(client, REG_WSETENA, 0)
        control_was_enabled = False
        return True
    except:
        return False


def get_battery_state(client):
    """Get complete battery state."""
    state = {
        'timestamp': datetime.now().isoformat(),
        'unix_time': time.time(),
        'ThrotPct': None,
        'ThrotSrc': None,
        'SoC': None,
        'Power_W': None,
        'TmpCab': None,
        'TmpSw': None,
        'InvState': None,
        'InvState_str': 'Unknown',
        'OpState': None,
        'OpState_str': 'Unknown',
        'heartbeat_ok': False,
    }
    
    # Send heartbeat before reading
    state['heartbeat_ok'] = send_heartbeat(client)
    
    # ThrotPct
    regs = read_registers(client, REG_THROTPCT, 1)
    if regs and regs[0] != 0xFFFF:
        state['ThrotPct'] = regs[0]
    
    # ThrotSrc
    regs = read_registers(client, REG_THROTSRC, 2)
    if regs:
        val = (regs[1] << 16) | regs[0]
        state['ThrotSrc'] = val if val != 0xFFFFFFFF else None
    
    # SoC
    regs = read_registers(client, REG_SOC, 1)
    if regs:
        state['SoC'] = regs[0] / 100.0
    
    # Power
    regs = read_registers(client, REG_W, 1)
    if regs:
        val = regs[0]
        if val > 32767:
            val -= 65536
        state['Power_W'] = val
    
    # Temps
    for reg, name in [(REG_TMPCAB, 'TmpCab'), (REG_TMPSW, 'TmpSw')]:
        regs = read_registers(client, reg, 1)
        if regs:
            val = regs[0]
            if val > 32767:
                val -= 65536
            state[name] = val / 10.0
    
    # States
    regs = read_registers(client, REG_INVST, 1)
    if regs:
        state['InvState'] = regs[0]
        state['InvState_str'] = INV_STATES.get(regs[0], f"Inv_{regs[0]}")
    
    regs = read_registers(client, REG_ST, 1)
    if regs:
        state['OpState'] = regs[0]
        state['OpState_str'] = OP_STATES.get(regs[0], f"Op_{regs[0]}")
    
    return state


def print_state(state, header=False):
    """Print current state."""
    if header:
        print(f"{'Time':<8} {'SoC':>6} {'Power':>7} {'Throt':>6} {'HB':>3} {'Temp':>6} {'State':>12}")
        print("-" * 70)
    
    time_str = datetime.now().strftime('%H:%M:%S')
    soc = f"{state['SoC']:.1f}%" if state['SoC'] is not None else "???"
    power = f"{state['Power_W']}W" if state['Power_W'] is not None else "???"
    throt = f"{state['ThrotPct']}%" if state['ThrotPct'] is not None else "???"
    hb = "OK" if state['heartbeat_ok'] else "ERR"
    temp = f"{state['TmpCab']:.1f}°C" if state['TmpCab'] is not None else "???"
    inv = state['InvState_str'][:11]
    
    if state['ThrotPct'] and state['ThrotPct'] > 0:
        throt = f"🔥{throt}"
    if state['InvState'] == 4:
        inv = f"⚠️{inv}"
    
    print(f"{time_str:<8} {soc:>6} {power:>7} {throt:>6} {hb:>3} {temp:>6} {inv:>12}")


def main():
    global stop_requested, UNIT_ID
    
    if len(sys.argv) < 2:
        print("Usage: python log_throttling_with_heartbeat.py <agate_ip> [unit_id] [duration_min]")
        print("Example: python log_throttling_with_heartbeat.py 192.0.2.110 2 60")
        print("  Default unit_id: 2")
        print("  Default duration: 60 minutes")
        print("\nUses WSetPct(0) heartbeat every 10s to keep VPP mode active")
        sys.exit(1)
    
    host = sys.argv[1]
    UNIT_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    duration_min = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"🔌 Connecting to {host}...")
    client = ModbusTcpClient(host, port=502, timeout=TIMEOUT)
    if not client.connect():
        print("❌ Failed to connect!")
        sys.exit(1)
    
    print("✅ Connected!\n")
    
    # Setup CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f"throttling_heartbeat_{timestamp}.csv"
    f = open(csv_file, 'w', newline='')
    writer = csv.writer(f)
    writer.writerow(['Timestamp', 'UnixTime', 'ThrotPct', 'SoC_%', 'Power_W', 
                     'TmpCab_C', 'InvState', 'Heartbeat_OK'])
    f.flush()
    
    print(f"💾 Logging to: {csv_file}")
    print(f"⏱️  Duration: {duration_min} minutes")
    print(f"💓 Heartbeat: Every {HEARTBEAT_INTERVAL}s (WSetPct=0)")
    print(f"📝 Sampling: Every {INTERVAL}s\n")
    
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_min)
    
    print_state(None, header=True)
    
    sample_count = 0
    max_throt = 0
    last_sample_time = 0
    
    try:
        while not stop_requested:
            now = time.time()
            
            # Sample every INTERVAL seconds
            if now - last_sample_time >= INTERVAL:
                state = get_battery_state(client)
                print_state(state)
                
                # Write to CSV
                writer.writerow([
                    state['timestamp'],
                    state['unix_time'],
                    state['ThrotPct'],
                    state['SoC'],
                    state['Power_W'],
                    state['TmpCab'],
                    state['InvState_str'],
                    state['heartbeat_ok']
                ])
                f.flush()
                
                sample_count += 1
                if state['ThrotPct'] and state['ThrotPct'] > max_throt:
                    max_throt = state['ThrotPct']
                
                last_sample_time = now
                
                # Check duration
                if datetime.now() >= end_time:
                    print(f"\n✅ Duration reached!")
                    break
            else:
                # Send heartbeat between samples
                time.sleep(HEARTBEAT_INTERVAL)
                hb_ok = send_heartbeat(client)
                if not hb_ok:
                    print(f"  ⚠️ Heartbeat failed at {datetime.now().strftime('%H:%M:%S')}")
                
    except KeyboardInterrupt:
        print("\n⛔ Interrupted")
    finally:
        f.close()
        
        # Release control
        print(f"\n🔄 Releasing control...")
        if release_control(client):
            print("   ✓ Control released")
        
        client.close()
    
    # Summary
    duration = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n{'='*70}")
    print("📊 SUMMARY")
    print(f"{'='*70}")
    print(f"Duration:     {duration:.1f} minutes")
    print(f"Samples:      {sample_count}")
    print(f"Max ThrotPct: {max_throt}%")
    print(f"Log file:     {csv_file}")
    
    if max_throt > 0:
        print(f"\n🔥 THROTTLING DETECTED!")
    else:
        print(f"\n✅ No throttling")
    
    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
