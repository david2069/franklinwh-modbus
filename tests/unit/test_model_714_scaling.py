import pytest
from unittest.mock import Mock, patch, MagicMock
from franklinwh_modbus import FranklinWHController, VirtualModeController, BatteryCommand
from franklinwh_modbus.sequencer import SunSpecSequencer
from franklinwh_modbus.monitor import CLIMonitor, MonitorConfig

class TestModel714Scaling:
    """Unit tests for Model 714 multi-port scaling, DCA workaround, and repeating blocks."""

    @pytest.fixture
    def mock_controller(self):
        """Create an unconnected FranklinWHController for testing."""
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            ctrl = FranklinWHController(ip_address='127.0.0.1')
            ctrl.dev = MagicMock()
            return ctrl

    def create_mock_block(self, dcw=None, dcv=None, dca=None, tmp=None, dcwh_inj=None, dcwh_abs=None):
        """Helper to create a mocked repeating block."""
        block = MagicMock()
        
        # Set up DCW (DC Power)
        if dcw is not None:
            block.DCW = MagicMock()
            block.DCW.value = dcw
            block.has_dcw = True
        else:
            block.has_dcw = False
            if hasattr(block, 'DCW'):
                delattr(block, 'DCW')
                
        # Set up DCV (DC Voltage)
        if dcv is not None:
            block.DCV = MagicMock()
            block.DCV.value = dcv
            block.has_dcv = True
        else:
            block.has_dcv = False
            if hasattr(block, 'DCV'):
                delattr(block, 'DCV')

        # Set up DCA (DC Current)
        if dca is not None:
            block.DCA = MagicMock()
            block.DCA.value = dca
            block.has_dca = True
        else:
            block.has_dca = False
            if hasattr(block, 'DCA'):
                delattr(block, 'DCA')

        # Set up Tmp (Temperature)
        if tmp is not None:
            block.Tmp = MagicMock()
            block.Tmp.value = tmp
            block.has_tmp = True
        else:
            block.has_tmp = False
            if hasattr(block, 'Tmp'):
                delattr(block, 'Tmp')

        # Set up DCWhInj / DCWhAbs (Energy)
        if dcwh_inj is not None:
            block.DCWhInj = MagicMock()
            block.DCWhInj.value = dcwh_inj
        if dcwh_abs is not None:
            block.DCWhAbs = MagicMock()
            block.DCWhAbs.value = dcwh_abs

        # Standard SunSpec model point validation checks hasattr
        def mock_hasattr(name):
            if name == 'DCW': return dcw is not None
            if name == 'DCV': return dcv is not None
            if name == 'DCA': return dca is not None
            if name == 'Tmp': return tmp is not None
            if name == 'DCWhInj': return dcwh_inj is not None
            if name == 'DCWhAbs': return dcwh_abs is not None
            return False
        block.__class__.__hasattr__ = mock_hasattr
        
        return block

    def test_single_battery_scaling(self, mock_controller):
        """Verify that NPrt = 1 reads and calculates DCA correctly."""
        m713 = MagicMock()
        m713.SoC.value = 550  # 55.0%
        m713.SoH.value = 956  # 95.6%
        m713.WHRtg.value = 13600
        m713.WHAvail.value = 7500
        m713.Sta.value = 0
        
        m714 = MagicMock()
        
        # Scale factors
        sf_pct = MagicMock(value=-1)
        sf_wh = MagicMock(value=0)
        sf_w = MagicMock(value=0)
        sf_a = MagicMock(value=0)
        sf_v = MagicMock(value=0)
        sf_tmp = MagicMock(value=0)
        
        # Attach SF attributes
        m713.Pct_SF = sf_pct
        m713.WH_SF = sf_wh
        m714.DCW_SF = sf_w
        m714.DCA_SF = sf_a
        m714.DCV_SF = sf_v
        m714.Tmp_SF = sf_tmp
        
        # Single repeating block (NPrt = 1)
        # Block 0 is fixed block. Block 1 is the repeating block.
        fixed_block = MagicMock()
        fixed_block.NPrt.value = 1
        port1 = self.create_mock_block(dcw=3000, dcv=240, dca=0, tmp=25)
        
        m714.blocks = [fixed_block, port1]
        
        def mock_get_model(model_id):
            if model_id == 713: return m713
            if model_id == 714: return m714
            return None
            
        with patch.object(mock_controller, 'get_model', side_effect=mock_get_model):
            # Probe extension read results
            mock_controller._extension_write_results = {'tested': True}
            
            status = mock_controller.read_battery_status()
            
            # Assertions
            assert status['soc'] == 55.0
            assert status['soh'] == 95.6
            assert status['battery_power_w'] == 3000
            assert status['battery_state'] == 'Discharging'  # positive DCW = discharging
            assert status['battery_current_a'] == 12.5      # 3000 / 240 = 12.5A
            assert status['battery_temp_c'] == 25.0
            
            # Validate individual battery array
            assert len(status['individual_batteries']) == 1
            assert status['individual_batteries'][0]['port'] == 1
            assert status['individual_batteries'][0]['power_w'] == 3000
            assert status['individual_batteries'][0]['voltage_v'] == 240
            assert status['individual_batteries'][0]['current_a'] == 0
            assert status['individual_batteries'][0]['temp_c'] == 25.0

    def test_multi_battery_scaling(self, mock_controller):
        """Verify aggregation logic for NPrt = 2 configurations."""
        m713 = MagicMock()
        m713.SoC.value = 800  # 80.0%
        m713.SoH.value = 980  # 98.0%
        m713.WHRtg.value = 27200
        m713.WHAvail.value = 21760
        m713.Sta.value = 0
        
        m714 = MagicMock()
        
        # Scale factors
        sf_pct = MagicMock(value=-1)
        sf_wh = MagicMock(value=0)
        sf_w = MagicMock(value=0)
        sf_a = MagicMock(value=0)
        sf_v = MagicMock(value=0)
        sf_tmp = MagicMock(value=0)
        
        m713.Pct_SF = sf_pct
        m713.WH_SF = sf_wh
        m714.DCW_SF = sf_w
        m714.DCA_SF = sf_a
        m714.DCV_SF = sf_v
        m714.Tmp_SF = sf_tmp
        
        # Parallel batteries (NPrt = 2)
        fixed_block = MagicMock()
        fixed_block.NPrt.value = 2
        port1 = self.create_mock_block(dcw=-2000, dcv=238, dca=0, tmp=24) # Charging
        port2 = self.create_mock_block(dcw=-2500, dcv=242, dca=0, tmp=28) # Charging
        
        m714.blocks = [fixed_block, port1, port2]
        
        def mock_get_model(model_id):
            if model_id == 713: return m713
            if model_id == 714: return m714
            return None
            
        with patch.object(mock_controller, 'get_model', side_effect=mock_get_model):
            status = mock_controller.read_battery_status()
            
            # Assertions
            assert status['soc'] == 80.0
            # Power sum: -2000 + -2500 = -4500W
            assert status['battery_power_w'] == -4500
            assert status['battery_state'] == 'Charging'  # negative DCW = charging
            # Voltage average: (238 + 242) / 2 = 240V
            # Current calculation: -4500 / 240 = -18.75A
            assert status['battery_current_a'] == -18.75
            # Max temperature: max(24, 28) = 28.0C
            assert status['battery_temp_c'] == 28.0
            
            # Individual battery entries
            assert len(status['individual_batteries']) == 2
            assert status['individual_batteries'][0]['port'] == 1
            assert status['individual_batteries'][0]['power_w'] == -2000
            assert status['individual_batteries'][0]['voltage_v'] == 238
            assert status['individual_batteries'][0]['temp_c'] == 24.0
            
            assert status['individual_batteries'][1]['port'] == 2
            assert status['individual_batteries'][1]['power_w'] == -2500
            assert status['individual_batteries'][1]['voltage_v'] == 242
            assert status['individual_batteries'][1]['temp_c'] == 28.0

    def test_modes_verify_command_execution(self, mock_controller):
        """Verify command execution checks correctly sum multi-battery DC power."""
        m714 = MagicMock()
        m714.DCW_SF = MagicMock(value=0)
        
        # Setpoint read back from WSetPct (WSet is never written):
        # hardware +80% = discharge 4000W of a 5000W rating
        m704 = MagicMock()
        m704.WSetPct_SF = MagicMock(value=0)
        m704.WSetPct.value = 80
        m704.WSetEna.value = 1
        
        # Parallel batteries discharging 3950W in total (within 5% of 4000W)
        fixed_block = MagicMock()
        port1 = self.create_mock_block(dcw=2000)
        port2 = self.create_mock_block(dcw=1950)
        m714.blocks = [fixed_block, port1, port2]
        
        models = {704: m704, 714: m714}
        with patch.object(mock_controller, 'get_model', side_effect=models.get):
            vmc = VirtualModeController(mock_controller, min_discharge_soc=20)
            vmc._last_commanded_power = -4000  # discharge, BatteryCommand convention
            ok, commanded, actual, diff = vmc.verify_command_execution(tolerance_percent=5.0)
            
            assert ok
            assert commanded == -4000
            assert actual == -3950
            assert diff == 1.25  # (4000 - 3950) / 4000 = 1.25%

    def test_sequencer_repeating_block_resolution(self):
        """Verify sequencer resolves repeating block suffixes correctly."""
        device = MagicMock()
        m714 = MagicMock()
        
        # Setup blocks
        fixed_block = MagicMock()
        port1 = MagicMock()
        port2 = MagicMock()
        
        # Add dummy attributes so getattr resolves them naturally
        m714.DCW = MagicMock()
        port1.DCW = MagicMock()
        port2.DCW = MagicMock()
        
        m714.blocks = [fixed_block, port1, port2]
        device.models = {714: m714}
        
        seq = SunSpecSequencer(device)
        
        # Test default (first repeating block / root lookup)
        model_res, point_res = seq.get_point("714.DCW")
        assert model_res == m714
        assert point_res == m714.DCW
        
        # Test suffix index (first repeating block: _1)
        model_res, point_res = seq.get_point("714.DCW_1")
        assert model_res == m714
        assert point_res == port1.DCW
        
        # Test suffix index (second repeating block: _2)
        model_res, point_res = seq.get_point("714.DCW_2")
        assert model_res == m714
        assert point_res == port2.DCW
