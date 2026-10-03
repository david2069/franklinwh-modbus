"""
FranklinWH Constants File
Contains hardware constants (device models, registers, dispatch codes).

For operating mode enums, see types.py (VirtualMode, ControlMode, ONGRID_MODES).
"""
from enum import Enum

# Legal notice. Logged once per process by FranklinWHController, and reproduced
# in readme.md and docs/index.md. Mirrors the notice in franklinwh-cloud.
DISCLAIMER = (
    "franklinwh-modbus | UNOFFICIAL · NOT ENDORSED, SUPPORTED OR AFFILIATED WITH FRANKLINWH "
    "| NO WARRANTY · PROVIDED AS-IS · USE AT YOUR OWN RISK "
    "| This software WRITES to energy hardware and can dispatch a battery. "
    "You assume all risk associated with its use. "
    "| It may break without notice due to firmware changes by FranklinWH. "
    "| Do NOT contact FranklinWH support about defects, issues or feature "
    "requests for this software — raise them at "
    "https://github.com/david2069/franklinwh-modbus/issues "
    "| MIT License — see LICENSE for details."
)

# Run mode of Gateway
RUN_STATUS = {
    0: "Standby",               # Inactive or Idle
    1: "Charging",
    2: "Discharging",
    3: "Unknown 3",             # To be added
    4: "Unknown 4",             # To be added
    5: "Off-Grid Standby",
    6: "Off-Grid Charging",
    7: "Off-Grid Discharging",
    8: "Debug Mode",           # Franklin Remote Support
    9: "VPP mode"              # Virtual Power Plant mode controlled
}


# Network connectivity options
NETWORK_TYPES = {
    1: "Ethernet 1",
    2: "Ethernet 2",
    3: "WiFi",
    4: "4G Mobile"
}

# aGate Health Status
AGATE_STATE = {
    0: "Normal",
    1: "Fault"
} 
# aGate Activity Status
AGATE_ACTIVE = {
    0: "Inactive",
    1: "Active"
}

COUNTRY_ID = {
    1: "China",
    2: "United States",
    3: "Australia"
}

# FranklinWH Device Models
# System ID, Model Designation, SKU and Model Type
FRANKLINWH_MODELS = {
    0: {"name": "aPower X", "sku": "APR-05K1V1-US", "model": "aPower X-10", "type": "Battery"},
    1: {"name": "aPower X", "sku": "APR-05K11V1-US", "model": "aPower X-10", "type": "Battery"},
    2: {"name": "aPower X", "sku": "APR-05K13V1-AU", "model": "aPower X-01-AU", "type": "Battery"},
    3: {"name": "aPower 2", "sku": "APR-10K15V2-US", "model": "aPower X-20", "type": "Battery"},
    4: {"name": "aPower S", "sku": "APRS-10K15V1-US", "model": "aPower S-10", "type": "Battery"},
    5: {"name": "aPower S", "sku": "APRS-11K15V2-US", "model": "aPower S-10", "type": "Battery"},
    6: {"name": "aPower X", "sku": "APR-05K15V1-US", "model": "aPower X-10", "type": "Battery"},
    100: {"name": "aGate X", "sku": "AGT-R1V1-US", "model": "aGate X-10", "type": "Gateway", "coupling": "AC"},
    101: {"name": "aGate X", "sku": "AGT-R1V2-US", "model": "aGate X-20", "type": "Gateway", "coupling": "AC"},
    102: {"name": "aGate X", "sku": "AGT-R1V1-AU", "model": "aGate X-01-AU", "type": "Gateway", "coupling": "AC"},
    103: {"name": "aGate X", "sku": "AGT-R1V3-US", "model": "aGate X 20 (US)", "type": "Gateway", "coupling": "AC"},
    104: {"name": "aGate X", "sku": "AGT-R1V3-US", "model": "aGate X 20 (US)", "type": "Gateway", "coupling": "AC"}
}

