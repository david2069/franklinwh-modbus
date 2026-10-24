#!/usr/bin/env python3
"""
FranklinWH Demo - Fixed connection handling, better monitoring
"""

import time
import logging
from pymodbus.client import ModbusTcpClient
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class FranklinWHController:
    """Working controller with proper connection management."""
    
    def __init__(self, ip: str = 'YOUR_AGATE_IP', unit: int = 2):
        self.ip = ip
        self.unit = unit
        self.sunspec = None
        self.raw = None
        self._m704 = None  # Cache model reference
        
    def connect(self) -> bool:
        try:
            logger.info(f"Connecting to {self.ip}...")
            
            # SunSpec first
            self.sunspec = SunSpecModbusClientDeviceTCP(
                slave_id=self.unit, ipaddr=self.ip, ipport=502, timeout=10
            )
            self.sunspec.connect()
            self.sunspec.scan()
            
            if 704 not in self.sunspec.models:
                logger.error("Model 704 not found")
                return False
            
            self._m704 = self.sunspec.models[704][0]
            
            # Raw Modbus
            self.raw = ModbusTcpClient(self.ip, port=502, timeout=10)
            if not self.raw.connect():
                logger.error("Raw connection failed")
                return False
            
            logger.info("Connected")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Safe disconnect with idle command."""
        try:
            if self._m704:
                logger.info("Setting idle before disconnect...")
                self._m704.read()
                self._m704.WSetEna.value = 0
                self._m704.WSet.value = 0
                self._m704.write()
                time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Idle command failed: {e}")
        
        try:
            if self.sunspec:
                self.sunspec.close()
        except:
            pass
            
        try:
            if self.raw:
                self.raw.close()
        except:
            pass
        
        logger.info("Disconnected")
    
    def read_status(self) -> dict:
        """Read with retry on connection error."""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                r = self.raw.read_holding_registers(
                    address=15500, count=14, device_id=self.unit
                )
                if not r.isError():
                    regs = r.registers
                    home_load_quantized = regs[6]  # ~100W steps
                    
                    # Try high-res home load from register 16000 (~1W precision)
                    home_load = home_load_quantized
                    try:
                        hires = self.raw.read_holding_registers(
                            address=16000, count=1, device_id=self.unit
                        )
                        if not hires.isError() and len(hires.registers) > 0:
                            val = hires.registers[0]
                            if val > 0 or home_load_quantized == 0:
                                home_load = val
                    except Exception:
                        pass
                    
                    return {
                        'pv_total_w': regs[2],
                        'home_load_w': home_load,
                        'ongrid_mode': regs[7],
                    }
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Read failed, retrying: {e}")
                    time.sleep(0.5)
                else:
                    logger.error(f"Read failed: {e}")
        
        return {}
    
    def read_battery_soc(self) -> int:
        """Read SOC from Model 713."""
        try:
            if 713 not in self.sunspec.models:
                return -1
            
            m713 = self.sunspec.models[713][0]
            m713.read()
            
            # Scale factor is typically -1 for SOC (tenths of percent)
            soc = m713.SoC.value
            sf = m713.Pct_SF.value if hasattr(m713, 'Pct_SF') else -1
            return int(soc * (10 ** sf))
        except Exception as e:
            logger.error(f"SOC read failed: {e}")
            return -1
    
    def command(self, power_w: float) -> bool:
        """Send battery power command as WSet watts, in the aGate's sign.

        WSet positive = discharge, negative = charge (V12R02B60D00, c3/c8).
        V12 refuses negative WSet (charge) with exception 3.
        """
        try:
            self._m704.read()
            
            old_wset = self._m704.WSet.value
            old_ena = self._m704.WSetEna.value
            
            self._m704.WSet.value = int(power_w)
            self._m704.WSetMod.value = 1  # WATTS (SunSpec 704; 2 is not defined)
            self._m704.WSetEna.value = 1
            
            self._m704.write()
            time.sleep(0.2)
            
            # Verify
            self._m704.read()
            success = (self._m704.WSetEna.value == 1 and 
                      self._m704.WSet.value == int(power_w))
            
            action = "discharge" if power_w > 0 else "charge" if power_w < 0 else "idle"
            logger.info(f"Command: {abs(power_w):.0f}W {action} "
                       f"(was: ena={old_ena}, wset={old_wset})")
            
            return success
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False

    def read_grid_simple(self) -> dict:
        """Read grid power with known scale factors."""
        try:
            # Read W, VA, Var, PF, A, V (Hz is 32-bit, skip for simplicity)
            result = self.raw.read_holding_registers(
                address=40080, count=7, device_id=self.unit
            )
            if result.isError():
                return {}
            
            regs = result.registers
            
            return {
                'w': regs[0],           # W_SF = 0, so direct value
                'va': regs[1],          # VA_SF = 0
                'var': regs[2],         # Var_SF = 0
                'pf': regs[3] / 1000,   # PF_SF = -3
                'a': regs[4] / 10,      # A_SF = -1
                'v': regs[6] / 10,      # V_SF = -1 (LNV at offset 6)
            }
            
        except Exception as e:
            return {}

def demo():
    """Demonstration with clear before/after comparison."""
    ctrl = FranklinWHController()
    
    if not ctrl.connect():
        print("Failed to connect")
        return
    
    try:
        print("\n" + "=" * 70)
        print("FRANKLINWH BATTERY CONTROL DEMO")
        print("=" * 70)
        print("\nWatching PV, Home Load, and inferred Battery activity")
        print("Home load INCREASE = battery charging")
        print("Home load DECREASE = battery discharging")
        print("-" * 70)
        
        # Baseline
        print("\n--- BASELINE (5 seconds) ---")
        for i in range(5):
            s = ctrl.read_status()
            soc = ctrl.read_battery_soc()
            print(f"  T+{i}s: PV={s.get('pv_total_w')}W, "
                  f"Home={s.get('home_load_w')}W, SOC={soc}%")
            time.sleep(1)
        
        # Discharge command (WSet positive = discharge)
        print("\n--- COMMAND: WSet +1000W DISCHARGE ---")
        ctrl.command(1000)
        
        print("Monitoring (10 seconds):")
        for i in range(10):
            s = ctrl.read_status()
            soc = ctrl.read_battery_soc()
            grid = ctrl.read_grid_simple()
            home = s.get('home_load_w', 0)
            grid_w = grid.get('w', 0)
            pv = s.get('pv_total_w', 0)
            
            # Estimate battery activity
            if home > pv:
                batt = home - pv  # Charging
                status = f"charging ~{batt}W"
            elif home < pv - 500:
                batt = pv - home  # Discharging or exporting
                status = f"exporting ~{batt}W"
            else:
                status = "balancing"
            battery_est = pv - home - grid_w  # Estimate battery activity
            
            print(f"  {i}s: PV={pv}W, Home={home}W,| Grid: {grid_w:+.0f}W | Battery: ~{battery_est:+.0f}W SOC={soc}% | {status}")

            time.sleep(1)
        
        # Idle
        print("\n--- COMMAND: IDLE (0W) ---")
        ctrl.command(0)
        
        for i in range(3):
            s = ctrl.read_status()
            print(f"  T+{i}s: PV={s.get('pv_total_w')}W, "
                  f"Home={s.get('home_load_w')}W")
            time.sleep(1)
        
        # Charge (WSet negative; refused on V12R02B60D00)
        print("\n--- COMMAND: WSet -500W CHARGE ---")
        ctrl.command(-500)
        
        for i in range(5):
            s = ctrl.read_status()
            soc = ctrl.read_battery_soc()
            home = s.get('home_load_w', 0)
            pv = s.get('pv_total_w', 0)
            
            if home < pv:
                status = f"discharging to cover load"
            else:
                status = "discharging to grid"
            
            print(f"  T+{i}s: PV={pv}W, Home={home}W, SOC={soc}% | {status}")
            time.sleep(1)
        
        # Final idle
        print("\n--- COMMAND: IDLE ---")
        ctrl.command(0)
        
        print("\n" + "=" * 70)
        print("DEMO COMPLETE")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        ctrl.disconnect()


if __name__ == '__main__':
    demo()