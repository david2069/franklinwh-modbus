import pytest
from unittest.mock import Mock, patch, MagicMock
from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.constants import get_pics_enum_desc, PICS_ENUMS

def test_get_pics_enum_desc():
    # Test valid models & points
    assert get_pics_enum_desc(701, "ACType", 0) == "SINGLE_PHASE"
    assert get_pics_enum_desc(701, "ACType", 1) == "SPLIT_PHASE"
    assert get_pics_enum_desc(701, "InvSt", 3) == "RUNNING"
    assert get_pics_enum_desc(701, "InvSt", 7) == "STANDBY"
    assert get_pics_enum_desc(703, "ES", 0) == "DISABLED"
    assert get_pics_enum_desc(703, "ES", 1) == "ENABLED"
    assert get_pics_enum_desc(704, "WSetMod", 0) == "W_MAX_PCT"
    assert get_pics_enum_desc(704, "WSetMod", 1) == "WATTS"
    assert get_pics_enum_desc(715, "LocRemCtl", 0) == "REMOTE"
    assert get_pics_enum_desc(715, "LocRemCtl", 1) == "LOCAL"
    
    # Test unknown value
    assert get_pics_enum_desc(701, "ACType", 99) == "UNKNOWN (99)"
    # Test unknown point
    assert get_pics_enum_desc(701, "UnknownPoint", 1) == "UNKNOWN (1)"
    # Test unknown model
    assert get_pics_enum_desc(999, "UnknownPoint", 1) == "UNKNOWN (1)"

class TestPICSControllerExposure:
    @pytest.fixture
    def mock_controller(self):
        """Create an un-connected FranklinWHController for unit testing."""
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            ctrl = FranklinWHController(ip_address='127.0.0.1')
            return ctrl

    def test_controller_get_enum_desc(self, mock_controller):
        """Verify that FranklinWHController.get_enum_desc correctly forwards to resolver."""
        assert mock_controller.get_enum_desc(701, "ACType", 0) == "SINGLE_PHASE"
        assert mock_controller.get_enum_desc(704, "WSetMod", 1) == "WATTS"
        assert mock_controller.get_enum_desc(715, "LocRemCtl", 1) == "LOCAL"
        assert mock_controller.get_enum_desc(701, "ACType", 99) == "UNKNOWN (99)"
