"""Find SunSpec Modbus devices — FranklinWH aGates in particular — on a network.

Read-only: nothing here writes a register. Promoted from
``tools/network_scanner.py`` so other projects (a setup wizard, a CLI) can
discover an aGate through this library instead of re-implementing Modbus I/O.

Two entry points:

* :func:`probe` — one host: is Modbus TCP open, and is it a SunSpec device
  whose first model is the Common model (1)? If so, what does the nameplate say.
* :func:`scan` — a subnet: a fast TCP check on every host, then :func:`probe`
  only the ones that answer.

Only SunSpec-compliant devices are identified. Anything else listening on the
port is reported as ``unknown``. A FranklinWH Modbus device is a SunSpec device
that returns model 1 with a manufacturer string containing "FranklinWH"
(:attr:`DiscoveryResult.is_franklinwh`).

A probe connects, reads as little as it can (two requests), and disconnects.
"""

from __future__ import annotations

import inspect
import ipaddress
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence

from pymodbus.client import ModbusTcpClient

#: Where the SunSpec chain may start. 0 first: FranklinWH aGates (and several
#: inverters) put it there; 40000 is the canonical SunSpec default.
SUNSPEC_BASES: tuple = (0, 40000, 50000, 30000)

#: The SunSpec marker "SunS" as two holding registers.
SUNSPEC_MARKER = b"SunS"

#: SunSpec Common model ID — must be the first model after the marker.
COMMON_MODEL_ID = 1

# Common model (1) layout, as offsets from the SunSpec base. The marker takes
# two registers, then model id and length; the nameplate strings follow.
_HEADER_COUNT = 4              # SunS (2) + model id + model length
_NAMEPLATE_OFFSET = 4
_NAMEPLATE_COUNT = 64          # Mn(16) Md(16) Opt(8) Vr(8) SN(16) — one read
_FIELDS = {                    # name: (offset within the nameplate read, length)
    "manufacturer": (0, 16),
    "model": (16, 16),
    "version": (40, 8),
    "serial": (48, 16),
}

# Statuses a probe can report.
SUNSPEC = "sunspec"            # SunSpec marker + Common model (1) found
UNKNOWN = "unknown"            # Something listens on the port, but not a SunSpec device
CLOSED = "closed"              # TCP port not open / unreachable


@dataclass
class DiscoveryResult:
    """What a probe found at one host."""

    host: str
    port: int
    status: str
    base_address: Optional[int] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    version: Optional[str] = None
    response_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def is_franklinwh(self) -> bool:
        """A SunSpec device returning model 1 whose manufacturer names FranklinWH."""
        return self.status == SUNSPEC and "franklinwh" in (self.manufacturer or "").lower()

    @property
    def summary(self) -> str:
        """One line for a person, e.g. in a scan list."""
        if self.status == SUNSPEC:
            who = " ".join(x for x in (self.manufacturer, self.model) if x) or "SunSpec device"
            return f"{who} at {self.host}:{self.port}"
        if self.status == UNKNOWN:
            return f"Unknown device listening on TCP port {self.port} at {self.host}"
        return f"Nothing listening on TCP port {self.port} at {self.host}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_franklinwh"] = self.is_franklinwh
        d["summary"] = self.summary
        return d


# ── pymodbus compatibility ──────────────────────────────────────────────────

def _unit_kwarg() -> str:
    """The keyword pymodbus uses for the Modbus unit id.

    It was ``slave=`` through most of 3.x and is ``device_id=`` from 3.10; the
    package declares ``pymodbus>=3.0``, so support both.
    """
    params = inspect.signature(ModbusTcpClient.read_holding_registers).parameters
    for name in ("device_id", "slave", "unit"):
        if name in params:
            return name
    return "device_id"


_UNIT_KW = _unit_kwarg()


def _read(client: Any, address: int, count: int, unit_id: int):
    return client.read_holding_registers(address, count=count, **{_UNIT_KW: unit_id})


def _registers_to_str(registers: Sequence[int]) -> str:
    raw = b"".join(struct.pack(">H", r & 0xFFFF) for r in registers)
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()


# ── single host ─────────────────────────────────────────────────────────────

