#!/usr/bin/env python3
"""
FranklinWH aGate X Throttle Control with Heartbeat & Safety
Compatible with pymodbus 2.x and 3.x APIs
"""

import time
import threading
import sys
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

AGATE_IP = "192.0.2.110"
UNIT_ID = 2

# Detect pymodbus version for API compatibility
PYMODBUS_VERSION = tuple(map(int, __import__('pymodbus').__version__.split('.')[:2]))
print(f"Detected pymodbus version: {PYMODBUS_VERSION}")

def get_slave_param(unit_id):
    """Return correct parameter name for unit/slave"""
    if PYMODBUS_VERSION >= (3, 0):
        return {'slave': unit_id}
    else:
        return {'unit': unit_id}


# Register addresses (0-based for pymodbus, relative to base 40001)
REG_CONTROLLER_HB = 41092 - 40001   # RW: Your heartbeat to aGate
REG_WMAX_LIM_PCT = 40311 - 40001    # RW: Power limit %
REG_WMAX_LIM_PCT_RVRT_TMS = 40314 - 40001  # RW: Reversion timeout
REG_WMAX_LIM_PCT_RVRT_REM = 40316 - 40001  # R: Remaining time
REG_THROT_PCT = 40180 - 40001       # R: Current throttle %
REG_THROT_SRC = 40181 - 40001       # R: Throttle source (2 words)
REG_OP_CTL = 41095 - 40001          # RW: Emergency stop
REG_LOC_REM_CTL = 41089 - 40001     # R: Control mode


class AGateThrottleController:
    def __init__(self, ip, unit_id):
        self.client = ModbusTcpClient(ip, port=502)
        self.unit_id = unit_id
        self.hb_counter = 0
        self.running = False
        self.hb_thread = None
        self._slave_kw = get_slave_param(unit_id)
        
    def connect(self):
        if not self.client.connect():
            raise ConnectionError(f"Failed to connect to {AGATE_IP}:502")
        print(f"✅ Connected to aGate at {AGATE_IP}")
        
        # Verify control mode
        try:
            mode = self._read_register(REG_LOC_REM_CTL)
            modes = {0: "Local", 1: "Remote", 2: "External EMS"}
            print(f"📡 Control mode: {modes.get(mode, f'Unknown ({mode})')}")
        except Exception as e:
            print(f"⚠️ Could not read control mode: {e}")
        
    def _read_register(self, address, count=1):
        """Read holding registers with version-compatible API"""
        try:
            if PYMODBUS_VERSION >= (3, 0):
                result = self.client.read_holding_registers(address, count, **self._slave_kw)
            else:
                result = self.client.read_holding_registers(address, count, **self._slave_kw)
                
            if result.isError():
                raise ModbusException(f"Modbus error: {result}")
            if count == 1:
                return result.registers[0]
            return result.registers
            
        except Exception as e:
            raise ModbusException(f"Read failed at {address}: {e}")
    
    def _write_register(self, address, value):
        """Write single register with version-compatible API"""
        try:
            if PYMODBUS_VERSION >= (3, 0):
                result = self.client.write_register(address, value, **self._slave_kw)
            else:
                result = self.client.write_register(address, value, **self._slave_kw)
                
            if result.isError():
                raise ModbusException(f"Write error: {result}")
            return True
            
        except Exception as e:
            raise ModbusException(f"Write failed at {address}: {e}")
        
    def start_heartbeat(self, interval_sec=5):
        """Start background heartbeat thread"""
        self.running = True
        
        def heartbeat_loop():
            failures = 0
            while self.running:
                try:
                    self._send_heartbeat()
                    failures = 0
                except Exception as e:
                    failures += 1
                    print(f"⚠️ Heartbeat failed ({failures}): {e}")
                    if failures >= 3:
                        print("❌ Too many heartbeat failures, stopping")
                        self.running = False
                        break
                time.sleep(interval_sec)
                
        self.hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.hb_thread.start()
        print(f"💓 Heartbeat started ({interval_sec}s interval)")
        
    def _send_heartbeat(self):
        """Write incrementing heartbeat to register 41092"""
        self.hb_counter = (self.hb_counter + 1) % 65536
        self._write_register(REG_CONTROLLER_HB, self.hb_counter)
            
    def set_power_limit(self, percent: float, timeout_sec: int = None):
        """
        Set power limit with optional safety timeout
        
        percent: 0-100 (e.g., 50.0 for 50%)
        timeout_sec: Reversion timeout, or None for persistent
        """
        # Scale: WMaxLimPct_SF = -1 → 500 = 50.0%
        raw_value = int(percent * 10)
        
        # Ensure heartbeat is running for safety
        if not self.running and timeout_sec:
            print("⚠️ Warning: Heartbeat not running, using shorter timeout")
            timeout_sec = min(timeout_sec, 60)
        
        # Write limit
        self._write_register(REG_WMAX_LIM_PCT, raw_value)
        
        # Write timeout if specified
        if timeout_sec is not None:
            self._write_register(REG_WMAX_LIM_PCT_RVRT_TMS, timeout_sec)
            print(f"🎯 Power limit: {percent}% (reverts in {timeout_sec}s)")
        else:
            print(f"🎯 Power limit: {percent}% (persistent)")
            
    def read_throttle_status(self):
        """Read current throttle state and remaining timeout"""
        # Read throttle percent (scale -1)
        throt_pct_raw = self._read_register(REG_THROT_PCT)
        throt_pct = throt_pct_raw * 0.1
        
        # Read throttle source (32-bit, big-endian)
        throt_src_words = self._read_register(REG_THROT_SRC, 2)
        throt_src = (throt_src_words[0] << 16) | throt_src_words[1]
        
        # Decode sources
        sources = self._decode_throt_src(throt_src)
        
        # Read remaining reversion time
        try:
            rvrt_rem = self._read_register(REG_WMAX_LIM_PCT_RVRT_REM)
        except:
            rvrt_rem = None
            
        return {
            "throttle_percent": throt_pct,
            "throttle_source_hex": f"0x{throt_src:08X}",
            "throttle_sources": sources,
            "reversion_remaining_sec": rvrt_rem,
            "heartbeat_count": self.hb_counter,
            "timestamp": time.time()
        }
    
    def _decode_throt_src(self, src_value):
        """Decode throttle source bitfield"""
        SOURCES = {
            0: ("GridCmd", "🔌 Utility command"),
            1: ("FreqReg", "📊 Frequency regulation"),
            2: ("VoltReg", "⚡ Voltage regulation"),
            3: ("TempDerate", "🌡️ Temperature derating"),
            4: ("SOCLimit", "🔋 Battery SOC limit"),
            5: ("GenLimit", "⛽ Generator capacity"),
            6: ("IslandStab", "🏝️ Island stabilization"),
            7: ("UserLimit", "👤 User-set limit"),
            8: ("PVLimit", "☀️ PV input limit"),
            9: ("CurrLimit", "🔒 Hardware current limit"),
            10: ("CommLoss", "📡 Communication loss"),
        }
        
        active = []
        for bit, (code, desc) in SOURCES.items():
            if src_value & (1 << bit):
                active.append({"bit": bit, "code": code, "description": desc})
        
        # Vendor reserved
        for bit in range(11, 32):
            if src_value & (1 << bit):
                active.append({"bit": bit, "code": f"Vendor_{bit}", "description": "🏭 FranklinWH proprietary"})
                
        return active
        
    def release_limit(self):
        """Remove power limit (100%)"""
        self.set_power_limit(100.0, timeout_sec=None)
        
    def emergency_stop(self):
        """Immediate shutdown via OpCtl"""
        self._write_register(REG_OP_CTL, 1)
        self.running = False
        print("🛑 Emergency stop triggered")
        
    def close(self):
        """Graceful shutdown"""
        self.running = False
        if self.hb_thread:
            self.hb_thread.join(timeout=3)
        try:
            self.client.close()
        except:
            pass
        print("🔌 Connection closed")


