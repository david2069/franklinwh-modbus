# Connections, Threading and Reconnect: How the Library Behaves

*Recorded 2026-10-12. Written in answer to questions from the Local Bridge (fwh-local) and franklinwh-modbus-bridge sessions; the Q&A is logged below.*

This page describes what the code **does**, not a design. It comes from reading `controller.py` at tag `v0.9.5` and `develop` `8af8301`, and pysunspec2 1.3.3 (the version in this repo's venv). Nothing here was measured on hardware unless it says so. Line numbers are for `develop` unless marked.

The defects found are queued in the change-management queue (`docs/IN_FLIGHT_WORK.md`, local-only). None are fixed yet.

## Summary

| Question | Answer |
|---|---|
| Persistent connection? | No. pysunspec2 opens and closes a TCP connection per read and per write, except after a raw-socket call leaves one open. |
| How is a dead link detected? | Only when a call raises. No idle timeout, no heartbeat. |
| What does a reconnect cost? | A 1 s sleep, a new client and a full model rescan. |
| Thread-safe? | No. There is no lock around Modbus I/O. |
| Safe with the command timeout timer? | No. The timer writes M704 from its own thread without synchronisation. |
| aGate connection limit on :502? | Unknown. Never measured. |
| Two Modbus masters? | Not handled at the connection layer. |

## Usage guidance and limitations

*Added 2026-10-13. Applies to 1.x (synchronous, on pysunspec2). Each statement names its evidence: a code location, a check in `tools/repro_raw_vs_pysunspec2.py` (C1–C7, output under [Evidence: reproduction run](#evidence-reproduction-run)), a cited specification, or "not measured".*

### What 1.x is suited for

- The CLI, scripts, the TUI monitor and the virtual-mode loop.
- One `FranklinWHController` per aGate per process, with calls made **one at a time**.
- Polling at a moderate rate. No safe rate is given, because the aGate's connection limit on :502 has not been measured.

### Rules for callers, especially async ones

The bridges run the library from asyncio through `asyncio.to_thread`. That works within these limits:

| # | Rule | Evidence |
|---|---|---|
| 1 | **Serialise every call per gateway**, including `connect()` and `reconnect()`. The controller has no lock around Modbus I/O. | Code: [Locks](#locks) |
| 2 | **Every call blocks a worker thread for its whole duration**: up to two retries, `reconnect()` (1 s sleep plus a full rescan) and the pauses between writes in `send_command()`. `to_thread` runs on asyncio's default executor, a `ThreadPoolExecutor` whose default size is 32 or the CPU count plus 4, whichever is smaller, so a scheduler that starts many jobs at once fills it, and the calls queue behind the caller's lock rather than run in parallel. | Code: [Failure handling](#failure-handling-_with_retry), [reconnect()](#reconnect), [send_command() sequence](#send_command-sequence). Python docs: `asyncio.to_thread`, `concurrent.futures.ThreadPoolExecutor`. Call durations: not measured. |
| 3 | **Cancelling doesn't stop the call.** If `asyncio.wait_for()` or a scheduler cancels a `to_thread` call, only the await stops; the thread runs to the end. A `send_command()` cancelled partway still carries on writing to the device. Don't use cancellation to abort a dispatch. | Repro C7 |
| 4 | **Don't pass `duration_s` if you hold your own lock.** The timer it starts calls `reset_control_state()` from its own thread, outside the caller's lock. Use a watchdog in the caller instead. | Code: [The command timeout timer](#the-command-timeout-timer) |
| 5 | **Each call opens one or more TCP connections**, so polling faster means more connections opened and closed on the aGate. Whether that causes the "Response timeout" closes is not proven. | Repro C1, C2; table under [Reads and writes](#reads-and-writes). Effect on the aGate: not measured. |
| 6 | **One owner per aGate.** Nothing in the library coordinates separate processes. | Code: no cross-process mechanism exists |

### What the Modbus TCP specification recommends

Source: *MODBUS Messaging on TCP/IP Implementation Guide V1.0b*, Modbus Organization, 24 October 2006, https://www.modbus.org/file/secure/messagingimplementationguide.pdf (downloaded 2026-10-13).

| Guide | Text | 1.x today |
|---|---|---|
| §4.2.1.1, p.10, rule 2 | "It is recommended to keep the TCP connection opened with a remote device and not to open and close it for each MODBUS/TCP transaction." The client "must be capable of accepting a close request from the server". | pysunspec2 opens and closes per read and per write (C2). |
| §4.2.1.1, p.10, rule 3 | "It is recommended for a MODBUS Client to open a minimum of TCP connections with a remote MODBUS server … One connection per application could be a good choice." | pysunspec2 plus the raw paths, plus a second client in the bridge. |
| §4.2.1.1, p.12 | A server keeps a pool of connections for unlisted clients; when it is full, "close the oldest connection when a new connection request arrives". | Whether the aGate does this is not known. If it does, it could explain the peer-closed "Response timeout" errors: not proven. |
| §4.2.1.1 rule 4, p.10; p.23; §4.4.1.3, p.24 | The transaction identifier must be unique on a connection at a time; a response whose identifier matches no pending request "must be discarded". | pysunspec2 and the raw paths always send 0 and never check the reply's identifier. Safe only while one request is outstanding per connection. |

These are recommendations for implementers ("it is recommended"), not a conformance test.

### Why some integrations use raw Modbus TCP

A Modbus TCP request is a 7-byte header (MBAP) plus a short PDU (Guide §3.1.3, p.5). The framing is not where 1.x spends its effort. The extra connections come from pysunspec2's connection handling (C1, C2), and the extra time from the library's retry, reconnect and rescan logic. Sending frames on one long-lived socket avoids both, which is why some integrations go raw.

A raw client then owns what the libraries did: matching responses to requests, serialising, reconnecting, scale factors, enum values (`SUNSPEC_ENUM_BASIS.md`) and model addresses. Hardcoded model addresses break without any error if a firmware update moves the model map. The device behaviour (the M704 write sequence, pauses, verify, command timeout, orphan release) still has to live somewhere.

1.x mixes the two. See [Raw Modbus TCP alongside pysunspec2](#raw-modbus-tcp-alongside-pysunspec2).

### API 2.0 (modbus-connection)

See `MODBUS_CONNECTION_EVALUATION.md`, which cites the project's documentation; none of this has been tested here.

- One persistent link per process, with requests serialised, responses matched to requests, and typed errors. Plain register reads and writes go on the same link, so no second transport is needed.
- Async only. The CLI and tools would need a sync facade or would have to become async.
- Requests are serialised per process. Sharing an aGate between programs is the role of Modbus Bridge 2.0.
- Python >= 3.12; a young API that changes quickly. Pin versions.

## Connection lifecycle

### connect()

`connect()` (`controller.py:108`) creates a `SunSpecModbusClientDeviceTCP` (default timeout 10 s, unit id 2) and calls `scan(base_addr=self.base_address)`. pysunspec2's `scan(connect=True)` opens one TCP connection for the whole scan and **closes it** at the end.

### Reads and writes

After the scan, the client's socket is `None`. `ModbusClientTCP.read()` and `write()` (pysunspec2 `modbus.py:686-733`, `839-876`) open a connection if there is none, do the request, and close it in `finally` (`local_connect`). So every `model.read()` and `model.write()` is its own TCP connection:

| Call | Models read | TCP connections (approx.) |
|---|---|---|
| `read_battery_status()` | 713, 714 | 2 |
| `read_grid_status()` | 701 | 1 |
| `read_solar_status()` | 502, 714 | 2 |
| `read_control_status()` | 704, 715 | 2 |
| `send_command()` | 704 ×4 reads, 3 writes | about 7 |
| `is_connected()` | `dev.read(40071, 1)` | 1 |

**Exception:** the raw-socket paths (`read_native_mode()` and the extension-register helpers around lines 800, 945, 990, 1058, 1123) call `self.dev.client.connect()`, which closes any existing socket, opens a new one, and **leaves it open**. Later pysunspec2 reads see a socket and reuse it without closing it. Connection lifetime therefore depends on which calls ran last.

### Failure handling: `_with_retry()`

`_with_retry(operation, max_retries=2)` (`controller.py:433`):

1. Runs the operation.
2. On an exception it treats as a connection error, calls `reconnect()` once, then runs the operation once more.
3. Otherwise, or if `reconnect()` fails, it re-raises. Callers such as `send_command()` catch the exception and return `(False, message)`.

An exception counts as a connection error if it is a `ConnectionError` or `OSError`, **or its message contains** "broken pipe", "socket", "timeout", "connection" or "modbus". The "modbus" match includes pysunspec2's `ModbusClientException('Modbus exception N …')`, which is a **device reply** (an exception code), not a dead link. Such replies trigger a reconnect and a full rescan.

### reconnect()

`reconnect()` (`controller.py:370`): `disconnect()` (closes the client, sets `self.dev = None`), sleeps 1.0 s, creates a new client, calls `scan()` **without** `base_addr` (unlike `connect()`), and replaces `self.models`. Because the scan closes its socket, reads afterwards go back to one connection per call.

### What "Response timeout" means

In pysunspec2 1.3.3, `_read()` raises `ModbusClientTimeout('Response timeout')` when `socket.recv()` returns 0 bytes, which means **the other end closed the connection** before the full reply arrived (`modbus.py:659-667`). A real socket timeout surfaces as `ModbusClientTimeout("timed out")` (`modbus.py:728-729`). Treat "Response timeout" as a dropped connection.

## Raw Modbus TCP alongside pysunspec2

*Added 2026-10-13. Code read on `develop`. Behaviour checked against a local fake Modbus server and the gateway emulator (C1–C7, [Evidence: reproduction run](#evidence-reproduction-run)); not tested on the aGate.*

1.x reads and writes standard SunSpec models through pysunspec2. It reaches the FranklinWH extension registers (15000+, 15500+, 16000) by building Modbus TCP frames with `struct.pack` and sending them on pysunspec2's own socket (`self.dev.client.socket`).

| Where | What |
|---|---|
| `controller.py` | `_read_extension_solar()` (15500–15513, 16000), `read_native_mode()` (15507–15509), the 15507/15508/15509 setters, the helpers inside `test_extension_writability()` |
| `sequencer.py` | `read_value()` and `execute_writes()` for address-only tags such as `"15507"`; `write_value()` for those tags calls `client.write_hregs()` |
| `tools/` | `probe_15000.py`, `retest_historical_discoveries.py`, `franklinwh_control_standalone.py` |

### The recorded reason doesn't hold

The quirks doc, the Modbus guide, the verification baseline and the code comments all said pysunspec2 "remaps addresses" and so can't reach the extension registers. That is wrong:
- pysunspec2 1.3.3's `ModbusClientTCP.read(addr, count)` and `write(addr, data)` (`sunspec2/modbus/modbus.py:686`, `:839`) send `addr` unchanged.
- The search through base addresses 40000, 0 and 50000 happens only inside `scan()` (`sunspec2/modbus/client.py:199`, `:242`).
- **C3:** `client.read(15500, 14)` put address 15500 on the wire.

What is true is that the client has no `read_holding_registers()`, only `read()` and `write()`, which work in bytes.

Not shown: that the aGate answers `client.read(15500, 14)`. The original "Modbus exception 2" was not recorded with its request, so its cause is unknown.

### Consequences

| # | Finding | Evidence |
|---|---|---|
| 1 | **How connections behave depends on which call ran last.** The controller's raw helpers call `client.connect()` and leave the socket open, and pysunspec2 then reuses it instead of opening its own. | C4; code: [Reads and writes](#reads-and-writes) |
| 2 | **The sequencer's raw path only works if something else left a socket open.** `read_value()` and `execute_writes()` take the raw path only `if client.socket`, and the sequencer never connects. After `scan()` the socket is `None` (C1). The raw reads then return `None`, and the raw writes are skipped with no error logged. With `verify: false` the step logs `[SENT]` and `run_sequence` returns `True`. With `verify` on (the default), the step should fail at verification, but that case wasn't run. | C6; code: `sequencer.py:132`, `:372` |
| 3 | **`SunSpecSequencer.write_value()` for extension tags calls a method pysunspec2 doesn't have.** `client.write_hregs()` (`sequencer.py:195`, `:197`) raises `AttributeError`, which is logged at DEBUG, and nothing is written. The unit test (`tests/unit/test_sequencer_extensions.py:111`) mocks the method, so it passes. The CLI's `--sequence` path uses `execute_writes()`, not `write_value()`. | C5; code |
| 4 | **The raw frames are minimal.** They always use transaction id 0 and a single `recv(256)` with no check of the MBAP length field, and some paths check only the response length. The Implementation Guide (§4.4.1.3, p.24) expects responses to be matched to requests by transaction id. | Code: `controller.py:222`, `:807`, `:949`; `sequencer.py:136`, `:382` |

### Severity

These are design defects in how 1.x reaches the extension registers. They are **not** failures seen in the main control path:
- `send_command()` writes M704 through pysunspec2.
- The controller's raw helpers open their own socket before use (`controller.py:217`, `:801`, `:945`, `:989`, `:1058`, `:1123`).
- `send_command()` has been tested on hardware (`tests/results/2026-10-09_pr23_live.md`).

The silent-loss risk is in the sequencer (items 2 and 3), which the CLI's `--sequence` option uses. All four are queued for a fix. For 1.x the fix is one transport for every register; API 2.0 gets that from modbus-connection.

### Evidence: reproduction run

`tools/repro_raw_vs_pysunspec2.py` starts a fake Modbus TCP server on 127.0.0.1 that logs every connection and every request, then runs each check through pysunspec2 and the library's own code. With `--host`/`--port` it runs against another server instead (connection counts and writes then come from that server's log). Run 2026-10-13, pysunspec2 1.3.3, Python 3.14.3:

```text
pysunspec2 1.3.3, Python 3.14.3
C1: CONFIRMED — scan used 1 connection(s); client.socket after scan = None
C2: CONFIRMED — 3 model reads opened 3 connection(s); socket after = None
C3: CONFIRMED — client.read(15500, 14) sent [(3, 15500, 14)], got 28 bytes
C4: CONFIRMED — raw call + 3 model reads used 1 connection(s); socket left open = True
C5: CONFIRMED — hasattr(client, 'write_hregs') = False; write_value returned None; writes on the wire = []; log = [('DEBUG', "Raw write at 15508 failed: 'ModbusClientTCP' object has no attribute 'write_hregs'")]
C6: CONFIRMED — run_sequence returned True; writes on the wire = []; errors/warnings logged = []; info log = ['Starting sequence with 1 steps...', '\n--- [1/1] raw write, no socket ---', '  Writing 15508 = 25 [Raw: 25, Addr: 15508]', '  Write 15508: None -> 25 [SENT]', '\nSequence complete.']
C7: CONFIRMED — await outcome = cancelled; thread finished its work anyway = True

7/7 claims confirmed
```

Against the gateway emulator (127.0.0.1:5020, profile agate-v10r01b04d00), 2026-10-13 19:21:14–19:21:16 AEDT: the client-side results matched. The emulator session's harness, which logs every connection and request on the server side, recorded (franklinwh-gateway-emulator `tests/results/2026-10-13_fwh_modbus_c1_c6.md`, commit `d87bc2f`):

| Check | Server log |
|---|---|
| C1 | Connection 1: 65 fc3 reads. The probe at 40000×3 got exception 2, so the scan used base 0 and read up to 1126. Then disconnect. |
| C2 | Connections 2, 3 and 4: one fc3 at 2×68 each, then disconnect. |
| C3 | Connection 5: fc3 at 15500×14, then disconnect. |
| C4 | Connection 6: fc3 at 15507×3, then three fc3 at 2×68 on the same connection, then disconnect. |
| C5, C6 | No fc6 or fc16 anywhere in the log; no requests outside connections 1–6. |

Totals: 6 connections, 0 refused, 0 writes, 73 requests, 1 exception (the 40000 probe). 15507–15509 read [2, 20, 20] afterwards, unchanged.

Limits: neither server is the aGate. Device-side behaviour (its connection limit, whether it answers `client.read(15500, 14)`, how it closes connections) is not tested here.

## Threading

### Locks

The controller has one lock, `_command_timer_lock`, which guards only the `_command_timer` object (create, cancel, status). **No lock covers Modbus I/O**, `self.dev`, `self.models` or the model objects. pysunspec2 has no locking either.

### What can go wrong with concurrent calls

From the code, not observed:

- **Shared model objects.** Each model (e.g. M704) is one object holding point values and dirty flags. A `read()` on one thread can overwrite values another thread just set; a `write()` sends every dirty point, including points another thread set.
- **Shared socket.** If one thread opened a connection, a second thread sees it, uses it and does not close it. The first thread's `finally` then closes it under the second.
- **Replies can be mismatched.** pysunspec2 sends transaction id 0 and never checks the id in the reply. Two threads interleaving on one socket can each take the other's reply, which gives wrong values rather than an error.

### The command timeout timer

`send_command(..., duration_s>0)` starts `threading.Timer(duration_s, _on_timeout)` (`controller.py:1543-1552`; v0.9.5 `1491-1500`). On expiry, `_on_timeout` calls `reset_control_state()` **on the timer thread**:

- `reset_control_state()` reads M704; if WSetEna is 1 it writes WSetPct=0 and WSet=0 and sleeps 1 s; then writes WSetEna=0, WSetPct=0, WSet=0; sleeps 0.5 s; reads back. All of this runs through `_with_retry`, so it can also call `reconnect()`.
- Nothing serialises this against a send or a poll running on another thread. It can land between the steps of a `send_command()`.
- The timer is cancelled only at the start of `send_command()` (`controller.py:1513`). `reset_control_state()` does not cancel or clear it, and `Timer.cancel()` cannot stop a callback that has already started.

### reconnect() with another thread mid-call

- A thread in the middle of a read has its socket closed under it (an error, or `AttributeError` if the socket is already `None`).
- For the 1 s sleep, `self.dev` is `None` while `self.models` still holds the old models. `get_model()` returns those, and they can still open connections on the old client. Any `self.dev.client` path raises `AttributeError`, whose message matches none of the retry keywords, so it is not retried.
- Two threads that both fail can run `reconnect()` at the same time, each rescanning and replacing `self.dev` and `self.models`.

**Rule for callers today:** use one controller from one thread at a time, serialise every call (including anything that can run the timeout timer), and don't pass `duration_s` if calls are serialised by a lock the timer can't see.

## send_command() sequence

`_do_send` (`v0.9.5 controller.py:1438-1505`, same on develop):

1. `m704.read()`; WSetEna=0; `write()`; sleep 0.3 s
2. `read()`; WSetMod=0, WSetPct=−pct; `write()`; sleep 0.3 s
3. `read()`; WSetEna=1; `write()`; sleep 0.5 s
4. "VERIFY": `read()`, log the readback at DEBUG, return True

- `write()` sends only points changed since the last write (pysunspec2 dirty flags).
- Step 4 **does not check** the readback. `verify_dispatch()` (develop, unreleased) is the real check: it was hardware-tested on 2026-10-09 (`tests/results/2026-10-09_pr23_live.md`).
- A retry re-runs from step 1, so a failure late in a send stops the battery (WSetEna=0) again before re-enabling.

## What we have measured

| Item | Result | Source |
|---|---|---|
| Discharge ramp after a send | Full output within 2.1 s (the sampling interval) | `tests/results/2026-10-09_pr23_live.md`, T2 |
| Charge at 99% SoC | Setpoint accepted, 0 W delivered; `verify_dispatch` reported "battery not responding" | same file, T1 |
| :502 concurrent-connection limit | Not measured | — |
| Churn vs long-lived connections | Not measured | — |
| Latency baseline, scan cost | Not measured | — |

## Q&A log, 2026-10-12

### Local Bridge (fwh-local): connection management

The Local Bridge is designing pooled connections because three clients (the Local Bridge, franklinwh-modbus-bridge and Energipay) use the same aGate :502 without coordination.

| Question | Answer |
|---|---|
| Persistent or per call; how is a dead link detected? | Per call in practice (above). Detection only on exception. |
| aGate connection limit on :502? | No evidence; never measured. |
| Different behaviour under churn vs long-lived connections? | Not observed. |
| Two masters? | Not handled at the connection layer; no exclusive-use assumption. Control-layer only: orphaned-dispatch check on connect, and manual coordination of live tests. |

### franklinwh-modbus-bridge: dispatch-reliability design (bridge PR #57)

The bridge asked us to fact-check the library claims in its design. Results:

| Claim | Verdict |
|---|---|
| P1: send is three steps; a failure after step 1 can leave the battery stopped | Correct. Added: dirty-flag writes; a retry repeats WSetEna=0; about 7 TCP connections per send. |
| P2: step 4 never checks the readback | Correct. |
| P3: two attempts; reconnect can fail | Correct. Added: the "modbus" text match sends device exception replies into reconnect + rescan. Hypothesis (unverified) that this drives the bridge's 1,200–2,300 reconnects a day; the bridge tracks it as U9. |
| C3: reconnect does a full rescan | Correct. Added: `scan()` runs without `base_addr`, and the scan closes its socket. |
| P9: `verify_dispatch` not hardware-verified | Out of date: tested 2026-10-09. Still unreleased. |
| 10-12 18:00, "Response timeout" reported as success | The library returned `ok=False`. The "ok" audit was bridge-side. "Response timeout" means the connection was closed (above). |

Open questions U1–U7: we had data only for U6 (ramp ≤2.1 s for discharge) and one related data point for U7 (0 W charge at 99% SoC, not established as the cause of bridge #26).

### franklinwh-modbus-bridge: synchronous library vs async bridge

| Question | Answer |
|---|---|
| C11: does the timeout timer's `reset_control_state()` run outside the caller's lock and overlap other calls? | Yes, in v0.9.5 and develop. |
| Does the controller hold an internal lock? | Only for the timer object; none for I/O. |
| Is `reconnect()` safe while another thread is mid-read? | No (above). |

The bridge's response in its design: route every call through one per-gateway queue, stop passing `duration_s` and use its own watchdog, and count overlapping requests in its Phase 0b measurements.

### franklinwh-modbus-bridge: enum decoding

Reported 2026-10-12: the bridge's M713.Sta decoding (`_STA_MAP` with 3 = Error; `_M713_STA_NAMES` with charge-state names) doesn't match SunSpec DER Information Model V1.2, where 713.Sta is OK 0, WARNING 1, ERROR 2. Basis: `docs/SUNSPEC_ENUM_BASIS.md` (PR #30).

## Versions

- This repo's venv: pysunspec2 1.3.3. The bridge deploys 1.3.6. `pyproject.toml` requires `pysunspec2>=1.1.0`. The bridge confirmed the per-call connection behaviour in 1.3.6; the "Response timeout" meaning has not yet been confirmed there.
