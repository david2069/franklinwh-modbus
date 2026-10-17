"""
Regression test for #38: a battery ERROR must block operation.

check_blocking_alarms() tested M713 Sta == 6, which SunSpec does not define.
model_713.json (pysunspec2 1.3.3) defines Sta as 0 OK, 1 WARNING, 2 ERROR,
so a battery reporting ERROR never raised BATTERY_FAULT.
"""
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    return c


def _models(sta):
    m701 = MagicMock()
    m701.Alrm.value = 0
    m714 = MagicMock()
    m714.PrtAlrms.value = 0
    m713 = MagicMock()
    m713.Sta.value = sta
    return {701: m701, 713: m713, 714: m714}.get


@pytest.mark.parametrize('sta, can_operate', [
    (0, True),     # OK
    (1, True),     # WARNING: logged, not blocking
    (2, False),    # ERROR: blocks
    (None, True),  # not implemented
])
def test_battery_sta_blocking(ctrl, sta, can_operate):
    with patch.object(ctrl, 'get_model', side_effect=_models(sta)):
        ok, reasons = ctrl.check_blocking_alarms()
    assert ok is can_operate
    assert ('BATTERY_FAULT' in reasons) is (not can_operate)


def test_battery_warning_is_logged(ctrl, caplog):
    with patch.object(ctrl, 'get_model', side_effect=_models(1)):
        ctrl.check_blocking_alarms()
    assert 'WARNING' in caplog.text and 'M713' in caplog.text


def test_undefined_value_6_no_longer_blocks(ctrl):
    # 6 is not a SunSpec 713 Sta value; it must not be treated as ERROR
    with patch.object(ctrl, 'get_model', side_effect=_models(6)):
        ok, reasons = ctrl.check_blocking_alarms()
    assert ok and 'BATTERY_FAULT' not in reasons
