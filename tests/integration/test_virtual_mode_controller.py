"""
Integration tests for VirtualModeController.

These tests verify the virtual mode logic works correctly with mocked hardware.
They serve as templates for hardware-in-the-loop tests.

Sign convention:
================
Every calculator returns power in the BatteryCommand convention:
positive = charge, negative = discharge. The inversion to the hardware's
WSetPct convention happens once, in FranklinWHController.send_command().
(Issue #20 fixed calculators that returned the opposite sign.)
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from franklinwh_modbus import (
    VirtualModeController, 
    VirtualMode, 
    TOUSchedule,
    FranklinWHController,
)


class TestVirtualModeControllerIntegration:
    """Integration tests for VirtualModeController with mocked hardware."""
    
    @pytest.fixture
    def mock_controller(self):
        """Create a mocked FranklinWHController."""
        ctrl = Mock(spec=FranklinWHController)
        
        # Set up rating attributes
        ctrl.RATED_MAX_W = 5000
        ctrl.RATED_MAX_CHARGE_W = 5000
        ctrl.RATED_MAX_DISCHARGE_W = 5000
        
        # Set up mock status methods
        ctrl.read_battery_status.return_value = {
            'soc': 75.0,
            'soh': 98.0,
            'dc_voltage_v': 400.0,
            'dc_current_a': 5.0,
            'dc_power_w': 2000.0,
            'temperature_c': 25.0,
        }
        
        ctrl.read_grid_status.return_value = {
            'grid_power_w': -500.0,
            'voltage_v': 230.0,
            'frequency_hz': 50.0,
        }
        
        ctrl.read_solar_status.return_value = {
            'dc_power_w': 3500.0,
            'extension': {
                'pv_total': 0,
                'pv_proximal': 2500,
                'pv_remote1': 1000,
                'pv_remote2': 0,
                'total_solar': 3500,
            }
        }
        
        ctrl.read_control_status.return_value = {
            'wset_watts': 1500.0,
            'wset_pct': 30.0,
            'wset_ena': 1,
        }
        
        ctrl.read_native_mode.return_value = {
            'mode_raw': 3,
            'mode_name': 'Manual',
            'self_reserve_pct': 20,
            'tou_reserve_pct': 15,
        }
        
        # Mock check_state to return no conflicts (required by set_mode())
        ctrl.check_state.return_value = {
            'conflicts': [],
            'soc': 75.0,
            'battery_activity': 'IDLE',
        }
        
        # Mock send_command to return success
        ctrl.send_command.return_value = (True, "Command sent: 1500W")
        
        return ctrl
    
    @pytest.fixture
    def vmc(self, mock_controller):
        """Create a VirtualModeController with mocked hardware."""
        return VirtualModeController(
            mock_controller,
            max_charge_soc=95,
            min_discharge_soc=20,
            soc_ramp_window=10,
        )
    
    def test_self_consumption_mode_solar_excess(self, vmc, mock_controller):
        """
        Test self_consumption mode with excess solar above reserve.
        
        Scenario: SoC at 75% (above 20% reserve, below 100% target),
        solar 3500W, home 2000W
        Expected: Charge from the 1500W of excess solar (positive = charge)
        """
        # Set up status with solar > home load
        mock_controller.read_solar_status.return_value = {
            'dc_power_w': 3500.0,
            'extension': {'total_solar': 3500}
        }
        mock_controller.read_grid_status.return_value = {
            'grid_power_w': -1500.0,  # Exporting excess
            'voltage_v': 230.0,
            'frequency_hz': 50.0,
        }
        
        # Execute self-consumption mode
        vmc.set_mode(VirtualMode.SELF_CONSUMPTION, self_reserve_pct=20)
        
        power = vmc._calc_self_consumption(
            solar=3500,
            home=2000,
            grid=-1500,
            soc=75.0
        )
        
        assert power == 1500, f"Expected charge from excess solar (+1500W), got {power}W"
    
    def test_self_consumption_mode_grid_import(self, vmc, mock_controller):
        """
        Test self_consumption mode when home load exceeds solar.
        
        Scenario: Solar producing 1000W, home using 3000W
        Expected: Discharge battery to cover deficit
        
        Positive = charge, negative = discharge (BatteryCommand convention).
        """
        mock_controller.read_solar_status.return_value = {
            'dc_power_w': 1000.0,
            'extension': {'total_solar': 1000}
        }
        mock_controller.read_grid_status.return_value = {
            'grid_power_w': 500.0,  # Importing from grid
            'voltage_v': 230.0,
            'frequency_hz': 50.0,
        }
        
        vmc.set_mode(VirtualMode.SELF_CONSUMPTION, self_reserve_pct=20)
        
        power = vmc._calc_self_consumption(
            solar=1000,
            home=3000,
            grid=500,
            soc=75.0
        )
        
        # Deficit of 2000W covered by discharging
        assert power == -2000, f"Expected discharge of -2000W, got {power}W"
    
    def test_emergency_backup_mode_charges_to_target(self, vmc, mock_controller):
        """
        Test emergency_backup mode charges battery to target SoC.
        
        Scenario: SoC at 60%, target is 95%
        Expected: Full charge rate
        
        Positive = charge (BatteryCommand convention).
        """
        mock_controller.read_battery_status.return_value = {
            'soc': 60.0,
            'dc_power_w': 0,
        }
        
        vmc.set_mode(VirtualMode.EMERGENCY_BACKUP, backup_target_soc=95)
        
        power = vmc._calc_emergency_backup(
            solar=2000,
            home=1500,
            grid=0,
            soc=60.0
        )
        
        # Should charge (positive power) when below target
        assert power > 0, f"Expected charging (positive power), got {power}W"
    
    def test_emergency_backup_mode_stops_at_target(self, vmc, mock_controller):
        """
        Test emergency_backup mode stops when target reached.
        
        Scenario: SoC at 96%, target is 95%
        Expected: Idle (0W command)
        
        NOTE: The new implementation uses universal target_soc which defaults to 100,
        so we need to explicitly set it lower for this test.
        """
        vmc.set_mode(VirtualMode.EMERGENCY_BACKUP, backup_target_soc=95, target_soc=95)
        
        power = vmc._calc_emergency_backup(
            solar=2000,
            home=1500,
            grid=0,
            soc=96.0  # Above target
        )
        
        # Should idle when above target
        assert power == 0, f"Expected idle at target SoC, got {power}W"
    
    def test_peak_shave_mode_triggers_on_threshold(self, vmc, mock_controller):
        """
        Test peak_shave mode discharges when load exceeds threshold.
        
        Scenario: Home load 6000W, threshold 5000W
        Expected: Discharge to reduce peak
        
        Negative = discharge (BatteryCommand convention).
        """
        vmc.set_mode(VirtualMode.PEAK_SHAVE, peak_shave_threshold=5000)
        
        power = vmc._calc_peak_shave(
            solar=1000,
            home=6000,  # Exceeds 5000W threshold
            grid=4000,  # Would import 4000W without battery
            soc=75.0
        )
        
        # Net load 5000W, discharged at the 5000W rating
        assert power == -5000, f"Expected discharge of -5000W, got {power}W"
    
    def test_peak_shave_mode_idle_below_threshold(self, vmc, mock_controller):
        """
        Test peak_shave mode stays idle when load below threshold.
        
        Scenario: Home load 3000W, threshold 5000W
        Expected: Idle
        """
        vmc.set_mode(VirtualMode.PEAK_SHAVE, peak_shave_threshold=5000)
        
        power = vmc._calc_peak_shave(
            solar=2000,
            home=3000,  # Below 5000W threshold
            grid=1000,
            soc=75.0
        )
        
        # Should idle when below threshold
        assert power == 0, f"Expected idle below threshold, got {power}W"
    
    def test_soc_limits_enforce_max_charge(self, vmc, mock_controller):
        """
        Test that max_charge_soc limits charging.
        
        Scenario: SoC at 93%, max_charge_soc=95, ramp_window=10
        Expected: Reduced charge rate due to ramping
        
        NOTE: VMC uses positive=charge, negative=discharge (opposite of BatteryCommand)
        """
        vmc.max_charge_soc = 95
        vmc.soc_ramp_window = 10
        
        # At 93% with 95% limit and 10% window, ramp is:
        # (95 - 93) / 10 = 20% of max power
        # In VMC: positive=charge, so we pass +5000
        power = vmc._apply_safety_limits(5000, soc=93.0)  # Trying to charge at max
        
        # Should be reduced due to ramping
        assert power < 5000, f"Expected ramped power, got {power}W"
        assert power > 0, "Should still be charging (positive in VMC)"
    
    def test_soc_limits_stop_at_max(self, vmc, mock_controller):
        """
        Test that charging stops at max_charge_soc.
        
        Scenario: SoC at 96%, max_charge_soc=95
        Expected: 0W (idle)
        
        NOTE: VMC uses positive=charge, negative=discharge (opposite of BatteryCommand)
        """
        vmc.max_charge_soc = 95
        
        # In VMC: positive=charge, so we pass +3000
        power = vmc._apply_safety_limits(3000, soc=96.0)  # Trying to charge
        
        # Should stop charging
        assert power == 0, f"Expected idle at max SoC, got {power}W"
    
    def test_soc_limits_enforce_min_discharge(self, vmc, mock_controller):
        """
        Test that min_discharge_soc limits discharging.
        
        Scenario: SoC at 22%, min_discharge_soc=20, ramp_window=10
        Expected: Reduced discharge rate
        
        NOTE: VMC uses positive=charge, negative=discharge (opposite of BatteryCommand)
        """
        vmc.min_discharge_soc = 20
        vmc.soc_ramp_window = 10
        
        # At 22% with 20% limit and 10% window, ramp is:
        # (22 - 20) / 10 = 20% of max power
        # In VMC: negative=discharge, so we pass -5000
        power = vmc._apply_safety_limits(-5000, soc=22.0)  # Trying to discharge at max
        
        # Should be reduced due to ramping (closer to zero)
        assert power > -5000, f"Expected ramped power, got {power}W"
        assert power < 0, "Should still be discharging (negative in VMC)"
    
    def test_soc_limits_stop_at_min(self, vmc, mock_controller):
        """
        Test that discharging stops at min_discharge_soc.
        
        Scenario: SoC at 18%, min_discharge_soc=20
        Expected: 0W (idle)
        
        NOTE: VMC uses positive=charge, negative=discharge (opposite of BatteryCommand)
        """
        vmc.min_discharge_soc = 20
        
        # In VMC: negative=discharge, so we pass -3000
        power = vmc._apply_safety_limits(-3000, soc=18.0)  # Trying to discharge
        
        # Should stop discharging
        assert power == 0, f"Expected idle at min SoC, got {power}W"
    
    def test_extension_solar_aggregation(self, vmc, mock_controller):
        """
        Test that solar from all extension sources is aggregated.
        
        Scenario: PV Proximal=2500W, Remote1=1500W, Remote2=500W
        Expected: Total solar = 4500W
        """
        mock_controller.read_solar_status.return_value = {
            'dc_power_w': 0,  # Model 714 shows 0 (AC-coupled)
            'extension': {
                'pv_total': 0,  # Not populated
                'pv_proximal': 2500,
                'pv_remote1': 1500,
                'pv_remote2': 500,
                'total_solar': 4500,  # Sum of individuals
            }
        }
        
        status = vmc.read_status()
        
        # Should have total from all sources
        assert status['derived']['total_solar_w'] == 4500, \
            f"Expected 4500W total solar, got {status['derived']['total_solar_w']}W"
    
    def test_tou_schedule_file_loading(self, vmc, sample_schedule_file):
        """
        Test loading TOU schedule from file.
        """
        schedule = TOUSchedule.from_file(sample_schedule_file)
        
        assert schedule.is_file_based()
        assert schedule.get_schedule_name() == "Test Schedule"
        assert schedule.get_min_soc() == 10
        assert schedule.get_max_soc() == 95
        
        # Should have 3 periods
        assert len(schedule._schedule_data['periods']) == 3
    
    def test_tou_strategy_selection(self, vmc, sample_schedule_file):
        """
        Test TOU strategy based on time of day.
        
        Note: This test uses the actual current hour, so it's time-dependent.
        In production, you'd mock datetime.now() for deterministic tests.
        """
        from datetime import datetime
        
        schedule = TOUSchedule.from_file(sample_schedule_file)
        vmc.tou = schedule
        
        # Get current hour strategy
        strategy = schedule.get_strategy()
        hour = datetime.now().hour
        
        # Verify strategy matches hour
        if hour in [0,1,2,3,4,5,6,22,23]:
            assert strategy == "charge", f"Expected 'charge' at hour {hour}"
        elif hour in [17,18,19,20]:
            assert strategy == "discharge", f"Expected 'discharge' at hour {hour}"
        else:
            assert strategy == "self_consumption", f"Expected 'self_consumption' at hour {hour}"


@pytest.mark.hardware
class TestVirtualModeControllerHardware:
    """
    Hardware-in-the-loop tests.
    
    These require an actual FranklinWH aGate on the network.
    Marked with 'hardware' marker and skipped by default.
    """
    
    def test_hardware_connection(self):
        """Verify hardware connection works."""
        # This would test actual connection to aGate
        # Skipped unless --run-hardware-tests flag provided
        pytest.skip("Hardware tests require actual aGate. Use --run-hardware-tests to enable.")
