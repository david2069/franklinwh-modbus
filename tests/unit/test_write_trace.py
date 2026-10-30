"""Opt-in write-trace hook: one record per write, with the aGate's reply (#124)."""
import logging
import struct
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController, WriteRecord
from franklinwh_modbus.sequencer import SunSpecSequencer


class FakeModbusException(Exception):
    pass


def _ctrl(records, raw_responses=()):
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1', write_trace=records.append)
    ctrl.dev = MagicMock()
    ctrl.dev.client.socket.recv.side_effect = list(raw_responses)
    m704 = MagicMock(model_addr=318, points={'WSetEna': MagicMock(offset=0), 'WSetPct': MagicMock(offset=6)})
    m1 = MagicMock(Vr=MagicMock(value='V12R02B60D00'))
    ctrl.models = {704: [m704], 1: [m1]}
    return ctrl


def _wrap(ctrl, side_effect=None):
    ctrl.dev.write = MagicMock(side_effect=side_effect)
    ctrl._track_writes()


def test_model_write_ok_recorded():
    recs = []
    ctrl = _ctrl(recs)
    _wrap(ctrl)
    ctrl.write_source = 'schedule:abc'
    ctrl.dev.write(324, struct.pack('>H', 100))
    (r,) = recs
    assert isinstance(r, WriteRecord)
    assert (r.address, r.function, r.values, r.ok) == (324, 6, (100,), True)
    assert r.point == '704.WSetPct' and r.firmware == 'V12R02B60D00' and r.source == 'schedule:abc'
    assert r.exception_code is None and r.error is None


def test_model_write_exception_recorded_and_reraised():
    recs = []
    ctrl = _ctrl(recs)
    _wrap(ctrl, FakeModbusException('Modbus exception: 3'))
    with pytest.raises(FakeModbusException):
        ctrl.dev.write(324, struct.pack('>H', 0xFF9C))
    (r,) = recs
    assert (r.ok, r.exception_code, r.error, r.values) == (False, 3, None, (0xFF9C,))


def test_multi_register_write_is_fc16():
    recs = []
    ctrl = _ctrl(recs)
    _wrap(ctrl)
    ctrl.dev.write(318, struct.pack('>3H', 1, 0, 500))
    assert recs[0].function == 16 and recs[0].values == (1, 0, 500) and recs[0].point == '704.WSetEna'


def test_raw_extension_write_recorded():
    recs = []
    ack = struct.pack('>HHHBBHH', 0, 0, 6, 1, 6, 15508, 20)
    read = struct.pack('>HHHBBBH', 0, 0, 5, 1, 3, 2, 8)
    ctrl = _ctrl(recs, [ack, read])
    with patch('franklinwh_modbus.controller.time.sleep'):
        ctrl.set_self_consumption_reserve(20)
    (r,) = recs   # the read-back is not a write
    assert (r.address, r.function, r.values, r.ok, r.point) == (15508, 6, (20,), True, None)


def test_raw_refusal_recorded():
    recs = []
    exc = struct.pack('>HHHBBB', 0, 0, 3, 1, 0x86, 2)
    ctrl = _ctrl(recs, [exc])
    ctrl.set_native_mode(3)
    assert (recs[0].ok, recs[0].exception_code) == (False, 2)


def test_raw_short_response_recorded():
    recs = []
    ctrl = _ctrl(recs, [b'\x00\x00'])
    ctrl.set_tou_reserve(15)
    assert recs[0].ok is False and recs[0].exception_code is None and 'len=2' in recs[0].error


def test_clear_alarms_records_both_writes():
    recs = []
    ack = lambda v: struct.pack('>HHHBBHH', 0, 0, 6, 1, 6, 1094, v)
    ctrl = _ctrl(recs, [ack(1), ack(0)])
    with patch('franklinwh_modbus.controller.time.sleep'):
        ctrl.clear_alarms()
    assert [(r.address, r.values, r.ok) for r in recs] == [(1094, (1,), True), (1094, (0,), True)]


def test_callback_error_does_not_break_write(caplog):
    def boom(_):
        raise RuntimeError('store full')
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1', write_trace=boom)
    ctrl.dev = MagicMock()
    ctrl.models = {}
    _wrap(ctrl)
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.writes'):
        ctrl.dev.write(324, struct.pack('>H', 1))
    assert 'write_trace callback raised' in caplog.text


def test_debug_log_without_callback(caplog):
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1')
    ctrl.dev = MagicMock()
    ctrl.models = {}
    _wrap(ctrl)
    with caplog.at_level(logging.DEBUG, logger='franklinwh_modbus.writes'):
        ctrl.dev.write(324, struct.pack('>H', 100))
    assert 'Modbus write FC06 324 [0x0064] -> OK' in caplog.text


@pytest.mark.parametrize('reg_type,raw,func,values', [
    ('uint16', 7, 6, (7,)),
    ('int32', -2, 16, (0xFFFF, 0xFFFE)),
])
def test_sequencer_raw_write_recorded(reg_type, raw, func, values):
    recs = []
    seq = SunSpecSequencer(MagicMock(slave_id=1), write_trace=recs.append)
    sock = MagicMock()
    sock.recv.return_value = struct.pack('>HHHBBHH', 0, 0, 6, 1, func, 40000, 2 if func == 16 else raw & 0xFFFF)
    assert seq._raw_write(sock, 40000, raw, reg_type)
    (r,) = recs
    assert (r.address, r.function, r.values, r.ok) == (40000, func, values, True)
