#!/usr/bin/env python3
"""
Quick validation test for FranklinWH Throttling Registers (ThrotPct/ThrotSrc)
Test if Model 701 registers 40180-40181 actually return data.

Run: python test_throttling_registers.py <agate_ip> [unit_id]
"""

import sys
import time
from datetime import datetime
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Register definitions from Model 701 DERMeasureAC
THROT_PCT_ADDR = 40180   # uint16 - Throttling percentage (0-100%)
THROT_SRC_ADDR = 40181   # bitfield32 - Throttling source flags

# ThrotSrc bitfield decoding (from SunSpec2 standard)
THROT_SOURCES = {
    0: ("GridCmd", "🔌 Utility/grid operator command"),
    1: ("FreqReg", "📊 Frequency regulation active"),
    2: ("VoltReg", "⚡ Voltage regulation active"),
    3: ("TempDerate", "🌡️ Temperature derating"),
    4: ("SOCLimit", "🔋 Battery SOC protection"),
    5: ("GenLimit", "⛽ Generator capacity limit"),
    6: ("IslandStab", "🏝️ Island mode stabilization"),
    7: ("UserLimit", "👤 User/installer manual limit"),
    8: ("PVLimit", "☀️ PV input limit"),
    9: ("CurrLimit", "🔒 Current/hardware limit"),
    10: ("CommLoss", "📡 Communication loss"),
}


def decode_throt_src(value: int | None) -> list:
    """Decode ThrotSrc bitfield to human-readable list."""
    if value is None:
        return ["⚠️ Register not implemented (0xFFFFFFFF)"]
    
    active = []
    for bit, (code, emoji_desc) in THROT_SOURCES.items():
        if value & (1 << bit):
            active.append(f"{emoji_desc} ({code})")
    
    # Vendor reserved bits (11-31)
    for bit in range(11, 32):
        if value & (1 << bit):
            active.append(f"🏭 VendorReserved_{bit}")
    
    return active


def read_registers_raw(client: ModbusTcpClient, unit_id: int) -> dict:
    """
    Read raw register values without any interpretation.
    Returns dict with success status and raw values.
    """
    result = {
        'success': False,
        'throt_pct': None,
        'throt_src': None,
        'throt_pct_raw': None,
        'throt_src_raw': None,
        'error': None
    }
    
    try:
        # Read 3 registers starting at 40180
        # 40180 = ThrotPct (uint16)
        # 40181 = ThrotSrc low word (uint16)
        # 40182 = ThrotSrc high word (uint16) - for bitfield32
        response = client.read_holding_registers(
            address=40180 - 40001,  # Convert to 0-based addressing
            count=3,
            device_id=unit_id
        )
        
        if response.isError():
            result['error'] = f"Modbus error: {response}"
            return result
        
        # Extract values
        pct_raw = response.registers[0]
        src_low = response.registers[1]
        src_high = response.registers[2]
        src_raw = (src_high << 16) | src_low
        
        result['success'] = True
        result['throt_pct_raw'] = pct_raw
        result['throt_src_raw'] = src_raw
        result['throt_pct'] = pct_raw if pct_raw != 0xFFFF else None
        result['throt_src'] = src_raw if src_raw != 0xFFFFFFFF else None
        
    except ModbusException as e:
        result['error'] = f"Modbus exception: {e}"
    except Exception as e:
        result['error'] = f"Unexpected error: {e}"
    
    return result


