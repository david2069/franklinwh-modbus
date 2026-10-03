"""
FranklinWH Modbus Battery Manager

A Python library for controlling FranklinWH aGate battery systems via Modbus TCP.

Example usage:
    from franklinwh_modbus import FranklinWHController, VirtualModeController, VirtualMode
    
    # Connect to aGate
    ctrl = FranklinWHController('192.168.1.100')
    ctrl.connect()
    
    # Use virtual modes
    vmc = VirtualModeController(ctrl)
    vmc.set_mode(VirtualMode.SELF_CONSUMPTION)
    vmc.run_continuous(duration_seconds=3600)
"""

__version__ = '0.9.4'

from .types import (
    ControlMode,
    VirtualMode,
    BatteryCommand,
    HealthStatus,
    ONGRID_MODES,
    ALARM_BITS,
    PICS_STATUS,
    DEFAULT_MAX_POWER_W,
)

from .schedule import TOUSchedule, DEFAULT_SCHEDULE

from .controller import FranklinWHController

from .modes import VirtualModeController, run_with_signal_handling

# Optional monitor import (requires rich dependency)
try:
    from .monitor import CLIMonitor, MonitorConfig
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    CLIMonitor = None
    MonitorConfig = None

__all__ = [
    # Types
    'ControlMode',
    'VirtualMode',
    'BatteryCommand',
    'HealthStatus',
    'ONGRID_MODES',
    'ALARM_BITS',
    'PICS_STATUS',
    'DEFAULT_MAX_POWER_W',
    # Schedule
    'TOUSchedule',
    'DEFAULT_SCHEDULE',
    # Controller
    'FranklinWHController',
    # Modes
    'VirtualModeController',
    'run_with_signal_handling',
    # Monitor (optional)
    'CLIMonitor',
    'MonitorConfig',
    'HAS_MONITOR',
]
