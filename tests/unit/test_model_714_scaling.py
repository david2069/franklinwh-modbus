"""Model 714 per-port reading, DCA workaround and repeating groups (#130).

Models are real pysunspec2 objects built from raw registers
(tests/unit/sunspec_raw.py), so the code under test sees pysunspec2's own
structure: ports are the ``Prt`` repeating group, not a ``blocks`` list.
"""
import pytest
from unittest.mock import MagicMock, patch
from franklinwh_modbus import FranklinWHController, VirtualModeController
from franklinwh_modbus.sequencer import SunSpecSequencer
from tests.unit.sunspec_raw import m714, m714_v12, NI16, NU16


def _m713(soc=550, soh=956, rtg=13600, avail=7500):
    m = MagicMock()
    m.SoC.value, m.SoH.value, m.WHRtg.value, m.WHAvail.value, m.Sta.value = soc, soh, rtg, avail, 0
    m.Pct_SF = MagicMock(value=-1)
    m.WH_SF = MagicMock(value=0)
    return m


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    return c


def _status(ctrl, model714, m713=None):
    models = {713: m713 or _m713(), 714: model714}
    with patch.object(ctrl, 'get_model', side_effect=models.get):
        return ctrl.read_battery_status()


class TestModel714Ports:

    def test_single_battery(self, ctrl):
        """NPrt = 1, DCA not populated: current = DCW / DCV."""
        s = _status(ctrl, m714(dcw=3000, ports=[{'dcv': 240, 'dcw': 3000, 'tmp': 25}]))
        assert s['soc'] == 55.0 and s['soh'] == 95.6
        assert s['battery_power_w'] == 3000
        assert s['battery_state'] == 'Discharging'      # positive DCW = discharging
        assert s['battery_current_a'] == 12.5            # 3000 / 240
        assert s['battery_temp_c'] == 25.0
        assert s['individual_batteries'] == [
            {'port': 1, 'power_w': 3000, 'voltage_v': 240, 'current_a': 12.5, 'temp_c': 25.0}]

    def test_multi_battery(self, ctrl):
        """NPrt = 2: total from model DCW, voltage averaged, hottest port."""
        s = _status(ctrl, m714(dcw=-4500, ports=[{'dcv': 238, 'dcw': -2000, 'tmp': 24},
                                                 {'dcv': 242, 'dcw': -2500, 'tmp': 28}]))
        assert s['battery_power_w'] == -4500
        assert s['battery_state'] == 'Charging'
        assert s['battery_current_a'] == -18.75          # -4500 / 240
        assert s['battery_temp_c'] == 28.0
        assert [b['port'] for b in s['individual_batteries']] == [1, 2]
        assert s['individual_batteries'][1]['voltage_v'] == 242
        assert s['individual_batteries'][1]['power_w'] == -2500

    def test_model_dca_used_when_populated(self, ctrl):
        s = _status(ctrl, m714(dcw=-1000, dca=-21, ports=[{'dcv': 48, 'dcw': -1000, 'dca': -21}]))
        assert s['battery_current_a'] == -21
        assert s['individual_batteries'][0]['current_a'] == -21

    def test_scale_factors(self, ctrl):
        # DCA_SF -1, DCV_SF -1, DCW_SF 0, DCWH_SF 0, Tmp_SF -1
        s = _status(ctrl, m714(dcw=500, ports=[{'dcv': 2500, 'dcw': 500, 'tmp': 315}],
                               sf=(-1, -1, 0, 0, -1)))
        assert s['individual_batteries'][0]['voltage_v'] == 250.0
        assert s['individual_batteries'][0]['temp_c'] == 31.5
        assert s['battery_current_a'] == 2.0

    def test_v12_zero_port_block_is_not_reported(self, ctrl):
        """V12R02B60D00 (#129): DCA 0 and the port block all 0 while DCW -600.
        Temperature, current and port values are None, not 0 °C / 0 A."""
        s = _status(ctrl, m714_v12(dcw=-600))
        assert s['battery_power_w'] == -600              # model DCW is real
        assert s['battery_state'] == 'Charging'
        assert s['battery_current_a'] is None
        assert s['battery_temp_c'] is None
        assert s['individual_batteries'] == [
            {'port': 1, 'power_w': None, 'voltage_v': None, 'current_a': None, 'temp_c': None}]

    def test_not_implemented_values_are_not_reported(self, ctrl):
        s = _status(ctrl, m714(dcw=0, dca=NI16, ports=[{'dcv': NU16, 'dca': NI16, 'dcw': NI16, 'tmp': NI16}]))
        assert s['battery_current_a'] is None
        assert s['battery_temp_c'] is None
        assert s['individual_batteries'][0]['voltage_v'] is None

    def test_no_ports(self, ctrl):
        s = _status(ctrl, m714(dcw=200))
        assert s['battery_power_w'] == 200
        assert s['individual_batteries'] == []
        assert s['battery_current_a'] is None and s['battery_temp_c'] is None


class TestModel714Totals:

    def test_verify_command_execution_uses_model_dcw(self, ctrl):
        m704 = MagicMock()
        m704.WSetPct_SF = MagicMock(value=0)
        m704.WSetPct.value = 80        # hardware +80 % = discharge 4000 W of 5000 W
        m704.WSetEna.value = 1
        models = {704: m704, 714: m714(dcw=3950, ports=[{'dcv': 50, 'dcw': 2000}, {'dcv': 50, 'dcw': 1950}])}
        with patch.object(ctrl, 'get_model', side_effect=models.get):
            vmc = VirtualModeController(ctrl, min_discharge_soc=20)
            vmc._last_commanded_power = -4000
            ok, commanded, actual, diff = vmc.verify_command_execution(tolerance_percent=5.0)
        assert ok and commanded == -4000 and actual == -3950 and diff == 1.25


class TestSequencerRepeatingGroup:

    def test_suffix_resolves_port_points(self):
        model = m714(dcw=-4500, ports=[{'dcv': 238, 'dcw': -2000}, {'dcv': 242, 'dcw': -2500}])
        device = MagicMock()
        device.models = {714: model}
        seq = SunSpecSequencer(device)
        assert seq.get_point('714.DCW') == (model, model.DCW)
        assert seq.get_point('714.DCW_1') == (model, model.Prt[0].DCW)
        assert seq.get_point('714.DCV_2')[1].value == 242
        with pytest.raises(ValueError):
            seq.get_point('714.DCV_3')
