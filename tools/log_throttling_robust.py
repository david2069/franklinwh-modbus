#!/usr/bin/env python3
"""
Robust Throttling Logger - Handles WiFi drops and reconnections
Uses same patterns as franklinwh_control_standalone.py

Usage: python log_throttling_robust.py <agate_ip> [unit_id] [duration_minutes]
Output: throttling_robust_YYYYMMDD_HHMMSS.csv
"""

import sys
import time
import signal
import csv
from datetime import datetime, timedelta
from pathlib import Path
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

# Configuration
DEFAULT_DURATION = 60  # minutes
INTERVAL = 30  # seconds
RECONNECT_DELAY = 5  # seconds after connection failure
MAX_RETRIES = 3  # retries per read
TIMEOUT = 30  # Modbus timeout

# SunSpec2 Register addresses (Model 701 DERMeasureAC + 713)
REG_THROTPCT = 40180      # uint16 - Throttling percentage (0-100%)
REG_THROTSRC = 40181      # bitfield32 - Throttle source (likely unimplemented)
REG_W = 40080             # int16 - Active power (W), scale 0
REG_SOC = 41037           # uint16 - Battery SoC, scale -2 (divide by 100)
REG_TMPCAB = 40106        # int16 - Cabinet temp, scale -1 (divide by 10)
REG_TMPSW = 40109         # int16 - IGBT temp, scale -1
REG_ST = 40073            # enum16 - Operating state
REG_INVST = 40074         # enum16 - Inverter state

# Scale factors
SF_W = 0      # W_SF at 40186
SF_TEMP = -1  # Tmp_SF at 40192
SF_SOC = -2   # SoC has scale -2

# State mappings
INV_STATES = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running', 
              4: 'Throttled', 5: 'ShuttingDown', 6: 'Fault', 7: 'Standby'}
OP_STATES = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault', 
             4: 'ShuttingDown', 5: 'Starting', 6: 'Maintenance'}


