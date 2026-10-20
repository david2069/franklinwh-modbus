#!/usr/bin/env python3
"""
1-Hour Throttling Monitor - Auto-logging for unattended testing
Logs ThrotPct, SoC, power, temperature every 30 seconds for 1 hour

Usage: python log_throttling_1hour.py <agate_ip> [unit_id]
Output: throttling_log_YYYYMMDD_HHMMSS.json

Author: Automated test for FranklinWH throttling discovery
"""

import sys
import json
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

# Configuration
LOG_INTERVAL = 30  # seconds between readings
DURATION_MINUTES = 60  # Total test duration
TIMEOUT = 30  # Modbus timeout for WiFi

# Register addresses (SunSpec2 Model 701 DERMeasureAC)
REGS = {
    'ThrotPct': 40180,      # uint16 - Throttling percentage
    'ThrotSrc': 40181,      # bitfield32 - Throttle source (likely unimplemented)
    'W': 40080,             # int16 - Active power (W) - check if throttling affects this
    'SoC': 41037,           # uint16 - Battery SoC from Model 713
    'TmpCab': 40106,        # int16 - Cabinet temperature (x10)
    'TmpSw': 40109,         # int16 - IGBT temperature (x10)
    'St': 40073,            # enum16 - Operating state
    'InvSt': 40074,         # enum16 - Inverter state
}

# Decode helpers
OPERATING_STATES = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault'}
INVERTER_STATES = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running', 
                   4: 'Throttled', 5: 'Shutting Down', 6: 'Fault'}