# Example usage
def main():
    ctrl = AGateThrottleController(AGATE_IP, UNIT_ID)
    
    try:
        ctrl.connect()
        
        # Read initial status
        print("\n📊 Initial status:")
        status = ctrl.read_throttle_status()
        print(f"   Throttle: {status['throttle_percent']:.1f}%")
        print(f"   Sources: {[s['code'] for s in status['throttle_sources']]}")
        
        # Start heartbeat for safety
        ctrl.start_heartbeat(interval_sec=5)
        
        # Example: Limit to 60% with 2-minute timeout
        print("\n🎛️ Setting 60% limit with 120s timeout...")
        ctrl.set_power_limit(60.0, timeout_sec=120)
        
        # Monitor loop
        print("\n📈 Monitoring (Ctrl+C to stop):")
        try:
            while True:
                time.sleep(10)
                status = ctrl.read_throttle_status()
                
                sources = ", ".join([s['code'] for s in status['throttle_sources']]) or "None"
                rvrt = f"{status['reversion_remaining_sec']}s" if status['reversion_remaining_sec'] else "N/A"
                
                print(f"[{time.strftime('%H:%M:%S')}] "
                      f"Throttle: {status['throttle_percent']:.1f}% | "
                      f"Sources: {sources} | "
                      f"Revert: {rvrt} | "
                      f"HB: {status['heartbeat_count']}")
                      
        except KeyboardInterrupt:
            print("\n⛔ Stopped by user")
            
        # Release limit before exit
        ctrl.release_limit()
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
        
    finally:
        ctrl.close()


if __name__ == "__main__":
    main()
