"""Opt-in record of every Modbus write the library sends (#124).

A caller passes ``write_trace=callback`` to FranklinWHController (or
SunSpecSequencer); the callback gets one WriteRecord per write, with the
aGate's reply. Storage, display and attribution are the caller's job: the
library only passes ``source`` through.

Every record is also logged at DEBUG on the ``franklinwh_modbus.writes`` logger.
"""
import logging
import re
import struct
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

logger = logging.getLogger('franklinwh_modbus.writes')

_EXC_RE = re.compile(r'Modbus exception:?\s*(\d+)')


@dataclass(frozen=True)
class WriteRecord:
    """One Modbus write and the aGate's reply.

    ok is True only for a normal write response. A Modbus exception sets
    exception_code; any other failure (short response, socket error) sets error.
    """
    timestamp: float                  # epoch seconds (UTC)
    address: int                      # PDU address
    function: int                     # 6 (one register) or 16 (several)
    values: Tuple[int, ...]           # raw uint16 register values as sent
    ok: bool
    exception_code: Optional[int] = None
    error: Optional[str] = None
    point: Optional[str] = None       # e.g. '704.WSetPct' when known
    firmware: Optional[str] = None    # M1 Vr when known
    source: Optional[str] = None      # caller-supplied, passed through unchanged

    def describe(self) -> str:
        values = ' '.join(f'0x{v:04X}' for v in self.values)
        if self.ok:
            reply = 'OK'
        elif self.exception_code is not None:
            reply = f'exception {self.exception_code}'
        else:
            reply = f'error: {self.error}'
        name = f' {self.point}' if self.point else ''
        fw = f', firmware {self.firmware}' if self.firmware else ''
        src = f', source {self.source}' if self.source else ''
        return f"Modbus write FC{self.function:02d} {self.address}{name} [{values}] -> {reply}{fw}{src}"


def regs_from_bytes(data: bytes) -> Tuple[int, ...]:
    n = len(data) // 2
    return struct.unpack(f'>{n}H', data[:n * 2])


def exception_code_from(e: Exception) -> Optional[int]:
    """Modbus exception code from a pysunspec2 exception message, if any."""
    m = _EXC_RE.search(str(e))
    return int(m.group(1)) if m else None


def reply_from_response(resp: bytes, function: int) -> Tuple[bool, Optional[int], Optional[str]]:
    """(ok, exception_code, error) from a raw Modbus TCP write response."""
    if len(resp) >= 9 and resp[7] == (function | 0x80):
        return False, resp[8], None
    if len(resp) >= 12 and resp[7] == function:
        return True, None, None
    return False, None, f'short or invalid response (len={len(resp)})'


def emit(callback: Optional[Callable[[WriteRecord], None]], address: int, function: int,
         values: Sequence[int], ok: bool, exception_code: Optional[int] = None,
         error: Optional[str] = None, point: Optional[str] = None,
         firmware: Optional[str] = None, source: Optional[str] = None) -> WriteRecord:
    """Build a record, log it at DEBUG and pass it to the callback.

    A callback that raises is logged at WARNING; it never affects the write.
    """
    rec = WriteRecord(time.time(), address, function, tuple(int(v) for v in values), ok,
                      exception_code, error, point, firmware, source)
    logger.debug(rec.describe())
    if callback is not None:
        try:
            callback(rec)
        except Exception as e:
            logger.warning(f"write_trace callback raised {e!r}; the write itself is unaffected")
    return rec