class ThrottlingLogger:
    def __init__(self, host: str, unit_id: int = 2):
        self.host = host
        self.unit_id = unit_id
        self.client = None
        self.logs = []
        self.start_time = None
        self.stop_requested = False
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        print(f"\n⚠️ Signal {signum} received, stopping...")
        self.stop_requested = True
        
    def connect(self) -> bool:
        """Connect to aGate."""
        self.client = ModbusTcpClient(self.host, port=502, timeout=TIMEOUT)
        if not self.client.connect():
            return False
        print(f"✅ Connected to {self.host}:502 (Unit ID: {self.unit_id})")
        return True
        
    def read_register(self, address: int, count: int = 1) -> list:
        """Read holding registers with error handling."""
        try:
            result = self.client.read_holding_registers(
                address=address - 40001,  # Convert to 0-based
                count=count,
                device_id=self.unit_id
            )
            if result.isError():
                return None
            return result.registers
        except Exception as e:
            return None
            
    def read_battery_soc(self) -> float:
        """Read battery SoC from Model 713 with scale factor."""
        # Model 713: SoC at 41037, scale factor -2 (divide by 100)
        regs = self.read_register(41037, 1)
        if regs:
            return regs[0] / 100.0  # Scale factor -2
        return None
        
    def read_sample(self) -> dict:
        """Take one sample of all relevant data."""
        timestamp = datetime.now().isoformat()
        sample = {
            'timestamp': timestamp,
            'timestamp_unix': time.time(),
        }
        
        # Read ThrotPct (the main one we're testing)
        regs = self.read_register(REGS['ThrotPct'], 1)
        if regs:
            val = regs[0]
            sample['ThrotPct'] = val if val != 0xFFFF else None
            sample['ThrotPct_raw'] = f"0x{val:04X}"
        else:
            sample['ThrotPct'] = None
            sample['ThrotPct_error'] = True
            
        # Read ThrotSrc (bitfield32 - likely unimplemented)
        regs = self.read_register(REGS['ThrotSrc'], 2)
        if regs:
            low, high = regs[0], regs[1]
            val = (high << 16) | low
            sample['ThrotSrc'] = val if val != 0xFFFFFFFF else None
            sample['ThrotSrc_raw'] = f"0x{val:08X}"
        else:
            sample['ThrotSrc'] = None
            
        # Read power (W) - to see if it drops when throttling
        regs = self.read_register(REGS['W'], 1)
        if regs:
            val = regs[0]
            # Handle signed int16
            if val > 32767:
                val -= 65536
            sample['W'] = val  # Positive = charging, Negative = discharging
        else:
            sample['W'] = None
            
        # Read battery SoC
        sample['SoC'] = self.read_battery_soc()
        
        # Read temperatures (scale factor -1, so divide by 10)
        for temp_reg in ['TmpCab', 'TmpSw']:
            regs = self.read_register(REGS[temp_reg], 1)
            if regs:
                val = regs[0]
                if val > 32767:
                    val -= 65536
                sample[temp_reg] = val / 10.0  # Scale factor -1
            else:
                sample[temp_reg] = None
                
        # Read states
        regs = self.read_register(REGS['St'], 1)
        if regs:
            st = regs[0]
            sample['St'] = st
            sample['St_str'] = OPERATING_STATES.get(st, f"Unknown({st})")
        else:
            sample['St'] = None
            
        regs = self.read_register(REGS['InvSt'], 1)
        if regs:
            inv_st = regs[0]
            sample['InvSt'] = inv_st
            sample['InvSt_str'] = INVERTER_STATES.get(inv_st, f"Unknown({inv_st})")
            # Note: InvSt=4 is "Throttled" per SunSpec
            sample['is_inv_throttled'] = (inv_st == 4)
        else:
            sample['InvSt'] = None
            sample['is_inv_throttled'] = False
            
        return sample
        
    def run(self):
        """Main logging loop."""
        if not self.connect():
            print("❌ Failed to connect!")
            return False
            
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(minutes=DURATION_MINUTES)
        
        print(f"\n📝 Starting 1-hour logging session")
        print(f"   Start: {self.start_time.strftime('%H:%M:%S')}")
        print(f"   End:   {end_time.strftime('%H:%M:%S')}")
        print(f"   Interval: {LOG_INTERVAL}s")
        print(f"   Expected samples: ~{DURATION_MINUTES * 60 // LOG_INTERVAL}")
        print(f"\n⏱️  Logging... (Press Ctrl+C to stop early)")
        print("=" * 70)
        
        # Header for console output
        print(f"{'Time':<12} {'SoC':>5} {'Power':>7} {'Throttle':>8} {'InvState':>10} {'CabTemp':>8}")
        print("-" * 70)
        
        sample_count = 0
        throttle_detected_count = 0
        
        while not self.stop_requested:
            now = datetime.now()
            if now >= end_time:
                print("\n✅ 1-hour duration reached!")
                break
                
            # Take sample
            sample = self.read_sample()
            self.logs.append(sample)
            sample_count += 1
            
            # Track throttling
            throt_pct = sample.get('ThrotPct')
            if throt_pct is not None and throt_pct > 0:
                throttle_detected_count += 1
                
            # Console output
            time_str = now.strftime('%H:%M:%S')
            soc = sample.get('SoC', '-')
            power = sample.get('W', '-')
            throttle = sample.get('ThrotPct', '-')
            inv_state = sample.get('InvSt_str', '-')
            cab_temp = sample.get('TmpCab', '-')
            
            # Format for display
            soc_str = f"{soc:.1f}%" if soc is not None else "-"
            power_str = f"{power}W" if power is not None else "-"
            throttle_str = f"{throttle}%" if throttle is not None else "-"
            temp_str = f"{cab_temp:.1f}°C" if cab_temp is not None else "-"
            
            # Highlight throttling
            if throttle is not None and throttle > 0:
                throttle_str = f"🔥{throttle}%"
            if sample.get('is_inv_throttled'):
                inv_state = f"⚠️{inv_state}"
                
            print(f"{time_str:<12} {soc_str:>5} {power_str:>7} {throttle_str:>8} {inv_state:>10} {temp_str:>8}")
            
            # Sleep until next interval
            elapsed = (datetime.now() - now).total_seconds()
            sleep_time = LOG_INTERVAL - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
        # Cleanup
        self.client.close()
        
        # Save results
        self._save_results(sample_count, throttle_detected_count)
        return True
        
    def _save_results(self, sample_count: int, throttle_events: int):
        """Save logs and generate report."""
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        output_file = Path(f"throttling_log_{timestamp}.json")
        report_file = Path(f"throttling_report_{timestamp}.md")
        
        # Save raw JSON log
        output_data = {
            'metadata': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'host': self.host,
                'unit_id': self.unit_id,
                'duration_minutes': DURATION_MINUTES,
                'interval_seconds': LOG_INTERVAL,
                'total_samples': sample_count,
                'throttle_events': throttle_events,
            },
            'logs': self.logs
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\n💾 Raw log saved: {output_file}")
        
        # Generate Markdown report
        self._generate_report(report_file, sample_count, throttle_events)
        print(f"📊 Report saved: {report_file}")
        
    def _generate_report(self, report_file: Path, sample_count: int, throttle_events: int):
        """Generate human-readable report."""
        # Calculate statistics
        throt_values = [s['ThrotPct'] for s in self.logs if s.get('ThrotPct') is not None]
        soc_values = [s['SoC'] for s in self.logs if s.get('SoC') is not None]
        power_values = [s['W'] for s in self.logs if s.get('W') is not None]
        
        max_throttle = max(throt_values) if throt_values else 0
        avg_throttle = sum(throt_values) / len(throt_values) if throt_values else 0
        
        start_soc = soc_values[0] if soc_values else None
        end_soc = soc_values[-1] if soc_values else None
        
        start_power = power_values[0] if power_values else None
        end_power = power_values[-1] if power_values else None
        
        # Find any throttling events with context
        throttle_details = []
        for i, sample in enumerate(self.logs):
            throt = sample.get('ThrotPct')
            if throt and throt > 0:
                throttle_details.append({
                    'time': sample['timestamp'],
                    'throttle_pct': throt,
                    'soc': sample.get('SoC'),
                    'power': sample.get('W'),
                    'cab_temp': sample.get('TmpCab'),
                    'inv_state': sample.get('InvSt_str')
                })
        
        # Write report
        with open(report_file, 'w') as f:
            f.write("# Throttling Monitor Report\n\n")
            f.write(f"**Date:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Host:** {self.host} (Unit ID: {self.unit_id})\n")
            f.write(f"**Duration:** {DURATION_MINUTES} minutes\n")
            f.write(f"**Interval:** {LOG_INTERVAL} seconds\n\n")
            
            f.write("## Summary\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Total Samples | {sample_count} |\n")
            f.write(f"| Throttling Events | {throttle_events} |\n")
            f.write(f"| Max Throttle | {max_throttle}% |\n")
            f.write(f"| Avg Throttle | {avg_throttle:.1f}% |\n")
            f.write(f"| Start SoC | {start_soc}% |\n") if start_soc else None
            f.write(f"| End SoC | {end_soc}% |\n") if end_soc else None
            f.write(f"| Start Power | {start_power}W |\n") if start_power else None
            f.write(f"| End Power | {end_power}W |\n") if end_power else None
            f.write("\n")
            
            if throttle_events > 0:
                f.write("## ⚠️ Throttling Events Detected!\n\n")
                f.write("| Time | Throttle% | SoC | Power | CabTemp | InvState |\n")
                f.write("|------|-----------|-----|-------|---------|----------|\n")
                for event in throttle_details:
                    f.write(f"| {event['time'].split('T')[1][:8]} | "
                           f"{event['throttle_pct']}% | "
                           f"{event['soc']}% | "
                           f"{event['power']}W | "
                           f"{event['cab_temp']:.1f}°C | "
                           f"{event['inv_state']} |\n")
                f.write("\n")
            else:
                f.write("## ✅ No Throttling Detected\n\n")
                f.write("ThrotPct remained at 0% throughout the test period.\n\n")
                
            f.write("## Key Findings\n\n")
            
            if max_throttle > 0:
                f.write(f"1. **Throttling occurred:** Maximum of {max_throttle}% detected\n")
                f.write(f"2. **ThrotPct works:** Register 40180 is functional\n")
                if throttle_details and any(e['soc'] and e['soc'] > 90 for e in throttle_details):
                    f.write(f"3. **High SoC correlation:** Throttling detected when SoC > 90%\n")
                if throttle_details and any(e['cab_temp'] and e['cab_temp'] > 40 for e in throttle_details):
                    f.write(f"3. **Thermal correlation:** Throttling detected when cabinet temp > 40°C\n")
            else:
                f.write(f"1. **No throttling:** ThrotPct remained at 0%\n")
                f.write(f"2. **ThrotPct readable:** Register 40180 returns valid data\n")
                if end_soc and end_soc < 95:
                    f.write(f"3. **SoC not limiting:** Battery at {end_soc}%, no charge throttling yet\n")
                    
            # Check ThrotSrc status
            throt_src_samples = [s for s in self.logs if s.get('ThrotSrc') is not None]
            if throt_src_samples:
                f.write(f"4. **ThrotSrc partially works:** {len(throt_src_samples)} samples had valid data\n")
            else:
                f.write(f"4. **ThrotSrc unimplemented:** Always returned 0xFFFFFFFF\n")
                
            f.write("\n## Conclusion\n\n")
            if max_throttle > 0:
                f.write("Throttling monitoring is **valuable** - detected active throttling. "
                       "Recommend adding to dashboard with alerts.\n")
            else:
                f.write("Throttling monitoring **works but no events occurred** during test. "
                       "Consider re-testing when SoC > 95% or on hot day.\n")
                
            f.write("\n---\n")
            f.write(f"*Report generated automatically by log_throttling_1hour.py*\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python log_throttling_1hour.py <agate_ip> [unit_id]")
        print("Example: python log_throttling_1hour.py 192.0.2.110 2")
        print("\nThis will log throttling data every 30 seconds for 1 hour.")
        print("Output files: throttling_log_YYYYMMDD_HHMMSS.json")
        print("              throttling_report_YYYYMMDD_HHMMSS.md")
        sys.exit(1)
        
    host = sys.argv[1]
    unit_id = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    
    logger = ThrottlingLogger(host, unit_id)
    success = logger.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
