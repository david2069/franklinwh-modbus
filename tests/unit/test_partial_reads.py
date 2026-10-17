"""
Regression tests for issue #52.

A model that fails inside an otherwise successful status read must not be
silent: it is logged at warning level (rate-limited, with a recovery line),
the result lists it in 'partial', and its values are left out rather than
reported as 0.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController


@pytest.fixture
def real_ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1')
    ctrl.dev = MagicMock()
    return ctrl


def _m713():
    m = MagicMock()
    for sf in ('WH_SF', 'Pct_SF'):
        setattr(m, sf, MagicMock(value=0))
    m.SoC.value = 55
    m.SoH.value = 98
    m.WHRtg.value = 13600
    m.WHAvail.value = 7000
    m.Sta.value = 0
    return m


def _m714(dcw=-1200):
    m = MagicMock()
    for sf in ('DCW_SF', 'DCA_SF', 'DCV_SF', 'Tmp_SF'):
        setattr(m, sf, MagicMock(value=0))
    block = MagicMock()
    block.DCW.value = dcw
    block.DCA.value = 25
    block.DCV.value = 48
    block.Tmp.value = 30
    m.blocks = [MagicMock(), block]
    return m


def _m502(out_w=3000):
    m = MagicMock()
    m.W_SF = MagicMock(value=0)
    m.OutPw.value = out_w
    return m


def _failing(model_obj):
    model_obj.read.side_effect = OSError('timed out')
    return model_obj


def _use(ctrl, models):
    return patch.object(ctrl, 'get_model', side_effect=lambda n: models.get(n))


def _partial_warnings(caplog, model):
    return [r for r in caplog.records
            if r.levelno == logging.WARNING and f'Model {model}' in r.getMessage()]


class TestBatteryStatus:

    def test_m714_failure_is_reported(self, real_ctrl, caplog):
        with _use(real_ctrl, {713: _m713(), 714: _failing(_m714())}), \
             caplog.at_level(logging.DEBUG, logger='franklinwh_modbus.controller'):
            result = real_ctrl.read_battery_status()
        assert result['soc'] == 55
        assert result['partial'] == ['714']
        assert 'battery_power_w' not in result
        assert 'battery_state' not in result
        assert len(_partial_warnings(caplog, 714)) == 1
        assert 'Model 714' in real_ctrl.last_error

    def test_healthy_read_has_no_partial(self, real_ctrl):
        with _use(real_ctrl, {713: _m713(), 714: _m714(dcw=-1200)}):
            result = real_ctrl.read_battery_status()
        assert 'partial' not in result
        assert result['battery_power_w'] == -1200
        assert result['battery_state'] == 'Charging'

    def test_warning_is_rate_limited_and_recovery_logged(self, real_ctrl, caplog):
        failing = {713: _m713(), 714: _failing(_m714())}
        with caplog.at_level(logging.DEBUG, logger='franklinwh_modbus.controller'):
            with _use(real_ctrl, failing):
                real_ctrl.read_battery_status()
                real_ctrl.read_battery_status()
            assert len(_partial_warnings(caplog, 714)) == 1
            with _use(real_ctrl, {713: _m713(), 714: _m714()}):
                real_ctrl.read_battery_status()
        recovered = [r for r in caplog.records
                     if r.levelno == logging.WARNING and 'Model 714 read recovered' in r.getMessage()]
        assert len(recovered) == 1

    def test_partial_failure_does_not_count_as_link_failure(self, real_ctrl):
        with _use(real_ctrl, {713: _m713(), 714: _failing(_m714())}):
            real_ctrl.read_battery_status()
        assert real_ctrl.consecutive_failures == 0


class TestSolarStatus:

    def test_m714_failure_omits_battery_dc_instead_of_zero(self, real_ctrl):
        with _use(real_ctrl, {502: _m502(3000), 714: _failing(_m714())}), \
             patch.object(real_ctrl, '_read_extension_solar', return_value=None):
            result = real_ctrl.read_solar_status()
        assert result['partial'] == ['714']
        assert 'battery_dc_power_w' not in result
        assert 'dc_power_w' not in result
        assert result['ac_power_w'] == 3000

    def test_m502_failure_omits_ac_power_instead_of_zero(self, real_ctrl):
        with _use(real_ctrl, {502: _failing(_m502()), 714: _m714(dcw=800)}), \
             patch.object(real_ctrl, '_read_extension_solar', return_value=None):
            result = real_ctrl.read_solar_status()
        assert result['partial'] == ['502']
        assert 'ac_power_w' not in result
        assert result['battery_dc_power_w'] == 800

    def test_m502_failure_falls_back_to_extension_total(self, real_ctrl):
        with _use(real_ctrl, {502: _failing(_m502()), 714: _m714()}), \
             patch.object(real_ctrl, '_read_extension_solar', return_value={'total_solar': 2500}):
            result = real_ctrl.read_solar_status()
        assert result['partial'] == ['502']
        assert result['ac_power_w'] == 2500

    def test_healthy_read_has_no_partial(self, real_ctrl):
        with _use(real_ctrl, {502: _m502(3000), 714: _m714(dcw=0)}), \
             patch.object(real_ctrl, '_read_extension_solar', return_value=None):
            result = real_ctrl.read_solar_status()
        assert 'partial' not in result
        assert result['ac_power_w'] == 3000
        assert result['battery_dc_power_w'] == 0
