"""Unit tests for tools/m704_setpoint_probe.py, against a fake Modbus client (no network)."""
import importlib.util
import json
import os
from types import SimpleNamespace

import pytest

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "m704_setpoint_probe.py")
_spec = importlib.util.spec_from_file_location("m704_setpoint_probe", _PATH)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


class _Resp:
    def __init__(self, regs=None, exc=None):
        self.registers = regs or []
        self.exception_code = exc

    def isError(self):
        return self.exception_code is not None


class FakeAGate:
    """Holds a register map; refuses WSetPct writes above `limit` with exception 3."""

    def __init__(self, limit=100, sf=-1):
        self.regs = {a: 0 for a in range(0, 1200)}
        self.regs[probe.WSET_PCT_SF] = sf & 0xFFFF
        self.regs[probe.M713_SOC] = 990
        vr = b"V12R02B60D00\x00\x00\x00\x00"
        for i in range(8):
            self.regs[probe.M1_VR + i] = (vr[2 * i] << 8) | vr[2 * i + 1]
        self.limit = limit
        self.writes = []

    def read_holding_registers(self, addr, count, device_id):
        return _Resp([self.regs[a] for a in range(addr, addr + count)])

    def write_register(self, addr, value, device_id):
        self.writes.append((addr, value))
        if addr == probe.WSET_PCT and abs(probe.s16(value)) > self.limit:
            return _Resp(exc=3)
        self.regs[addr] = value
        if addr == probe.WSET_ENA:
            pct = probe.s16(self.regs[probe.WSET_PCT])
            self.regs[probe.M714_DCW] = (pct * 5 if value else 0) & 0xFFFF
        return _Resp()


def _args(**kw):
    base = dict(values=[100, 110], repeat=1, hold=0.01, gap=0.0, interval=0.0, min_soc=20.0,
                expect_sf=-1, force=False)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(probe.time, "sleep", lambda s: None)


def _log(tmp_path):
    return probe.CappedLog(str(tmp_path / "out.jsonl"), 10**7, 60, echo=lambda s: None)


def test_accepted_and_refused_values_are_recorded(tmp_path):
    fake = FakeAGate(limit=100)
    log = _log(tmp_path)
    results = probe.run_probe(probe.Device(fake, 1), log, _args())
    log.close()
    assert [r["raw"] for r in results] == [100, 110]
    assert results[0]["accepted"] and results[0]["latched"] and results[0]["exception"] is None
    assert not results[1]["accepted"] and results[1]["exception"] == 3
    assert results[0]["dcw_median_w"] == 500


def test_every_step_ends_released(tmp_path):
    fake = FakeAGate(limit=100)
    log = _log(tmp_path)
    probe.run_probe(probe.Device(fake, 1), log, _args(values=[100, 500, -100]))
    log.close()
    assert fake.regs[probe.WSET_ENA] == 0 and fake.regs[probe.WSET_PCT] == 0
    events = [json.loads(l)["event"] for l in open(tmp_path / "out.jsonl")]
    assert events.count("release") == 3


def test_refused_write_stops_sequence_before_enable(tmp_path):
    fake = FakeAGate(limit=100)
    log = _log(tmp_path)
    probe.run_probe(probe.Device(fake, 1), log, _args(values=[200]))
    log.close()
    # WSetEna=0, WSetMod=0, WSetPct=200 (refused), then the release writes; never WSetEna=1
    assert (probe.WSET_ENA, 1) not in fake.writes


def test_aborts_when_another_client_is_in_control(tmp_path):
    fake = FakeAGate()
    fake.regs[probe.WSET_ENA] = 1
    log = _log(tmp_path)
    assert probe.run_probe(probe.Device(fake, 1), log, _args()) == []
    log.close()
    assert fake.writes == []


def test_aborts_on_unexpected_scale_factor(tmp_path):
    fake = FakeAGate(sf=0)
    log = _log(tmp_path)
    assert probe.run_probe(probe.Device(fake, 1), log, _args()) == []
    log.close()
    assert fake.writes == []


def test_discharge_skipped_below_min_soc(tmp_path):
    fake = FakeAGate()
    fake.regs[probe.M713_SOC] = 150  # 15.0 %
    log = _log(tmp_path)
    results = probe.run_probe(probe.Device(fake, 1), log, _args(values=[100, -100]))
    log.close()
    assert [r["raw"] for r in results] == [-100]


def test_size_cap_stops_the_run(tmp_path):
    fake = FakeAGate()
    log = probe.CappedLog(str(tmp_path / "out.jsonl"), 200, 60, echo=lambda s: None)
    probe.run_observe(probe.Device(fake, 1), log, 0.0)
    log.close()
    assert log.stop_reason == "max-bytes reached"


def test_firmware_read_and_no_ip_in_output(tmp_path):
    fake = FakeAGate()
    log = _log(tmp_path)
    probe.run_probe(probe.Device(fake, 1), log, _args(values=[10]))
    log.close()
    text = open(tmp_path / "out.jsonl").read()
    assert '"firmware":"V12R02B60D00"' in text
    assert "192." not in text


def test_link_loss_releases_and_stops_writing(tmp_path):
    fake = FakeAGate()
    real_read = fake.read_holding_registers
    calls = {"n": 0}

    def flaky(addr, count, device_id):
        calls["n"] += 1
        if calls["n"] > 12:  # link drops after the first step's reads
            raise ConnectionError("no route")
        return real_read(addr, count, device_id)
    fake.read_holding_registers = flaky
    log = _log(tmp_path)
    probe.run_probe(probe.Device(fake, 1), log, _args(values=[100, 50, 10], hold=0.05))
    log.close()
    assert log.stop_reason.startswith("link lost")
    assert (probe.WSET_PCT, 50) not in fake.writes and (probe.WSET_PCT, 10) not in fake.writes
    assert fake.writes[-2:] == [(probe.WSET_ENA, 0), (probe.WSET_PCT, 0)]


def test_dry_run_and_max_raw_never_connect(capsys):
    assert probe.main(["-i", "192.0.2.1", "probe", "--values", "100,110"]) == 0
    assert "Dry run" in capsys.readouterr().out
    assert probe.main(["-i", "192.0.2.1", "probe", "--values", "2000", "--execute"]) == 2
