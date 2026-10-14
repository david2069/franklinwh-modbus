"""
Regression test for #39: read_alarms() must fill 'decoded'.

It initialised 'decoded' to {} and never wrote to it, so --check-alarms
always printed Battery Status UNKNOWN and empty alarm lists. Names come
from the SunSpec model definitions shipped with pysunspec2: model 701
Alrm, model 714 DCAlrm (per port; PrtAlrms only flags which ports have
an alarm) and model 713 Sta.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    return c


def _pt(value):
    return SimpleNamespace(value=value)


def _models(alrm=0, prt_alrms=0, port_alrms=(), sta=0):
    m701 = SimpleNamespace(Alrm=_pt(alrm))
    m714 = SimpleNamespace(PrtAlrms=_pt(prt_alrms),
                           Prt=[SimpleNamespace(DCAlrm=_pt(a)) for a in port_alrms])
    m713 = SimpleNamespace(Sta=_pt(sta))
    return {701: m701, 713: m713, 714: m714}.get


def _read(ctrl, **kw):
    with patch.object(ctrl, 'get_model', side_effect=_models(**kw)):
        return ctrl.read_alarms()['decoded']


def test_no_alarms(ctrl):
    d = _read(ctrl)
    assert d == {'system': [], 'dc_port': [], 'battery_status': 'OK'}


def test_system_alarm_names_follow_model_701(ctrl):
    # bit 0 GROUND_FAULT, bit 5 CABINET_OPEN, bit 7 OVER_TEMP (model_701.json)
    d = _read(ctrl, alrm=(1 << 0) | (1 << 5) | (1 << 7))
    assert d['system'] == ['GROUND_FAULT', 'CABINET_OPEN', 'OVER_TEMP']


def test_undefined_system_bit_is_named_by_number(ctrl):
    assert _read(ctrl, alrm=1 << 30)['system'] == ['BIT_30']


def test_dc_port_alarms_name_the_port_and_its_dcalrm_bits(ctrl):
    # PrtAlrms bit 1 = second port; its DCAlrm bit 7 = OVER_TEMP (model_714.json)
    d = _read(ctrl, prt_alrms=1 << 1, port_alrms=(0, 1 << 7))
    assert d['dc_port'] == ['Port 1: OVER_TEMP']


def test_dc_port_flagged_without_port_detail(ctrl):
    d = _read(ctrl, prt_alrms=1 << 0, port_alrms=())
    assert d['dc_port'] == ['Port 0']


@pytest.mark.parametrize('sta, name', [
    (0, 'OK'), (1, 'WARNING'), (2, 'ERROR'), (6, 'UNDEFINED (6)'),
])
def test_battery_status_follows_model_713(ctrl, sta, name):
    assert _read(ctrl, sta=sta)['battery_status'] == name