# Architecture Types
COUPLING_TYPES = {
    "AC": "AC-Coupled (Solar via AC inputs)",
    "DC": "DC-Coupled (Solar via MPPT DC inputs)",
    "HYBRID": "Hybrid (Both AC and DC solar inputs)"
}

# aGate X Architecture Note:
# - AC-coupled battery system
# - Solar connects via AC inputs (2x 63A circuits on aGate X)
# - Can also have remote solar via aPbox or aHub accessories
# - Battery is AC-coupled (inverter built into aGate)

# aPower S Architecture Note:
# - DC-coupled with 4x MPPT inputs for solar
# - Also has AC solar inputs (hybrid)

# Accessories
FRANKLINWH_ACCESSORIES = {
    301: {"name": "Generator Module", "sku": "ACCY-GENV1-AU", "model": "Generator Module-01-AU", "compatiable": "102"},
    302: {"name": "Smart Circuits", "sku": "ACCY-SCV1-AU", "model": "Smart Circuits-01-AU", "compatiable": "102"},
    201: {"name": "Generator Module", "sku": "ACCY-GENV1-US", "model": "Generator Module-01", "compatiable": "100|101"},
    202: {"name": "Smart Circuits", "sku": "ACCY-SCV1-US", "model": "Smart Circuits-01", "compatiable": "100|101"},
    203: {"name": "Generator Module", "sku": "ACCY-GENV2-US", "model": "Generator Module-02", "compatiable": "103|104"},
    204: {"name": "Smart Circuits", "sku": " ACCY-SCV2-US", "model": "Smart Circuits-02", "compatiable": "102|103|104"},
    251: {"name": "aPbox", "sku": "ACCY-RCV1-US", "model": "aPbox-10", "compatiable": "ALL"},
    252: {"name": "Split-CT", "sku": "ACCY-CT200V1-US", "model": "Split-CT-US", "compatiable": "ALL"},
    253: {"name": "aHub", "sku": "ACCY-AHUBV1-US", "model": "aHub-20-04", "compatiable": "4|5"},
    254: {"name": "Meter Adapter Controller", "sku": "MAC-R1V1-US", "compatiable": "4|5"},
}


# Time-of-Use Dispatch Codes
class dispatchCodeType(Enum):
    """Dispatch Codes for TOU scheduling"""
    HOME = 2
    HOME_LOADS = 2
    STANDBY = 3
    SELF = 6
    SELF_CONSUMPTION = 6
    SOLAR = 1
    SOLAR_CHARGE = 1
    GRID_CHARGE = 8
    GRID_IMPORT = 8
    FORCE_CHARGE = 8
    GRID_EXPORT = 7
    GRID_DISCHARGE = 7
    FORCE_DISCHARGE = 7
    CUSTOM = 0
    PREDEFINED = 0


valid_tou_modes = [ 
    "HOME", 
    "HOME_LOADS", 
    "STANDBY", 
    "SOLAR", 
    "SOLAR_CHARGE", 
    "SELF", 
    "SELF_CONSUMPTION", 
    "GRID_EXPORT", 
    "GRID_DISCHARGE", 
    "GRID_IMPORT", 
    "GRID_DISCHARGE",
    "FORCE_CHARGE", 
    "FORCE_DISCHARGE", 
    "CUSTOM",
    "PREDEFINED",
    "JSON"
]


DISPATCH_CODES = {
    "HOME": 1,
    "HOME_LOADS": 1,
    "STANDBY": 2,
    "SOLAR": 3,
    "SOLAR_CHARGING": 3,
    "SELF": 6,
    "SELF_CONSUMPTION": 6,
    "GRID_EXPORT": 7,
    "GRID_DISCHARGE": 7,
    "FORCE_DISCHARGE": 7,
    "GRID_CHARGE": 8,
    "GRID_IMPORT": 8,
    "FORCE_CHARGE": 8,
    1: "aPower to home (surplus solar to grid)",
    2: "aPower on standby (surplus solar to grid)",
    6: "Self-consumption (surplus solar to grid)",
    3: "aPower charges from solar",
    7: "aPower to home/grid",
    8: "aPower charges from solar/grid",
}


