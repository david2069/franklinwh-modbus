#!/usr/bin/env python3
"""
⚠️  DEPRECATED: This script is deprecated and will be removed in a future version.
    
    Please use the new CLI instead:
        python franklinwh_cli.py -i <ip> --charge 3000
    
    Or use the library directly:
        from franklinwh_modbus_library import FranklinWHController

FranklinWH aGate Battery Control Script (DEPRECATED)
Uses sunspec2 library with model-based addressing

Includes:
- Direct hardware control via Model 704
- Virtual mode controller with 6 automated modes
- Time-of-use scheduling
- Continuous tick-based execution
- Graceful shutdown with idle-on-exit
- Health check with zombie state detection
- SPAN extension detection (conditional read/write)
- Cloud API placeholder for future integration

Usage:
    # Direct control (legacy --power with sign)
    python franklinwh_control.py -i YOUR_AGATE_IP --power 3000      # Charge
    python franklinwh_control.py -i YOUR_AGATE_IP --power -2000     # Discharge
    
    # Direct control (explicit action flags - RECOMMENDED)
    python franklinwh_control.py -i YOUR_AGATE_IP --charge 3000     # Charge at 3000W
    python franklinwh_control.py -i YOUR_AGATE_IP --discharge 2000  # Discharge at 2000W
    python franklinwh_control.py -i YOUR_AGATE_IP --standby         # Set to 0W
    
    # Status and health check
    python franklinwh_control.py -i YOUR_AGATE_IP --status
    python franklinwh_control.py -i YOUR_AGATE_IP --healthcheck
    
    # Virtual modes
    python franklinwh_control.py -i YOUR_AGATE_IP --mode self_consumption
    python franklinwh_control.py -i YOUR_AGATE_IP --mode emergency_backup --target-soc 90
    
    # With reset (recommended if zombie state detected)
    python franklinwh_control.py -i YOUR_AGATE_IP --reset-on-start --mode manual --charge 1500
"""

import argparse
import sys
import time
import signal
import atexit
import logging
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from enum import Enum, IntEnum
from typing import Optional, Callable, Dict, Any, Tuple, List, Union

try:
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
    from sunspec2.modbus.client import SunSpecModbusClientException
except ImportError as e:
    print(f"Error: sunspec2 not installed. Run: pip install pysunspec2")
    sys.exit(1)

# Import alarm enums if available
try:
    from enum_alarms import SystemAlarm, DCPortAlarm, SolarEvent, BatteryStatus, FranklinWHAlarmStatus
    ALARM_ENUMS_AVAILABLE = True
except ImportError:
    ALARM_ENUMS_AVAILABLE = False
    # Define minimal alarm constants
    class SystemAlarm:
        GROUND_FAULT = 1 << 0
        DC_OVER_VOLTAGE = 1 << 2
        AC_DISCONNECT = 1 << 3
        GRID_DISCONNECT = 1 << 5
        MANUAL_SHUTDOWN = 1 << 7
        OVER_TEMP = 1 << 8
        CRITICAL_FAULTS = GROUND_FAULT | MANUAL_SHUTDOWN

# Future cloud integration (v2.0+)
# try:
#     from franklinwh_cloud import FranklinWHCloudClient
#     CLOUD_API_AVAILABLE = True
# except ImportError:
#     CLOUD_API_AVAILABLE = False
CLOUD_API_AVAILABLE = False  # PLANNED for v2.0


# Module exports for library use
__all__ = [
    'ControlMode',
    'BatteryCommand',
    'VirtualMode',
    'TOUSchedule',
    'FranklinWHController',
    'VirtualModeController',
    'HealthStatus',
]


# Setup logging (module level for backward compatibility)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ControlMode(IntEnum):
    """DERCtlAC WSetMod values per SunSpec 802/704."""
    LIMIT_ABS = 0      # Limit active power to WSet (absolute watts)
    LIMIT_PCT = 1      # Limit to percentage of max
    SET_ABS = 2        # Set active power to WSet (signed, charge/discharge)
    SET_PCT = 3        # Set to percentage of max (signed)


class VirtualMode(Enum):
    """Software-implemented battery modes."""
    SELF_CONSUMPTION = "self_consumption"    # Maximize solar self-use
    EMERGENCY_BACKUP = "emergency_backup"    # Keep full for outages
    TIME_OF_USE = "time_of_use"              # Grid price arbitrage
    GRID_ZERO = "grid_zero"                  # Minimize grid import/export
    PEAK_SHAVE = "peak_shave"                # Discharge during peak demand
    MANUAL = "manual"                        # Direct power setting


@dataclass
class BatteryCommand:
    """Battery control command."""
    power_watts: float  # Positive=charge, negative=discharge, 0=idle
    mode: ControlMode = ControlMode.LIMIT_ABS


