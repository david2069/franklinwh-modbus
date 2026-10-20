#!/usr/bin/env python3
"""
Throttling Charge Test - Controls battery to create throttling conditions
Shows SoC, mode, reserve, and throttling status WITHOUT asking user

Usage: python throttling_charge_test.py <agate_ip> [unit_id] [target_soc]

What it does:
1. Reads current state (SoC, mode, reserve, temps)
2. Optionally sets MAX CHARGE mode to force charging
3. Monitors ThrotPct as SoC approaches 100%
4. Restores original mode when done
"""

import sys
import json
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

TIMEOUT = 30  # Modbus TCP timeout in seconds (WiFi: 30, Ethernet: 10)
UNIT_ID = 2

# Register addresses
REG_THROTPCT = 40180
REG_THROTSRC = 40181
REG_W = 40080
REG_SOC = 41037
REG_TMPCAB = 40106
REG_TMPSW = 40109
REG_ST = 40073
REG_INVST = 40074

# Extension registers for control/mode
EXT_MODE = 15507
EXT_SELF_RESERVE = 15508

# State mappings
INV_STATES = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running', 
              4: 'Throttled', 5: 'ShuttingDown', 6: 'Fault', 7: 'Standby'}
OP_STATES = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault', 
             4: 'ShuttingDown', 5: 'Starting', 6: 'Maintenance'}
MODES = {0: 'OFF', 1: 'ON_GRID', 2: 'SELF_CONSUMPTION', 3: 'TOU', 4: 'BACKUP', 5: 'ECO'}

stop_requested = False
original_mode = None


def signal_handler(signum, frame):
    global stop_requested
    print("\n⛔ Stopping... restoring original mode")
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


def get_battery_state(client):
    """Get complete battery state including mode, SoC, temps."""
    state = {
        'timestamp': datetime.now().isoformat(),
        'ThrotPct': None,
        'ThrotSrc': None,
        'SoC': None,
        'Power_W': None,
        'TmpCab': None,
        'TmpSw': None,
        'Mode': None,
        'Mode_str': 'Unknown',
        'SelfReserve': None,
        'InvState': None,
        'InvState_str': 'Unknown',
        'OpState': None,
        'OpState_str': 'Unknown',
    }
    
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
    for reg, name, scale in [(REG_TMPCAB, 'TmpCab', 0.1), (REG_TMPSW, 'TmpSw', 0.1)]:
        regs = read_registers(client, reg, 1)
        if regs:
            val = regs[0]
            if val > 32767:
                val -= 65536
            state[name] = val * scale
    
    # Mode (extension register)
    regs = read_registers(client, EXT_MODE, 1)
    if regs:
        state['Mode'] = regs[0]
        state['Mode_str'] = MODES.get(regs[0], f"Mode_{regs[0]}")
    
    # Self reserve
    regs = read_registers(client, EXT_SELF_RESERVE, 1)
    if regs:
        state['SelfReserve'] = regs[0]
    
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
    """Print current state in readable format."""
    if header:
        print(f"{'Time':<8} {'SoC':>6} {'Power':>8} {'Throt':>6} {'Mode':>16} {'Reserve':>8} {'Temp':>6} {'State':>12}")
        print("-" * 90)
    
    time_str = datetime.now().strftime('%H:%M:%S')
    soc = f"{state['SoC']:.1f}%" if state['SoC'] is not None else "???"
    power = f"{state['Power_W']}W" if state['Power_W'] is not None else "???"
    throt = f"{state['ThrotPct']}%" if state['ThrotPct'] is not None else "???"
    mode = state['Mode_str'][:15]
    reserve = f"{state['SelfReserve']}%" if state['SelfReserve'] is not None else "???"
    temp = f"{state['TmpCab']:.1f}°C" if state['TmpCab'] is not None else "???"
    inv = state['InvState_str'][:11]
    
    # Highlight throttling
    if state['ThrotPct'] and state['ThrotPct'] > 0:
        throt = f"🔥{throt}"
    if state['InvState'] == 4:
        inv = f"⚠️{inv}"
    
    print(f"{time_str:<8} {soc:>6} {power:>8} {throt:>6} {mode:>16} {reserve:>8} {temp:>6} {inv:>12}")