class WaveType(Enum):
    """Setup WaveType Tariff Codes"""
    OFF_PEAK = 0
    MID_PEAK = 1
    ON_PEAK = 2
    SUPER_OFF_PEAK = 4


WAVE_TYPES = {
    0: "Off-Peak",
    1: "Mid-Peak",
    2: "On-Peak",
    4: "Super Off-Peak",
    "OFF_PEAK": 0,
    "MID_PEAK": 1,
    "ON_PEAK": 2,
    "SUPER_OFF_PEAK": 4,
    "Off-Peak": 0,
    "Mid-Peak": 1,
    "On-Peak": 2,
    "Super Off-Peak": 4
}


# Power Control Settings
PCS_CONTROL = {
    "ENABLED": 0.1,
    "DISABLED": 0,
    "UNLIMITED": -1.0,
    "disable_grid_export": 0,
    "unlimted_grid_export": -1.0,
    "disable_grid_import": 0,
    "unlimited_grid_import": -1.0,
    "custom_power_setting": 0.1,
}

# Emergency Backup Periods
EMERGENCY_BACKUP_PERIODS = {
    "one_day": 1440,
    "two_day": 2880,
    "three_day": 4320,
    "indefinite": 1,
    "custom": 2,
}

# Device Architecture Info
DEVICE_ARCHITECTURE = {
    "aGate X": {
        "coupling": "AC",
        "description": "AC-coupled battery with AC solar inputs",
        "solar_inputs": "2x 63A AC circuits",
        "battery_coupling": "AC (internal inverter)",
        "remote_solar": "Supported via aPbox/aHub",
    },
    "aPower S": {
        "coupling": "Hybrid",
        "description": "DC-coupled with both AC and DC solar inputs",
        "solar_inputs": "4x MPPT DC + AC inputs",
        "battery_coupling": "DC",
    },
    "aPower 2": {
        "coupling": "DC",
        "description": "DC-coupled battery",
        "solar_inputs": "MPPT DC inputs",
        "battery_coupling": "DC",
    }
}


