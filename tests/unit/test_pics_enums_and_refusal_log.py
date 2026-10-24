"""#114 A1 and A4.

A1: PICS_ENUMS used 1-based values (1 DISABLED, 2 ENABLED; InvSt 1 OFF ...).
SunSpec 2 model JSON (pysunspec2) defines them 0-based, and the aGate reads
WSetEna 1 when enabled.
A4: a Modbus exception response from the aGate was raised to the caller but
never logged. It is now logged at WARNING with the refused frame.
"""
import json
import logging
import os
from unittest.mock import MagicMock, patch

import pytest
import sunspec2

from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.constants import PICS_ENUMS, get_pics_enum_desc
from franklinwh_modbus.controller import ModbusClientException

MODEL_DIR = os.path.join(os.path.dirname(sunspec2.__file__), 'models', 'json')


def _spec_symbols():
    for mid, points in PICS_ENUMS.items():
        with open(os.path.join(MODEL_DIR, f'model_{mid}.json')) as f:
            group = json.load(f)['group']
        spec = {p['name']: p for p in group.get('points', [])}
        for name, mapping in points.items():
            p = spec.get(name)
            if p and 'symbols' in p:
                yield mid, name, mapping, {s['value']: s['name'] for s in p['symbols']}


@pytest.mark.parametrize('mid,name,mapping,symbols',
                         list(_spec_symbols()), ids=lambda v: str(v) if not isinstance(v, dict) else '')
def test_enum_matches_sunspec(mid, name, mapping, symbols):
    assert mapping == symbols


def test_known_device_values():
    assert get_pics_enum_desc(704, 'WSetEna', 1) == 'ENABLED'
    assert get_pics_enum_desc(704, 'PFWInjEna', 1) == 'ENABLED'
    assert get_pics_enum_desc(701, 'InvSt', 3) == 'RUNNING'
    assert get_pics_enum_desc(701, 'InvSt', 7) == 'STANDBY'


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    m1 = MagicMock()
    m1.Vr.value = 'V12R02B60D00'
    c.models = {1: m1}
    return c


def _refuse(addr, data):
    raise ModbusClientException('Modbus exception: 3')


def test_write_refusal_logged_with_frame(ctrl, caplog):
    ctrl.dev.write = _refuse
    ctrl._track_writes()
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'), \
            pytest.raises(ModbusClientException, match='Rejected by the aGate'):
        ctrl._with_retry(lambda: ctrl.dev.write(40324, b'\xff\xce'))
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert msgs == ['Refused by the aGate: write to register 40324 [0xFFCE] '
                    '-> Modbus exception: 3, firmware V12R02B60D00']


def test_read_refusal_logged_without_stale_write(ctrl, caplog):
    ctrl.dev.write = _refuse
    ctrl._track_writes()
    with pytest.raises(ModbusClientException):
        ctrl._with_retry(lambda: ctrl.dev.write(40324, b'\xff\xce'))
    caplog.clear()

    def read():
        raise ModbusClientException('Modbus exception 2: addr: 50000 count: 1')
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'), \
            pytest.raises(ModbusClientException):
        ctrl._with_retry(read)
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert msgs == ['Refused by the aGate: read -> Modbus exception 2: addr: 50000 count: 1, '
                    'firmware V12R02B60D00']


def test_accepted_write_not_logged(ctrl, caplog):
    ctrl.dev.write = lambda addr, data: None
    ctrl._track_writes()
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ctrl._with_retry(lambda: ctrl.dev.write(40324, b'\x00\x64'))
    assert not [r for r in caplog.records if 'Refused' in r.getMessage()]
