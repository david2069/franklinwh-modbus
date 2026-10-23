"""
send_command uses the M704 watts path (WSetMod=1 + WSet), not WSetPct.

V12R02B60D00 refuses WSetPct above 10 % with exception 3, so a 5000 W
Force Discharge sent as WSetPct=100 % never ran (bridge log 2026-10-23,
116 refusals). WSetMod=1 + WSet=5000 delivered 4900-5000 W, 3 of 3 runs
(docs/SUNSPEC_M704_V12_CONFORMANCE_RESULTS.md, c8).

Also #96: a Modbus exception response is a refusal, so _with_retry must
not reconnect and resend.
"""
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController, BatteryCommand
from franklinwh_modbus.controller import ModbusClientException


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    c.RATED_MAX_CHARGE_W = 5000
    c.RATED_MAX_DISCHARGE_W = 5000
    return c


class Recorder:
    """M704 stand-in that records the point values at every write()."""

    def __init__(self, ena=0, mod=0, wset=0):
        self.WSet_SF = MagicMock(value=0)
        self.WSetPct_SF = MagicMock(value=-1)
        self.WSetEna = MagicMock(value=ena)
        self.WSetMod = MagicMock(value=mod)
        self.WSet = MagicMock(value=wset)
        self.WSetPct = MagicMock(value=0)
        self.writes = []

    def read(self):
        pass

    def write(self):
        self.writes.append((self.WSetEna.value, self.WSetMod.value, self.WSet.value))


def _send(ctrl, m704, watts, **kw):
    with patch.object(ctrl, 'get_model', return_value=m704), \
         patch('franklinwh_modbus.controller.time.sleep'):
        return ctrl.send_command(BatteryCommand(power_watts=watts), **kw)


def test_discharge_5000_uses_wset_not_wsetpct(ctrl):
    m704 = Recorder()
    ok, msg = _send(ctrl, m704, -5000)
    assert ok, msg
    # setpoint first, then enable; hardware WSet positive = discharge
    assert m704.writes == [(0, 1, 5000), (1, 1, 5000)]
    assert m704.WSetPct.value == 0


def test_no_enable_cycling_when_already_enabled(ctrl):
    m704 = Recorder(ena=1, mod=1, wset=1000)
    ok, msg = _send(ctrl, m704, -2000)
    assert ok, msg
    assert m704.writes == [(1, 1, 2000)]  # no WSetEna=0, no enable rewrite


def test_readback_mismatch_reports_failure(ctrl):
    m704 = Recorder()
    m704.read = lambda: setattr(m704.WSetEna, 'value', 0)
    ok, msg = _send(ctrl, m704, -1000)
    assert not ok
    assert 'not applied' in msg


def test_dry_run_writes_nothing(ctrl):
    m704 = Recorder()
    ok, msg = _send(ctrl, m704, -5000, dry_run=True)
    assert ok and 'WSet=5000' in msg
    assert m704.writes == []


def test_rejection_is_not_retried(ctrl):
    m704 = Recorder()

    def refuse():
        raise ModbusClientException('Modbus exception: 3')

    m704.write = refuse
    with patch.object(ctrl, 'reconnect') as reconnect:
        ok, msg = _send(ctrl, m704, 500)
    assert not ok
    assert 'Rejected by the aGate' in msg
    reconnect.assert_not_called()


def test_transport_error_still_reconnects(ctrl):
    calls = []

    def op():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError('socket closed')
        return 'ok'

    with patch.object(ctrl, 'reconnect', return_value=True) as reconnect:
        assert ctrl._with_retry(op) == 'ok'
    reconnect.assert_called_once()


# --------------------------------------------- real pysunspec2 frame check

class _FakeDev:
    """Register store under a real pysunspec2 M704; logs every Modbus write."""

    def __init__(self):
        self.regs = {296: 704, 297: 67}
        self.writes = []

    def is_connected(self):
        return True

    def read(self, addr, count, max_count=None):
        import struct
        return b''.join(struct.pack('>H', self.regs.get(addr + i, 0)) for i in range(count))

    def write(self, addr, data, write_scan_offset=None):
        import struct
        vals = struct.unpack('>%dH' % (len(data) // 2), data)
        self.writes.append((addr, vals))
        for i, v in enumerate(vals):
            self.regs[addr + i] = v


def test_mod_and_wset_go_in_one_frame(ctrl):
    sunspec_client = pytest.importorskip('sunspec2.modbus.client')
    dev = _FakeDev()
    m704 = sunspec_client.SunSpecModbusClientModel(
        model_id=704, model_addr=296, model_len=67, data=dev.read(296, 69), mb_device=dev)
    ok, msg = _send(ctrl, m704, -5000)
    assert ok, msg
    # 319 WSetMod, 320-321 WSet (int32): one FC16; then 318 WSetEna on its own
    assert dev.writes == [(319, (1, 0, 5000)), (318, (1,))]
