"""on_error / retry / cleanup handling in SunSpecSequencer (#101)."""
from unittest.mock import MagicMock

import pytest
from sunspec2.modbus.modbus import ModbusClientException, ModbusClientTimeout

from franklinwh_modbus.sequencer import SunSpecSequencer, WriteRejected, _classify


def make_seq(outcomes):
    """Sequencer whose _run_step pops one outcome per call: True/False or an exception."""
    seq = SunSpecSequencer(MagicMock())
    calls = []

    def run_step(step, dry_run):
        calls.append(step.get('step'))
        out = outcomes.pop(0) if outcomes else True
        if isinstance(out, BaseException):
            raise out
        return out
    seq._run_step = run_step
    return seq, calls


def test_classify():
    assert _classify(ModbusClientException('Modbus exception 3')) == ('rejected', 3)
    assert _classify(ModbusClientException('Modbus exception: 2')) == ('rejected', 2)
    assert _classify(WriteRejected(4)) == ('rejected', 4)
    assert _classify(ModbusClientTimeout('Response timeout'))[0] == 'transport'
    assert _classify(ConnectionError())[0] == 'transport'
    assert _classify(ValueError())[0] == 'error'


def test_rejection_aborts_but_cleanup_runs():
    seq, calls = make_seq([True, ModbusClientException('Modbus exception 3'), True, True])
    ok = seq.run_sequence({"steps": [{"step": "a"}, {"step": "b"}, {"step": "c"}],
                           "cleanup": [{"step": "restore"}]})
    assert not ok
    assert calls == ["a", "b", "restore"]
    assert ("b", "REJECTED (exc 3)") in seq.results
    assert ("c", "SKIPPED (abort)") in seq.results
    assert ("restore", "CLEANUP OK") in seq.results


def test_continue_goes_on_after_rejection():
    seq, calls = make_seq([ModbusClientException('Modbus exception 3'), True])
    ok = seq.run_sequence([{"step": "probe", "on_error": "continue"}, {"step": "next"}])
    assert not ok
    assert calls == ["probe", "next"]


def test_retry_only_for_transport_errors():
    seq, calls = make_seq([ModbusClientTimeout('Response timeout'), True])
    assert seq.run_sequence([{"step": "t", "on_error": "retry", "retries": 2, "retry_ms": 0}])
    assert calls == ["t", "t"]

    seq, calls = make_seq([ModbusClientException('Modbus exception 3'), True])
    assert not seq.run_sequence([{"step": "r", "on_error": "retry", "retries": 2, "retry_ms": 0}])
    assert calls == ["r"]  # a rejection is never retried (#96)


def test_retries_exhausted_aborts():
    seq, calls = make_seq([ModbusClientTimeout('x')] * 3)
    ok = seq.run_sequence({"steps": [{"step": "t", "on_error": "retry", "retries": 1, "retry_ms": 0},
                                     {"step": "after"}], "cleanup": [{"step": "restore"}]})
    assert not ok
    assert calls == ["t", "t", "restore"]


def test_verify_failure_keeps_abort_on_failure_flag():
    seq, calls = make_seq([False, True])
    seq.run_sequence([{"step": "v", "abort_on_failure": False}, {"step": "next"}])
    assert calls == ["v", "next"]
    seq, calls = make_seq([False, True])
    seq.run_sequence([{"step": "v"}, {"step": "next"}])
    assert calls == ["v"]


def test_cleanup_failure_does_not_stop_cleanup():
    seq, calls = make_seq([True, ModbusClientException('Modbus exception 3'), True])
    ok = seq.run_sequence({"steps": [{"step": "a"}],
                           "cleanup": [{"step": "r1"}, {"step": "r2"}]})
    assert not ok
    assert calls == ["a", "r1", "r2"]


def test_interrupt_runs_cleanup():
    seq, calls = make_seq([KeyboardInterrupt(), True])
    ok = seq.run_sequence({"steps": [{"step": "a"}, {"step": "b"}],
                           "cleanup": [{"step": "restore"}]})
    assert not ok
    assert calls == ["a", "restore"]


def test_plain_list_still_works():
    seq, calls = make_seq([True, True])
    assert seq.run_sequence([{"step": "a"}, {"step": "b"}])
    assert calls == ["a", "b"]


def test_raw_write_exception_response_raises_rejected():
    device = MagicMock()
    device.slave_id = 1
    sock = MagicMock()
    device.client.socket = sock
    import struct
    sock.recv.side_effect = [
        struct.pack('>HHHBBB', 0, 0, 5, 1, 3, 2) + struct.pack('>H', 0),   # before-read
        struct.pack('>HHHBBB', 0, 0, 3, 1, 0x86, 3),                       # FC06 exception 3
    ]
    seq = SunSpecSequencer(device)
    with pytest.raises(WriteRejected) as ei:
        seq.execute_writes({"15600": 1}, {}, dry_run=False)
    assert ei.value.code == 3
