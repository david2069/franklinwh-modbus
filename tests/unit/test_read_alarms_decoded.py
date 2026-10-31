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
    assert d['dc_port'] == ['Port 2: OVER_TEMP']


def test_dc_port_flagged_without_port_detail(ctrl):
    d = _read(ctrl, prt_alrms=1 << 0, port_alrms=())
    assert d['dc_port'] == ['Port 1']


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
    assert d['dc_port'] == ['Port 1: GROUND_FAULT', 'Port 1: OVER_TEMP',
                            'Port 3: BLOWN_FUSE']


def test_port_status_warning_or_error_is_reported(ctrl):
    # Prt.DCSta 0 OFF, 1 ON, 2 WARNING, 3 ERROR (model_714.json)
    d = _read(ctrl, port_alrms=(0, 0), port_sta=[3, 2])
    assert d['dc_port'] == ['Port 1: status ERROR', 'Port 2: status WARNING']


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


def test_ports_are_numbered_from_one_like_individual_batteries(ctrl):
    # First port (bit 0, Prt[0]) is "Port 1", matching
    # read_battery_status()['individual_batteries'][0]['port'] == 1.
    assert _read(ctrl, prt_alrms=0b1, port_alrms=(1 << 7,))['dc_port'] == ['Port 1: OVER_TEMP']


def test_failed_read_is_reported_not_silent(ctrl, caplog):
    # A failed read must not look like "no alarms".
    import logging
    models = _models()
    models[701].read.side_effect = OSError('timed out')
    with patch.object(ctrl, 'get_model', side_effect=models.get), \
         caplog.at_level(logging.DEBUG, logger='franklinwh_modbus.controller'):
        alarms = ctrl.read_alarms()
    assert 'timed out' in alarms['error']
    assert ctrl.consecutive_failures == 1
    assert any(r.levelno == logging.WARNING and 'Failed to read alarms' in r.getMessage()
               for r in caplog.records)


def test_successful_read_has_no_error(ctrl):
    models = _models()
    with patch.object(ctrl, 'get_model', side_effect=models.get):
        assert 'error' not in ctrl.read_alarms()


def _real_m701(text):
    """A real pysunspec2 model 701 with MnAlrmInfo set from raw registers (#136)."""
    import struct
    import sunspec2.device as dev
    points = dev.get_model_def(701)['group']['points']
    off = 2 + sum(p['size'] for p in points[2:[p['name'] for p in points].index('MnAlrmInfo')])
    regs = [701, dev.Model(model_id=701).len] + [0] * dev.Model(model_id=701).len
    raw = text.encode().ljust(32, b'\0')
    regs[off:off + 16] = struct.unpack('>16H', raw)
    m = dev.Model(model_id=701, model_addr=0, model_len=regs[1],
                  data=struct.pack(f'>{len(regs)}H', *regs))
    m.read = MagicMock()
    return m


@pytest.mark.parametrize('text, info', [
    ('Manufacturer custom error info', ''),     # V10R01B04D00 and V12R02B60D00, always
    ('E042 relay', 'E042 relay'),
])
def test_placeholder_vendor_text_is_not_reported(ctrl, text, info):
    models = _models()
    models[701] = _real_m701(text)
    assert models[701].MnAlrmInfo.value == text
    with patch.object(ctrl, 'get_model', side_effect=models.get):
        alarms = ctrl.read_alarms()
    assert alarms['vendor_info'] == info
    assert alarms['decoded']['vendor_info'] == info
    assert alarms['vendor_info_raw'] == text
    assert ctrl.active_alarms(alarms) == []