def port_open(host: str, port: int = 502, timeout: float = 0.3) -> bool:
    """TCP connect check. Opens and closes a socket; sends nothing."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe(
    host: str,
    port: int = 502,
    unit_id: int = 1,
    timeout: float = 2.0,
    attempts: int = 1,
    bases: Iterable[int] = SUNSPEC_BASES,
    retry_backoff_s: float = 0.3,
    client_factory: Optional[Callable[..., Any]] = None,
) -> DiscoveryResult:
    """Identify the device at ``host:port`` — read-only.

    Tries each SunSpec base in turn for the ``SunS`` marker followed by the
    Common model (1) and, on a match, reads its nameplate in a single request.
    Status is ``sunspec`` only then; anything else listening is ``unknown``,
    with the reason in ``error``. If the host gives no Modbus answer at all on
    a base, the remaining bases are skipped for that attempt: they would only
    time out too.

    ``attempts`` > 1 retries the whole sequence, for a device that is slow or
    briefly busy. ``client_factory`` is for tests.
    """
    make_client = client_factory or ModbusTcpClient
    bases = tuple(bases)
    start = time.monotonic()
    answered = False      # any Modbus response at all (even an error)
    last_error: Optional[str] = None
    reason: Optional[str] = None   # why an answering device isn't SunSpec

    def elapsed_ms() -> float:
        return round((time.monotonic() - start) * 1000, 1)

    for attempt in range(max(1, attempts)):
        for base in bases:
            client = make_client(host, port=port, timeout=timeout, retries=0)
            try:
                if not client.connect():
                    if not answered and attempt == 0 and base == bases[0]:
                        return DiscoveryResult(host, port, CLOSED, response_time_ms=elapsed_ms())
                    last_error = "connect failed"
                    break
                try:
                    rr = _read(client, base, _HEADER_COUNT, unit_id)
                except Exception as exc:  # timeout / connection dropped: no answer
                    last_error = str(exc) or type(exc).__name__
                    break
                if rr is None:
                    last_error = "no response"
                    break
                answered = True
                if rr.isError():
                    continue  # e.g. illegal data address: try the next base
                regs = list(getattr(rr, "registers", []) or [])
                if len(regs) >= 2 and struct.pack(">HH", regs[0] & 0xFFFF, regs[1] & 0xFFFF) == SUNSPEC_MARKER:
                    model_id = regs[2] if len(regs) > 2 else None
                    if model_id == COMMON_MODEL_ID:
                        return _with_nameplate(client, host, port, base, unit_id, elapsed_ms)
                    reason = f"SunSpec marker at {base}, but first model is {model_id}, not {COMMON_MODEL_ID}"
            finally:
                client.close()
        if attempt < attempts - 1:
            time.sleep(retry_backoff_s)

    if answered:
        error = reason or "Modbus reply, but no SunSpec marker at any base"
    else:
        error = f"no Modbus reply ({last_error})" if last_error else "no Modbus reply"
    return DiscoveryResult(host, port, UNKNOWN, response_time_ms=elapsed_ms(), error=error)


def _with_nameplate(client, host, port, base, unit_id, elapsed_ms) -> DiscoveryResult:
    result = DiscoveryResult(host, port, SUNSPEC, base_address=base)
    try:
        rr = _read(client, base + _NAMEPLATE_OFFSET, _NAMEPLATE_COUNT, unit_id)
        if rr is not None and not rr.isError():
            regs = list(rr.registers)
            for name, (off, length) in _FIELDS.items():
                setattr(result, name, _registers_to_str(regs[off:off + length]) or None)
    except Exception as exc:  # marker found; nameplate unreadable is still a find
        result.error = f"nameplate: {exc}"
    result.response_time_ms = elapsed_ms()
    return result


# ── subnet ──────────────────────────────────────────────────────────────────

def scan(
    subnet: str,
    port: int = 502,
    unit_id: int = 1,
    workers: int = 64,
    connect_timeout: float = 0.3,
    probe_timeout: float = 2.0,
    attempts: int = 1,
    max_hosts: int = 254,
    allow_public: bool = False,
    on_result: Optional[Callable[[DiscoveryResult], None]] = None,
    client_factory: Optional[Callable[..., Any]] = None,
    port_check: Optional[Callable[[str, int, float], bool]] = None,
) -> List[DiscoveryResult]:
    """Find Modbus/SunSpec devices on ``subnet`` (e.g. ``"192.168.1.0/24"``).

    A TCP check on ``port`` runs against every host in parallel; only hosts
    with the port open are probed. Returns those results (never ``closed``
    ones), sorted by address. ``on_result`` is called as each one completes,
    for progress reporting.

    Refuses public address space unless ``allow_public`` (Tailscale's
    100.64.0.0/10, for instance, is not "private"), and more than ``max_hosts``
    hosts.
    """
    net = ipaddress.ip_network(subnet, strict=False)
    if net.version != 4:
        raise ValueError("only IPv4 subnets can be scanned")
    if not allow_public and not net.is_private:
        raise ValueError(f"{net} is not a private range (pass allow_public=True to scan it)")
    hosts = [str(h) for h in net.hosts()] or [str(net.network_address)]
    if len(hosts) > max_hosts:
        raise ValueError(f"{net} has {len(hosts)} hosts; the limit is {max_hosts}")

    check = port_check or port_open
    found: List[DiscoveryResult] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        open_hosts = [
            h for h, is_open in zip(hosts, pool.map(lambda h: check(h, port, connect_timeout), hosts))
            if is_open
        ]
        futures = [
            pool.submit(probe, h, port, unit_id, probe_timeout, attempts,
                        client_factory=client_factory)
            for h in open_hosts
        ]
        for fut in as_completed(futures):
            res = fut.result()
            if res.status == CLOSED:  # closed between the check and the probe
                continue
            found.append(res)
            if on_result is not None:
                on_result(res)
    return sorted(found, key=lambda r: ipaddress.ip_address(r.host))
