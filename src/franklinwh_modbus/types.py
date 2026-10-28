"""
FranklinWH Modbus Battery Manager - Core Types and Enums

This module contains all shared types, enums, and data classes used by
the FranklinWH Modbus library.
"""

from enum import Enum, IntEnum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ControlMode(IntEnum):
    """Model 704 WSetMod values (SunSpec 2 model_704.json).

    WATTS sends BatteryCommand.power_watts through WSet; W_MAX_PCT sends
    BatteryCommand.power_pct through WSetPct. Neither is converted to the
    other (#114 B1).
    """
    W_MAX_PCT = 0       # WSetPct: percent of WMax
    WATTS = 1           # WSet: watts


class VirtualMode(Enum):
    """Virtual/software control modes."""
    SELF_CONSUMPTION = "self_consumption"
    EMERGENCY_BACKUP = "emergency_backup"
    TIME_OF_USE = "time_of_use"
    GRID_ZERO = "grid_zero"
    PEAK_SHAVE = "peak_shave"
    MANUAL = "manual"


# Default max power rating (overridden by M702 discovery)
DEFAULT_MAX_POWER_W = 10000


@dataclass
class BatteryCommand:
    """Battery control command.
    
    Attributes:
        power_watts: Target power in watts (mode WATTS)
                     Positive = charge, negative = discharge, 0 = idle
        mode: WSetMod for the command: WATTS (default) or W_MAX_PCT
        power_pct: Target power in percent of WMax (mode W_MAX_PCT),
                   -100 to 100, same sign convention as power_watts
    
    Note:
        power_watts is clamped to [-DEFAULT_MAX_POWER_W, DEFAULT_MAX_POWER_W]
        at construction time. The controller applies a second clamp using
        actual device ratings from M702. The device itself performs NO
        input validation (PICS Issue 5).
    """
    power_watts: float = 0.0
    mode: ControlMode = ControlMode.WATTS
    power_pct: Optional[float] = None
    
    def __post_init__(self):
        """Validate and clamp power_watts to safe range."""
        if self.mode == ControlMode.W_MAX_PCT:
            if self.power_pct is None:
                raise ValueError("mode W_MAX_PCT needs power_pct")
            if not -100 <= self.power_pct <= 100:
                raise ValueError(f"power_pct {self.power_pct} is outside -100..100")
        elif self.power_pct is not None:
            raise ValueError("power_pct is only used with mode W_MAX_PCT")
        limit = DEFAULT_MAX_POWER_W
        if abs(self.power_watts) > limit:
            original = self.power_watts
            self.power_watts = max(-limit, min(limit, self.power_watts))
            logger.warning(
                f"BatteryCommand: {original}W exceeds ±{limit}W limit "
                f"— clamped to {self.power_watts}W. "
                f"Device has NO input validation (PICS Issue 5). "
                f"[approved workaround #114 B3: power clamp]"
            )


@dataclass
class HealthStatus:
    """System health check result.
    
    Attributes:
        healthy: True if system is in a good state
        message: Summary message describing health state
        recommendations: Suggested actions
        details: Additional diagnostic information
        zombie_state: True if system is in an unrecoverable state
    """
    healthy: bool
    message: str
    recommendations: list
    details: Optional[dict] = None
    zombie_state: bool = False


# Scale factor helpers
SUNSPEC_SCALES = {
    'W': 0,      # Watts
    'V': 0,      # Volts  
    'A': -3,     # Amps (often scaled)
    'Hz': -2,    # Hertz
    'C': 0,      # Celsius
    'Wh': 0,     # Watt-hours
    'kWh': 0,    # Kilowatt-hours
}


# Model IDs for reference
MODEL_IDS = {
    1: 'Common',
    502: 'METROLOGY',
    701: 'DERInfo',
    702: 'DERCapacity',
    703: 'DERRtg',
    704: 'DERCtrl',
    705: 'DERCtrl2',
    706: 'DERStatus',
    707: 'DERStatus2',
    708: 'DERStorageCapacity',
    709: 'DERStorageStatus',
    710: 'DERStorageCtrl',
    711: 'DERPricing',
    712: 'DERPricing2',
    713: 'DERPricing3',
    714: 'DERStorageStatus2',
    715: 'DERCtrl3',
}


# Grid connection states
GRID_CONNECTION_STATES = {
    0: 'Disconnected',
    1: 'Connected',
    2: 'Fault',
}


# Storage operation states
STORAGE_OPERATION_STATES = {
    1: 'Off',
    2: 'Standby',
    3: 'Starting',
    4: 'Charge',
    5: 'Discharge',
    6: 'Fault',
}


# Control modes from M704
WSET_MODES = {
    0: 'WSet',
    1: 'VarSet',
    2: 'VarSetPct',
    3: 'VArSet',
    4: 'VArSetPct',
    5: 'MinMaxVarSet',
    6: 'MinMaxVarSetPct',
}


# Local/Remote control states
LOC_REM_CTL = {
    0: 'Remote',
    1: 'Local',
}


# DER control modes
DER_CTRL_MODES = {
    0: 'None',
    1: 'WSet',
    2: 'VarSet',
    3: 'VArSet',
    4: 'MinMaxVarSet',
}


# OnGridMode values from FranklinWH extension registers (1-indexed)
ONGRID_MODES = {
    1: 'Emergency Backup',
    2: 'Self-Consumption',
    3: 'TOU',
}


# M701 Alarm bitmask definitions (DERInfo.Alrm)
# Per SunSpec Model 701, each bit indicates an active alarm condition
ALARM_BITS = {
    0: 'GROUND_FAULT',
    1: 'DC_OVER_VOLT',
    2: 'AC_DISCONNECT',
    3: 'DC_DISCONNECT',
    4: 'GRID_DISCONNECT',
    5: 'CABINET_OPEN',
    6: 'MANUAL_SHUTDOWN',
    7: 'OVER_TEMP',
    8: 'OVER_FREQUENCY',
    9: 'UNDER_FREQUENCY',
    10: 'AC_OVER_VOLT',
    11: 'AC_UNDER_VOLT',
    12: 'BLOWN_STRING_FUSE',
    13: 'UNDER_TEMP',
    14: 'MEMORY_LOSS',
    15: 'HW_TEST_FAILURE',
}


# PICS conformance status — what actually works on FranklinWH aGate X
# Firmware: V10R01B04D00, tested 2026-03-13
PICS_STATUS = {
    # FUNCTIONAL — works as declared
    'WSetEna': 'functional',       # M704.318 — VPP enable
    'WSetMod': 'functional',       # M704.319 — mode select
    'WSet': 'functional',          # M704.320 — power setpoint (W)
    'WSetPct': 'functional',       # M704.324 — power setpoint (%)
    'PFWInjEna': 'cosmetic',       # M704.298 — writable but gates nothing (Issue 6)
    
    # COSMETIC — register mechanics work but no physical effect
    'WSetRvrt': 'cosmetic',        # M704.322 — reversion target sticky (Issue 4)
    'WSetEnaRvrt': 'cosmetic',     # M704.326 — writable but reversion never fires
    'WSetRvrtTms': 'cosmetic',     # M704.327 — countdown works, no reversion (SAFETY)
    'WSetRvrtRem': 'cosmetic',     # M704.329 — countdown readback, cosmetic
    
    # BLOCKED — silently discards writes (0/160 tests)
    'WMaxLimPctEna': 'blocked',    # M704.310 — Issue 1
    'VarSetEna': 'blocked',        # M704.331 — Issue 1
    'ControllerHb': 'blocked',     # M715.1092 — Issue 1
    'WMax': 'blocked',             # M702.251 — Issue 2
}