@dataclass
class TOUSchedule:
    """Time-of-use rate periods for arbitrage.
    
    Supports both legacy hardcoded schedules and file-based configuration.
    File-based schedules provide more flexibility with custom periods,
    strategies, and constraint rules.
    """
    # Legacy fields (for backward compatibility)
    peak_hours: Tuple[int, int] = (16, 21)      # 4 PM - 9 PM
    shoulder_hours: Tuple[int, int] = (7, 16)    # 7 AM - 4 PM
    off_peak_hours: Tuple[int, int] = (21, 7)   # 9 PM - 7 AM
    
    peak_price: float = 0.50          # $/kWh
    shoulder_price: float = 0.25
    off_peak_price: float = 0.10
    
    # File-based schedule support
    _schedule_data: Optional[Dict] = field(default=None, repr=False)
    _source_file: Optional[str] = field(default=None, repr=False)
    
    @classmethod
    def from_file(cls, filepath: str) -> "TOUSchedule":
        """Load TOU schedule from JSON file.
        
        Args:
            filepath: Path to JSON schedule file
            
        Returns:
            TOUSchedule instance with loaded configuration
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid JSON or schema
        """
        import json
        from pathlib import Path
        
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Schedule file not found: {filepath}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Validate basic schema
        cls._validate_schedule(data)
        
        # Create instance with schedule data
        instance = cls(_schedule_data=data, _source_file=str(path))
        
        # Try to populate legacy fields for compatibility
        instance._populate_legacy_fields(data)
        
        logger.info(f"Loaded TOU schedule from {filepath}: {data.get('name', 'unnamed')}")
        return instance
    
    @staticmethod
    def _validate_schedule(data: Dict) -> None:
        """Validate schedule file schema."""
        if not isinstance(data, dict):
            raise ValueError("Schedule must be a JSON object")
        
        if 'version' not in data:
            raise ValueError("Schedule must have 'version' field")
        
        if 'periods' not in data or not isinstance(data['periods'], list):
            raise ValueError("Schedule must have 'periods' array")
        
        if len(data['periods']) == 0:
            raise ValueError("Schedule must have at least one period")
        
        for i, period in enumerate(data['periods']):
            if 'id' not in period:
                raise ValueError(f"Period {i} missing 'id' field")
            if 'hours' not in period or not isinstance(period['hours'], list):
                raise ValueError(f"Period '{period.get('id', i)}' missing 'hours' array")
            if 'strategy' not in period:
                raise ValueError(f"Period '{period.get('id', i)}' missing 'strategy' field")
    
    def _populate_legacy_fields(self, data: Dict) -> None:
        """Try to populate legacy fields from schedule for backward compat."""
        # Look for known period types
        for period in data.get('periods', []):
            pid = period.get('id', '').lower()
            hours = period.get('hours', [])
            
            if 'peak' in pid and hours:
                self.peak_hours = (min(hours), max(hours) + 1)
                self.peak_price = period.get('price', self.peak_price)
            elif 'shoulder' in pid and hours:
                self.shoulder_hours = (min(hours), max(hours) + 1)
                self.shoulder_price = period.get('price', self.shoulder_price)
            elif 'off' in pid or 'valley' in pid and hours:
                self.off_peak_hours = (min(hours), max(hours) + 1)
                self.off_peak_price = period.get('price', self.off_peak_price)
    
    def is_file_based(self) -> bool:
        """Check if using file-based schedule."""
        return self._schedule_data is not None
    
    def get_schedule_name(self) -> str:
        """Get schedule name or 'Legacy' if using defaults."""
        if self._schedule_data:
            return self._schedule_data.get('name', 'Unnamed')
        return 'Legacy (hardcoded)'
    
    def get_current_period(self) -> str:
        """Determine current TOU period.
        
        Uses file-based schedule if loaded, otherwise legacy logic.
        """
        if self._schedule_data:
            hour = datetime.now().hour
            for period in self._schedule_data['periods']:
                if hour in period.get('hours', []):
                    return period['id']
            return "unknown"
        
        # Legacy logic
        hour = datetime.now().hour
        p_start, p_end = self.peak_hours
        
        if p_start <= hour < p_end:
            return "peak"
        elif self.shoulder_hours[0] <= hour < self.shoulder_hours[1]:
            return "shoulder"
        else:
            return "off_peak"
    
    def get_current_price(self) -> float:
        """Get current electricity price."""
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('price', 0.25)
            return 0.25
        
        # Legacy logic
        period = self.get_current_period()
        return getattr(self, f"{period}_price", 0.25)
    
    def get_strategy(self) -> str:
        """Get battery strategy for current period.
        
        Returns:
            Strategy name: 'charge', 'discharge', 'self_consumption', 
                          'grid_zero', or 'standby'
        """
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('strategy', 'self_consumption')
        
        # Default strategy based on legacy period
        period = self.get_current_period()
        if period == 'peak':
            return 'discharge'
        elif period == 'off_peak':
            return 'charge'
        else:
            return 'self_consumption'
    
    def get_rules(self) -> Dict[str, Any]:
        """Get constraint rules from schedule."""
        if self._schedule_data:
            return self._schedule_data.get('rules', {})
        return {}
    
    def get_min_soc(self) -> int:
        """Get minimum SoC constraint."""
        return self.get_rules().get('min_soc', 10)
    
    def get_max_soc(self) -> int:
        """Get maximum SoC constraint."""
        return self.get_rules().get('max_soc', 95)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export schedule as dictionary."""
        if self._schedule_data:
            return self._schedule_data
        
        # Legacy format
        return {
            'version': '1.0 (legacy)',
            'name': 'Legacy Hardcoded',
            'periods': [
                {
                    'id': 'peak',
                    'name': 'Peak',
                    'hours': list(range(self.peak_hours[0], self.peak_hours[1])),
                    'price': self.peak_price,
                    'strategy': 'discharge'
                },
                {
                    'id': 'shoulder',
                    'name': 'Shoulder',
                    'hours': list(range(self.shoulder_hours[0], self.shoulder_hours[1])),
                    'price': self.shoulder_price,
                    'strategy': 'self_consumption'
                },
                {
                    'id': 'off_peak',
                    'name': 'Off-Peak',
                    'hours': list(range(self.off_peak_hours[0], 24)) + list(range(0, self.off_peak_hours[1])),
                    'price': self.off_peak_price,
                    'strategy': 'charge'
                }
            ]
        }
    
    def __str__(self) -> str:
        """String representation of schedule."""
        name = self.get_schedule_name()
        period = self.get_current_period()
        price = self.get_current_price()
        strategy = self.get_strategy()
        return f"{name} | Current: {period} (${price:.2f}/kWh) | Strategy: {strategy}"


@dataclass
class HealthStatus:
    """Health check results."""
    healthy: bool
    message: str
    details: Dict[str, Any]
    recommendations: List[str]


class FranklinWHController:
    """FranklinWH aGate controller using sunspec2 model-based access."""
    
    # FranklinWH SPAN extension registers (15500+)
    # NOTE: Write access requires installer-enabled "SPAN Modbus" option
    EXT_BASE = 15500
    EXT_PV_TOTAL = 15502
    EXT_HOME_LOAD = 15506
    EXT_HOME_LOAD_HIRES = 16000       # Undocumented high-res mirror (~1W vs ~100W quantized)
    EXT_ONGRID_MODE = 15507      # 0=Backup, 1=TOU, 2=Self-Consumption, 3=Manual
    EXT_SELF_RESERVE = 15508     # Percentage
    EXT_TOU_RESERVE = 15509      # Percentage
    
    def __init__(
        self,
        ip_address: str,
        port: int = 502,
        unit_id: int = 2,  # FranklinWH default
        timeout: float = 10.0,  # Increased from 5.0 for reliability
        base_address: int = 0,  # sunspec2 uses 0 for auto/scan
    ):
        self.ip_address = ip_address
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.base_address = base_address
        self.dev: Optional[SunSpecModbusClientDeviceTCP] = None
        self.models: dict = {}
        self._span_writable: Optional[bool] = None  # Detected at runtime
        
    def connect(self) -> bool:
        """Connect and scan for models."""
        try:
            logger.info(f"Connecting to {self.ip_address}:{self.port} (unit {self.unit_id})")
            self.dev = SunSpecModbusClientDeviceTCP(
                slave_id=self.unit_id,
                ipaddr=self.ip_address,
                ipport=self.port,
                timeout=self.timeout,
            )
            
            logger.info("Scanning for SunSpec models...")
            self.dev.scan()
            
            self.models = {
                int(k) if str(k).isdigit() else k: v 
                for k, v in self.dev.models.items()
            }
            
            numeric_models = [k for k in self.models.keys() if isinstance(k, int)]
            logger.info(f"Found models: {sorted(numeric_models)}")
            
            # Verify critical models exist
            required = [704, 713, 701]  # Control, Battery, Grid
            missing = [m for m in required if m not in self.models]
            if missing:
                logger.warning(f"Missing recommended models: {missing}")
            
            self.discover_ratings()  # Read actual device capabilities
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close connection."""
        if self.dev:
            self.dev.close()
            self.dev = None
            logger.info("Disconnected")
    
    def get_model(self, model_id: int):
        """Get model instance, handling list wrapper."""
        model = self.models.get(model_id)
        if model is None:
            return None
        if isinstance(model, list):
            return model[0] if model else None
        return model
    
    def read_battery_status(self) -> dict:
        """Read current battery status from Model 713."""
        m713 = self.get_model(713)
        if not m713:
            return {}
        
        m713.read()
        
        # Scale factors
        sf_wh = self._get_scale_factor(m713, 'WH_SF')
        sf_pct = self._get_scale_factor(m713, 'Pct_SF')
        
        return {
            'soc': m713.SoC.value * (10 ** sf_pct),
            'soh': m713.SoH.value * (10 ** sf_pct),
            'wh_rating': m713.WHRtg.value * (10 ** sf_wh),
            'wh_available': m713.WHAvail.value * (10 ** sf_wh),
            'status': m713.Sta.value,
        }
    
    def read_grid_status(self) -> dict:
        """Read grid status from Model 701."""
        m701 = self.get_model(701)
        if not m701:
            return {}
        
        m701.read()
        
        sf_w = self._get_scale_factor(m701, 'W_SF')
        sf_v = self._get_scale_factor(m701, 'V_SF')
        sf_hz = self._get_scale_factor(m701, 'Hz_SF')
        
        # Basic electrical readings
        voltage = m701.LNV.value * (10 ** sf_v) if m701.LNV.value is not None else 0
        freq = m701.Hz.value * (10 ** sf_hz) if m701.Hz.value is not None else 0
        
        # Connection state
        conn_st = m701.ConnSt.value if hasattr(m701, 'ConnSt') and m701.ConnSt.value is not None else -1
        CONN_STATES = {0: 'Disconnected', 1: 'Connected', 2: 'Fault'}
        
        # Operating and inverter states
        st = m701.St.value if hasattr(m701, 'St') and m701.St.value is not None else -1
        inv_st = m701.InvSt.value if hasattr(m701, 'InvSt') and m701.InvSt.value is not None else -1
        
        OPERATING_STATES = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault',
                           4: 'Shutting Down', 5: 'Starting', 6: 'Maintenance'}
        INVERTER_STATES = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running',
                          4: 'Throttled', 5: 'Shutting Down', 6: 'Fault',
                          7: 'Standby', 8: 'Test', 9: 'Manufacturing'}
        
        # DERMode contains grid support mode in upper bits
        der_mode_raw = m701.DERMode.value if hasattr(m701, 'DERMode') and m701.DERMode.value is not None else 0
        
        # Grid mode from upper bits (16-17)
        if der_mode_raw & (1 << 17):
            grid_mode = 'Grid Forming'
        elif der_mode_raw & (1 << 16):
            grid_mode = 'Grid Following'
        else:
            grid_mode = 'Grid Following (default)'
        
        # Determine AC type based on voltage and available readings
        # Single phase: ~230V (AU/EU) or ~120V (US)
        # Split phase: ~240V (US split phase, L1-L2)
        # Three phase: Would typically have phase voltage ~230V and line-line ~400V
        # For now, we classify based on voltage level and what's available
        if 200 <= voltage <= 260:
            ac_type = 'Single-Phase (230V Nominal)'
        elif 100 <= voltage < 200:
            ac_type = 'Single-Phase (120V Nominal)'
        elif 380 <= voltage <= 420:
            ac_type = 'Three-Phase (400V Line-Line)'
        else:
            ac_type = 'Unknown'
        
        return {
            'grid_power_w': m701.W.value * (10 ** sf_w) if m701.W.value is not None else 0,
            'grid_va': m701.VA.value * (10 ** sf_w) if m701.VA.value is not None else 0,
            'grid_var': m701.Var.value * (10 ** sf_w) if m701.Var.value is not None else 0,
            'voltage_v': voltage,
            'frequency_hz': freq,
            'connection_state': CONN_STATES.get(conn_st, f'Unknown({conn_st})'),
            'connection_state_raw': conn_st,
            'operating_state': OPERATING_STATES.get(st, f'Unknown({st})'),
            'operating_state_raw': st,
            'inverter_state': INVERTER_STATES.get(inv_st, f'Unknown({inv_st})'),
            'inverter_state_raw': inv_st,
            'grid_mode': grid_mode,
            'der_mode_raw': der_mode_raw,
            'ac_type': ac_type,
        }
    
    def read_solar_status(self) -> dict:
        """Read solar status from Model 714 and FranklinWH extensions."""
        m714 = self.get_model(714)
        if not m714:
            return {}
        
        m714.read()
        
        sf_w = self._get_scale_factor(m714, 'DCW_SF')
        
        # Base solar from Model 714 (DC power)
        solar_status = {
            'dc_power_w': m714.DCW.value * (10 ** sf_w),
            'dc_current_a': m714.DCA.value * (10 ** self._get_scale_factor(m714, 'DCA_SF')) if hasattr(m714, 'DCA') else None,
            'dc_energy_injected_wh': m714.DCWhInj.value,
            'dc_energy_absorbed_wh': m714.DCWhAbs.value,
        }
        
        # Also read FranklinWH extension registers for AC-coupled solar
        # These may provide more accurate data for AC-coupled systems
        try:
            ext_solar = self._read_extension_solar()
            if ext_solar:
                solar_status['extension'] = ext_solar
                # Use extension total if available and DC is 0 (AC-coupled case)
                if solar_status['dc_power_w'] == 0 and ext_solar.get('pv_total', 0) > 0:
                    solar_status['dc_power_w'] = ext_solar['pv_total']
        except Exception as e:
            logger.debug(f"Could not read extension solar: {e}")
        
        return solar_status
    
    def _read_extension_solar(self) -> Optional[dict]:
        """Read FranklinWH extension registers for solar (15500-15513).
        
        Home load sourced from undocumented register 16000 (~1W precision)
        with fallback to 15506 (~100W quantized). Discovered 2026-03-15.
        """
        try:
            # Read raw registers 15500-15513 (14 registers)
            result = self.dev.client.read_holding_registers(15500, count=14, device_id=self.unit_id)
            if result.isError():
                return None
            
            regs = result.registers
            
            pv_total = regs[2] if len(regs) > 2 else 0
            pv_proximal = regs[3] if len(regs) > 3 else 0
            pv_remote1 = regs[4] if len(regs) > 4 else 0
            pv_remote2 = regs[5] if len(regs) > 5 else 0
            home_load_quantized = regs[6] if len(regs) > 6 else 0  # ~100W steps
            ongrid_mode = regs[7] if len(regs) > 7 else -1
            self_reserve = regs[8] if len(regs) > 8 else 0
            tou_reserve = regs[9] if len(regs) > 9 else 0
            
            # Read high-res home load from register 16000 (~1W precision)
            home_load = home_load_quantized  # fallback
            try:
                hires = self.dev.client.read_holding_registers(self.EXT_HOME_LOAD_HIRES, count=1, device_id=self.unit_id)
                if not hires.isError() and len(hires.registers) > 0:
                    val = hires.registers[0]
                    if val > 0 or home_load_quantized == 0:
                        home_load = val
            except Exception:
                pass  # Fall back to quantized value
            
            individual_sum = pv_proximal + pv_remote1 + pv_remote2
            if pv_total > 0 and abs(pv_total - individual_sum) < 100:
                total_solar = pv_total
            elif individual_sum > 0:
                total_solar = individual_sum
            else:
                total_solar = pv_total
            
            return {
                'pv_total': pv_total,
                'pv_proximal': pv_proximal,
                'pv_remote1': pv_remote1,
                'pv_remote2': pv_remote2,
                'total_solar': total_solar,
                'home_load_ext': home_load,
                'home_load_ext_quantized': home_load_quantized,
                'ongrid_mode': ongrid_mode,
                'self_reserve': self_reserve,
                'tou_reserve': tou_reserve,
            }
        except Exception as e:
            logger.debug(f"Extension solar read failed: {e}")
            return None
    
    def read_nameplate(self) -> dict:
        """Read device nameplate information from Model 1 (Common).
        
        Returns:
            Dict with manufacturer, model, serial, version, etc.
        """
        m1 = self.get_model(1)
        if not m1:
            return {}
        
        try:
            m1.read()
            return {
                'manufacturer': getattr(m1, 'Mn', None),
                'model': getattr(m1, 'Md', None),
                'serial': getattr(m1, 'SN', None),
                'version': getattr(m1, 'Vr', None),
                'options': getattr(m1, 'Opt', None),
            }
        except Exception as e:
            logger.debug(f"Could not read Model 1 nameplate: {e}")
            return {}
    
    def read_control_status(self) -> dict:
        """Read current control settings from Model 704."""
        m704 = self.get_model(704)
        if not m704:
            return {}
        
        m704.read()
        
        sf_w = self._get_scale_factor(m704, 'WSet_SF')
        
        sf_pct = self._get_scale_factor(m704, 'WSetPct_SF')
        
        return {
            'wset_enabled': m704.WSetEna.value,
            'wset_mode': m704.WSetMod.value,
            'wset_watts': m704.WSet.value * (10 ** sf_w),
            'wset_pct': m704.WSetPct.value * (10 ** sf_pct),  # Actual percentage
            'wset_pct_raw': m704.WSetPct.value,  # Raw register value
            'wset_revert_watts': m704.WSetRvrt.value * (10 ** sf_w) if m704.WSetRvrt.value != -0x80000000 else None,
            'wset_revert_time_s': m704.WSetRvrtTms.value,
            'wset_revert_remain_s': m704.WSetRvrtRem.value,
        }
    
    def _get_scale_factor(self, model, sf_name: str) -> int:
        """Get scale factor value, default to 0."""
        sf_point = getattr(model, sf_name, None)
        if sf_point and hasattr(sf_point, 'value'):
            return sf_point.value
        return 0
    
    def healthcheck(self) -> HealthStatus:
        """
        Comprehensive system health check.
        
        Detects:
        - Connection status
        - Model availability
        - Zombie state (WSetEna=1 with expired revert timer)
        - Battery safety bounds
        - SPAN extension availability
        - OnGridMode (safety for remote control)
        
        Returns:
            HealthStatus with recommendations
        """
        checks = {}
        recommendations = []
        
        # 1. Connection
        checks['connection'] = self.dev is not None
        if not checks['connection']:
            return HealthStatus(
                healthy=False,
                message="CONNECTION FAILED",
                details=checks,
                recommendations=["Check IP address and network connectivity"]
            )
        
        # 2. Critical models
        checks['model_704'] = 704 in self.models
        checks['model_713'] = 713 in self.models
        checks['model_701'] = 701 in self.models
        
        if not checks['model_704']:
            return HealthStatus(
                healthy=False,
                message="CRITICAL: Model 704 (Control) not available",
                details=checks,
                recommendations=["Verify aGate firmware supports SunSpec Model 704"]
            )
        
        # 3. Control state analysis
        m704 = self.get_model(704)
        m704.read()
        
        checks['wset_ena'] = m704.WSetEna.value
        checks['wset_mode'] = m704.WSetMod.value
        checks['wset'] = m704.WSet.value
        checks['revert_rem'] = m704.WSetRvrtRem.value
        checks['revert_tms'] = m704.WSetRvrtTms.value
        
        # Zombie state: enabled but timer expired
        checks['zombie_state'] = (
            m704.WSetEna.value == 1 and
            m704.WSetRvrtRem.value == 0 and
            m704.WSetRvrtTms.value > 0
        )
        
        if checks['zombie_state']:
            recommendations.append(
                "ZOMBIE STATE DETECTED: Use --reset-on-start to clear "
                "(WSetEna=1 with expired revert timer)"
            )
        
        # 4. Battery safety
        bat = self.read_battery_status()
        checks['soc'] = bat.get('soc', 0)
        checks['soc_safe'] = 5 < checks['soc'] < 99
        
        if not checks['soc_safe']:
            recommendations.append(
                f"WARNING: SoC {checks['soc']}% outside safe range (5-99%)"
            )
        
        # 5. Grid safety — use Model 703 enter-service limits when available
        grid = self.read_grid_status()
        checks['grid_voltage'] = grid.get('voltage_v', 0)
        checks['grid_frequency'] = grid.get('frequency_hz', 0)

        # Read Model 703 (DER Enter Service) for configured grid limits
        m703 = self.get_model(703)
        if m703:
            try:
                m703.read()
                sf_v = self._get_scale_factor(m703, 'V_SF')
                sf_hz = self._get_scale_factor(m703, 'Hz_SF')
                # Voltage limits are in % of nominal (e.g. 253% → 253V on 230V grid)
                # but register holds the actual threshold voltage
                v_hi = m703.ESVHi.value * (10 ** sf_v) if m703.ESVHi.value is not None else 260
                v_lo = m703.ESVLo.value * (10 ** sf_v) if m703.ESVLo.value is not None else 220
                hz_hi = m703.ESHzHi.value * (10 ** sf_hz) if m703.ESHzHi.value is not None else 53
                hz_lo = m703.ESHzLo.value * (10 ** sf_hz) if m703.ESHzLo.value is not None else 47
                checks['enter_service'] = {
                    'available': True,
                    'permit': m703.ES.value if m703.ES.value is not None else None,
                    'v_hi': v_hi, 'v_lo': v_lo,
                    'hz_hi': hz_hi, 'hz_lo': hz_lo,
                }
            except Exception as e:
                logger.warning(f"Failed to read Model 703: {e}")
                v_hi, v_lo, hz_hi, hz_lo = 260, 220, 53, 47
                checks['enter_service'] = {'available': False}
        else:
            # Fallback: hardcoded defaults for systems without M703
            v_hi, v_lo, hz_hi, hz_lo = 260, 220, 53, 47
            checks['enter_service'] = {'available': False}

        checks['grid_safe'] = (
            v_lo < checks['grid_voltage'] < v_hi and
            hz_lo < checks['grid_frequency'] < hz_hi
        )
        
        if not checks['grid_safe']:
            recommendations.append(
                f"WARNING: Grid {checks['grid_voltage']:.1f}V / "
                f"{checks['grid_frequency']:.2f}Hz outside limits "
                f"(V: {v_lo}-{v_hi}, Hz: {hz_lo}-{hz_hi})"
            )
        
        # 6. SPAN extension detection
        span_status = self._detect_span_capability()
        checks['span'] = span_status
        
        if span_status['readable']:
            # Check OnGridMode for safety
            ongrid_mode = span_status.get('ongrid_mode', -1)
            mode_names = {0: 'Backup', 1: 'Self', 2: 'TOU', 3: 'Manual'}
            checks['ongrid_mode'] = ongrid_mode
            checks['ongrid_mode_name'] = mode_names.get(ongrid_mode, 'Unknown')
            
            # Safety: remote control only safe in Self-Consumption (2)
            checks['remote_control_safe'] = (ongrid_mode == 2)
            
            if not checks['remote_control_safe'] and ongrid_mode >= 0:
                recommendations.append(
                    f"SAFETY: OnGridMode={ongrid_mode} ({checks['ongrid_mode_name']}). "
                    f"Remote control recommended only in Self-Consumption (2) mode"
                )
        
        # 7. Cloud API status (placeholder)
        checks['cloud_api'] = {
            'available': CLOUD_API_AVAILABLE,
            'status': 'Not implemented in current release',
            'span_enabled': None,  # Would come from cloud
        }
        
        # Determine overall health
        critical_issues = [
            not checks['connection'],
            not checks['model_704'],
            not checks['soc_safe'],
        ]
        
        warnings = [
            checks.get('zombie_state', False),
            not checks.get('remote_control_safe', True),
        ]
        
        if any(critical_issues):
            healthy = False
            message = "CRITICAL ISSUES DETECTED"
        elif any(warnings):
            healthy = False  # Degraded, not fully healthy
            message = "DEGRADED (warnings present)"
        else:
            healthy = True
            message = "HEALTHY"
        
        return HealthStatus(
            healthy=healthy,
            message=message,
            details=checks,
            recommendations=recommendations if recommendations else ["No action required"]
        )
    
    def _detect_span_capability(self) -> dict:
        """
        Detect SPAN extension availability.
        Attempts read, then test write to determine capability.
        """
        result = {
            'readable': False,
            'writable': False,
            'ongrid_mode': -1,
            'self_reserve': -1,
            'tou_reserve': -1,
        }
        
        # Try to read extensions using sunspec2 raw access if possible
        # Fallback: assume not available for safety
        try:
            # Note: sunspec2 doesn't expose raw register access easily
            # Now handled by read_native_mode() using raw Modbus TCP
            result['readable'] = False
            result['note'] = 'Use read_native_mode() for native register access'
            
        except Exception as e:
            result['error'] = str(e)
        
        # Cache write capability (detect once)
        self._span_writable = result['writable']
        
        return result

    def read_native_mode(self) -> dict:
        """Read FranklinWH native operating mode via raw Modbus TCP.
        
        Registers 15507-15509 are outside the SunSpec address space and
        require a raw Modbus read (the sunspec2 API doesn't expose them).
        
        Returns dict with mode, reserves, or empty dict on failure.
        """
        FRANKLIN_MODES = {0: 'Emergency Backup', 1: 'Time of Use',
                          2: 'Self-Consumption', 3: 'Manual'}
        try:
            import struct
            client = self.dev.client
            # sunspec2 disconnects between operations — reconnect for raw access
            client.connect()
            sock = client.socket
            if not sock:
                return {}
            # Raw Modbus TCP: transaction=0, protocol=0, length=6,
            # unit_id, function=3 (read holding), start=15507, count=3
            req = struct.pack('>HHHBBHH', 0, 0, 6, self.unit_id, 3, 15507, 3)
            sock.sendall(req)
            resp = sock.recv(256)
            if len(resp) >= 15:
                vals = struct.unpack('>HHH', resp[9:15])
                return {
                    'mode_raw': vals[0],
                    'mode_name': FRANKLIN_MODES.get(vals[0], f'Unknown({vals[0]})'),
                    'self_reserve_pct': vals[1],
                    'tou_reserve_pct': vals[2],
                }
        except Exception as e:
            logger.debug(f"Native mode read failed: {e}")
        return {}
    
    def reset_control_state(self) -> bool:
        """
        Reset aGate to known clean state.
        
        Clears:
        - WSetEna (disable control)
        - WSetPct (zero percentage setpoint — the real control)
        - WSet (zero watt setpoint)
        
        NOTE: M715 registers (OpCtl, ControllerHb) reject writes on current firmware.
        NOTE: WSetRvrtTms is unimplemented per PICS SM-000028.
        
        Returns:
            True if successfully reset
        """
        logger.info("Resetting control state to idle...")
        
        m704 = self.get_model(704)
        if not m704:
            logger.error("Model 704 not available for reset")
            return False
        
        try:
            # Read current state
            m704.read()
            logger.info(f"Before reset: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}, WSet={m704.WSet.value}")
            
            # Disable control — only M704 registers are writable
            m704.WSetEna.value = 0
            m704.WSetPct.value = 0   # Primary control register
            m704.WSet.value = 0
            
            m704.write()
            time.sleep(0.5)
            
            # Verify
            m704.read()
            success = (m704.WSetEna.value == 0 and m704.WSetPct.value == 0)
            
            if success:
                logger.info(f"✓ Reset successful: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}")
            else:
                logger.warning(f"Reset verification failed: WSetEna={m704.WSetEna.value}, WSetPct={m704.WSetPct.value}")
            
            return success
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            return False
    
    # Default fallback — overridden by discover_ratings() on connect
    RATED_MAX_W = 5000
    RATED_MAX_CHARGE_W = 5000
    RATED_MAX_DISCHARGE_W = 5000

    def discover_ratings(self):
        """Read M702 nameplate ratings to replace hardcoded limits.

        Reads READ-ONLY rating registers (not RW settings which return None):
        - WMaxRtg (40227): Active Power Max Rating
        - WChaRteMaxRtg (40235): Charge Rate Max Rating
        - WDisChaRteMaxRtg (40236): Discharge Rate Max Rating

        Different FranklinWH models may have asymmetric charge/discharge ratings.
        """
        m702 = self.get_model(702)
        if not m702:
            logger.warning("Model 702 not found; using default 5000W ratings")
            return
        try:
            m702.read()
            sf = self._get_scale_factor(m702, 'W_SF')

            def read_rating(attr, default):
                pt = getattr(m702, attr, None)
                if pt is None or pt.value is None or pt.value == 0:
                    return default
                return int(pt.value * (10 ** sf))

            w_max = read_rating('WMaxRtg', 5000)
            w_cha = read_rating('WChaRteMaxRtg', w_max)
            w_dis = read_rating('WDisChaRteMaxRtg', w_max)

            self.RATED_MAX_W = w_max
            self.RATED_MAX_CHARGE_W = w_cha
            self.RATED_MAX_DISCHARGE_W = w_dis

            logger.info(f"Device ratings: Max={w_max}W, Charge={w_cha}W, Discharge={w_dis}W")
        except Exception as e:
            logger.warning(f"Failed to read M702 ratings: {e}; using defaults")

    def _validate_power(self, power_watts: float) -> float:
        """Safety clamp: ensure requested power doesn't exceed device ratings."""
        is_charge = power_watts > 0
        limit = self.RATED_MAX_CHARGE_W if is_charge else self.RATED_MAX_DISCHARGE_W
        if abs(power_watts) > limit:
            clamped = limit if is_charge else -limit  # keep the requested direction
            logger.warning(f"SAFETY CLAMP: {power_watts}W exceeds {'charge' if is_charge else 'discharge'} "
                          f"limit {limit}W — clamped to {clamped}W")
            return clamped
        return power_watts

    def read_alarms(self) -> Dict[str, Any]:
        """
        Read all alarm registers from the aGate.
        
        Returns dict with:
            - system_alrm: Model 701 Alrm bitfield
            - dc_port_alrm: Model 714 PrtAlrms bitfield
            - solar_evt: Model 502 Evt bitfield (if available)
            - battery_sta: Model 713 Sta enum
            - vendor_info: Manufacturer alarm info string
            - decoded: Human-readable alarm descriptions (if enums available)
        """
        alarms = {
            'system_alrm': 0,
            'dc_port_alrm': 0,
            'solar_evt': 0,
            'battery_sta': 0,
            'vendor_info': '',
            'decoded': {},
        }
        
        try:
            # Model 701: System alarms (Alrm at offset 76, 2 registers for bitfield32)
            m701 = self.get_model(701)
            if m701 and hasattr(m701, 'Alrm'):
                alarms['system_alrm'] = m701.Alrm.value if m701.Alrm.value else 0
                
                # Vendor alarm info (MnAlrmInfo) if available
                if hasattr(m701, 'MnAlrmInfo') and m701.MnAlrmInfo.value:
                    alarms['vendor_info'] = str(m701.MnAlrmInfo.value)
            
            # Model 714: DC Port alarms
            m714 = self.get_model(714)
            if m714 and hasattr(m714, 'PrtAlrms'):
                alarms['dc_port_alrm'] = m714.PrtAlrms.value if m714.PrtAlrms.value else 0
            
            # Model 713: Battery status
            m713 = self.get_model(713)
            if m713 and hasattr(m713, 'Sta'):
                alarms['battery_sta'] = m713.Sta.value if m713.Sta.value else 0
            
            # Decode alarms if enums available
            if ALARM_ENUMS_AVAILABLE:
                sys_alm = SystemAlarm(alarms['system_alrm'])
                dc_alm = DCPortAlarm(alarms['dc_port_alrm'])
                bat_sta = BatteryStatus(alarms['battery_sta'])
                
                alarms['decoded'] = {
                    'system': [a.name for a in SystemAlarm if a in sys_alm and a != 0],
                    'dc_port': [a.name for a in DCPortAlarm if a in dc_alm and a != 0],
                    'battery_status': bat_sta.name if bat_sta else 'UNKNOWN',
                    'critical': bool(sys_alm & SystemAlarm.CRITICAL_FAULTS),
                    'blocking_dc': bool(dc_alm & DCPortAlarm.ELECTRICAL_FAULTS),
                }
            else:
                # Basic decoding without enums
                sys_alm = alarms['system_alrm']
                critical_bits = (1 << 0) | (1 << 6) | (1 << 7) | (1 << 13) | (1 << 14)
                alarms['decoded'] = {
                    'system': [],
                    'dc_port': [],
                    'battery_status': 'UNKNOWN',
                    'critical': bool(sys_alm & critical_bits),
                    'blocking_dc': False,
                }
                
                # Decode basic alarm bits
                ALARM_NAMES = {
                    0: 'GROUND_FAULT', 1: 'INPUT_OVER_CURRENT', 2: 'DC_OVER_VOLTAGE',
                    3: 'AC_DISCONNECT', 4: 'DC_DISCONNECT', 5: 'GRID_DISCONNECT',
                    6: 'CABINET_OPEN', 7: 'MANUAL_SHUTDOWN', 8: 'OVER_TEMP',
                    9: 'OVER_FREQUENCY', 10: 'UNDER_FREQUENCY', 11: 'AC_OVER_VOLTAGE',
                    12: 'AC_UNDER_VOLTAGE', 13: 'STRING_FAULT', 14: 'ARC_FAULT',
                    15: 'THERMAL_DERATE'
                }
                for bit, name in ALARM_NAMES.items():
                    if sys_alm & (1 << bit):
                        alarms['decoded']['system'].append(name)
            
        except Exception as e:
            logger.debug(f"Could not read all alarms: {e}")
        
        return alarms

    def clear_alarms(self) -> Tuple[bool, str]:
        """
        Attempt to clear alarms by writing to AlarmReset register.
        
        Returns (success, message).
        Only clears if no critical faults are active.
        """
        try:
            # First check current alarms
            alarms = self.read_alarms()
            decoded = alarms.get('decoded', {})
            
            # Check if safe to clear
            if decoded.get('critical'):
                return False, f"Cannot clear: Critical alarms active: {decoded.get('system', [])}"
            
            if alarms['battery_sta'] == 6:  # FAULT
                return False, "Cannot clear: Battery status is FAULT"
            
            # Model 715 AlarmReset is at register 41094
            m715 = self.get_model(715)
            if not m715:
                return False, "Model 715 not available for alarm reset"
            
            # Check if AlarmReset point exists
            if not hasattr(m715, 'AlarmReset'):
                return False, "AlarmReset register not available in Model 715"
            
            # Write 1 to reset
            m715.read()
            m715.AlarmReset.value = 1
            m715.write()
            time.sleep(0.5)
            
            # Clear the reset bit
            m715.read()
            m715.AlarmReset.value = 0
            m715.write()
            
            logger.info("Alarm reset command sent")
            return True, "Alarm reset command sent successfully"
            
        except Exception as e:
            return False, f"Alarm reset failed: {e}"

    def check_blocking_alarms(self) -> Tuple[bool, List[str]]:
        """
        Check if any alarms are blocking operation.
        
        Returns (can_operate, blocking_reasons).
        """
        alarms = self.read_alarms()
        decoded = alarms.get('decoded', {})
        blocking = []
        
        if decoded.get('critical'):
            blocking.extend(decoded.get('system', []))
        
        if decoded.get('blocking_dc'):
            blocking.extend([f"DC:{a}" for a in decoded.get('dc_port', [])])
        
        if alarms['battery_sta'] == 6:  # FAULT
            blocking.append('BATTERY_FAULT')
        
        return len(blocking) == 0, blocking

    def send_command(
        self,
        command: BatteryCommand,
        revert_time_s: int = 0,
        heartbeat_interval: float = 5.0,
        dry_run: bool = False
    ) -> Tuple[bool, str]:
        """
        Send battery control command.

        FranklinWH Systematic Test Results (2026-02-18):
        - WSetPct is the ONLY working control register (WSet accepted but ignored)
        - Positive WSetPct = discharge, Negative = charge
        - Scale factor WSetPct_SF = -1, so raw 300 = 30.0% of 5kW = 1500W
        - M715 registers (ControllerHb, OpCtl) reject all writes (LocRemCtl=LOCAL)
        - M702 rate limits (WChaRteMax etc.) unimplemented (return None)
        - WSetRvrtTms unimplemented per PICS SM-000028 — no auto-timeout
        - WMaxLimPctEna/WMaxLimPct PICS says supported, firmware rejects writes
        """
        m704 = self.get_model(704)
        m715 = self.get_model(715)
        if not m704:
            return False, "Model 704 not available"

        # Safety clamp against device ratings
        safe_watts = self._validate_power(command.power_watts)

        # Calculate WSetPct: percentage of rated max
        pct_sf = self._get_scale_factor(m704, 'WSetPct_SF')
        pct_raw = int((safe_watts / self.RATED_MAX_W) * 100 / (10 ** pct_sf))

        if dry_run:
            return True, f"Dry Run: WSetPct={pct_raw} ({command.power_watts}W)"

        # 1. STOP & CLEAR (Pre-flight reset)
        m704.read()
        m704.WSetEna.value = 0
        m704.write()
        time.sleep(0.3)

        # 2. CONFIGURE — WSetPct is the ONLY working control for FranklinWH
        # NOTE: Invert sign - hardware WSetPct: positive=discharge, negative=charge
        m704.read()
        m704.WSetMod.value = 0  # Absolute W mode
        m704.WSetPct.value = -pct_raw  # INVERTED for hardware convention
        # NOTE: Do NOT set WSet - it causes mode flickering (Export↔VPP↔Self-Consumption)
        # WSetPct is the sole working register for FranklinWH control
        m704.write()
        time.sleep(0.3)

        # 3. ENABLE
        m704.read()
        m704.WSetEna.value = 1
        m704.write()
        time.sleep(0.5)

        # 4. VERIFY
        m704.read()
        actual_pct = m704.WSetPct.value * (10 ** pct_sf) if m704.WSetPct.value else 0
        logger.info(f"Command sent: WSetPct={actual_pct}% (raw={m704.WSetPct.value}), "
                   f"WSet={m704.WSet.value}, WSetEna={m704.WSetEna.value}")
        return True, f"Command Sent: {command.power_watts}W ({actual_pct}% of {self.RATED_MAX_W}W)"


