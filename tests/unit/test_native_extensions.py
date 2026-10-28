import pytest
from unittest.mock import Mock, patch, MagicMock
from franklinwh_modbus import ControlMode
from franklinwh_modbus import FranklinWHController, VirtualModeController, VirtualMode

class TestNativeExtensions:
    """Unit tests for FranklinWH proprietary extensions and 1-indexed modes."""

    @pytest.fixture
    def mock_controller(self):
        """Create an un-connected FranklinWHController for unit testing."""
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            ctrl = FranklinWHController(ip_address='127.0.0.1')
            ctrl.dev = MagicMock()
            # Set up default test write results
            ctrl._extension_write_results = {
                'tested': True,
                'ongrid_mode': {'writable': True, 'error': None},
                'self_reserve': {'writable': True, 'error': None},
                'tou_reserve': {'writable': True, 'error': None},
            }
            return ctrl

    def test_native_modes_dictionary(self, mock_controller):
        """Verify that NATIVE_MODES is Backup (1), Self (2), TOU (3) and nothing else (#75)."""
        assert mock_controller.NATIVE_MODES[1] == 'Emergency Backup'
        assert mock_controller.NATIVE_MODES[2] == 'Self-Consumption'
        assert mock_controller.NATIVE_MODES[3] == 'TOU'
        assert set(mock_controller.NATIVE_MODES) == {1, 2, 3}

    def test_set_self_consumption_reserve_validation(self, mock_controller):
        """Verify that set_self_consumption_reserve validates bounds (0-100)."""
        success, msg = mock_controller.set_self_consumption_reserve(-1)
        assert not success
        assert "Must be 0-100" in msg

        success, msg = mock_controller.set_self_consumption_reserve(101)
        assert not success
        assert "Must be 0-100" in msg

        # Dry run should pass
        success, msg = mock_controller.set_self_consumption_reserve(35, dry_run=True)
        assert success
        assert "Would set Self-Consumption reserve to 35%" in msg

    def test_set_tou_reserve_validation(self, mock_controller):
        """Verify that set_tou_reserve validates bounds (0-100)."""
        success, msg = mock_controller.set_tou_reserve(-1)
        assert not success
        assert "Must be 0-100" in msg

        success, msg = mock_controller.set_tou_reserve(101)
        assert not success
        assert "Must be 0-100" in msg

        # Dry run should pass
        success, msg = mock_controller.set_tou_reserve(40, dry_run=True)
        assert success
        assert "Would set TOU reserve to 40%" in msg

    def test_get_effective_reserve_level_1_indexed(self, mock_controller):
        """Verify get_effective_reserve_level() uses correct 1-indexed operating mode mapping."""
        # 1. Self-Consumption (2)
        with patch.object(mock_controller, 'read_native_mode') as mock_read:
            mock_read.return_value = {
                'mode_raw': 2,
                'mode_name': 'Self-Consumption',
                'self_reserve_pct': 30,
                'tou_reserve_pct': 15,
            }
            reserve, source = mock_controller.get_effective_reserve_level()
            assert reserve == 30
            assert source == 'self'

        # 2. TOU (3)
        with patch.object(mock_controller, 'read_native_mode') as mock_read:
            mock_read.return_value = {
                'mode_raw': 3,
                'mode_name': 'TOU',
                'self_reserve_pct': 30,
                'tou_reserve_pct': 15,
            }
            reserve, source = mock_controller.get_effective_reserve_level()
            assert reserve == 15
            assert source == 'tou'

        # 3. Emergency Backup (1)
        with patch.object(mock_controller, 'read_native_mode') as mock_read:
            mock_read.return_value = {
                'mode_raw': 1,
                'mode_name': 'Emergency Backup',
                'self_reserve_pct': 30,
                'tou_reserve_pct': 15,
            }
            reserve, source = mock_controller.get_effective_reserve_level()
            assert reserve == 30
            assert source == 'self'

        # 4. Unobserved value (4): no known mode, so no reserve
        with patch.object(mock_controller, 'read_native_mode') as mock_read:
            mock_read.return_value = {
                'mode_raw': 4,
                'mode_name': 'Unknown(4)',
                'self_reserve_pct': 30,
                'tou_reserve_pct': 15,
            }
            reserve, source = mock_controller.get_effective_reserve_level()
            assert reserve is None
            assert source == 'unknown'

    def test_virtual_mode_controller_read_agate_reserve_1_indexed(self, mock_controller):
        """Verify VirtualModeController._read_agate_reserve_soc() maps correctly under 1-indexed modes."""
        # 1. Self-Consumption (2) should return self_reserve_pct
        with patch.object(mock_controller, 'read_native_mode') as mock_read:
            mock_read.return_value = {
                'mode_raw': 2,
                'mode_name': 'Self-Consumption',
                'self_reserve_pct': 35,
                'tou_reserve_pct': 10,
            }
            vmc = VirtualModeController(mock_controller, min_discharge_soc=None)
            assert vmc.min_discharge_soc == 35

        # 2. TOU (3) should return tou_reserve_pct
        with patch.object(mock_controller, 'read_native_mode') as mock_read:
            mock_read.return_value = {
                'mode_raw': 3,
                'mode_name': 'TOU',
                'self_reserve_pct': 35,
                'tou_reserve_pct': 12,
            }
            vmc = VirtualModeController(mock_controller, min_discharge_soc=None)
            assert vmc.min_discharge_soc == 12

    def test_parse_duration(self, mock_controller):
        """Verify the internal _parse_duration helper supports multiple formats."""
        # Raw numeric values
        assert mock_controller._parse_duration(120) == 120
        assert mock_controller._parse_duration(3600.0) == 3600

        # HH:MM:SS / MM:SS format
        assert mock_controller._parse_duration("01:30:00") == 5400
        assert mock_controller._parse_duration("30:00") == 1800

        # Suffix formats
        assert mock_controller._parse_duration("1h") == 3600
        assert mock_controller._parse_duration("1.5hr") == 5400
        assert mock_controller._parse_duration("30m") == 1800
        assert mock_controller._parse_duration("45 min") == 2700
        assert mock_controller._parse_duration("10s") == 10
        assert mock_controller._parse_duration("15 sec") == 15

        # Error cases
        with pytest.raises(ValueError):
            mock_controller._parse_duration("invalid")
        with pytest.raises(ValueError):
            mock_controller._parse_duration("01:02:03:04")

    def test_dispatch_stop_standby(self, mock_controller):
        """Verify dispatch handles stop and standby actions correctly."""
        # Stop action
        with patch.object(mock_controller, 'reset_control_state') as mock_reset:
            mock_reset.return_value = True
            success, msg = mock_controller.dispatch('stop')
            assert success
            assert "Control released" in msg
            mock_reset.assert_called_once()

        # Standby action
        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('standby', duration="1h")
            assert success
            # Standby translates to 0W power flow
            cmd = mock_send.call_args[0][0]
            assert cmd.power_watts == 0
            assert mock_send.call_args[1].get('duration_s') == 3600

    def test_dispatch_charge_discharge_power_resolutions(self, mock_controller):
        """Verify power value resolutions (max, watts, percentages) in dispatch."""
        mock_controller.RATED_MAX_CHARGE_W = 5000.0
        mock_controller.RATED_MAX_DISCHARGE_W = 5000.0

        # Watts
        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('charge', power=3000, duration=1800)
            assert success
            cmd = mock_send.call_args[0][0]
            assert cmd.power_watts == 3000
            assert mock_send.call_args[1].get('duration_s') == 1800

        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('discharge', power=2000)
            assert success
            cmd = mock_send.call_args[0][0]
            # Discharge is negative in our convention
            assert cmd.power_watts == -2000

        # 'max' rate
        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('charge', power='max')
            assert success
            cmd = mock_send.call_args[0][0]
            assert cmd.power_watts == 5000.0

        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('discharge', power='max')
            assert success
            cmd = mock_send.call_args[0][0]
            assert cmd.power_watts == -5000.0

        # Percentage
        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('charge', power='40%')
            assert success
            cmd = mock_send.call_args[0][0]
            # Sent as a percent (WSetPct), not converted to watts (#114 B1)
            assert cmd.mode == ControlMode.W_MAX_PCT and cmd.power_pct == 40.0

        with patch.object(mock_controller, 'send_command') as mock_send:
            mock_send.return_value = (True, "Command Sent")
            success, msg = mock_controller.dispatch('discharge', power='60%')
            assert success
            cmd = mock_send.call_args[0][0]
            assert cmd.mode == ControlMode.W_MAX_PCT and cmd.power_pct == -60.0

