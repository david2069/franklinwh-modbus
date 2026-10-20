#!/usr/bin/env python3
"""
FranklinWH aGate X Throttle Monitor
Polls ThrotPct and ThrotSrc, logs with timestamp
"""

from pymodbus.client import ModbusTcpClient
from datetime import datetime
import json
import time

AGATE_IP = "192.0.2.110"
UNIT_ID = 2
THROT_PCT_ADDR = 40180  # 40000 base + 180 offset
THROT_SRC_ADDR = 40181

SOURCES = {
    0:  ("GridCmd",     "🔌 Utility/grid operator command"),
    1:  ("FreqReg",     "📊 Frequency regulation active"),
    2:  ("VoltReg",     "⚡ Voltage regulation active"),
    3:  ("TempDerate",  "🌡️  Temperature derating"),
    4:  ("SOCLimit",    "🔋 Battery SOC protection"),
    5:  ("GenLimit",    "⛽ Generator capacity limit"),
    6:  ("IslandStab",  "🏝️  Island mode stabilization"),
    7:  ("UserLimit",   "👤 User/installer manual limit"),
    8:  ("PVLimit",     "☀️  PV input limit"),
    9:  ("CurrLimit",   "🔒 Current/hardware limit"),
    10: ("CommLoss",    "📡 Communication loss"),
}


def read_registers(client):
    """Read throttle registers from aGate"""
    # Note: Modbus addresses are 0-based in pymodbus
    result = client.read_holding_registers(
        address=THROT_PCT_ADDR - 40001,  # Convert to 0-based
        count=2,
        slave=UNIT_ID
    )
    if result.isError():
        raise Exception(f"Modbus error: {result}")
    
    throt_pct = result.registers[0]
    throt_src = (result.registers[1] << 16) | 0  # 32-bit, high word first
    
    return throt_pct, throt_src


def decode_sources(src_value):
    """Decode bitfield to human-readable list"""
    active = []
    for bit, (code, emoji_desc) in SOURCES.items():
        if src_value & (1 << bit):
            active.append(f"{emoji_desc} ({code})")
    
    # Vendor reserved
    for bit in range(11, 32):
        if src_value & (1 << bit):
            active.append(f"🏭 VendorReserved_{bit}")
    
    return active


def main():
    client = ModbusTcpClient(AGATE_IP, port=502)
    
    if not client.connect():
        print(f"❌ Failed to connect to {AGATE_IP}")
        return
    
    print(f"✅ Connected to FranklinWH aGate X at {AGATE_IP}")
    print("=" * 60)
    
    try:
        while True:
            timestamp = datetime.now().isoformat()
            pct, src = read_registers(client)
            sources = decode_sources(src)
            
            status = {
                "timestamp": timestamp,
                "throttle_percent": pct,
                "throttle_sources_raw": src,
                "throttle_sources_hex": f"0x{src:08X}",
                "active_sources": sources,
                "is_throttled": pct > 0 or src != 0
            }
            
            # Console output
            print(f"\n🕐 {timestamp}")
            print(f"   Throttle: {pct}% | Raw: 0x{src:08X}")
            
            if sources:
                print("   Active limits:")
                for s in sources:
                    print(f"      • {s}")
            else:
                print("   ✅ No throttling active")
            
            # JSON log line (for parsing)
            print(json.dumps(status))
            
            time.sleep(5)  # Poll every 5 seconds
            
    except KeyboardInterrupt:
        print("\n⛔ Stopped by user")
    finally:
        client.close()


if __name__ == "__main__":
    main()
