#!/usr/bin/env python3
"""
Simple Throttling Monitor - Quick 5-second polling like original Kimi K2.5 analysis
No CSV, just console output with JSON log lines for parsing

Usage: python log_throttling_simple.py <agate_ip> [unit_id] [duration_min]
"""

import sys
import json
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

AGATE_IP = None
UNIT_ID = 2
TIMEOUT = 30  # Default 30s for WiFi. Use 10s for stable Ethernet

# ThrotSrc bitfield decoding (from SunSpec2 standard)
SOURCES = {
    0:  ("GridCmd",     "🔌 Utility/grid operator command"),
    1:  ("FreqReg",     "📊 Frequency regulation active"),
    2:  ("VoltReg",     "⚡ Voltage regulation active"),
    3:  ("TempDerate",  "🌡️ Temperature derating"),
    4:  ("SOCLimit",    "🔋 Battery SOC protection"),
    5:  ("GenLimit",    "⛽ Generator capacity limit"),
    6:  ("IslandStab",  "🏝️ Island mode stabilization"),
    7:  ("UserLimit",   "👤 User/installer manual limit"),
    8:  ("PVLimit",     "☀️ PV input limit"),
    9:  ("CurrLimit",   "🔒 Current/hardware limit"),
    10: ("CommLoss",    "📡 Communication loss"),
}

stop_requested = False


def signal_handler(signum, frame):
    global stop_requested
    print("\n⛔ Stopping...")
    stop_requested = True


def read_registers(client):
    """Read ThrotPct and ThrotSrc from aGate."""
    try:
        # Read 3 registers: ThrotPct (1) + ThrotSrc (2 for bitfield32)
        result = client.read_holding_registers(
            address=40180 - 40001,  # 0-based addressing
            count=3,
            device_id=UNIT_ID
        )
        
        if result.isError():
            return None, None
        
        throt_pct = result.registers[0]
        throt_src_low = result.registers[1]
        throt_src_high = result.registers[2]
        throt_src = (throt_src_high << 16) | throt_src_low
        
        return throt_pct, throt_src
        
    except Exception as e:
        print(f"  ⚠️ Read error: {e}")
        return None, None


def decode_sources(src_value):
    """Decode ThrotSrc bitfield to human-readable list."""
    if src_value is None or src_value == 0xFFFFFFFF:
        return ["⚠️ Not implemented (0xFFFFFFFF)"]
    
    if src_value == 0:
        return []
    
    active = []
    for bit, (code, emoji_desc) in SOURCES.items():
        if src_value & (1 << bit):
            active.append(f"{emoji_desc} ({code})")
    
    # Vendor reserved bits (11-31)
    for bit in range(11, 32):
        if src_value & (1 << bit):
            active.append(f"🏭 VendorReserved_{bit}")
    
    return active


def main():
    global AGATE_IP, UNIT_ID, stop_requested
    
    if len(sys.argv) < 2:
        print("Usage: python log_throttling_simple.py <agate_ip> [unit_id] [duration_min] [timeout_sec]")
        print("Example: python log_throttling_simple.py 192.0.2.110 2 60 30")
        print("  Default unit_id: 2")
        print("  Default duration: 60 minutes")
        print("  Default timeout: 30 seconds (use 10 for Ethernet, 30+ for WiFi)")
        print("\nOutputs JSON log lines every 5 seconds")
        sys.exit(1)
    
    AGATE_IP = sys.argv[1]
    UNIT_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    duration_min = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    TIMEOUT = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"🔌 Connecting to FranklinWH aGate X at {AGATE_IP}...")
    
    client = ModbusTcpClient(AGATE_IP, port=502, timeout=TIMEOUT)
    if not client.connect():
        print("❌ Failed to connect!")
        sys.exit(1)
    
    print("=" * 60)
    print(f"✅ Connected! Logging for {duration_min} minutes")
    print("=" * 60)
    
    # Prepare log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f"throttling_simple_{timestamp}.jsonl"
    log_file = open(log_filename, 'w')
    print(f"💾 Logging to: {log_filename}")
    print()
    
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_min)
    sample_count = 0
    success_count = 0
    
    try:
        while not stop_requested:
            if datetime.now() >= end_time:
                print("\n✅ Duration reached!")
                break
            
            timestamp = datetime.now()
            pct, src = read_registers(client)
            
            sample_count += 1
            
            if pct is not None:
                success_count += 1
                sources = decode_sources(src)
                
                # Determine status
                pct_display = pct if pct != 0xFFFF else None
                is_throttled = pct_display is not None and pct_display > 0
                
                status = {
                    "timestamp": timestamp.isoformat(),
                    "sample_num": sample_count,
                    "throttle_percent": pct_display,
                    "throttle_sources_raw": src,
                    "throttle_sources_hex": f"0x{src:08X}" if src else None,
                    "active_sources": sources,
                    "is_throttled": is_throttled
                }
                
                # Console output
                time_str = timestamp.strftime('%H:%M:%S')
                if pct_display is None:
                    pct_str = "ERR"
                elif is_throttled:
                    pct_str = f"🔥{pct_display}%"
                else:
                    pct_str = f"{pct_display}%"
                
                src_str = f"0x{src:08X}" if src else "ERR"
                
                print(f"🕐 #{sample_count:3d} {time_str} | Throttle: {pct_str:>6} | Raw: {src_str}")
                
                if sources and "Not implemented" not in sources[0]:
                    for s in sources:
                        print(f"         • {s}")
                elif sources:
                    print(f"         {sources[0]}")
                elif pct_display == 0:
                    print(f"         ✅ No throttling")
                
                # JSON log line
                log_file.write(json.dumps(status) + '\n')
                log_file.flush()
            else:
                print(f"🕐 #{sample_count:3d} {datetime.now().strftime('%H:%M:%S')} | ❌ Read failed")
            
            # Wait 5 seconds (unless stopping)
            for _ in range(5):
                if stop_requested:
                    break
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n⛔ Stopped by user")
    finally:
        log_file.close()
        client.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Duration:      {duration_min} minutes")
    print(f"Total samples: {sample_count}")
    print(f"Successful:    {success_count} ({100*success_count/sample_count:.1f}%)")
    print(f"Log file:      {log_filename}")
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
