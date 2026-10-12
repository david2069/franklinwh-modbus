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
