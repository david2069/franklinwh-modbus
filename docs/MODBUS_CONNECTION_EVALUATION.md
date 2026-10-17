# modbus-connection: Evaluation for a Forked Version

*Recorded 2026-10-12. Status: direction set for API 2.0 (2026-10-12).*

## Decision

**Direction set by the owner on 2026-10-12:**

- **FranklinWH Modbus API 2.0** will be based on this library (franklinwh-modbus 1.x) as its model, and built on **modbus-connection** as the transport.
- **FranklinWH Modbus Bridge 2.0** will use FranklinWH Modbus API 2.0, and is to be the **single owner of the aGate's Modbus connection**, shared by the other bridges.
- **The Energipays bridge** will likely be forked as well, and its fork would use FranklinWH Modbus API 2.0.
- **franklinwh-modbus 1.x is not rewritten.** The connection and threading defects in the current library (see `CONNECTION_AND_THREADING.md`) stay queued and are fixed in the current design.

This follows the bridge's recommendation below, which proposed modbus-connection as the transport inside a franklinwh-modbus successor rather than a bridge-only switch, and only after measurement.

Still to decide: the name of the 2.0 package and its repository, the timing, whether 2.0 keeps a synchronous facade for the CLI and tools, and whether the Energipays fork goes ahead.

**Sharing the aGate is the role of Modbus Bridge 2.0.** modbus-connection serialises requests within one process only, so it can't stop separate programs competing for the aGate's port 502. Modbus Bridge 2.0 is to be the single owner of the aGate connection, which the other bridges share through it. Still to decide: how other clients, such as Energipays, reach the aGate through Bridge 2.0 (for example a Modbus TCP proxy that API 2.0 clients connect to, or Bridge 2.0's REST/MQTT interfaces).

## What modbus-connection is

A small, backend-neutral Modbus client abstraction from the Open Home Foundation's `home-assistant-libs` organisation. One `ModbusConnection` owns the link, and `for_unit(n)` hands out per-unit handles. An optional `model` framework maps registers to typed fields, and it has SunSpec support.

| Item | Value (checked 2026-10-12) |
|---|---|
| Repository | https://github.com/home-assistant-libs/modbus-connection |
| Documentation | https://home-assistant-libs.github.io/modbus-connection/ |
| Licence | Apache-2.0 |
| Created | 2026-06-23 |
| Latest release | 4.12.4 (2026-10-09) |
| Python | >= 3.12 |
| API style | asyncio only |
| Backends | pymodbus (>= 3.11) or tmodbus (>= 0.6.1), as install extras |

### Source review

balloob, *Evaluating modbus-connection against real-world Python Modbus libraries* (2026-07-02): https://gist.github.com/balloob/b9fa91ba1a0914a9787f8f6ceb637b83

- It surveys about 60 Modbus projects for how well they'd fit modbus-connection.
- It rates **franklinwh-modbus "Friction"**: "auto-reconnect, inter-write sleeps + watchdog + read-back-verify".
- It treats our write-then-read-back verify, and keepalive/watchdog duties in general, as the device library's responsibility, not as gaps in modbus-connection.
- It lists **pysunspec2** (our current SunSpec layer) as "Blocked" for migration: "own transport + richer dynamic model".
- At the time of the gist, a full SunSpec model-chain `scan()` was "deferred by design". It has since been added (below).

## What it would fix

Each item maps to a finding in `CONNECTION_AND_THREADING.md`.

| Current behaviour (franklinwh-modbus + pysunspec2) | modbus-connection | Source |
|---|---|---|
| A TCP connection opened and closed per read and per write (about 7 per `send_command`) | One persistent link. Connects on the first request; after a drop, the next request reconnects. | docs: connection/connections-and-units |
| No lock around Modbus I/O; threads can interleave on one socket | "Requests are serialized over that link, so two units never interleave frames." | same |
| Replies not matched to requests (transaction id always 0, never checked) | Mismatches raise `ModbusDesyncError` ("reply answers a different exchange") | docs: connection/reference, Exceptions |
| `reconnect()` does a full model rescan, and isn't thread-safe | Reconnect without a rescan. `disconnect()` recycles a wedged link, and unit handles keep working across the recycle. | connections-and-units |
| Errors classified by message text ("modbus" in the message triggers a reconnect) | Typed hierarchy: `ModbusConnectionError`, `ModbusTimeoutError`, `ModbusProtocolError`, `ModbusExceptionError` with a subclass per exception code | reference, Exceptions |
| "Response timeout" from pysunspec2 actually means the peer closed the connection | Timeout and connection errors are separate types | same |
| No pacing between requests | `message_spacing` per connection | reference |
| SunSpec discovery and decoding via pysunspec2 | `scan(unit, 40000)`; `SunSpecComponent` checks the model header after every update and raises `SunSpecMapShiftError` if it moved; scale factors read for you, including on writes | docs: modelling/sunspec, sunspec-discovery |
| Hand-written enum maps (`PICS_ENUMS`, numbered from 1) | Component classes generated from the SunSpec `sunspec/models` JSON, which uses the V1.2, 0-based numbering (see `SUNSPEC_ENUM_BASIS.md`) | sunspec-discovery, "Generating component classes" |
| Second client for vendor registers (bridge) | Plain `unit.read_holding_registers(addr, count)` on the same link | docs: connection/operations |

## What it would not fix

- **Several processes on one aGate.** It serialises requests within **one process**. The franklinwh-modbus-bridge and Energipay are separate processes, and each would still open its own connection to :502. **Planned answer (owner, 2026-10-12):** Modbus Bridge 2.0 is the single owner of the aGate connection, and the other bridges go through it (see [Decision](#decision)).
- **Device behaviour.** These stay in the device library whatever the transport:
  - the M704 write sequence and the pauses between writes;
  - the software command timeout (the hardware `WSetRvrtTms` reversion is cosmetic on this firmware);
  - `verify_dispatch` (setpoint plus M714.DCW read-back);
  - orphaned-dispatch release on connect;
  - the extension registers (15000+, 16000+);
  - the quirks in `FRANKLINWH_SUNSPEC_QUIRKS.md`.
- **The aGate's connection limit.** Still unmeasured. A persistent link reduces churn, but whether that helps the device is not known.

## Costs and risks

| Factor | Detail |
|---|---|
| Async only | This library and its tools (CLI, TUI monitor, virtual-mode loop) are synchronous. A fork would need an async core, plus either a sync facade (an event loop on a background thread) or async callers. |
| Python version | Needs >= 3.12; this library supports >= 3.10. |
| Maturity | About 4 months old, already at major version 4 with frequent releases, 10 GitHub stars. Expect API changes, and pin versions. |
| Generated SunSpec classes | Its docs say generated classes are "a starting point", to be reviewed against the manufacturer's implementation. The aGate's quirks and PICS differences would have to go in by hand. |
| Hardware verification | Any control path on a new transport needs the full live test cycle on the reference aGate, coordinated with the bridge and emulator sessions. |

## For franklinwh-modbus-bridge

The bridge is already async and runs every library call through `asyncio.to_thread` under a per-gateway lock. Its dispatch-reliability design (franklinwh-modbus-bridge PR #57) proposes a per-gateway queue, cites Home Assistant's single-client, single-lock `ModbusHub` as precedent, and wants to drop its second (vendor-register) connection. modbus-connection provides that pattern directly. If the bridge moves its Modbus I/O onto it, it takes on the device behaviour listed under "What it would not fix", or keeps this library for control, which brings back a second connection.

## The bridge's view (2026-10-12)

Received through the owner; documented in franklinwh-modbus-bridge PR #57, `docs/dispatch-reliability-design.md` §11. The owner classes it as a future recommendation, not current scope.

- **Yes to modbus-connection as the transport, but inside franklinwh-modbus** (this roadmap item), not as a bridge-only switch. Reasons:
  1. The bridge's own rule is that franklinwh-modbus handles all Modbus I/O; the bridge doesn't re-implement it.
  2. A bridge-only switch would move the control logic into the bridge (M704 sequence, verify, watchdog, orphan release, quirks), or keep this library for control and bring back two sockets.
- **Not before evidence.** It is untested on this aGate, and since connections are being closed mid-request (the "Response timeout" finding), a long-lived connection might help or hurt. The API is moving fast, and it doesn't solve multiple clients on :502.
- **Fit:** it addresses the bridge's findings C1, C3, C10, C14, C15, P3/U9 and the reply-mismatch risk in one move, and the bridge is already async.
- **Checked by the bridge:** PyPI 4.12.4, 41 releases since 2026-06-24, major versions 1–4. The bridge container runs Python 3.12.15 and pymodbus 3.13.1, which meet the requirements; the bridge's `pyproject.toml` (>= 3.11) would need raising. Feature claims were taken from this page and the project's docs, not tested.
- **Suggested path:**
  1. The bridge's Phase 0b measurement baseline plus its experiments E1–E5.
  2. A read-only trial: a minimal modbus-connection poller with the bridge poller paused, compared against the baseline on connection closes, "Response timeout" vs "timed out", and latency.
  3. If it wins, adopt it in the franklinwh-modbus fork behind an async API that keeps the dispatch semantics.

  Meanwhile the bridge's Phase 1 (truthful dispatch reporting) proceeds on the current library.

## Possible spike (not scheduled)

Read-only, against the emulator, not the live aGate:

1. Read models 701, 713 and 714 with modbus-connection's SunSpec scan and generated classes.
2. Compare the decoded values (including enums and scale factors) with `FranklinWHController.read_grid_status()` / `read_battery_status()`.
3. Compare the number of TCP connections opened per status pass.

No writes. Any control experiment would need owner sign-off and a coordinated window.

## References

- `docs/CONNECTION_AND_THREADING.md`: how the current library handles connections and threads, and the 2026-10-12 Q&A.
- `docs/SUNSPEC_ENUM_BASIS.md`: the SunSpec edition used for enum values.
- `docs/FRANKLINWH_SUNSPEC_QUIRKS.md`: aGate SunSpec deviations.
- `docs/IN_FLIGHT_WORK.md` (local-only): the queued roadmap item.
