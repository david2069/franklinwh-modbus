"""Extension writes log a refusal or a read-back that differs (#114 A5)."""
import logging
import struct
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController


def _ctrl(responses):
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1')
    ctrl.dev = MagicMock()
    ctrl.dev.client.socket.recv.side_effect = responses
    ctrl.get_model = lambda n: MagicMock(Vr=MagicMock(value='V12R02B60D00')) if n == 1 else None
    return ctrl


def _ack(reg, val):
    return struct.pack('>HHHBBHH', 0, 0, 6, 1, 6, reg, val)


def _read(val):
    return struct.pack('>HHHBBBH', 0, 0, 5, 1, 3, 2, val)


SETTERS = [
    ('set_native_mode', 15507, 3, 2),
    ('set_self_consumption_reserve', 15508, 20, 8),
    ('set_tou_reserve', 15509, 20, 15),
]


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch('franklinwh_modbus.controller.time.sleep'):
        yield


@pytest.mark.parametrize('method,reg,val,stays', SETTERS)
def test_not_applied_logged(caplog, method, reg, val, stays):
    ctrl = _ctrl([_ack(reg, val), _read(stays)])
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ok, _ = getattr(ctrl, method)(val)
    assert not ok
    assert (f"Extension write not applied: register {reg} wrote {val}, "
            f"read back {stays}, firmware V12R02B60D00") in caplog.text


@pytest.mark.parametrize('method,reg,val,stays', SETTERS)
def test_applied_not_warned(caplog, method, reg, val, stays):
    ctrl = _ctrl([_ack(reg, val), _read(val)])
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ok, _ = getattr(ctrl, method)(val)
    assert ok
    assert 'Extension write' not in caplog.text


@pytest.mark.parametrize('method,reg,val,stays', SETTERS)
def test_refusal_logged(caplog, method, reg, val, stays):
    exc = struct.pack('>HHHBBB', 0, 0, 3, 1, 0x86, 2)
    ctrl = _ctrl([exc])
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ok, _ = getattr(ctrl, method)(val)
    assert not ok
    assert (f"Refused by the aGate: write to register {reg} [0x{val:04X}] "
            f"-> Modbus exception: 2, firmware V12R02B60D00") in caplog.text


@pytest.mark.parametrize('method,reg,val,stays', SETTERS)
def test_short_readback_logged(caplog, method, reg, val, stays):
    ctrl = _ctrl([_ack(reg, val), b'\x00\x00'])
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ok, _ = getattr(ctrl, method)(val)
    assert not ok
    assert f"Extension write to register {reg} ({val}): read-back failed (len=2)" in caplog.text
