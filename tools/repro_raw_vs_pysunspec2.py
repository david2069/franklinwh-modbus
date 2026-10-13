#!/usr/bin/env python3
"""Reproduce how pysunspec2 and the library's raw-socket paths behave, against a
local fake Modbus TCP server. No aGate, no network beyond 127.0.0.1.

The fake server logs every TCP connection and every request (function code,
address, count), so each claim below is checked from what reached the wire.

    PYTHONPATH=src:. python3 tools/repro_raw_vs_pysunspec2.py
    PYTHONPATH=src:. python3 tools/repro_raw_vs_pysunspec2.py --host 127.0.0.1 --port 5020

With --host, no fake server is started and the script runs against that server
(e.g. the gateway emulator). Connection counts and writes on the wire can then
only be read from that server's own log, so those parts print "server log".

Claims checked (docs/CONNECTION_AND_THREADING.md, "Raw Modbus TCP alongside pysunspec2"):
  C1  scan() closes its socket; client.socket is None afterwards
  C2  each model.read() after scan opens and closes its own TCP connection
  C3  client.read(15500, n) sends address 15500 unchanged (no remapping)
  C4  after a raw helper calls client.connect(), pysunspec2 reuses that socket
  C5  pysunspec2's client has no write_hregs(); SunSpecSequencer.write_value()
      on an extension tag sends nothing
  C6  SunSpecSequencer raw writes with no open socket send nothing and log no error
  C7  cancelling an asyncio.to_thread() call (wait_for timeout) does not stop the thread
"""

import argparse
import asyncio
import importlib.metadata
import logging
import socket
import socketserver
import struct
import sys
import threading
import time

import sunspec2
import sunspec2.modbus.client as sclient

from franklinwh_modbus.sequencer import SunSpecSequencer

HOST, PORT, UNIT = "127.0.0.1", 15020, 1

# ── Register map: SunSpec header at 0, model 1 (len 66), end marker; extension block ──
REGS = {}
REGS[0], REGS[1] = 0x5375, 0x6E53            # "SunS"
REGS[2], REGS[3] = 1, 66                     # model 1, length 66
for i in range(66):
    REGS[4 + i] = 0
REGS[70], REGS[71] = 0xFFFF, 0               # end of map
for a in range(15500, 15514):
    REGS[a] = a - 15500                      # extension registers
REGS[16000] = 1234

EVENTS = []                                  # ("conn", n) / ("req", fc, addr, count)
LOCK = threading.Lock()


def log_event(*e):
    with LOCK:
        EVENTS.append(e)


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        log_event("conn", self.client_address[1])
        sock = self.request
        while True:
            hdr = sock.recv(7)
            if len(hdr) < 7:
                return
            tid, pid, length, unit = struct.unpack(">HHHB", hdr)
            pdu = sock.recv(length - 1)
            fc = pdu[0]
            if fc == 3:
                addr, count = struct.unpack(">HH", pdu[1:5])
                log_event("req", fc, addr, count)
                if all(addr + i in REGS for i in range(count)):
                    data = b"".join(struct.pack(">H", REGS[addr + i]) for i in range(count))
                    resp = bytes([3, len(data)]) + data
                else:
                    resp = bytes([0x83, 2])  # illegal data address
            elif fc == 6:
                addr, val = struct.unpack(">HH", pdu[1:5])
                log_event("req", fc, addr, 1)
                REGS[addr] = val
                resp = pdu[:5]
            elif fc == 16:
                addr, count = struct.unpack(">HH", pdu[1:5])
                log_event("req", fc, addr, count)
                vals = struct.unpack(f">{count}H", pdu[6:6 + 2 * count])
                for i, v in enumerate(vals):
                    REGS[addr + i] = v
                resp = pdu[:5]
            else:
                resp = bytes([fc | 0x80, 1])
            sock.sendall(struct.pack(">HHHB", tid, 0, len(resp) + 1, unit) + resp)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def snapshot():
    with LOCK:
        return len(EVENTS)


def since(mark):
    with LOCK:
        return EVENTS[mark:]


EXTERNAL = False


def conns(evts):
    if EXTERNAL:
        return None
    return sum(1 for e in evts if e[0] == "conn")


def reqs(evts, fc=None):
    if EXTERNAL:
        return []
    return [e[1:] for e in evts if e[0] == "req" and (fc is None or e[1] == fc)]


def settle():
    time.sleep(0.2)


def new_device():
    return sclient.SunSpecModbusClientDeviceTCP(slave_id=UNIT, ipaddr=HOST, ipport=PORT, timeout=2)


