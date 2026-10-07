"""franklinwh_modbus.discovery — read-only SunSpec discovery, without hardware.

A fake Modbus client stands in for the network: it serves a register map,
answers "illegal address" elsewhere, or stays silent, so every probe outcome
can be exercised.
"""

from __future__ import annotations

import struct

import pytest

from franklinwh_modbus import discovery as d


def _str_regs(text: str, length: int) -> list:
    raw = text.encode().ljust(length * 2, b"\x00")[: length * 2]
    return [struct.unpack(">H", raw[i:i + 2])[0] for i in range(0, len(raw), 2)]


def sunspec_map(base: int, manufacturer="FranklinWH Technologies Co., Ltd",
                model="aGate X", version="V10R01B04D00", serial="10060006A01234") -> dict:
    """Register map with a SunSpec marker and Common model at ``base``."""
    regs = {base: 0x5375, base + 1: 0x6E53, base + 2: 1, base + 3: 66}
    nameplate = (_str_regs(manufacturer, 16) + _str_regs(model, 16) + [0] * 8
                 + _str_regs(version, 8) + _str_regs(serial, 16))
    for i, r in enumerate(nameplate):
        regs[base + 4 + i] = r
    return regs


class _Resp:
    def __init__(self, registers=None, error=False):
        self.registers = registers or []
        self._error = error

    def isError(self):
        return self._error


class FakeClient:
    """Mimics pymodbus' ModbusTcpClient for one fake device."""

    instances: list = []

    def __init__(self, device: dict, host, port=502, timeout=3, retries=0):
        self.device = device
        self.reads: list = []
        self.closed = False
        FakeClient.instances.append(self)

    def connect(self):
        return self.device.get("connect", True)

    def close(self):
        self.closed = True

    def read_holding_registers(self, address, count=1, **unit):
        self.reads.append((address, count, unit))
        if self.device.get("silent"):
            raise TimeoutError("no response")
        regs = self.device.get("regs", {})
        if address not in regs:
            return _Resp(error=True)  # illegal data address
        return _Resp([regs.get(a, 0) for a in range(address, address + count)])


def factory(device: dict):
    FakeClient.instances = []
    return lambda host, **kw: FakeClient(device, host, **kw)


def test_agate_at_base_zero():
    res = d.probe("10.0.0.5", client_factory=factory({"regs": sunspec_map(0)}))
    assert res.status == d.SUNSPEC
    assert res.base_address == 0
    assert res.is_franklinwh
    assert (res.manufacturer, res.model, res.serial, res.version) == (
        "FranklinWH Technologies Co., Ltd", "aGate X", "10060006A01234", "V10R01B04D00")
    # Marker read + ONE nameplate read: minimal time on the aGate's single session.
    reads = [r[:2] for c in FakeClient.instances for r in c.reads]
    assert reads == [(0, 2), (4, 64)]
    assert all(c.closed for c in FakeClient.instances)


def test_falls_back_to_40000_after_an_illegal_address():
    res = d.probe("10.0.0.5", client_factory=factory({"regs": sunspec_map(40000)}))
    assert res.status == d.SUNSPEC and res.base_address == 40000


def test_other_sunspec_device_is_found_but_not_franklinwh():
    regs = sunspec_map(0, manufacturer="SolarEdge", model="SE10K")
    res = d.probe("10.0.0.6", client_factory=factory({"regs": regs}))
    assert res.status == d.SUNSPEC and not res.is_franklinwh


def test_modbus_device_without_sunspec():
    res = d.probe("10.0.0.7", client_factory=factory({"regs": {}}))
    assert res.status == d.NOT_SUNSPEC


def test_open_port_but_no_modbus_answer_is_reported_distinctly():
    """What an aGate looks like while another client holds its session."""
    res = d.probe("10.0.0.8", client_factory=factory({"silent": True}))
    assert res.status == d.NO_RESPONSE
    # Silent on the first base → don't wait out a timeout on every other base.
    assert sum(len(c.reads) for c in FakeClient.instances) == 1


def test_closed_port():
    res = d.probe("10.0.0.9", client_factory=factory({"connect": False}))
    assert res.status == d.CLOSED


def test_attempts_retry_the_sequence():
    res = d.probe("10.0.0.8", attempts=3, retry_backoff_s=0,
                  client_factory=factory({"silent": True}))
    assert res.status == d.NO_RESPONSE
    assert len(FakeClient.instances) == 3


def test_unit_id_is_passed_with_the_installed_pymodbus_keyword():
    d.probe("10.0.0.5", unit_id=7, client_factory=factory({"regs": sunspec_map(0)}))
    unit = FakeClient.instances[0].reads[0][2]
    assert unit == {d._UNIT_KW: 7}
    assert d._UNIT_KW in ("device_id", "slave", "unit")


# ── scan ────────────────────────────────────────────────────────────────────

def test_scan_probes_only_open_hosts_and_sorts_results():
    open_hosts = {"192.168.50.10", "192.168.50.2"}
    seen = []
    results = d.scan(
        "192.168.50.0/24",
        port_check=lambda h, p, t: h in open_hosts,
        client_factory=lambda host, **kw: FakeClient({"regs": sunspec_map(0)}, host, **kw),
        on_result=seen.append,
        workers=8,
    )
    assert [r.host for r in results] == ["192.168.50.2", "192.168.50.10"]
    assert all(r.is_franklinwh for r in results)
    assert len(seen) == 2


def test_scan_refuses_public_ranges_unless_allowed():
    with pytest.raises(ValueError, match="not a private range"):
        d.scan("8.8.8.0/24", port_check=lambda *a: False)
    # Tailscale's CGNAT range is not "private" either — allowed when asked.
    assert d.scan("100.64.0.0/30", allow_public=True, port_check=lambda *a: False) == []


def test_scan_refuses_more_than_max_hosts():
    with pytest.raises(ValueError, match="limit is 254"):
        d.scan("10.0.0.0/23", port_check=lambda *a: False)


def test_scan_rejects_ipv6():
    with pytest.raises(ValueError, match="IPv4"):
        d.scan("fd00::/120", port_check=lambda *a: False)