def main():
    global UNIT_ID, stop_requested, original_mode
    
    if len(sys.argv) < 2:
        print("Usage: python throttling_charge_test.py <agate_ip> [unit_id] [target_soc]")
        print("Example: python throttling_charge_test.py 192.0.2.110 2 95")
        print("  Default unit_id: 2")
        print("  Default target_soc: 95 (stop when SoC reaches this)")
        sys.exit(1)
    
    host = sys.argv[1]
    UNIT_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    target_soc = int(sys.argv[3]) if len(sys.argv) > 3 else 95
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"🔌 Connecting to {host}...")
    client = ModbusTcpClient(host, port=502, timeout=TIMEOUT)
    if not client.connect():
        print("❌ Failed to connect!")
        sys.exit(1)
    
    print("✅ Connected!\n")
    
    # Get initial state
    print("📊 Current Battery State:")
    state = get_battery_state(client)
    print_state(state, header=True)
    original_mode = state.get('Mode')
    original_reserve = state.get('SelfReserve')
    
    print(f"\n📋 Configuration:")
    print(f"   Current Mode: {state['Mode_str']}")
    print(f"   Current SoC:  {state['SoC']:.1f}%" if state['SoC'] else "   Current SoC:  ???")
    print(f"   Target SoC:   {target_soc}%")
    print(f"   Self Reserve: {state['SelfReserve']}%" if state['SelfReserve'] else "   Self Reserve: ???")
    
    # Decision logic
    current_soc = state.get('SoC', 0)
    
    if current_soc >= target_soc:
        print(f"\n⚠️  SoC ({current_soc:.1f}%) already at/above target ({target_soc}%)")
        print("   No charging needed. Monitoring current state only.")
        charge_mode = False
    elif state['Mode'] == 2 and state['SelfReserve'] == 7:
        print(f"\n✅ Already in SELF_CONSUMPTION mode with 7% reserve")
        print("   Will charge from solar tomorrow morning.")
        print("   Monitoring now to establish baseline...")
        charge_mode = False
    else:
        print(f"\n🤔 Current mode ({state['Mode_str']}) may not charge optimally")
        print("   Night time: No solar, battery will discharge to supply home loads")
        print("   To see throttling: Run during solar hours when SoC > 90%")
        print("\n   Monitoring current state anyway...")
        charge_mode = False
    
    # Setup logging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f"throttling_test_{timestamp}.jsonl"
    f = open(log_file, 'w')
    print(f"\n💾 Logging to: {log_file}")
    
    # Monitoring loop
    print(f"\n⏱️  Monitoring (Ctrl+C to stop)...")
    print_state(None, header=True)
    
    sample_count = 0
    max_throt = 0
    start_time = datetime.now()
    
    try:
        while not stop_requested:
            state = get_battery_state(client)
            print_state(state)
            
            # Log to file
            f.write(json.dumps(state) + '\n')
            f.flush()
            
            sample_count += 1
            if state['ThrotPct'] and state['ThrotPct'] > max_throt:
                max_throt = state['ThrotPct']
            
            # Check if target reached
            if state['SoC'] and state['SoC'] >= target_soc:
                print(f"\n🎯 Target SoC {target_soc}% reached!")
                break
            
            # Check if throttling detected
            if state['ThrotPct'] and state['ThrotPct'] > 0:
                print(f"   🔥 THROTTLING DETECTED: {state['ThrotPct']}%")
            
            time.sleep(30)  # 30 second intervals
            
    except KeyboardInterrupt:
        print("\n⛔ Interrupted by user")
    finally:
        f.close()
        
        # Restore original mode if we changed it
        if charge_mode and original_mode is not None and original_reserve is not None:
            print(f"\n🔄 Restoring original mode...")
            write_register(client, EXT_SELF_RESERVE, original_reserve)
            print(f"   ✓ Reserve restored to {original_reserve}%")
        
        client.close()
    
    # Summary
    duration = (datetime.now() - start_time).total_seconds() / 60
    print(f"\n{'='*70}")
    print("📊 TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Duration:       {duration:.1f} minutes")
    print(f"Samples:        {sample_count}")
    print(f"Max ThrotPct:   {max_throt}%")
    print(f"Final SoC:      {state.get('SoC', 0):.1f}%" if state.get('SoC') else "Final SoC:      ???")
    print(f"Log file:       {log_file}")
    
    if max_throt > 0:
        print(f"\n✅ SUCCESS! Throttling was detected")
        print(f"   ThrotPct reached {max_throt}%")
    else:
        print(f"\n⚠️  No throttling detected")
        print(f"   Battery may not have reached high enough SoC")
        print(f"   Or charging rate was never limited")
    
    print(f"\n{'='*70}")


if __name__ == "__main__":
    main()