# Certified FranklinWH PICS Enum Mappings (Sourced from PICS documentation SM-000028)
PICS_ENUMS = {
    701: {
        "ACType": {
            1: "SINGLE_PHASE",
            2: "SPLIT_PHASE",
            3: "THREE_PHASE"
        },
        "St": {
            1: "OFF",
            2: "ON"
        },
        "InvSt": {
            1: "OFF",
            2: "SLEEPING",
            3: "STARTING",
            4: "RUNNING",
            5: "THROTTLED",
            6: "SHUTTING_DOWN",
            7: "FAULT",
            8: "STANDBY"
        },
        "ConnSt": {
            1: "DISCONNECTED",
            2: "CONNECTED"
        },
        "DERMode": {
            1: "GRID_FOLLOWING",
            2: "GRID_FORMING",
            3: "PV_CLIPPED"
        }
    },
    703: {
        "ES": {
            1: "DISABLED",
            2: "ENABLED"
        },
        "NorOpCatRtg": {
            1: "CAT_A",
            2: "CAT_B"
        },
        "AbnOpCatRtg": {
            1: "CAT_1",
            2: "CAT_2",
            3: "CAT_3"
        },
        "IntIslandCatRtg": {
            1: "UNCATEGORIZED",
            2: "INT_ISL_CAPABLE",
            3: "BLACK_START_CAPABLE",
            4: "ISOCH_CAPABLE"
        },
        "IntIslandCat": {
            1: "UNCATEGORIZED",
            2: "INT_ISL_CAPABLE",
            3: "BLACK_START_CAPABLE",
            4: "ISOCH_CAPABLE"
        }
    },
    704: {
        "PFWInjEna": {1: "DISABLED", 2: "ENABLED"},
        "PFWInjEnaRvrt": {1: "DISABLED", 2: "ENABLED"},
        "PFWAbsEna": {1: "DISABLED", 2: "ENABLED"},
        "PFWAbsEnaRvrt": {1: "DISABLED", 2: "ENABLED"},
        "WMaxLimPctEna": {1: "DISABLED", 2: "ENABLED"},
        "WMaxLimPctEnaRvrt": {1: "DISABLED", 2: "ENABLED"},
        "WSetEna": {1: "DISABLED", 2: "ENABLED"},
        "WSetMod": {0: "W_MAX_PCT", 1: "WATTS"},
        "WSetEnaRvrt": {1: "DISABLED", 2: "ENABLED"},
        "VarSetEna": {1: "DISABLED", 2: "ENABLED"},
        "VarSetMod": {
            0: "W_MAX_PCT",
            1: "VAR_MAX_PCT",
            2: "VAR_AVAIL_PCT",
            3: "VA_MAX_PCT",
            4: "VARS"
        },
        "VarSetPri": {0: "ACTIVE", 1: "REACTIVE", 2: "VENDOR"},
        "VarSetEnaRvrt": {1: "DISABLED", 2: "ENABLED"},
        "WRmpRef": {0: "A_MAX", 1: "W_MAX"},
        "AntiIslEna": {1: "DISABLED", 2: "ENABLED"},
        "PFWInj.Ext": {0: "OVER_EXCITED", 1: "UNDER_EXCITED"},
        "PFWInjRvrt.Ext": {0: "OVER_EXCITED", 1: "UNDER_EXCITED"},
        "PFWAbs.Ext": {0: "OVER_EXCITED", 1: "UNDER_EXCITED"},
        "PFWAbsRvrt.Ext": {0: "OVER_EXCITED", 1: "UNDER_EXCITED"},
        "AdptCrvRslt": {0: "IN_PROGRESS", 1: "COMPLETED", 2: "FAILED"}
    },
    715: {
        "LocRemCtl": {0: "REMOTE", 1: "LOCAL"},
        "OpCtl": {0: "STOP", 1: "START", 2: "ENTER_STANDBY", 3: "EXIT_STANDBY"}
    }
}


# FranklinWH Proprietary / Extension Modbus Register Definitions
EXTENSION_REGISTRY = {
    15506: {"name": "LoadActiveP", "type": "uint16", "sf": 0},
    15507: {
        "name": "OnGridMode",
        "type": "uint16",
        "sf": 0,
        "symbols": {
            1: "Emergency Backup",
            2: "Self-Consumption",
            3: "TOU",
            4: "Manual"
        }
    },
    15508: {"name": "SelfReserve", "type": "uint16", "sf": 0},
    15509: {"name": "TouReserve", "type": "uint16", "sf": 0},
    15510: {"name": "PVOutputWh", "type": "uint32", "sf": 0},
    15512: {"name": "proxOutputWh", "type": "uint32", "sf": 0},
    16000: {"name": "HomeLoadHighRes", "type": "uint16", "sf": 0},
}


def get_pics_enum_desc(model_id: int, point_name: str, value: int) -> str:
    """Resolve a PICS-certified integer enum value to its string representation.
    
    Args:
        model_id: SunSpec model ID (e.g. 701, 703, 704, 715)
        point_name: The SunSpec point/register name (e.g. 'InvSt', 'ES', 'WSetMod')
        value: The raw integer value read from the register
        
    Returns:
        The string description of the enum value, or "UNKNOWN (value)" if not found.
    """
    model_maps = PICS_ENUMS.get(model_id, {})
    point_map = model_maps.get(point_name, {})
    return point_map.get(value, f"UNKNOWN ({value})")