def print_results(result: dict, iteration: int = 1):
    """Pretty print the test results."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🕐 Test #{iteration} at {timestamp}")
    print(f"{'='*60}")
    
    if not result['success']:
        print(f"❌ FAILED: {result['error']}")
        return
    
    # ThrotPct
    print(f"\n📊 ThrotPct (40180):")
    print(f"   Raw value: 0x{result['throt_pct_raw']:04X} ({result['throt_pct_raw']})")
    if result['throt_pct'] is None:
        print("   ⚠️  Value is 0xFFFF (Not implemented / invalid)")
    elif result['throt_pct'] == 0:
        print("   ✅ Value = 0% (No throttling active)")
    else:
        print(f"   🔥 Value = {result['throt_pct']}% (Throttling active!)")
    
    # ThrotSrc
    print(f"\n📋 ThrotSrc (40181-2):")
    print(f"   Raw value: 0x{result['throt_src_raw']:08X}")
    print(f"   Binary:    {result['throt_src_raw']:032b}")
    
    if result['throt_src'] is None:
        print("   ⚠️  Value is 0xFFFFFFFF (Not implemented / invalid)")
    elif result['throt_src'] == 0:
        print("   ✅ No active throttle sources")
    else:
        print(f"   🔥 Active throttle sources ({bin(result['throt_src']).count('1')} bits set):")
        for source in decode_throt_src(result['throt_src']):
            print(f"      • {source}")
    
    # Interpretation
    print(f"\n📝 Interpretation:")
    if result['throt_pct'] == 0 and result['throt_src'] == 0:
        print("   System is operating normally without throttling")
    elif result['throt_pct'] is None and result['throt_src'] is None:
        print("   ⚠️  Registers appear unimplemented (always 0xFFFF)")
    elif result['throt_pct'] == 0 and result['throt_src'] != 0:
        print("   ⚠️  Inconsistent: Sources flagged but 0% throttle")
    elif result['throt_pct'] != 0 and result['throt_src'] == 0:
        print("   ⚠️  Inconsistent: Throttling active but no source flagged")
    else:
        print(f"   System is throttled to {result['throt_pct']}%")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_throttling_registers.py <agate_ip> [unit_id] [timeout_sec]")
        print("Example: python test_throttling_registers.py 192.0.2.110 2 15")
        print("  Default unit_id: 2")
        print("  Default timeout: 10 seconds")
        sys.exit(1)
    
    host = sys.argv[1]
    unit_id = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    timeout_sec = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    print(f"🔌 Connecting to FranklinWH aGate at {host}:502 (Unit ID: {unit_id}, Timeout: {timeout_sec}s)...")
    
    client = ModbusTcpClient(host, port=502, timeout=timeout_sec)
    if not client.connect():
        print("❌ Failed to connect!")
        sys.exit(1)
    
    print("✅ Connected!")
    print(f"\n📍 Target registers:")
    print(f"   ThrotPct (40180): uint16 - Throttling percentage")
    print(f"   ThrotSrc (40181): bitfield32 - Throttle source flags")
    
    # Run tests
    iterations = 3
    interval = 5  # seconds
    
    print(f"\n🧪 Running {iterations} tests with {interval}s interval...")
    print("(Press Ctrl+C to stop early)")
    
    all_results = []
    
    try:
        for i in range(1, iterations + 1):
            result = read_registers_raw(client, unit_id)
            all_results.append(result)
            print_results(result, i)
            
            if i < iterations:
                time.sleep(interval)
        
    except KeyboardInterrupt:
        print("\n\n⛔ Stopped by user")
    finally:
        client.close()
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    
    success_count = sum(1 for r in all_results if r['success'])
    print(f"Successful reads: {success_count}/{len(all_results)}")
    
    if all_results and all_results[0]['success']:
        first = all_results[0]
        
        # Check if registers are implemented
        if first['throt_pct'] is None and first['throt_src'] is None:
            print("\n❌ VERDICT: Registers NOT IMPLEMENTED (return 0xFFFF)")
            print("   The throttling registers exist in the model but aren't populated.")
            print("   Don't invest time in a PoC for these registers.")
        elif first['throt_pct'] == 0 and first['throt_src'] == 0:
            print("\n✅ VERDICT: Registers READABLE, currently no throttling")
            print("   Registers work! But you need to trigger throttling to see non-zero values.")
            print("   Try: High temperature, generator overload, or grid export limiting.")
        else:
            print(f"\n🔥 VERDICT: Registers ACTIVE!")
            print(f"   Throttling: {first['throt_pct']}%")
            src_list = decode_throt_src(first.get('throt_src'))
        print(f"   Sources: {src_list}")
    else:
        print("\n❌ Could not read registers - check connection and Modbus settings")


if __name__ == "__main__":
    main()