# ============================================================
# VIRTUAL MODE CONTROLLER
# ============================================================

class VirtualModeController:
    """
    Software-based battery mode controller for FranklinWH aGate.
    
    Since hardware modes (15507-15509) are Modbus read-only without SPAN unlock,
    we implement equivalent logic using direct WSet control via Model 704.
    
    Usage:
        hw = FranklinWHController(ip='YOUR_AGATE_IP', timeout=10.0)
        hw.connect()
        
        modes = VirtualModeController(hw)
        modes.set_mode(VirtualMode.TIME_OF_USE)
        modes.run_continuous()
    """
    
    def __init__(self, franklinwh_controller: FranklinWHController,
                 max_charge_soc: int = 100,
                 min_discharge_soc: Optional[int] = None,
                 soc_ramp_window: int = 10,
                 force_soc_limits: bool = False):
        """
        Initialize virtual mode controller.
        
        Args:
            franklinwh_controller: Connected FranklinWHController instance
            max_charge_soc: Maximum SoC for charging (with ramping)
            min_discharge_soc: Minimum SoC for discharging (with ramping).
                             If None, reads from aGate native mode.
            soc_ramp_window: SoC percentage for ramping before hard limit
            force_soc_limits: If True, allows override of SoC limits (logged warning)
        """
        self.ctrl = franklinwh_controller
        self.mode = VirtualMode.SELF_CONSUMPTION
        self.tou = TOUSchedule()
        
        # Mode-specific parameters
        self.self_reserve_pct = 20        # Keep 20% for self-consumption
        self.backup_target_soc = 95       # Charge to 95% for backup (legacy)
        self.target_soc = 100             # Universal target SoC for all modes
        self.grid_zero_buffer = 100       # Watts tolerance for grid zero
        self.peak_shave_threshold = 2000  # Discharge if home load > 2kW
        
        # Manual mode setting
        self.manual_power_w = 0
        
        # SoC limit parameters
        self.max_charge_soc = max_charge_soc
        self.soc_ramp_window = soc_ramp_window
        self.force_soc_limits = force_soc_limits
        
        # Read min discharge from aGate if not specified
        if min_discharge_soc is None:
            self.min_discharge_soc = self._read_agate_reserve_soc()
        else:
            # Validate against aGate reserve (cannot go below)
            agate_reserve = self._read_agate_reserve_soc()
            if min_discharge_soc < agate_reserve:
                logger.warning(f"Requested min-discharge-soc {min_discharge_soc}% is below "
                              f"aGate reserve {agate_reserve}%. Using {agate_reserve}%.")
                self.min_discharge_soc = agate_reserve
            else:
                self.min_discharge_soc = min_discharge_soc
        
        logger.info(f"SoC limits configured: min_discharge={self.min_discharge_soc}%, "
                   f"max_charge={self.max_charge_soc}%, ramp_window={self.soc_ramp_window}%")
        if self.force_soc_limits:
            logger.warning("FORCE MODE ENABLED: SoC limits can be overridden (use with caution)")
        
        # State for tick() method
        self.last_tick = 0
        self.tick_interval = 5  # seconds
        
        # Shutdown flag
        self._shutdown_requested = False
        
        # Register cleanup handler
        atexit.register(self._emergency_idle)
    
    def _read_agate_reserve_soc(self) -> int:
        """Read reserve SOC from aGate native mode registers.
        
        Returns:
            Reserve SOC percentage (defaults to 10 if cannot read)
        """
        try:
            native = self.ctrl.read_native_mode()
            if native:
                # TOU reserve (15509) or Self reserve (15508)
                # Use the higher of the two for safety
                tou_reserve = native.get('tou_reserve_pct', 10)
                self_reserve = native.get('self_reserve_pct', 10)
                reserve = max(tou_reserve, self_reserve)
                logger.info(f"Read aGate reserve SOC: {reserve}% (TOU={tou_reserve}%, Self={self_reserve}%)")
                return reserve
        except Exception as e:
            logger.warning(f"Could not read aGate reserve SOC: {e}, using default 10%")
        return 10  # Safe default
    
    def _emergency_idle(self):
        """Ensure battery control is fully released on unexpected exit.
        
        CRITICAL: Must set WSetEna=0 (not just WSetPct=0) so the aGate
        resumes its configured operating mode (e.g. Self-Consumption).
        WSetEna=1 + WSetPct=0 = 'actively commanding standby' = VPP mode.
        """
        if hasattr(self.ctrl, 'reset_control_state'):
            try:
                logger.warning("Emergency shutdown: releasing Modbus control (WSetEna=0)")
                self.ctrl.reset_control_state()
            except Exception as e:
                logger.error(f"Emergency reset failed: {e}")
    
    def set_mode(self, mode: VirtualMode, **kwargs):
        """
        Change operating mode with optional parameters.
        
        Examples:
            controller.set_mode(VirtualMode.SELF_CONSUMPTION, self_reserve_pct=15)
            controller.set_mode(VirtualMode.EMERGENCY_BACKUP, backup_target_soc=90)
            controller.set_mode(VirtualMode.MANUAL, manual_power_w=3000)
        """
        self.mode = mode
        
        # Update parameters if provided
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Set {key} = {value}")
        
        logger.info(f"Mode changed to: {mode.value}")
        
        # Immediate action
        self.execute_once()
    
    def get_current_period(self) -> str:
        """Determine current TOU period."""
        hour = datetime.now().hour
        start, end = self.tou.peak_hours
        
        if start <= hour < end:
            return "peak"
        elif self.tou.shoulder_hours[0] <= hour < self.tou.shoulder_hours[1]:
            return "shoulder"
        else:
            return "off_peak"
    
    def read_status(self) -> Dict[str, Any]:
        """Get current system status from hardware."""
        status = {
            'battery': self.ctrl.read_battery_status(),
            'grid': self.ctrl.read_grid_status(),
            'solar': self.ctrl.read_solar_status(),
            'control': self.ctrl.read_control_status(),
        }
        
        # Add derived values
        solar_data = status['solar']
        solar = solar_data.get('dc_power_w', 0)
        
        # Get total solar from all sources (including extensions if available)
        total_solar = solar
        extension_data = solar_data.get('extension', {})
        if extension_data:
            total_solar = extension_data.get('total_solar', solar)
        
        grid = status['grid'].get('grid_power_w', 0)
        
        # Use extension home load if available (more accurate), otherwise estimate
        home_ext = extension_data.get('home_load_ext', 0) if extension_data else 0
        if home_ext > 0:
            home_est = home_ext
        else:
            # Estimate home load: solar + grid_import - battery_activity
            battery_w = status['control'].get('wset_watts', 0)
            home_est = solar + grid - battery_w  # Simplified
        
        status['derived'] = {
            'home_load_w': home_est,
            'excess_solar_w': max(total_solar - home_est, 0),
            'grid_import_w': max(grid, 0),
            'grid_export_w': max(-grid, 0),
            'total_solar_w': total_solar,  # From all sources
        }
        
        return status
    
    def _check_inverter_safety(self, status: Dict, proposed_power: float) -> Tuple[bool, str, float]:
        """
        Check if proposed battery operation is safe for inverter.
        
        For AC-coupled systems (aGate X), monitors total power balance:
        - Available: Battery discharge + Solar generation
        - Required: Home loads
        - If Required > Available in off-grid, system will shutdown
        
        Returns:
            (is_safe, reason, safe_power)
            is_safe: True if operation is safe
            reason: Description of safety check result
            safe_power: Adjusted power if needed
        """
        solar = status['solar'].get('dc_power_w', 0)  # Solar AC-coupled or DC
        home = status['derived'].get('home_load_w', 0)
        grid = status['grid'].get('grid_power_w', 0)
        battery_actual = status['battery'].get('dc_power_w', 0)  # Current battery power
        
        # Get inverter ratings
        max_dc_power = self.ctrl.RATED_MAX_W  # Max inverter DC handling (battery side)
        
        # Check 1: Battery DC limits (independent of solar for AC-coupled)
        # For AC-coupled aGate X, solar comes in on separate AC inputs
        # We only control battery DC via Modbus
        if proposed_power > 0:  # Charging
            if proposed_power > max_dc_power * 1.05:
                safe_charge = max_dc_power
                logger.error(f"INVERTER SAFETY: Charge request {proposed_power:.0f}W exceeds max {max_dc_power}W. "
                            f"Limiting to {safe_charge:.0f}W")
                return False, f"Charge limit exceeded", safe_charge
        else:  # Discharging
            if abs(proposed_power) > max_dc_power * 1.05:
                safe_discharge = max_dc_power
                logger.error(f"INVERTER SAFETY: Discharge request {abs(proposed_power):.0f}W exceeds max {max_dc_power}W. "
                            f"Limiting to {safe_discharge:.0f}W")
                return False, f"Discharge limit exceeded", -safe_discharge
        
        # Check 2: Off-grid load vs capacity (CRITICAL for AC-coupled systems)
        # In off-grid or high-load scenarios, home demand may exceed supply
        # Available supply = Battery discharge capacity + Solar generation
        # If home load > available, aGate will shutdown
        
        grid_status = status.get('grid', {})
        conn_state = grid_status.get('grid_connection_state', 1)  # 1 = Connected
        
        # Estimate available discharge capacity
        available_discharge = max_dc_power  # Max battery can provide
        available_solar = solar if solar > 0 else 0
        total_available = available_discharge + available_solar
        
        # Warning: Home load approaching total capacity
        if home > total_available * 0.8:
            logger.warning(f"OFF-GRID RISK: Home load {home:.0f}W at {home/total_available*100:.0f}% of capacity "
                          f"({total_available:.0f}W = Battery {available_discharge:.0f}W + Solar {available_solar:.0f}W)")
            
            # If we're in discharge mode and home load is critical, limit discharge
            # to preserve capacity for surge handling
            # VMC convention: positive=charge, negative=discharge
            if proposed_power < 0 and home > total_available * 0.9:
                # Reduce discharge to leave headroom
                max_safe_discharge = total_available - home - 500  # 500W buffer
                if max_safe_discharge < 0:
                    max_safe_discharge = 0
                if abs(proposed_power) > max_safe_discharge:
                    logger.error(f"EMERGENCY: Home load {home:.0f}W would exceed supply capacity! "
                                f"Limiting discharge to {max_safe_discharge:.0f}W to prevent shutdown")
                    return False, f"Load exceeds capacity - discharge limited", -max_safe_discharge
            
            # If we're charging and home load is critical, that's actually GOOD
            # Charging adds capacity to the system (battery + solar + charging power)
            # Only warn if we're not providing enough help
            elif proposed_power > 0 and home > total_available * 0.9:
                # When charging, available capacity includes the charge power
                # (we're adding energy to the battery which can be used later)
                effective_available = total_available + proposed_power
                if home > effective_available * 0.95:
                    logger.warning(f"CRITICAL: Even with charging, home load {home:.0f}W near capacity "
                                  f"{effective_available:.0f}W. Consider reducing loads.")
        
        # Check 3: Grid stability for high power operations
        voltage = grid_status.get('voltage_v', 230)
        freq = grid_status.get('frequency_hz', 50)
        
        # If grid is unstable or disconnected, be more conservative
        if voltage < 210 or voltage > 250 or freq < 48 or freq > 52 or conn_state != 1:
            if abs(proposed_power) > max_dc_power * 0.5:
                reduced_power = proposed_power * 0.5
                grid_state = "DISCONNECTED" if conn_state != 1 else "UNSTABLE"
                logger.warning(f"GRID {grid_state}: V={voltage:.1f}V, F={freq:.2f}Hz. "
                              f"Limiting power from {proposed_power:.0f}W to {reduced_power:.0f}W")
                return True, f"Grid {grid_state} - power limited to 50%", reduced_power
        
        return True, "Inverter safety check passed", proposed_power
    
    def calculate_power(self) -> float:
        """
        Calculate desired battery power based on current mode.
        Returns: watts (positive=charge, negative=discharge, 0=idle)
        """
        # Read current status
        status = self.read_status()
        
        solar = status['solar'].get('dc_power_w', 0)
        home = status['derived'].get('home_load_w', 0)
        grid = status['grid'].get('grid_power_w', 0)
        soc = status['battery'].get('soc', 50)
        
        # Calculate based on mode
        calculator = self._get_calculator()
        power = calculator(solar, home, grid, soc)
        
        # Safety limits (SoC)
        power = self._apply_safety_limits(power, soc)
        
        # Inverter safety check (DC limits, grid stability)
        is_safe, reason, safe_power = self._check_inverter_safety(status, power)
        if not is_safe:
            logger.error(f"SAFETY VIOLATION: {reason}. Using safe power: {safe_power:.0f}W")
            power = safe_power
        elif power != safe_power:
            logger.info(f"Safety adjustment: {power:.0f}W -> {safe_power:.0f}W ({reason})")
            power = safe_power
        
        return power
    
    def _get_calculator(self) -> Callable:
        """Get the power calculation function for current mode."""
        calculators = {
            VirtualMode.SELF_CONSUMPTION: self._calc_self_consumption,
            VirtualMode.EMERGENCY_BACKUP: self._calc_emergency_backup,
            VirtualMode.TIME_OF_USE: self._calc_time_of_use,
            VirtualMode.GRID_ZERO: self._calc_grid_zero,
            VirtualMode.PEAK_SHAVE: self._calc_peak_shave,
            VirtualMode.MANUAL: self._calc_manual,
        }
        return calculators.get(self.mode, self._calc_self_consumption)
    
    def _calc_self_consumption(self, solar: float, home: float, 
                                grid: float, soc: float) -> float:
        """
        Maximize self-consumption of solar generation.
        
        Strategy:
        - Charge battery with excess solar (until target_soc reached)
        - Discharge to cover home load when solar insufficient
        - Maintain reserve for nighttime
        
        Uses actual device ratings from M702 nameplate.
        Respects target_soc - will not charge beyond target.
        """
        # Get actual device ratings (not hardcoded)
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        target_soc = getattr(self, 'target_soc', 100)
        
        excess_solar = solar - home
        
        # At or above target - stop charging, only discharge if needed
        if soc >= target_soc:
            if excess_solar < 0:
                # Need power, discharge to cover
                return max(home - solar, -max_discharge)
            else:
                # Excess solar but at target - idle or export
                return 0
        
        # High SOC (above reserve) - prioritize using battery
        if soc > (100 - self.self_reserve_pct):
            if excess_solar > 0 and soc < target_soc - 5:
                # Still charging but gently if below target
                return min(excess_solar * 0.5, max_charge * 0.2)  # 20% of max
            elif excess_solar < 0:
                # Discharge to cover deficit
                return max(home - solar, -max_discharge)
            else:
                return 0
        
        # Low SOC - aggressive charging if excess solar (until target)
        if excess_solar > 0 and soc < target_soc:
            return min(excess_solar, max_charge)  # Up to rated max
        
        # No excess solar, discharge if needed
        if home > solar and soc > 10:
            return max(solar - home, -max_discharge)
        
        return 0
    
    def _calc_emergency_backup(self, solar: float, home: float,
                                grid: float, soc: float) -> float:
        """
        Keep battery as full as possible for outage protection.
        
        Strategy:
        - Charge from any available source (solar + grid)
        - Only discharge if absolutely necessary
        - Target 95% SOC
        
        Uses actual device ratings from M702 nameplate.
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        if soc >= self.backup_target_soc:
            # Full enough, minimal activity
            if home > solar:
                # Small discharge to help (10% of max)
                return max(solar - home, -max_discharge * 0.1)
            return 0
        
        # Need to charge
        # Estimate energy needed (rough calc using rated capacity)
        rated_wh = self.ctrl.RATED_MAX_W * 2.72  # ~13.6kWh for 5kW rated
        charge_needed = (self.backup_target_soc - soc) / 100 * rated_wh
        hours_to_charge = 2  # Target 2 hours to full
        target_watts = min(charge_needed / hours_to_charge, max_charge)
        
        # Use solar first, then grid if needed
        if solar > home:
            # Excess solar available
            return min(solar - home, target_watts)
        else:
            # Charge from grid + solar
            return min(target_watts, max_charge)
    
    def _calc_time_of_use(self, solar: float, home: float,
                          grid: float, soc: float) -> float:
        """
        Arbitrage grid prices: charge cheap, discharge expensive.
        
        Uses TOU schedule strategy if file-based schedule loaded,
        otherwise falls back to hardcoded logic.
        
        Strategies:
        - charge: Maximize charging (off-peak)
        - discharge: Maximize discharging (peak)
        - self_consumption: Normal solar self-use (shoulder)
        - grid_zero: Minimize grid import/export
        - standby: Let aGate manage itself
        
        Uses actual device ratings from M702 nameplate.
        """
        # Get actual device ratings
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        # Get strategy from schedule (file-based or legacy)
        strategy = self.tou.get_strategy()
        min_soc = self.tou.get_min_soc()
        max_soc = self.tou.get_max_soc()
        
        if strategy == "charge":
            # Cheap power - charge if not full
            if soc < max_soc - 5:  # 5% buffer
                # Use excess solar first, then grid
                if solar > home:
                    # Charge excess solar + some from grid (60% of max)
                    return min(solar - home + max_charge * 0.6, max_charge)
                else:
                    return max_charge  # Max charge from grid
            return 0
            
        elif strategy == "discharge":
            # Expensive power - discharge to cover load
            if soc > min_soc + 5:  # 5% buffer
                # Cover home load from battery
                return max(min(home - solar, max_discharge), -max_discharge)
            return 0
            
        elif strategy == "grid_zero":
            # Minimize grid interaction
            return self._calc_grid_zero(solar, home, grid, soc)
            
        elif strategy == "solar_priority":
            # Priority: Charge battery from solar first, home loads from grid
            # This is useful when you want to maximize battery storage
            # for later use (e.g., before peak pricing period)
            if soc < max_soc - 5:  # If not near full
                if solar > 0:
                    # Use all solar for charging, home takes from grid
                    return min(solar, max_charge)
            # Otherwise normal self-consumption
            return self._calc_self_consumption(solar, home, grid, soc)
            
        elif strategy == "standby":
            # Let aGate manage itself
            return 0
            
        else:  # self_consumption or unknown
            # Normal self-consumption
            return self._calc_self_consumption(solar, home, grid, soc)
    
    def _calc_grid_zero(self, solar: float, home: float,
                        grid: float, soc: float) -> float:
        """
        Minimize grid interaction (island mode simulation).
        
        Strategy:
        - Target zero grid import/export
        - Battery buffers all imbalances
        
        Uses actual device ratings from M702 nameplate.
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        target_grid = 0
        current_grid = grid  # Positive = importing
        
        # Calculate battery power to achieve zero grid
        # If importing 500W, discharge 500W
        # If exporting 500W, charge 500W
        power = -current_grid
        
        # Add buffer for stability
        if abs(power) < self.grid_zero_buffer:
            power = 0
            
        # Limit to actual battery capabilities
        return max(min(power, max_charge), -max_discharge)
    
    def _calc_peak_shave(self, solar: float, home: float,
                         grid: float, soc: float) -> float:
        """
        Discharge during high home demand to reduce peak grid draw.
        
        Strategy:
        - Monitor home load
        - Discharge if load exceeds threshold
        - Charge during low demand
        
        Uses actual device ratings from M702 nameplate.
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        if home > self.peak_shave_threshold and soc > 30:
            # High demand - discharge to help
            discharge = min(home - solar, max_discharge)
            return -discharge
        
        elif home < 500 and soc < 80:
            # Low demand - charge if solar available (60% of max)
            if solar > home:
                return min(solar - home, max_charge * 0.6)
        
        return 0
    
    def _calc_manual(self, solar: float, home: float,
                     grid: float, soc: float) -> float:
        """Direct manual control."""
        return self.manual_power_w
    
    def _apply_safety_limits(self, power: float, soc: float) -> float:
        """Apply safety limits based on SOC.
        
        Implements soft limits with ramping:
        - Hard limits at absolute boundaries (0%, 100%)
        - Configurable limits with ramping window
        - Emergency override available (--force)
        """
        # Absolute hard limits (never override)
        if soc >= 99.5 and power > 0:
            logger.warning(f"SoC {soc:.1f}% at absolute maximum - blocking all charge")
            return 0
        
        if soc <= 0.5 and power < 0:
            logger.warning(f"SoC {soc:.1f}% at absolute minimum - blocking all discharge")
            return 0
        
        # Get limit parameters
        max_charge_soc = getattr(self, 'max_charge_soc', 100)
        min_discharge_soc = getattr(self, 'min_discharge_soc', 5)
        ramp_window = getattr(self, 'soc_ramp_window', 10)
        force_override = getattr(self, 'force_soc_limits', False)
        
        # Apply max charge limit with ramping
        if power > 0 and soc >= (max_charge_soc - ramp_window):
            if soc >= max_charge_soc:
                # Hard stop at limit
                if not force_override:
                    logger.info(f"SoC {soc:.1f}% at max charge limit ({max_charge_soc}%) - blocking charge")
                    return 0
                else:
                    logger.warning(f"FORCE OVERRIDE: SoC {soc:.1f}% exceeds max ({max_charge_soc}%) but charging anyway")
            else:
                # Ramping zone
                ramp_progress = (soc - (max_charge_soc - ramp_window)) / ramp_window
                ramp_factor = 1.0 - ramp_progress  # 1.0 at start, 0.0 at limit
                ramped_power = power * max(ramp_factor, 0.05)  # Minimum 5% power
                
                if ramp_factor < 0.9:  # Log when significantly ramped
                    logger.info(f"SoC {soc:.1f}% approaching max ({max_charge_soc}%) - "
                               f"ramping charge: {power:.0f}W → {ramped_power:.0f}W "
                               f"({ramp_factor*100:.0f}%)")
                power = ramped_power
        
        # Apply min discharge limit with ramping
        if power < 0 and soc <= (min_discharge_soc + ramp_window):
            if soc <= min_discharge_soc:
                # Hard stop at limit
                if not force_override:
                    logger.info(f"SoC {soc:.1f}% at min discharge limit ({min_discharge_soc}%) - blocking discharge")
                    return 0
                else:
                    logger.warning(f"FORCE OVERRIDE: SoC {soc:.1f}% below min ({min_discharge_soc}%) but discharging anyway")
            else:
                # Ramping zone
                ramp_progress = ((min_discharge_soc + ramp_window) - soc) / ramp_window
                ramp_factor = 1.0 - ramp_progress  # 1.0 at start, 0.0 at limit
                ramped_power = power * max(ramp_factor, 0.05)  # Minimum 5% power (negative)
                
                if ramp_factor < 0.9:  # Log when significantly ramped
                    logger.info(f"SoC {soc:.1f}% approaching min ({min_discharge_soc}%) - "
                               f"ramping discharge: {power:.0f}W → {ramped_power:.0f}W "
                               f"({ramp_factor*100:.0f}%)")
                power = ramped_power
        
        return power
    
    def _check_emergency_shutdown(self, status: Dict) -> Tuple[bool, str]:
        """
        Check if emergency shutdown is required due to dangerous conditions.
        
        Returns:
            (should_shutdown, reason)
        """
        grid = status.get('grid', {})
        battery = status.get('battery', {})
        
        voltage = grid.get('voltage_v', 230)
        freq = grid.get('frequency_hz', 50)
        temp = battery.get('temperature_c', 25)
        
        # Critical voltage limits (EMERGENCY SHUTDOWN)
        if voltage < 180 or voltage > 270:
            return True, f"EMERGENCY: Grid voltage {voltage:.1f}V outside safe range (180-270V)"
        
        # Critical frequency limits (EMERGENCY SHUTDOWN)
        if freq < 45 or freq > 55:
            return True, f"EMERGENCY: Grid frequency {freq:.2f}Hz outside safe range (45-55Hz)"
        
        # Critical battery temperature
        if temp and temp > 60:
            return True, f"EMERGENCY: Battery temperature {temp:.1f}°C exceeds 60°C limit"
        
        # Battery temperature too low (charging unsafe)
        if temp and temp < 0 and battery.get('dc_power_w', 0) < 0:
            return True, f"EMERGENCY: Battery temperature {temp:.1f}°C - charging prohibited"
        
        return False, ""
    
    def execute_once(self) -> float:
        """
        Calculate and send single command.
        Returns actual power sent.
        """
        # Read status for emergency check
        status = self.read_status()
        
        # Check for emergency shutdown conditions
        should_shutdown, reason = self._check_emergency_shutdown(status)
        if should_shutdown:
            logger.critical(reason)
            logger.critical("EMERGENCY SHUTDOWN: Releasing control and setting idle")
            try:
                self.ctrl.reset_control_state()
            except Exception as e:
                logger.error(f"Emergency reset failed: {e}")
            self._shutdown_requested = True
            return 0
        
        power = self.calculate_power()
        
        # Send via hardware controller
        cmd = BatteryCommand(power_watts=power, mode=ControlMode.LIMIT_ABS)
        success, msg = self.ctrl.send_command(cmd)
        
        if success:
            logger.info(f"{self.mode.value}: {power:.0f}W")
        else:
            logger.error(f"Failed: {msg}")
        
        return power if success else 0
    
    def tick(self) -> bool:
        """
        Call periodically to maintain control.
        Returns True if action taken, False if skipped.
        """
        now = time.time()
        if now - self.last_tick >= self.tick_interval:
            self.execute_once()
            self.last_tick = now
            return True
        return False
    
    def _format_duration(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _get_target_soc_display(self) -> str:
        """Get target SoC display based on current mode."""
        # Universal target_soc applies to all modes
        target = getattr(self, 'target_soc', 100)
        
        if self.mode == VirtualMode.EMERGENCY_BACKUP:
            # Show both universal target and legacy backup_target_soc
            return f"{target}% (charge to target)"
        elif self.mode == VirtualMode.SELF_CONSUMPTION:
            return f"{self.self_reserve_pct}% reserve / {target}% target"
        elif self.mode == VirtualMode.TIME_OF_USE:
            # Show schedule info and target
            if self.tou.is_file_based():
                period = self.tou.get_current_period()
                strategy = self.tou.get_strategy()
                price = self.tou.get_current_price()
                return f"{period} (${price:.2f}) → {strategy} | target: {target}%"
            else:
                return f"Legacy schedule | target: {target}%"
        elif self.mode == VirtualMode.PEAK_SHAVE:
            return f"{self.peak_shave_threshold}W threshold / {target}% target"
        elif self.mode == VirtualMode.GRID_ZERO:
            return f"Zero grid | {target}% target"
        elif self.mode == VirtualMode.MANUAL:
            return f"Manual {self.manual_power_w}W | {target}% target"
        else:
            return f"{target}% target"
    
    def _print_telemetry(self, status: Dict, start_time: float, duration_seconds: Optional[float] = None):
        """Print formatted telemetry to console."""
        now = time.time()
        elapsed = now - start_time
        remaining = duration_seconds - elapsed if duration_seconds else None
        
        battery = status.get('battery', {})
        grid = status.get('grid', {})
        solar = status.get('solar', {})
        derived = status.get('derived', {})
        control = status.get('control', {})
        
        soc = battery.get('soc', 0)
        battery_power = control.get('wset_watts', 0)
        wset_ena = control.get('wset_enabled', 0)  # Fixed: was 'wset_ena'
        wset_pct = control.get('wset_pct', 0)  # Will be calculated below
        solar_power = solar.get('dc_power_w', 0)
        grid_power = grid.get('grid_power_w', 0)
        home_load = derived.get('home_load_w', 0)
        
        # Get total solar from all sources (including extensions)
        # For AC-coupled systems, Model 714 DC power may be 0, use extensions
        total_solar = derived.get('total_solar_w', solar_power)
        # Ensure solar is never negative (it's production)
        total_solar = abs(total_solar) if total_solar != 0 else 0
        
        # Derive actual command power from WSetPct (more reliable than WSet)
        # FranklinWH firmware uses WSetPct for actual power control
        wset_pct_value = control.get('wset_pct', 0)  # Already scaled
        rated_max = getattr(self.ctrl, 'RATED_MAX_W', 5000)
        
        if wset_ena == 1:
            # Calculate power from percentage (WSetPct is the actual control)
            actual_power = wset_pct_value / 100.0 * rated_max
        else:
            actual_power = battery_power  # Fallback to WSet
        
        # Get individual solar sources from extensions if available
        ext_solar = solar.get('extension', {})
        pv_proximal = ext_solar.get('pv_proximal', 0)
        pv_remote1 = ext_solar.get('pv_remote1', 0)
        pv_remote2 = ext_solar.get('pv_remote2', 0)
        pv_total_reg = ext_solar.get('pv_total', 0)
        has_extension_data = bool(ext_solar)
        
        # Read aGate native mode (OnGridMode and reserves)
        native_mode = self.ctrl.read_native_mode() or {}
        ongrid_mode = native_mode.get('mode_raw', -1)
        ongrid_name = native_mode.get('mode_name', 'Unknown')
        self_reserve = native_mode.get('self_reserve_pct', -1)
        tou_reserve = native_mode.get('tou_reserve_pct', -1)
        
        # Determine which reserve is active based on OnGridMode
        # 0=Backup (no reserve shown), 1=Self, 2=TOU, 3=Manual
        active_reserve = "N/A"
        if ongrid_mode == 1:
            active_reserve = f"{self_reserve}% (Self)"
        elif ongrid_mode == 2:
            active_reserve = f"{tou_reserve}% (TOU)"
        
        # Detect potential Cloud API activity
        dc_power = battery.get('dc_power_w', 0)  # Actual battery DC power
        cloud_active_warning = ""
        
        # Check for activity not from our Modbus control
        if ongrid_mode != 3:  # Not in Manual mode
            if abs(dc_power) > 100:  # Battery is actively charging/discharging
                cloud_active_warning = f" ⚠️  CLOUD ACTIVE (OnGridMode={ongrid_name})"
        
        # Battery state icon
        # FranklinWH defect: dc_power from Model 713 is often 0 even when active
        # Derive from: 1) actual DC power, 2) WSetPct-derived power if WSetEna=1
        if abs(dc_power) > 50:
            # Use actual DC power if available (from hardware)
            if dc_power < 0:
                bat_icon = "⚡ CHARGING"
                bat_detail = f"{abs(dc_power):.0f}W"
            else:
                bat_icon = "🔋 DISCHARGING"
                bat_detail = f"{dc_power:.0f}W"
        elif wset_ena == 1 and abs(actual_power) > 50:
            # Derive from WSetPct when DC power not available
            # WSetPct < 0 = charging, WSetPct > 0 = discharging
            if actual_power < 0:
                bat_icon = "⚡ CHARGING"
                bat_detail = f"{abs(actual_power):.0f}W"
            else:
                bat_icon = "🔋 DISCHARGING"
                bat_detail = f"{actual_power:.0f}W"
        else:
            bat_icon = "💤 IDLE"
            bat_detail = "0W"
        
        # Grid state
        if grid_power > 50:
            grid_icon = "↓ IMPORTING"
            grid_detail = f"{grid_power:.0f}W"
        elif grid_power < -50:
            grid_icon = "↑ EXPORTING"
            grid_detail = f"{abs(grid_power):.0f}W"
        else:
            grid_icon = "─ BALANCED"
            grid_detail = f"{grid_power:.0f}W"
        
        # Clear screen (optional, for cleaner output)
        # print("\033[2J\033[H", end="")  # Uncomment for terminal clear
        
        print("\n" + "=" * 70)
        print(f"  MODE: {self.mode.value.upper()}{cloud_active_warning}")
        print(f"  {'─' * 66}")
        print(f"  ⏱️  ELAPSED: {self._format_duration(elapsed)}" + 
              (f"  |  ⏳ REMAINING: {self._format_duration(remaining)}" if remaining is not None else ""))
        print(f"  🎯 TARGET:   {self._get_target_soc_display()}")
        print(f"  aGATE:      OnGridMode={ongrid_name} ({ongrid_mode}) | Reserve: {active_reserve}")
        print(f"  {'─' * 66}")
        print(f"  BATTERY:    {bat_icon:15s} {bat_detail:>10s}  |  SoC: {soc:.1f}%")
        print(f"  MODBUS:     WSetEna={wset_ena} | Command: {actual_power:.0f}W (from WSetPct={wset_pct_value:.1f}%)")
        
        # Solar display - show total and individual sources
        # Use total_solar (from extensions if available, else Model 714)
        display_solar = abs(total_solar)  # Ensure positive
        if has_extension_data and (pv_proximal > 0 or pv_remote1 > 0 or pv_remote2 > 0):
            # Show detailed breakdown with FranklinWH extensions
            print(f"  SOLAR PV:   {'☀️  TOTAL':15s} {display_solar:>10.0f}W")
            if pv_proximal > 0:
                print(f"              {'  └─ Proximal':15s} {pv_proximal:>10.0f}W  (local AC-coupled)")
            if pv_remote1 > 0:
                print(f"              {'  └─ Remote 1':15s} {pv_remote1:>10.0f}W  (additional array)")
            if pv_remote2 > 0:
                print(f"              {'  └─ Remote 2':15s} {pv_remote2:>10.0f}W  (additional array)")
            if pv_total_reg > 0 and pv_total_reg != total_solar:
                print(f"              {'  (Reg 15502)':15s} {pv_total_reg:>10.0f}W")
        else:
            # Simple display - Model 714 only
            print(f"  SOLAR PV:   {'☀️  PRODUCING':15s} {display_solar:>10.0f}W  |  ")
        
        print(f"  HOME LOAD:  {'🏠 CONSUMING':15s} {home_load:>10.0f}W  |  ")
        print(f"  GRID:       {grid_icon:15s} {grid_detail:>10s}")
        print(f"  {'─' * 66}")
        # SoC limit status
        limit_status = ""
        ramp_pct = 100.0
        if actual_power > 0 and soc >= (self.max_charge_soc - self.soc_ramp_window):
            if soc >= self.max_charge_soc:
                limit_status = " 🔒 MAX LIMIT"
            else:
                ramp_pct = (self.max_charge_soc - soc) / self.soc_ramp_window * 100
                limit_status = f" ↓ RAMPING ({ramp_pct:.0f}%)"
        elif actual_power < 0 and soc <= (self.min_discharge_soc + self.soc_ramp_window):
            if soc <= self.min_discharge_soc:
                limit_status = " 🔒 MIN LIMIT"
            else:
                ramp_pct = (soc - self.min_discharge_soc) / self.soc_ramp_window * 100
                limit_status = f" ↓ RAMPING ({ramp_pct:.0f}%)"
        
        if self.force_soc_limits and (soc >= self.max_charge_soc or soc <= self.min_discharge_soc):
            limit_status += " [FORCE]"
        
        print(f"  CMD: WSetPct={wset_pct_value:.1f}%  ({actual_power:.0f}W){limit_status}")
        print(f"  LIMITS: Discharge≥{self.min_discharge_soc}% Charge≤{self.max_charge_soc}% (window:{self.soc_ramp_window}%)")
        
        # Inverter load check (battery DC only for AC-coupled)
        max_dc = self.ctrl.RATED_MAX_W
        # Use actual DC power if available, otherwise derive from command
        battery_dc_load = abs(dc_power) if abs(dc_power) > 50 else abs(actual_power)
        battery_load_pct = (battery_dc_load / max_dc * 100) if max_dc > 0 else 0
        
        if battery_load_pct > 95:
            print(f"  ⚠️  BATTERY INVERTER: {battery_load_pct:.0f}% ({battery_dc_load:.0f}W / {max_dc}W) - CRITICAL!")
        elif battery_load_pct > 80:
            print(f"  ⚠️  BATTERY INVERTER: {battery_load_pct:.0f}% ({battery_dc_load:.0f}W / {max_dc}W) - HIGH")
        else:
            print(f"  BATTERY INVERTER: {battery_load_pct:.0f}% ({battery_dc_load:.0f}W / {max_dc}W)")
        
        # Off-grid capacity monitoring (AC-coupled systems)
        # Available: Battery max discharge + Solar AC (from all sources)
        # Required: Home load
        available_battery = max_dc
        available_solar = max(0, total_solar)  # Solar from all sources (extensions + Model 714)
        total_available = available_battery + available_solar
        
        if home_load > 0 and total_available > 0:
            capacity_used_pct = (home_load / total_available * 100)
            
            if capacity_used_pct > 95:
                print(f"  🚨 OFF-GRID RISK: Home load {home_load:.0f}W at {capacity_used_pct:.0f}% of supply capacity!")
                print(f"     Available: Battery {available_battery:.0f}W + Solar {available_solar:.0f}W = {total_available:.0f}W")
                print(f"     ⚠️  System may shutdown if load exceeds supply!")
            elif capacity_used_pct > 80:
                print(f"  ⚠️  CAPACITY: Home load {home_load:.0f}W using {capacity_used_pct:.0f}% of supply")
                print(f"     Available: {total_available:.0f}W (Battery {available_battery:.0f}W + Solar {available_solar:.0f}W)")
            else:
                print(f"  CAPACITY: {capacity_used_pct:.0f}% ({home_load:.0f}W / {total_available:.0f}W available)")
        
        # Grid stability check
        voltage = grid.get('voltage_v', 230)
        freq = grid.get('frequency_hz', 50)
        
        grid_warning = ""
        if voltage < 210 or voltage > 250:
            grid_warning += f" ⚠️ VOLTAGE {voltage:.1f}V"
        if freq < 48 or freq > 52:
            grid_warning += f" ⚠️ FREQUENCY {freq:.2f}Hz"
        
        if grid_warning:
            print(f"  🚨 GRID ALERT:{grid_warning}")
        
        print("=" * 70)

    def run_continuous(self, duration_seconds: Optional[float] = None):
        """
        Run controller continuously with graceful shutdown.
        
        Args:
            duration_seconds: Run for N seconds, or None for indefinite
        """
        logger.info(f"Starting continuous control: {self.mode.value}")
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler) # systemd stop
        
        start = time.time()
        last_status_log = 0
        last_console_output = 0
        
        # Print initial header
        print("\n" + "=" * 70)
        print(f"  STARTING: {self.mode.value} mode")
        if duration_seconds:
            print(f"  DURATION: {self._format_duration(duration_seconds)}")
        print(f"  Press Ctrl+C to stop")
        print("=" * 70)
        
        try:
            while not self._shutdown_requested:
                # Execute control tick
                self.tick()
                
                now = time.time()
                
                # Console telemetry output (every 5 seconds for visibility)
                if now - last_console_output >= 5:
                    status = self.read_status()
                    self._print_telemetry(status, start, duration_seconds)
                    last_console_output = now
                
                # Periodic status logging (every 60 seconds to file)
                if now - last_status_log >= 60:
                    status = self.read_status()
                    battery = status.get('battery', {})
                    grid = status.get('grid', {})
                    logger.info(f"Status: SOC={battery.get('soc', 0):.1f}%, "
                               f"Grid={grid.get('grid_power_w', 0):.0f}W, "
                               f"Mode={self.mode.value}")
                    
                    # Check for alarms during operation
                    can_operate, blocking = self.ctrl.check_blocking_alarms()
                    if not can_operate:
                        logger.warning(f"BLOCKING ALARMS: {blocking}")
                    
                    last_status_log = now
                
                # Small sleep to prevent busy-wait
                time.sleep(0.1)
                
                # Check duration limit
                if duration_seconds and (now - start) > duration_seconds:
                    print("\n✓ Duration expired, stopping...")
                    break
                    
        except Exception as e:
            logger.error(f"Runtime error: {e}")
        finally:
            # Safe shutdown — MUST set WSetEna=0 to release Modbus control.
            # Without this, aGate stays in VPP standby instead of resuming
            # its configured mode (e.g. Self-Consumption).
            print("\n" + "=" * 70)
            print("  SHUTTING DOWN: Releasing Modbus control (WSetEna=0)")
            print("=" * 70)
            try:
                self.ctrl.reset_control_state()
                print("✓ Control released - aGate will resume configured mode")
            except Exception as e:
                logger.error(f"Shutdown reset failed: {e}")
                print(f"✗ Error releasing control: {e}")

    def read_all_alarms(client):
        """Read all alarm sources from FranklinWH aGate"""
        alarms = {
            'system': client.read_holding_registers(40076, 2),      # Model 701 Alrm
            'solar': client.read_holding_registers(41104, 2),       # Model 502 Evt
            'dc_port': client.read_holding_registers(41044, 2),     # Model 714 PrtAlrms
            'battery_status': client.read_holding_registers(41039, 1),  # Model 713 Sta
            'vendor_info': client.read_string(40193, 16),           # Model 701 MnAlrmInfo
        }
        return alarms

    def check_critical_alarms(alarms):
        """Determine if safe to operate"""
        system_alrm = (alarms['system'][1] << 16) | alarms['system'][0]
        dc_alrm = (alarms['dc_port'][1] << 16) | alarms['dc_port'][0]
        battery_sta = alarms['battery_status'][0]
        
        # Critical faults that block operation
        CRITICAL_BITS = (1 << 0) | (1 << 6) | (1 << 7) | (1 << 13) | (1 << 14)  # GROUND, CABINET_OPEN, MANUAL_SHUTDOWN, STRING_FAULT, ARC_FAULT
        
        if system_alrm & CRITICAL_BITS:
            return False, f"Critical system alarm: 0x{system_alrm:08X}"
        
        if dc_alrm & 0x3F:  # Any DC port electrical fault
            return False, f"DC port alarm: 0x{dc_alrm:08X}"
        
        if battery_sta == 6:  # FAULT
            return False, "Battery status: FAULT"
        
        return True, "System healthy"

    def reset_alarms_if_cleared(client):
        """Write to Model 715 AlarmReset after fault conditions resolved"""
        # First verify no active alarms
        alarms = read_all_alarms(client)
        safe, msg = check_critical_alarms(alarms)
        
        if safe:
            client.write_register(41094, 1)  # Write 1 to AlarmReset
            time.sleep(0.5)
            client.write_register(41094, 0)  # Clear reset bit
            return True
        else:
            return False, f"Cannot reset: {msg}"

# ============================================================
# COMMAND LINE INTERFACE
# ============================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all options."""
    parser = argparse.ArgumentParser(
        description='FranklinWH aGate Battery Control with Virtual Modes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Health check (recommended first step)
  %(prog)s -i YOUR_AGATE_IP --healthcheck
  
  # Quick stop — release Modbus control, resume Self-Consumption
  %(prog)s -i YOUR_AGATE_IP --stop
  
  # Direct control (explicit action flags - RECOMMENDED)
  %(prog)s -i YOUR_AGATE_IP --charge 3000           # Charge at 3000W (import)
  %(prog)s -i YOUR_AGATE_IP --discharge 2000        # Discharge at 2000W (export)
  %(prog)s -i YOUR_AGATE_IP --standby               # Set to 0W (idle)
  
  # Direct control (legacy --power with sign)
  %(prog)s -i YOUR_AGATE_IP --power 3000            # Charge at 3000W
  %(prog)s -i YOUR_AGATE_IP --power -2000 --revert 3600  # Discharge 2000W for 1hr
  %(prog)s -i YOUR_AGATE_IP --status
  
  # Virtual modes with reset (recommended)
  %(prog)s -i YOUR_AGATE_IP --reset-on-start --mode self_consumption
  %(prog)s -i YOUR_AGATE_IP --reset-on-start --mode emergency_backup --target-soc 90
  %(prog)s -i YOUR_AGATE_IP --reset-on-start --mode time_of_use
  %(prog)s -i YOUR_AGATE_IP --reset-on-start --mode manual --charge 1500 --duration 7200
  
  # With custom timeout
  %(prog)s -i YOUR_AGATE_IP -t 15.0 --status
        """
    )
    
    # Connection parameters
    parser.add_argument('-i', '--ip', 
                       help='aGate IP address (required for most operations)')
    parser.add_argument('-p', '--port', type=int, default=502,
                       help='Modbus TCP port (default: 502)')
    parser.add_argument('-u', '--unit', type=int, default=2,
                       help='Modbus unit ID (default: 2)')
    parser.add_argument('-t', '--timeout', type=float, default=10.0,
                       help='Connection timeout in seconds (default: 10.0)')
    
    # Startup behavior
    parser.add_argument('--reset-on-start', action='store_true',
                       help='Reset control state to idle before operation '
                            '(recommended if zombie state detected)')
    parser.add_argument('--assume-clean-state', action='store_true',
                       help='Skip health check warnings (use with caution)')
    
    # Direct control (original and explicit action flags)
    power_group = parser.add_mutually_exclusive_group()
    power_group.add_argument('--power', type=float,
                       help='Power in watts (+charge, -discharge). Legacy option, use --charge or --discharge for clarity.')
    power_group.add_argument('--charge', type=float, metavar='WATTS',
                       help='Charge battery at specified watts (import from grid). Positive value.')
    power_group.add_argument('--discharge', type=float, metavar='WATTS',
                       help='Discharge battery at specified watts (export to grid). Positive value.')
    power_group.add_argument('--standby', action='store_true',
                       help='Set battery to standby (0W). Equivalent to --idle.')
    
    parser.add_argument('--idle', action='store_true',
                       help='Set to idle (0W). Deprecated: use --standby instead.')
    parser.add_argument('--stop', action='store_true',
                       help='Release Modbus control (WSetEna=0) and exit. '
                            'Use this to resume normal aGate operation (e.g. Self-Consumption)')
    parser.add_argument('--revert', type=int, default=0,
                       help='Auto-revert time in seconds')
    
    # Virtual modes (new)
    parser.add_argument('--mode', type=str, choices=[m.value for m in VirtualMode],
                       help='Virtual operating mode')
    parser.add_argument('--reserve', type=int, default=20,
                       help='Self-consumption reserve %% (default: 20)')
    parser.add_argument('--target-soc', type=int, default=95,
                       help='Emergency backup target SOC (default: 95)')
    parser.add_argument('--threshold', type=int, default=2000,
                       help='Peak shave threshold in watts (default: 2000)')
    parser.add_argument('--duration', type=int,
                       help='Mode duration in seconds (default: indefinite)')
    
    # SoC Limits (with ramping)
    parser.add_argument('--max-charge-soc', type=int, default=100,
                       help='Maximum SoC for charging with ramping (default: 100)')
    parser.add_argument('--min-discharge-soc', type=int, default=None,
                       help='Minimum SoC for discharging with ramping '
                            '(default: read from aGate reserve)')
    parser.add_argument('--soc-ramp-window', type=int, default=10,
                       help='SoC ramping window in percent (default: 10)')
    parser.add_argument('--force', action='store_true',
                       help='Force operation even if SoC limits would prevent it '
                            '(logged warning, use with caution)')
    parser.add_argument('--off-grid-permitted', action='store_true',
                       help='Allow operation when grid is disconnected (off-grid)')
    
    # TOU Schedule file support
    parser.add_argument('--schedule-file', type=str, metavar='FILE',
                       help='TOU schedule JSON file (for time_of_use mode). '
                            'See schedules/ directory for examples.')
    parser.add_argument('--show-schedule', type=str, metavar='FILE',
                       help='Display schedule file contents and exit')
    parser.add_argument('--validate-schedule', type=str, metavar='FILE',
                       help='Validate schedule file and exit')
    
    # Information
    parser.add_argument('--status', action='store_true',
                       help='Read status only')
    parser.add_argument('--healthcheck', action='store_true',
                       help='Run health check and exit')
    parser.add_argument('--clear-alarms', action='store_true',
                       help='Clear alarms if safe (no critical faults)')
    parser.add_argument('--check-alarms', action='store_true',
                       help='Check and display all alarm states')
    parser.add_argument('--test-extension-write', action='store_true',
                       help='Test extension register writability (15507-15509)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate without writing')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable debug logging')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Minimal output (warnings and errors only)')
    
    return parser


def print_health_report(health: HealthStatus):
    """Pretty print health check results."""
    print("\n" + "=" * 70)
    print("HEALTH CHECK REPORT")
    print("=" * 70)
    print(f"Overall Status: {health.message}")
    print(f"Healthy: {'✓ YES' if health.healthy else '✗ NO'}")
    print("-" * 70)
    
    details = health.details
    
    # Connection
    print(f"\nConnection:")
    print(f"  Modbus TCP: {'✓ Connected' if details.get('connection') else '✗ Failed'}")
    
    # Models
    print(f"\nSunSpec Models:")
    print(f"  Model 704 (Control):  {'✓ Present' if details.get('model_704') else '✗ Missing'}")
    print(f"  Model 713 (Battery):  {'✓ Present' if details.get('model_713') else '✗ Missing'}")
    print(f"  Model 701 (Grid):     {'✓ Present' if details.get('model_701') else '✗ Missing'}")
    
    # Control state
    print(f"\nControl State (Model 704):")
    print(f"  WSetEna:              {details.get('wset_ena', 'N/A')}")
    print(f"  WSetMod:              {details.get('wset_mode', 'N/A')}")
    print(f"  WSet:                 {details.get('wset', 'N/A')} W")
    print(f"  Revert Timer:         {details.get('revert_tms', 'N/A')} s")
    print(f"  Revert Remaining:     {details.get('revert_rem', 'N/A')} s")
    
    if details.get('zombie_state'):
        print(f"  ⚠ ZOMBIE STATE:       Control enabled with expired timer!")
    
    # Battery
    print(f"\nBattery (Model 713):")
    soc = details.get('soc', 0)
    soc_safe = details.get('soc_safe', False)
    print(f"  SoC:                  {soc:.1f}% {'✓' if soc_safe else '⚠'}")
    
    # Grid
    print(f"\nGrid (Model 701):")
    v = details.get('grid_voltage', 0)
    f = details.get('grid_frequency', 0)
    grid_safe = details.get('grid_safe', False)
    print(f"  Voltage:              {v:.1f} V {'✓' if grid_safe else '⚠'}")
    print(f"  Frequency:            {f:.2f} Hz {'✓' if grid_safe else '⚠'}")
    
    # SPAN / OnGridMode
    print(f"\nSPAN Extensions:")
    span = details.get('span', {})
    if span.get('readable'):
        ongrid = details.get('ongrid_mode', -1)
        ongrid_name = details.get('ongrid_mode_name', 'Unknown')
        remote_safe = details.get('remote_control_safe', False)
        print(f"  Status:               ✓ Detected")
        print(f"  OnGridMode:           {ongrid} ({ongrid_name})")
        print(f"  Remote Control:       {'✓ Safe' if remote_safe else '⚠ Caution'}")
    else:
        print(f"  Status:               Not detected (SunSpec mode only)")
        print(f"  Note:                 SPAN extensions require installer unlock")
    
    # Cloud API
    print(f"\nCloud API:")
    cloud = details.get('cloud_api', {})
    print(f"  Status:               {'✓ Available' if cloud.get('available') else '✗ Not implemented'}")
    if not cloud.get('available'):
        print(f"  Note:                 Planned for v2.0 release")
    
    # Recommendations
    print("\n" + "-" * 70)
    print("RECOMMENDATIONS:")
    for rec in health.recommendations:
        print(f"  • {rec}")
    
    print("=" * 70)


def check_startup_state(ctrl, requested_mode: str = None, args=None) -> dict:
    """
    Check current system state at startup and detect potential conflicts.
    
    Returns dict with:
        - current_state: Description of current battery/grid state
        - conflicts: List of potential conflicts
        - can_proceed: Whether it's safe to proceed
        - warnings: List of warning messages
    """
    result = {
        'current_state': {},
        'conflicts': [],
        'warnings': [],
        'can_proceed': True
    }
    
    try:
        # Check alarms first
        can_operate, blocking = ctrl.check_blocking_alarms()
        alarms = ctrl.read_alarms()
        decoded = alarms.get('decoded', {})
        
        result['alarms'] = {
            'system': decoded.get('system', []),
            'dc_port': decoded.get('dc_port', []),
            'battery_status': decoded.get('battery_status', 'UNKNOWN'),
            'blocking': blocking
        }
        
        if not can_operate:
            result['conflicts'].append(f"BLOCKING ALARMS: {', '.join(blocking)}")
            result['can_proceed'] = False
        elif decoded.get('system') or decoded.get('dc_port'):
            # Non-blocking alarms present
            all_alarms = decoded.get('system', []) + decoded.get('dc_port', [])
            result['warnings'].append(f"Active alarms (non-blocking): {', '.join(all_alarms)}")
        
        # Read current battery status
        bat = ctrl.read_battery_status()
        soc = bat.get('soc', 0)
        result['current_state']['soc'] = soc
        
        # Read grid status
        grid = ctrl.read_grid_status()
        grid_power = grid.get('grid_power_w', 0)
        voltage = grid.get('voltage_v', 0)
        result['current_state']['grid_power'] = grid_power
        result['current_state']['grid_voltage'] = voltage
        # Grid connection: check both voltage and ConnSt register
        connection_state = grid.get('connection_state', 'Unknown')
        result['current_state']['connection_state'] = connection_state
        voltage_ok = 180 < voltage < 270
        conn_st_connected = connection_state == 'Connected'
        result['current_state']['grid_connected'] = voltage_ok and conn_st_connected
        
        # Off-grid warning (will block unless --off-grid-permitted)
        if not result['current_state']['grid_connected']:
            result['warnings'].append(
                f"OFF-GRID: Grid connection state is '{connection_state}' (voltage: {voltage:.1f}V)"
            )
        
        # Read control status
        ctl = ctrl.read_control_status()
        wset_ena = ctl.get('wset_enabled', 0)
        wset_pct = ctl.get('wset_pct', 0)
        result['current_state']['wset_ena'] = wset_ena
        result['current_state']['wset_pct'] = wset_pct
        
        # Calculate actual power
        rated_max = getattr(ctrl, 'RATED_MAX_W', 5000)
        actual_power = (wset_pct / 100.0 * rated_max) if wset_ena == 1 else 0
        result['current_state']['actual_power'] = actual_power
        
        # Determine battery activity
        if wset_ena == 1:
            if actual_power < -50:
                result['current_state']['battery_activity'] = f'CHARGING ({abs(actual_power):.0f}W)'
            elif actual_power > 50:
                result['current_state']['battery_activity'] = f'DISCHARGING ({actual_power:.0f}W)'
            else:
                result['current_state']['battery_activity'] = 'IDLE'
        else:
            result['current_state']['battery_activity'] = 'IDLE (no control)'
        
        # Read native mode
        native = ctrl.read_native_mode()
        if native:
            ongrid_mode = native.get('mode_raw', -1)
            ongrid_name = native.get('mode_name', 'Unknown')
            result['current_state']['ongrid_mode'] = ongrid_name
            result['current_state']['ongrid_mode_raw'] = ongrid_mode
            
            # Check for conflicts - including Cloud API control (WSetEna=0 but battery active)
            # Read actual battery DC power from Model 714 to detect Cloud API activity
            m714 = ctrl.get_model(714)
            battery_dc_power = 0
            if m714:
                try:
                    m714.read()
                    sf_w = ctrl._get_scale_factor(m714, 'DCW_SF')
                    battery_dc_power = m714.DCW.value * (10 ** sf_w) if m714.DCW.value else 0
                    result['current_state']['battery_dc_power'] = battery_dc_power
                except Exception:
                    pass
            
            # Detect active control: either Modbus (wset_ena=1) OR Cloud API (battery moving)
            is_modbus_control = wset_ena == 1
            is_cloud_charging = battery_dc_power < -500
            is_cloud_discharging = battery_dc_power > 500
            is_cloud_active = is_cloud_charging or is_cloud_discharging
            
            # Store for display
            result['current_state']['control_source'] = 'Modbus' if is_modbus_control else ('Cloud API' if is_cloud_active else 'Idle')
            
            if requested_mode:
                # Map requested mode to OnGridMode
                mode_mapping = {
                    'emergency_backup': 0,
                    'self_consumption': 1,
                    'time_of_use': 2,
                    'manual': 3,
                }
                requested_ongrid = mode_mapping.get(requested_mode, -1)
                
                # CONFLICT: aGate is actively controlling via Cloud API or Modbus
                if is_modbus_control or is_cloud_active:
                    conflict_msg = f"CONFLICT: aGate '{ongrid_name}' mode is actively controlling"
                    if is_cloud_charging:
                        conflict_msg += f" (CHARGING {abs(battery_dc_power):.0f}W via Cloud API)"
                    elif is_cloud_discharging:
                        conflict_msg += f" (DISCHARGING {battery_dc_power:.0f}W via Cloud API)"
                    elif is_modbus_control:
                        conflict_msg += f" (WSetEna=1, {actual_power:.0f}W)"
                    
                    result['conflicts'].append(conflict_msg)
                    result['conflicts'].append(f"         Requested '{requested_mode}' conflicts with active operation")
                    result['can_proceed'] = False
                
                elif ongrid_mode != 3 and ongrid_mode != requested_ongrid:
                    # Different mode but not actively controlling
                    result['warnings'].append(
                        f"NOTE: aGate is in '{ongrid_name}' mode but idle"
                    )
                    result['warnings'].append(
                        f"      Mode change recommended for '{requested_mode}' operation"
                    )
        
        # Check grid stability
        if voltage < 210 or voltage > 250:
            result['warnings'].append(f"Grid voltage {voltage:.1f}V outside normal range (210-250V)")
        
        # Check SoC limits
        if soc < 10:
            result['warnings'].append(f"SoC very low ({soc:.1f}%) - charging may be limited")
        elif soc > 95:
            result['warnings'].append(f"SoC very high ({soc:.1f}%) - discharging may be limited")
        
        # Check if target SoC already reached
        if requested_mode and hasattr(args, 'target_soc') and args.target_soc:
            target = args.target_soc
            if requested_mode in ['emergency_backup', 'self_consumption']:
                if soc >= target:
                    result['warnings'].append(
                        f"TARGET ALREADY REACHED: Current SoC {soc:.1f}% >= Target {target:.1f}%"
                    )
                    if requested_mode == 'emergency_backup':
                        result['warnings'].append("Battery is already at/above backup target")
                    elif requested_mode == 'self_consumption':
                        result['warnings'].append("Will NOT charge from grid. Only excess solar will be stored")
            
    except Exception as e:
        result['warnings'].append(f"Could not read full state: {e}")
    
    return result


def print_startup_summary(state: dict, requested_mode: str = None, args=None):
    """Print clear startup state summary."""
    print("\n" + "=" * 70)
    print("  CURRENT SYSTEM STATE")
    print("=" * 70)
    
    current = state['current_state']
    soc = current.get('soc', 0)
    
    # Build SOC summary line with ETA
    soc_line = f"    SoC: {soc:.1f}%"
    if args and hasattr(args, 'target_soc') and args.target_soc:
        target = args.target_soc
        soc_line += f" | Target: {target:.1f}%"
        if soc < target:
            eta_min = (target - soc) * 1.6  # ~1.6 min per % at 5kW
            soc_line += f" | ETA: +{int(eta_min)}min"
        elif soc == target:
            soc_line += " | AT TARGET"
        else:
            soc_line += " | ABOVE TARGET"
    
    print(f"\n  Battery:")
    print(soc_line)
    print(f"    Activity:      {current.get('battery_activity', 'Unknown')}")
    
    print(f"\n  Grid:")
    print(f"    Status:        {'✓ Connected' if current.get('grid_connected') else '✗ Disconnected/Unsafe'}")
    print(f"    Power:         {current.get('grid_power', 0):.0f}W")
    print(f"    Voltage:       {current.get('grid_voltage', 0):.1f}V")
    
    print(f"\n  Control:")
    print(f"    WSetEna:       {current.get('wset_ena', 0)}")
    print(f"    WSetPct:       {current.get('wset_pct', 0):.1f}%")
    print(f"    Actual Power:  {current.get('actual_power', 0):.0f}W")
    
    if current.get('ongrid_mode'):
        print(f"\n  aGate Mode:")
        print(f"    OnGridMode:    {current.get('ongrid_mode')} ({current.get('ongrid_mode_raw')})")
    
    # Display alarms if any
    alarms = state.get('alarms', {})
    if alarms.get('system') or alarms.get('dc_port'):
        print(f"\n  ⚠️  ALARMS:")
        if alarms.get('system'):
            print(f"    System:        {', '.join(alarms['system'])}")
        if alarms.get('dc_port'):
            print(f"    DC Port:       {', '.join(alarms['dc_port'])}")
        if alarms.get('blocking'):
            print(f"    BLOCKING:      {', '.join(alarms['blocking'])}")
    
    if state['warnings']:
        print(f"\n  ⚠️  WARNINGS:")
        for warning in state['warnings']:
            print(f"      • {warning}")
    
    if state['conflicts']:
        print(f"\n  🚨 CONFLICTS:")
        for conflict in state['conflicts']:
            print(f"      • {conflict}")
    
    if requested_mode:
        print(f"\n  Requested Mode: {requested_mode}")
        if state['can_proceed']:
            print(f"  Status:         ✓ Can proceed")
        else:
            print(f"  Status:         ✗ CONFLICTS DETECTED - use --reset-on-start to override")
    
    print("=" * 70)


def print_system_status(ctrl):
    """Print comprehensive system status with clear operational state."""

    # SunSpec enum lookups
    OPERATING_STATE = {0: 'Off', 1: 'Operating', 2: 'Standby', 3: 'Fault',
                       4: 'Shutting Down', 5: 'Starting', 6: 'Maintenance'}
    INVERTER_STATE = {0: 'Off', 1: 'Sleeping', 2: 'Starting', 3: 'Running',
                      4: 'Throttled', 5: 'Shutting Down', 6: 'Fault',
                      7: 'Standby', 8: 'Test', 9: 'Manufacturing'}
    CONN_STATE = {0: 'Disconnected', 1: 'Connected'}
    DER_SOURCE = {0: 'PV', 1: 'Battery', 2: 'Hybrid', 3: 'Charger',
                  4: 'STATCOM', 5: 'Load', 6: 'Generator'}
    LOC_REM = {0: 'Remote', 1: 'Local'}

    print("\n" + "=" * 60)
    print("  FranklinWH aGate System Status")
    print("=" * 60)

    # --- Read all models ---
    m701 = ctrl.get_model(701)
    m703 = ctrl.get_model(703)
    m704 = ctrl.get_model(704)
    m713 = ctrl.get_model(713)
    m714 = ctrl.get_model(714)
    m715 = ctrl.get_model(715)

    if m701: m701.read()
    if m703: m703.read()
    if m704: m704.read()
    if m713: m713.read()
    if m714: m714.read()
    if m715: m715.read()

    # --- FranklinWH Operating Mode (native registers) ---
    native = ctrl.read_native_mode()
    if native:
        print(f"\n  FranklinWH Operating Mode")
        print(f"  {'─' * 40}")
        print(f"  Mode:              {native['mode_name']}")
        print(f"  Self Reserve:      {native['self_reserve_pct']}%")
        print(f"  TOU Reserve:       {native['tou_reserve_pct']}%")

    # --- Inverter & Grid ---
    if m701:
        sf_w = ctrl._get_scale_factor(m701, 'W_SF')
        sf_v = ctrl._get_scale_factor(m701, 'V_SF')
        sf_hz = ctrl._get_scale_factor(m701, 'Hz_SF')
        sf_tmp = ctrl._get_scale_factor(m701, 'Tmp_SF')

        st = m701.St.value if m701.St.value is not None else -1
        inv_st = m701.InvSt.value if m701.InvSt.value is not None else -1
        conn_st = m701.ConnSt.value if m701.ConnSt.value is not None else -1
        der_mode_raw = m701.DERMode.value if m701.DERMode.value is not None else 0
        ac_power_w = m701.W.value * (10 ** sf_w) if m701.W.value is not None else 0
        voltage = m701.LNV.value * (10 ** sf_v) if m701.LNV.value is not None else 0
        freq = m701.Hz.value * (10 ** sf_hz) if m701.Hz.value is not None else 0
        alrm = m701.Alrm.value if m701.Alrm.value is not None else 0
        tmp_cab = m701.TmpCab.value * (10 ** sf_tmp) if m701.TmpCab.value is not None else None
        tmp_amb = m701.TmpAmb.value * (10 ** sf_tmp) if m701.TmpAmb.value is not None else None

        # Decode DERMode bitfield (NOT a simple enum!)
        # Lower bits (0-6): Source type flags
        # Upper bits (16+): Grid mode flags (FranklinWH may not populate these)
        der_sources = [name for bit, name in DER_SOURCE.items() if der_mode_raw & (1 << bit)]

        # FranklinWH product line architecture:
        #   aGate X (AU/US): AC-coupled — PV via AC solar inputs (2x 63A circuits)
        #   aPower S (US):   Hybrid — PV via 4x MPPT DC + AC inputs
        #   aPower 2:        DC-coupled — PV via MPPT DC inputs
        # 
        # Firmware DERMode register only reports bit 0 (PV), missing bit 1 (Battery).
        # We correct this to reflect actual hardware: AC-coupled battery + AC solar inputs
        if der_sources == ['PV']:
            # aGate X is AC-coupled: Battery (AC) + Solar (AC inputs)
            der_source_str = 'Battery+Solar (AC-Coupled)'
        elif der_sources:
            der_source_str = '+'.join(der_sources)
        else:
            der_source_str = 'Unknown'

        # Grid mode from upper bits (16-17) — FranklinWH firmware does not
        # populate these bits, so we interpret absence as grid-following
        # (the default operating mode for residential battery inverters)
        if der_mode_raw & (1 << 17):
            grid_mode_str = 'Grid Forming'
        elif der_mode_raw & (1 << 16):
            grid_mode_str = 'Grid Following'
        else:
            grid_mode_str = 'Grid Following (default)'

        print(f"\n  Inverter & Grid")
        print(f"  {'─' * 40}")
        print(f"  Operating State:   {OPERATING_STATE.get(st, f'Unknown({st})')}")
        print(f"  Inverter State:    {INVERTER_STATE.get(inv_st, f'Unknown({inv_st})')}")
        print(f"  Grid Connection:   {CONN_STATE.get(conn_st, f'Unknown({conn_st})')}")
        print(f"  DER Type:          {der_source_str}")
        print(f"  DER Grid Mode:     {grid_mode_str}")
        print(f"  DERMode Raw:       0x{der_mode_raw:08X} ({der_mode_raw})")

        print(f"  Grid Voltage:      {voltage:.1f} V")
        print(f"  Grid Frequency:    {freq:.2f} Hz")
        if tmp_cab:
            print(f"  Cabinet Temp:      {tmp_cab:.1f} °C")
        if tmp_amb:
            print(f"  Ambient Temp:      {tmp_amb:.1f} °C")
        # --- Alarms Section ---
        print(f"\n  Alarms & Events")
        print(f"  {'─' * 40}")
        
        # Read comprehensive alarm status
        alarms = ctrl.read_alarms()
        decoded = alarms.get('decoded', {})
        
        # System alarms (Model 701)
        sys_alarms = decoded.get('system', [])
        if sys_alarms:
            print(f"  ⚠ System Alarms:   0x{alarms['system_alrm']:08X}")
            for alarm in sys_alarms:
                print(f"                     → {alarm}")
        else:
            print(f"  ✓ System Alarms:   None")
        
        # DC Port alarms (Model 714)
        dc_alarms = decoded.get('dc_port', [])
        if dc_alarms:
            print(f"  ⚠ DC Port Alarms:  0x{alarms['dc_port_alrm']:08X}")
            for alarm in dc_alarms:
                print(f"                     → {alarm}")
        else:
            print(f"  ✓ DC Port Alarms:  None")
        
        # Battery status
        bat_status = decoded.get('battery_status', 'UNKNOWN')
        if alarms['battery_sta'] == 6:  # FAULT
            print(f"  🚨 Battery Status:  {bat_status} (FAULT)")
        else:
            print(f"  ✓ Battery Status:  {bat_status}")
        
        # Vendor alarm info if available
        if alarms.get('vendor_info'):
            print(f"  Vendor Info:       {alarms['vendor_info']}")

    # --- Battery ---
    if m713:
        sf_pct = ctrl._get_scale_factor(m713, 'Pct_SF')
        sf_wh = ctrl._get_scale_factor(m713, 'WH_SF')
        soc = m713.SoC.value * (10 ** sf_pct) if m713.SoC.value is not None else 0
        soh = m713.SoH.value * (10 ** sf_pct) if m713.SoH.value is not None else 0
        wh_rtg = m713.WHRtg.value * (10 ** sf_wh) if m713.WHRtg.value is not None else 0
        wh_avail = m713.WHAvail.value * (10 ** sf_wh) if m713.WHAvail.value is not None else 0

        # Derive actual state from DC power (M713.Sta always reports IDLE)
        dc_w = 0
        if m714 and m714.DCW.value is not None:
            sf_dcw = ctrl._get_scale_factor(m714, 'DCW_SF')
            dc_w = m714.DCW.value * (10 ** sf_dcw)

        if dc_w < -50:
            bat_state = f"⚡ Charging ({abs(dc_w):.0f}W)"
            bat_icon = "↓"
        elif dc_w > 50:
            bat_state = f"🔋 Discharging ({dc_w:.0f}W)"
            bat_icon = "↑"
        else:
            bat_state = "💤 Idle"
            bat_icon = "─"

        # SOC bar
        bar_len = 20
        filled = int(soc / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"\n  Battery")
        print(f"  {'─' * 40}")
        print(f"  State:             {bat_state}")
        print(f"  SoC:               {soc:.1f}%  [{bar}]")
        print(f"  SoH:               {soh:.1f}%")
        print(f"  Energy Available:  {wh_avail/1000:.1f} / {wh_rtg/1000:.1f} kWh")
        print(f"  DC Power:          {dc_w:.0f} W  {bat_icon}")
        print(f"  Note:              M713.Sta always reports IDLE (firmware bug)")

    # --- Power Flow ---
    if m701 and m714:
        grid_w = m701.W.value * (10 ** sf_w) if m701.W.value is not None else 0

        print(f"\n  Power Flow")
        print(f"  {'─' * 40}")
        print(f"  AC Power (total):  {ac_power_w:.0f} W")
        if grid_w > 50:
            print(f"  Grid:              ↓ Importing {grid_w:.0f} W")
        elif grid_w < -50:
            print(f"  Grid:              ↑ Exporting {abs(grid_w):.0f} W")
        else:
            print(f"  Grid:              ─ Balanced ({grid_w:.0f} W)")
        print(f"  Battery (DC):      {dc_w:.0f} W {'(charging)' if dc_w < 0 else '(discharging)' if dc_w > 0 else '(idle)'}")

    # --- Control State ---
    if m704:
        wset_ena = m704.WSetEna.value if m704.WSetEna.value is not None else 0
        wset_pct = m704.WSetPct.value if m704.WSetPct.value is not None else 0
        sf_pct704 = ctrl._get_scale_factor(m704, 'WSetPct_SF')
        pct_real = wset_pct * (10 ** sf_pct704) if wset_pct else 0

        print(f"\n  Modbus Control (M704)")
        print(f"  {'─' * 40}")
        if wset_ena == 0:
            print(f"  Status:            ✅ Released (aGate in self-control)")
        elif wset_pct == 0:
            print(f"  Status:            ⚠️  Active at 0% (VPP Standby!)")
        else:
            direction = "Discharge" if pct_real > 0 else "Charge"
            pct_w = abs(pct_real / 100 * ctrl.RATED_MAX_W)
            print(f"  Status:            🔌 Active: {direction} {abs(pct_real):.1f}% ({pct_w:.0f}W)")
        print(f"  WSetEna:           {wset_ena}")
        print(f"  WSetPct:           {pct_real:.1f}% (raw={wset_pct})")

    # --- DER Control (M715) ---
    if m715:
        loc_rem = m715.LocRemCtl.value if m715.LocRemCtl.value is not None else -1
        print(f"\n  DER Control (M715)")
        print(f"  {'─' * 40}")
        print(f"  Control Mode:      {LOC_REM.get(loc_rem, f'Unknown({loc_rem})')}")
        if loc_rem == 1:
            print(f"  Note:              Local mode — advanced registers locked")

    # --- Enter Service (M703) ---
    if m703:
        ES_STATUS = {0: 'Disabled', 1: 'Enabled'}
        sf_v703 = ctrl._get_scale_factor(m703, 'V_SF')
        sf_hz703 = ctrl._get_scale_factor(m703, 'Hz_SF')
        es_permit = m703.ES.value if m703.ES.value is not None else -1
        v_hi = m703.ESVHi.value * (10 ** sf_v703) if m703.ESVHi.value is not None else None
        v_lo = m703.ESVLo.value * (10 ** sf_v703) if m703.ESVLo.value is not None else None
        hz_hi = m703.ESHzHi.value * (10 ** sf_hz703) if m703.ESHzHi.value is not None else None
        hz_lo = m703.ESHzLo.value * (10 ** sf_hz703) if m703.ESHzLo.value is not None else None
        dly_tms = m703.ESDlyTms.value if hasattr(m703, 'ESDlyTms') and m703.ESDlyTms.value is not None else None
        rmp_tms = m703.ESRmpTms.value if hasattr(m703, 'ESRmpTms') and m703.ESRmpTms.value is not None else None

        print(f"\n  Enter Service (M703)")
        print(f"  {'─' * 40}")
        print(f"  Permit:            {ES_STATUS.get(es_permit, f'Unknown({es_permit})')}")
        if v_lo is not None and v_hi is not None:
            print(f"  Voltage Range:     {v_lo:.1f} – {v_hi:.1f} %Vnom")
        if hz_lo is not None and hz_hi is not None:
            print(f"  Frequency Range:   {hz_lo:.2f} – {hz_hi:.2f} Hz")
        if dly_tms is not None:
            print(f"  Connect Delay:     {dly_tms} s")
        if rmp_tms is not None:
            print(f"  Ramp Time:         {rmp_tms} s")

    # --- Device Ratings ---
    print(f"\n  Device Ratings (M702)")
    print(f"  {'─' * 40}")
    print(f"  Max Power:         {ctrl.RATED_MAX_W} W")
    print(f"  Max Charge:        {ctrl.RATED_MAX_CHARGE_W} W")
    print(f"  Max Discharge:     {ctrl.RATED_MAX_DISCHARGE_W} W")

    print("\n" + "=" * 60)


def validate_mode_params(args) -> Tuple[bool, List[str]]:
    """
    Validate that CLI parameters are compatible with selected mode.
    
    Returns (is_valid, warning_messages).
    """
    warnings = []
    
    # Parameter to mode mapping: which modes have specialized use for these parameters
    # target_soc is now universal - works with all modes
    PARAM_MODE_MAP = {
        'reserve': ['self_consumption'],
        'threshold': ['peak_shave'],
        'power': ['manual'],
        'schedule_file': ['time_of_use'],
    }
    
    # Check each parameter
    mode = args.mode
    
    # target_soc now works with ALL modes - no warning needed
    # It sets a universal target SoC that modes will respect
    
    # reserve only valid for self_consumption
    if args.reserve != 20:  # Non-default value provided
        if mode not in PARAM_MODE_MAP['reserve']:
            warnings.append(
                f"--reserve={args.reserve} is only used by 'self_consumption' mode, "
                f"not '{mode}'. This parameter will be ignored."
            )
    
    # threshold only valid for peak_shave
    if args.threshold != 2000:  # Non-default value provided
        if mode not in PARAM_MODE_MAP['threshold']:
            warnings.append(
                f"--threshold={args.threshold} is only used by 'peak_shave' mode, "
                f"not '{mode}'. This parameter will be ignored."
            )
    
    # power (or --charge/--discharge) only valid for manual
    power_provided = args.power is not None or getattr(args, 'charge', None) is not None or getattr(args, 'discharge', None) is not None
    if power_provided:
        if mode not in PARAM_MODE_MAP['power']:
            power_val = args.power if args.power is not None else (args.charge if args.charge is not None else -args.discharge)
            warnings.append(
                f"Power control ({power_val}W) is only used by 'manual' mode, "
                f"not '{mode}'. This parameter will be ignored."
            )
    
    # schedule_file only valid for time_of_use
    if args.schedule_file:
        if mode not in PARAM_MODE_MAP['schedule_file']:
            warnings.append(
                f"--schedule-file is only used by 'time_of_use' mode, "
                f"not '{mode}'. This parameter will be ignored."
            )
    
    return len(warnings) == 0, warnings


def main():
    """Main entry point."""
    # Deprecation warning
    print("\n" + "="*70, file=sys.stderr)
    print("⚠️  DEPRECATION WARNING", file=sys.stderr)
    print("="*70, file=sys.stderr)
    print("This script (franklinwh_control_standalone.py) is deprecated.", file=sys.stderr)
    print("\nPlease migrate to the new CLI:", file=sys.stderr)
    print("  python franklinwh_cli.py -i <ip> --charge 3000", file=sys.stderr)
    print("\nOr use the library directly:", file=sys.stderr)
    print("  from franklinwh_modbus_library import FranklinWHController", file=sys.stderr)
    print("="*70 + "\n", file=sys.stderr)
    
    parser = create_parser()
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Normalize explicit action flags to power value
    # Priority: --charge, --discharge, --standby, --idle, then --power
    if args.charge is not None:
        args.power = abs(args.charge)  # Positive = charge
        logger.debug(f"--charge {args.charge}W → power={args.power}W (charge)")
    elif args.discharge is not None:
        args.power = -abs(args.discharge)  # Negative = discharge
        logger.debug(f"--discharge {args.discharge}W → power={args.power}W (discharge)")
    elif args.standby or args.idle:
        args.power = 0
        logger.debug("--standby/--idle → power=0W")
    # else: args.power remains as set (or None)
    
    # Validate parameter combinations when mode is specified
    if args.mode:
        is_valid, warnings = validate_mode_params(args)
        if warnings:
            print("\n⚠️  Parameter/Mode Mismatch Warnings:")
            for warning in warnings:
                print(f"   • {warning}")
            print(f"\n   For mode '{args.mode}', valid parameters are:")
            if args.mode == 'self_consumption':
                print("   --reserve (reserve percentage)")
            elif args.mode == 'emergency_backup':
                print("   --target-soc (target SoC percentage)")
            elif args.mode == 'peak_shave':
                print("   --threshold (watts threshold)")
            elif args.mode == 'manual':
                print("   --power (watts)")
            elif args.mode == 'time_of_use':
                print("   --schedule-file (JSON schedule file)")
            print("")
            # Don't exit - just warn the user
    
    # Handle schedule file display/validation (no hardware needed)
    if args.show_schedule:
        try:
            schedule = TOUSchedule.from_file(args.show_schedule)
            print(f"\nSchedule: {schedule.get_schedule_name()}")
            print("=" * 60)
            import json
            print(json.dumps(schedule.to_dict(), indent=2))
            print("=" * 60)
            print(f"Current period: {schedule.get_current_period()}")
            print(f"Current price: ${schedule.get_current_price():.2f}/kWh")
            print(f"Current strategy: {schedule.get_strategy()}")
            print(f"Rules: {schedule.get_rules()}")
            sys.exit(0)
        except Exception as e:
            print(f"Error loading schedule: {e}")
            sys.exit(1)
    
    if args.validate_schedule:
        try:
            schedule = TOUSchedule.from_file(args.validate_schedule)
            print(f"✓ Schedule '{schedule.get_schedule_name()}' is valid")
            print(f"  Periods: {len(schedule._schedule_data.get('periods', []))}")
            print(f"  Current period: {schedule.get_current_period()}")
            print(f"  Current strategy: {schedule.get_strategy()}")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Schedule validation failed: {e}")
            sys.exit(1)
    
    # Check required IP for hardware operations
    if not args.ip:
        print("Error: -i/--ip is required (except for --show-schedule and --validate-schedule)")
        sys.exit(1)
    
    # Create hardware controller
    ctrl = FranklinWHController(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit,
        timeout=args.timeout,
    )
    
    if not ctrl.connect():
        sys.exit(1)
    
    # Check current system state and detect conflicts
    startup_state = check_startup_state(ctrl, args.mode, args)
    
    # Print startup summary (unless in quiet mode)
    if not args.quiet:
        print_startup_summary(startup_state, args.mode, args)
    
    # If conflicts detected and no reset flag, exit
    if not startup_state['can_proceed'] and not args.reset_on_start:
        print("\n⚠️  Cannot proceed due to conflicts. Options:")
        print("    1. Use --reset-on-start to take control anyway")
        print("    2. Change aGate mode via FranklinWH app to match requested mode")
        print("    3. Wait for current operation to complete")
        sys.exit(1)
    
    # Check for off-grid condition
    grid_connected = startup_state['current_state'].get('grid_connected', False)
    connection_state = startup_state['current_state'].get('connection_state', 'Unknown')
    if not grid_connected and not args.off_grid_permitted:
        print(f"\n🚨 OFF-GRID DETECTED - Grid connection state: {connection_state}")
        print("   Operating without grid connection can be unsafe.")
        print("   Use --off-grid-permitted to explicitly allow off-grid operation.")
        sys.exit(1)
    elif not grid_connected and args.off_grid_permitted:
        print(f"\n⚠️  WARNING: Operating OFF-GRID (connection: {connection_state})")
        print("   --off-grid-permitted specified, continuing...")
    
    # Validate SoC limits before operation
    current_soc = startup_state['current_state'].get('soc', 0)
    requested_power = args.power or 0
    is_charge_request = requested_power < 0 or args.mode in ['self_consumption', 'emergency_backup', 'time_of_use']
    is_discharge_request = requested_power > 0 or args.mode == 'peak_shave'
    
    # Check 1: target_soc for charge modes
    if hasattr(args, 'target_soc') and args.target_soc:
        if is_charge_request and current_soc >= args.target_soc:
            print(f"\n🛑 SoC VALIDATION FAILED:")
            print(f"   Current SoC: {current_soc:.1f}%")
            print(f"   Target SoC:  {args.target_soc:.1f}%")
            print(f"   Cannot charge - already at or above target.")
            print(f"   Options:")
            print(f"      1. Lower --target-soc below {current_soc:.1f}%")
            print(f"      2. Wait for battery to discharge naturally")
            print(f"      3. Use --power with positive value to discharge first")
            sys.exit(1)
    
    # Check 2: max_charge_soc for charge modes
    if is_charge_request and current_soc >= args.max_charge_soc:
        print(f"\n🛑 SoC VALIDATION FAILED:")
        print(f"   Current SoC: {current_soc:.1f}%")
        print(f"   Max Charge SoC: {args.max_charge_soc}%")
        print(f"   Cannot charge - at maximum charge limit.")
        sys.exit(1)
    
    # Check 3: min_discharge_soc for discharge modes
    min_discharge = args.min_discharge_soc or startup_state['current_state'].get('reserve_soc', 20)
    if is_discharge_request and current_soc <= min_discharge:
        print(f"\n🛑 SoC VALIDATION FAILED:")
        print(f"   Current SoC: {current_soc:.1f}%")
        print(f"   Min Discharge SoC: {min_discharge}%")
        print(f"   Cannot discharge - at minimum discharge limit.")
        sys.exit(1)
    
    # Log startup information (INFO level - hidden in quiet mode)
    logger.info("FranklinWH Control Starting")
    logger.info(f"  Target: {args.ip}:{args.port} (unit {args.unit})")
    logger.info(f"  Mode: {args.mode or 'direct control'}")
    logger.info(f"  SoC Limits: min_discharge={args.min_discharge_soc or 'auto'}, "
                f"max_charge={args.max_charge_soc}, ramp_window={args.soc_ramp_window}%")
    
    # Log native mode
    if startup_state['current_state'].get('ongrid_mode'):
        logger.info(f"  aGate OnGridMode: {startup_state['current_state']['ongrid_mode']}")
    logger.info(f"  Battery SoC: {startup_state['current_state'].get('soc', 0):.1f}%")
    logger.info(f"  Battery Activity: {startup_state['current_state'].get('battery_activity', 'Unknown')}")
    
    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        raise SystemExit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Health check mode
        if args.check_alarms:
            print("\n" + "=" * 70)
            print("  ALARM STATUS CHECK")
            print("=" * 70)
            alarms = ctrl.read_alarms()
            decoded = alarms.get('decoded', {})
            
            print(f"\n  System Alarms (Model 701): 0x{alarms['system_alrm']:08X}")
            sys_alarms = decoded.get('system', [])
            if sys_alarms:
                for alarm in sys_alarms:
                    print(f"    ⚠ {alarm}")
            else:
                print(f"    ✓ None active")
            
            print(f"\n  DC Port Alarms (Model 714): 0x{alarms['dc_port_alrm']:08X}")
            dc_alarms = decoded.get('dc_port', [])
            if dc_alarms:
                for alarm in dc_alarms:
                    print(f"    ⚠ {alarm}")
            else:
                print(f"    ✓ None active")
            
            print(f"\n  Battery Status: {decoded.get('battery_status', 'UNKNOWN')}")
            
            can_operate, blocking = ctrl.check_blocking_alarms()
            if blocking:
                print(f"\n  🚨 BLOCKING: {', '.join(blocking)}")
            else:
                print(f"\n  ✓ No blocking alarms")
            
            print("=" * 70)
            sys.exit(0 if can_operate else 1)
        
        if args.clear_alarms:
            print("\n" + "=" * 70)
            print("  CLEARING ALARMS")
            print("=" * 70)
            success, msg = ctrl.clear_alarms()
            if success:
                print(f"  ✓ {msg}")
            else:
                print(f"  ✗ {msg}")
            print("=" * 70)
            sys.exit(0 if success else 1)
        
        if args.test_extension_write:
            print("\n" + "=" * 70)
            print("  TESTING EXTENSION REGISTER WRITABILITY")
            print("=" * 70)
            
            # Force re-test by resetting results and running again
            ctrl._extension_write_results = {
                'tested': False,
                'timestamp': None,
                'ongrid_mode': {'writable': False, 'error': None},
                'self_reserve': {'writable': False, 'error': None},
                'tou_reserve': {'writable': False, 'error': None},
            }
            results = ctrl._test_extension_writability()
            
            print(f"\n  Results:")
            for reg_name in ['ongrid_mode', 'self_reserve', 'tou_reserve']:
                reg_result = results.get(reg_name, {})
                addr = {'ongrid_mode': 15507, 'self_reserve': 15508, 'tou_reserve': 15509}[reg_name]
                if reg_result.get('writable'):
                    print(f"    ✓ {reg_name.replace('_', ' ').title():12} ({addr}): WRITABLE")
                else:
                    err = reg_result.get('error', 'unknown')
                    print(f"    ✗ {reg_name.replace('_', ' ').title():12} ({addr}): READ-ONLY ({err})")
            
            writable_count = sum(1 for k in ['ongrid_mode', 'self_reserve', 'tou_reserve']
                                if results.get(k, {}).get('writable'))
            
            print(f"\n  Summary: {writable_count}/3 registers writable")
            if writable_count == 0:
                print("  Note: Write access requires 'SPAN Modbus' unlock in installer settings")
            elif writable_count < 3:
                print("  Note: Partial write access - some features may be limited")
            else:
                print("  Full write access - all extension features available")
            
            print("=" * 70)
            sys.exit(0)
        
        if args.healthcheck:
            health = ctrl.healthcheck()
            print_health_report(health)
            sys.exit(0 if health.healthy else 1)
        
        # Always run health check unless suppressed
        if not args.assume_clean_state:
            health = ctrl.healthcheck()
            if not health.healthy:
                print_health_report(health)
                if health.details.get('zombie_state'):
                    print("\n⚠ ZOMBIE STATE DETECTED!")
                    print("   Use --reset-on-start to clear, or --assume-clean-state to ignore")
                    if not args.reset_on_start:
                        sys.exit(1)
        
        # Reset if requested or required
        if args.reset_on_start:
            if not ctrl.reset_control_state():
                logger.error("Failed to reset control state")
                sys.exit(1)
        
        # Quick stop mode — release control and exit
        if args.stop:
            print("Releasing Modbus control (WSetEna=0)...")
            if ctrl.reset_control_state():
                print("✓ Control released — aGate will resume configured mode")
                sys.exit(0)
            else:
                print("✗ Failed to release control")
                sys.exit(1)
        
        # Status-only mode
        if args.status:
            print_system_status(ctrl)
            return
        
        # Virtual mode operation
        if args.mode:
            # Safety: require reset-on-start for virtual modes
            if not args.reset_on_start and not args.assume_clean_state:
                health = ctrl.healthcheck()
                if health.details.get('wset_ena') == 1:
                    print("\n⚠ Control already active. Use --reset-on-start for clean state.")
                    sys.exit(1)
            
            # Create virtual mode controller with SoC limits
            vmc = VirtualModeController(
                ctrl,
                max_charge_soc=args.max_charge_soc,
                min_discharge_soc=args.min_discharge_soc,
                soc_ramp_window=args.soc_ramp_window,
                force_soc_limits=args.force
            )
            
            # Load schedule file if provided (for time_of_use mode)
            if args.schedule_file:
                try:
                    schedule = TOUSchedule.from_file(args.schedule_file)
                    vmc.tou = schedule
                    print(f"Loaded TOU schedule: {schedule}")
                except Exception as e:
                    print(f"Error loading schedule file: {e}")
                    sys.exit(1)
            
            # Map CLI args to mode parameters
            # target_soc is universal - applies to all modes
            mode_kwargs = {'target_soc': args.target_soc}
            
            if args.mode == 'self_consumption':
                mode_kwargs['self_reserve_pct'] = args.reserve
            elif args.mode == 'emergency_backup':
                mode_kwargs['backup_target_soc'] = args.target_soc  # Legacy support
            elif args.mode == 'peak_shave':
                mode_kwargs['peak_shave_threshold'] = args.threshold
            elif args.mode == 'manual':
                mode_kwargs['manual_power_w'] = args.power or 0
            elif args.mode == 'time_of_use':
                # Schedule file is optional - will use default if not provided
                if vmc.tou.is_file_based():
                    mode_kwargs['tou_schedule'] = vmc.tou
            
            # Set mode and run
            vmc.set_mode(VirtualMode(args.mode), **mode_kwargs)
            
            if args.duration:
                vmc.run_continuous(duration_seconds=args.duration)
            else:
                vmc.run_continuous()
            
            return
        
        # Direct control (original functionality with new explicit flags)
        if args.power is not None or args.idle or args.standby:
            power = 0.0 if (args.idle or args.standby) else args.power
            cmd = BatteryCommand(power_watts=power, mode=ControlMode.LIMIT_ABS)
            
            success, msg = ctrl.send_command(cmd, args.revert, args.dry_run)
            print(f"\nResult: {'SUCCESS' if success else 'FAILED'} - {msg}")
            # If revert timer set, stay connected and wait
            if args.revert > 0 and success:
                print(f"Waiting {args.revert} seconds for revert timer...")
                try:
                    time.sleep(args.revert)
                except KeyboardInterrupt:
                    print("\nInterrupted, setting idle...")
                # After wait, idle will be sent by finally block

        sys.exit(0 if success else 1)
        
        # No action specified
        parser.print_help()
        
    except SystemExit:
        # Graceful shutdown handled
        pass
    except Exception as e:
        logger.error(f"Runtime error: {e}")
        raise
    finally:
        # Ensure control is released before disconnect
        try:
            ctrl.reset_control_state()
            logger.info("Control released (WSetEna=0)")
        except Exception as e:
            logger.warning(f"Could not release control: {e}")
        ctrl.disconnect()


if __name__ == '__main__':
    main()