class RobustThrottlingLogger:
    def __init__(self, host: str, unit_id: int = 2, duration_min: int = 60):
        self.host = host
        self.unit_id = unit_id
        self.duration = timedelta(minutes=duration_min)
        self.client = None
        self.connected = False
        self.logs = []
        self.start_time = None
        self.stop_requested = False
        self.csv_file = None
        self.csv_writer = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        print(f"\n⚠️ Signal received, finishing...")
        self.stop_requested = True
        
    def connect(self) -> bool:
        """Connect to aGate with retry logic."""
        if self.client:
            try:
                self.client.close()
            except:
                pass
                
        print(f"🔌 Connecting to {self.host}:502...")
        try:
            self.client = ModbusTcpClient(
                self.host, 
                port=502, 
                timeout=TIMEOUT
            )
            self.connected = self.client.connect()
            if self.connected:
                print("✅ Connected!")
            return self.connected
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False
            
    def _read_registers(self, address: int, count: int) -> list:
        """Read holding registers with retry logic."""
        for attempt in range(MAX_RETRIES):
            if not self.connected:
                if not self.connect():
                    return None
                    
            try:
                result = self.client.read_holding_registers(
                    address=address - 40001,  # Convert to 0-based
                    count=count,
                    device_id=self.unit_id
                )
                
                if result.isError():
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(1)
                        continue
                    return None
                    
                return result.registers
                
            except ConnectionException:
                print(f"  ⚠️ Connection lost, reconnecting...")
                self.connected = False
                if not self.connect():
                    return None
                    
            except ModbusException as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)
                    continue
                return None
                
            except Exception as e:
                print(f"  ⚠️ Read error: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)
                    continue
                return None
                
        return None
        
    def read_sample(self) -> dict:
        """Read all registers for one sample with error handling per field."""
        sample = {
            'timestamp': datetime.now().isoformat(),
            'unix_time': time.time(),
        }
        
        # Read ThrotPct (most important)
        regs = self._read_registers(REG_THROTPCT, 1)
        if regs:
            val = regs[0]
            sample['ThrotPct'] = val if val != 0xFFFF else None
            sample['ThrotPct_ok'] = True
        else:
            sample['ThrotPct'] = None
            sample['ThrotPct_ok'] = False
            
        # Read ThrotSrc (bitfield32)
        regs = self._read_registers(REG_THROTSRC, 2)
        if regs:
            val = (regs[1] << 16) | regs[0]
            sample['ThrotSrc'] = val if val != 0xFFFFFFFF else None
        else:
            sample['ThrotSrc'] = None
            
        # Read Power (W) - signed
        regs = self._read_registers(REG_W, 1)
        if regs:
            val = regs[0]
            if val > 32767:
                val -= 65536
            sample['W'] = val  # Scale factor 0, so raw = actual
        else:
            sample['W'] = None
            
        # Read SoC from Model 713
        regs = self._read_registers(REG_SOC, 1)
        if regs:
            sample['SoC'] = regs[0] / 100.0  # Scale factor -2
        else:
            sample['SoC'] = None
            
        # Read temperatures
        for reg, name in [(REG_TMPCAB, 'TmpCab'), (REG_TMPSW, 'TmpSw')]:
            regs = self._read_registers(reg, 1)
            if regs:
                val = regs[0]
                if val > 32767:
                    val -= 65536
                sample[name] = val / 10.0  # Scale factor -1
            else:
                sample[name] = None
                
        # Read states
        regs = self._read_registers(REG_ST, 1)
        if regs:
            st = regs[0]
            sample['St'] = st
            sample['St_str'] = OP_STATES.get(st, f'Unknown({st})')
        else:
            sample['St'] = None
            sample['St_str'] = 'Error'
            
        regs = self._read_registers(REG_INVST, 1)
        if regs:
            inv = regs[0]
            sample['InvSt'] = inv
            sample['InvSt_str'] = INV_STATES.get(inv, f'Unknown({inv})')
            sample['is_throttled'] = (inv == 4)
        else:
            sample['InvSt'] = None
            sample['InvSt_str'] = 'Error'
            sample['is_throttled'] = False
            
        return sample
        
    def _init_csv(self):
        """Initialize CSV file for logging."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"throttling_robust_{timestamp}.csv"
        self.csv_file = open(filename, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header
        self.csv_writer.writerow([
            'Timestamp', 'UnixTime', 'ThrotPct', 'ThrotSrc', 'SoC_%', 
            'Power_W', 'CabTemp_C', 'SwTemp_C', 'OpState', 'InvState',
            'Throttled', 'ReadOK'
        ])
        self.csv_file.flush()
        print(f"💾 Logging to: {filename}")
        
    def _write_csv(self, sample: dict):
        """Write sample to CSV."""
        self.csv_writer.writerow([
            sample['timestamp'],
            sample['unix_time'],
            sample.get('ThrotPct'),
            sample.get('ThrotSrc'),
            sample.get('SoC'),
            sample.get('W'),
            sample.get('TmpCab'),
            sample.get('TmpSw'),
            sample.get('St_str'),
            sample.get('InvSt_str'),
            sample.get('is_throttled'),
            sample.get('ThrotPct_ok', False)
        ])
        self.csv_file.flush()
        
    def _print_status(self, sample: dict, sample_num: int):
        """Print status line."""
        time_str = datetime.now().strftime('%H:%M:%S')
        throt = sample.get('ThrotPct')
        soc = sample.get('SoC')
        power = sample.get('W')
        inv = sample.get('InvSt_str', '?')
        temp = sample.get('TmpCab')
        ok = sample.get('ThrotPct_ok', False)
        
        # Format values
        throt_str = f"{throt}%" if throt is not None else "ERR"
        soc_str = f"{soc:.1f}%" if soc is not None else "ERR"
        power_str = f"{power}W" if power is not None else "ERR"
        temp_str = f"{temp:.1f}°C" if temp is not None else "ERR"
        
        # Highlight issues
        if not ok:
            throt_str = "❌ERR"
        elif throt and throt > 0:
            throt_str = f"🔥{throt}%"
            
        if sample.get('is_throttled'):
            inv = f"⚠️{inv}"
            
        print(f"#{sample_num:3d} {time_str} | SoC:{soc_str:>6} | P:{power_str:>7} | "
              f"Throt:{throt_str:>6} | {inv:12s} | {temp_str:>6}")
        
    def run(self):
        """Main logging loop with reconnection handling."""
        print(f"\n{'='*70}")
        print(f"📝 Robust Throttling Logger")
        print(f"   Host: {self.host}:{self.unit_id}")
        print(f"   Duration: {self.duration.total_seconds()/60:.0f} minutes")
        print(f"   Interval: {INTERVAL}s")
        print(f"{'='*70}\n")
        
        if not self.connect():
            print("❌ Failed to connect!")
            return False
            
        self._init_csv()
        self.start_time = datetime.now()
        end_time = self.start_time + self.duration
        
        print(f"⏱️  Logging until {end_time.strftime('%H:%M:%S')}...")
        print(f"   (Press Ctrl+C to stop early)")
        print(f"\nSample #Time     | SoC     | Power   | Throttle | InvState     | Temp")
        print("-" * 70)
        
        sample_count = 0
        success_count = 0
        
        while not self.stop_requested:
            now = datetime.now()
            if now >= end_time:
                print(f"\n✅ Duration reached!")
                break
                
            sample_count += 1
            sample = self.read_sample()
            
            if sample.get('ThrotPct_ok'):
                success_count += 1
                
            self._print_status(sample, sample_count)
            self._write_csv(sample)
            self.logs.append(sample)
            
            # Sleep until next interval
            elapsed = (datetime.now() - now).total_seconds()
            sleep_time = INTERVAL - elapsed
            if sleep_time > 0 and not self.stop_requested:
                time.sleep(sleep_time)
                
        # Cleanup
        if self.csv_file:
            self.csv_file.close()
        if self.client:
            try:
                self.client.close()
            except:
                pass
                
        self._print_summary(sample_count, success_count)
        return True
        
    def _print_summary(self, total: int, success: int):
        """Print summary statistics."""
        print(f"\n{'='*70}")
        print("📊 SUMMARY")
        print(f"{'='*70}")
        print(f"Total samples:     {total}")
        print(f"Successful reads:  {success} ({100*success/total:.1f}%)")
        
        # Throttling stats
        throt_values = [s.get('ThrotPct') for s in self.logs 
                       if s.get('ThrotPct') is not None and s.get('ThrotPct_ok')]
        if throt_values:
            max_throt = max(throt_values)
            avg_throt = sum(throt_values) / len(throt_values)
            print(f"Max ThrotPct:      {max_throt}%")
            print(f"Avg ThrotPct:      {avg_throt:.1f}%")
            
            if max_throt > 0:
                print(f"\n🔥 THROTTLING DETECTED!")
                print(f"   ThrotPct went above 0% during test")
            else:
                print(f"\n✅ No throttling (ThrotPct remained 0%)")
        else:
            print(f"\n❌ No valid ThrotPct readings")
            
        # SoC change
        soc_values = [s.get('SoC') for s in self.logs if s.get('SoC') is not None]
        if soc_values:
            print(f"SoC range:         {min(soc_values):.1f}% → {max(soc_values):.1f}%")
            
        print(f"\n💾 CSV saved: {self.csv_file.name if self.csv_file else 'N/A'}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python log_throttling_robust.py <agate_ip> [unit_id] [duration_min] [timeout_sec]")
        print("Example: python log_throttling_robust.py 192.0.2.110 2 60 30")
        print("  Default unit_id: 2")
        print("  Default duration: 60 minutes")
        print("  Default timeout: 30 seconds (10 for Ethernet, 30+ for WiFi)")
        sys.exit(1)
        
    host = sys.argv[1]
    unit_id = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    duration = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_DURATION
    
    # Allow global TIMEOUT override
    global TIMEOUT
    TIMEOUT = int(sys.argv[4]) if len(sys.argv) > 4 else TIMEOUT
    
    logger = RobustThrottlingLogger(host, unit_id, duration)
    success = logger.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
