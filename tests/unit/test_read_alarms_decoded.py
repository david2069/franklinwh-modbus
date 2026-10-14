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


def _model(**points):
    m = SimpleNamespace(**points)
    m.read = MagicMock()
    return m


def _models(alrm=0, prt_alrms=0, port_alrms=(), port_sta=None, sta=0,
            evt=0, vendor=None, with_502=True):
    m701 = _model(Alrm=_pt(alrm), MnAlrmInfo=_pt(vendor))
    sta_list = port_sta or [1] * len(port_alrms)
    m714 = _model(PrtAlrms=_pt(prt_alrms),
                  Prt=[SimpleNamespace(DCAlrm=_pt(a), DCSta=_pt(st))
                       for a, st in zip(port_alrms, sta_list)])
    m713 = _model(Sta=_pt(sta))
    models = {701: m701, 713: m713, 714: m714}
    if with_502:
        models[502] = _model(Evt=_pt(evt))
    return models


def _read(ctrl, **kw):
    models = _models(**kw)
    with patch.object(ctrl, 'get_model', side_effect=models.get):
        return ctrl.read_alarms()['decoded']


def test_no_alarms(ctrl):
    d = _read(ctrl)
    assert d == {'system': [], 'dc_port': [], 'solar': [], 'battery_status': 'OK',
                 'vendor_info': ''}


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


def test_several_system_and_solar_alarms_are_all_listed(ctrl):
    # model_502.json Evt: bit 0 GROUND_FAULT, bit 3 DC_DISCONNECT
    d = _read(ctrl, alrm=(1 << 0) | (1 << 12) | (1 << 16), evt=(1 << 0) | (1 << 3))
    assert d['system'] == ['GROUND_FAULT', 'BLOWN_STRING_FUSE', 'MANUFACTURER_ALRM']
    assert d['solar'] == ['GROUND_FAULT', 'DC_DISCONNECT']


def test_several_ports_each_with_several_alarms(ctrl):
    d = _read(ctrl, prt_alrms=0b101, port_alrms=((1 << 0) | (1 << 7), 0, 1 << 12))
    assert d['dc_port'] == ['Port 0: GROUND_FAULT', 'Port 0: OVER_TEMP',
                            'Port 2: BLOWN_FUSE']


def test_port_status_warning_or_error_is_reported(ctrl):
    # Prt.DCSta 0 OFF, 1 ON, 2 WARNING, 3 ERROR (model_714.json)
    d = _read(ctrl, port_alrms=(0, 0), port_sta=[3, 2])
    assert d['dc_port'] == ['Port 0: status ERROR', 'Port 1: status WARNING']


def test_vendor_alarm_text_is_reported(ctrl):
    assert _read(ctrl, vendor='E042 relay')['vendor_info'] == 'E042 relay'


def test_no_model_502(ctrl):
    assert _read(ctrl, with_502=False)['solar'] == []


def test_refresh_reads_the_models(ctrl):
    models = _models()
    with patch.object(ctrl, 'get_model', side_effect=models.get):
        ctrl.read_alarms()
    assert all(m.read.called for m in models.values())


def test_refresh_false_uses_the_last_read(ctrl):
    models = _models()
    with patch.object(ctrl, 'get_model', side_effect=models.get):
        ctrl.read_alarms(refresh=False)
    assert not any(m.read.called for m in models.values())