def main():
    global EXTERNAL, HOST, PORT, UNIT
    ap = argparse.ArgumentParser()
    ap.add_argument("--host")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--unit", type=int, default=1)
    args = ap.parse_args()
    srv = None
    if args.host:
        EXTERNAL, HOST, PORT, UNIT = True, args.host, args.port, args.unit
        print(f"target {HOST}:{PORT} unit {UNIT} (external; connection counts and wire writes: server log)")
    else:
        srv = Server((HOST, PORT), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"target fake server {HOST}:{PORT}")
    print(f"start {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    results = []

    def check(cid, ok, detail):
        results.append((cid, ok, detail))
        print(f"{cid}: {'CONFIRMED' if ok else 'NOT CONFIRMED'} — {detail}")

    print(f"pysunspec2 {importlib.metadata.version('pysunspec2')}, Python {sys.version.split()[0]}")

    # C1
    dev = new_device()
    m = snapshot()
    dev.scan()
    settle()
    e = since(m)
    check("C1", dev.client.socket is None and conns(e) in (1, None),
          f"scan used {conns(e)} connection(s); client.socket after scan = {dev.client.socket!r}")

    # C2
    m = snapshot()
    for _ in range(3):
        dev.models[1][0].read()
    settle()
    e = since(m)
    check("C2", conns(e) in (3, None) and dev.client.socket is None,
          f"3 model reads opened {conns(e)} connection(s); socket after = {dev.client.socket!r}")

    # C3
    m = snapshot()
    data = dev.client.read(15500, 14)
    settle()
    e = since(m)
    check("C3", (EXTERNAL or reqs(e, 3) == [(3, 15500, 14)]) and len(data) == 28,
          f"client.read(15500, 14) sent {reqs(e, 3)}, got {len(data)} bytes")

    # C4: what the controller's raw helpers do (controller.py read_native_mode etc.)
    m = snapshot()
    dev.client.connect()
    sock = dev.client.socket
    sock.sendall(struct.pack(">HHHBBHH", 0, 0, 6, UNIT, 3, 15507, 3))
    sock.recv(256)
    for _ in range(3):
        dev.models[1][0].read()
    settle()
    e = since(m)
    check("C4", conns(e) in (1, None) and dev.client.socket is not None,
          f"raw call + 3 model reads used {conns(e)} connection(s); socket left open = {dev.client.socket is not None}")
    dev.client.disconnect()

    # C5
    has = hasattr(dev.client, "write_hregs")
    seq = SunSpecSequencer(dev)
    caught = []

    class Capture(logging.Handler):
        def emit(self, rec):
            caught.append((rec.levelname, rec.getMessage()))

    cap = Capture(level=logging.DEBUG)
    slog = logging.getLogger("franklinwh_modbus.sequencer")
    slog.addHandler(cap)
    slog.setLevel(logging.DEBUG)
    m = snapshot()
    ret = seq.write_value("15508", 25)
    settle()
    e = since(m)
    check("C5", (not has) and not reqs(e, 6) and not reqs(e, 16),
          f"hasattr(client, 'write_hregs') = {has}; write_value returned {ret!r}; "
          f"writes on the wire = {reqs(e, 6) + reqs(e, 16)}; log = {[c for c in caught if '15508' in c[1]]}")

    # C6
    caught.clear()
    dev.client.disconnect()
    m = snapshot()
    ok = seq.run_sequence([{"name": "raw write, no socket", "writes": {"15508": 25}, "verify": False}])
    settle()
    e = since(m)
    errors = [c for c in caught if c[0] in ("ERROR", "WARNING")]
    check("C6", not reqs(e, 6) and not reqs(e, 16) and not errors,
          f"run_sequence returned {ok}; writes on the wire = {reqs(e, 6) + reqs(e, 16)}; "
          f"errors/warnings logged = {errors}; info log = {[c[1] for c in caught if c[0] == 'INFO']}")

    # C7: a blocking call cancelled from asyncio keeps running in its thread
    finished = threading.Event()

    def blocking_call():
        time.sleep(1.0)          # stands in for a send_command() mid-sequence
        finished.set()

    async def cancel_it():
        try:
            await asyncio.wait_for(asyncio.to_thread(blocking_call), timeout=0.2)
        except asyncio.TimeoutError:
            return "cancelled"
        return "completed"

    outcome = asyncio.run(cancel_it())
    ran_on = finished.wait(timeout=3)
    check("C7", outcome == "cancelled" and ran_on,
          f"await outcome = {outcome}; thread finished its work anyway = {ran_on}")

    print(f"end {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    if srv:
        srv.shutdown()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} claims confirmed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
