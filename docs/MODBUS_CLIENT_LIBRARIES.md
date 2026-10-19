# Modbus Client Libraries and Dependencies

How this library talks to the aGate's **Modbus TCP Server (aGate :502)** today, which Python Modbus client libraries exist, the trade-offs of raw register reads, worked examples with pysunspec2, the planned move to the Open Home Foundation's **modbus-connection**, and whether a FranklinWH-specific library is needed at all.

> **Evidence.** Package facts are from PyPI, checked 2026-10-19. Behaviour of pysunspec2 is from its source (version 1.3.6, installed). modbus-connection facts are from its documentation, checked 2026-10-19. Each claim links to its source under [References](#references). Where something is not verified, it says so.

---

## 1. What this library depends on today

| Dependency | Declared in `pyproject.toml` | Used for |
|---|---|---|
| **pysunspec2** | `pysunspec2>=1.1.0` | Everything SunSpec: connecting, scanning the "SunS" model chain, reading and writing models 1, 502 and 701–715 |
| **pymodbus** | `pymodbus>=3.0.0` | Only `discovery.py` (finding aGates on a network) |
| *(raw sockets)* | — | The FranklinWH extension registers (15500+, 16000+) and M715 `AlarmReset`. Hand-built Modbus TCP frames sent on pysunspec2's socket |

Optional: `rich` for the TUI monitor.

---

## 2. Python Modbus client libraries

From PyPI, 2026-10-19 ([R1](#references)):

| Package | Latest | Python | Licence | First release | What it is (PyPI summary) |
|---|---|---|---|---|---|
| [pymodbus](https://github.com/pymodbus-dev/pymodbus) | 3.16.1 (2026-10-11) | ≥ 3.10 | BSD-3-Clause | 2012 | "A fully featured modbus protocol stack in python" |
| [pysunspec2](https://sunspec.org/) | 1.3.6 (2026-06-01) | ≥ 3.5 | Apache | 2021 | "Python SunSpec Tools" (SunSpec Alliance's own client, with its own Modbus transport) |
| [modbus-connection](https://github.com/home-assistant-libs/modbus-connection) | 4.12.5 (2026-10-15) | ≥ 3.12 | Apache-2.0 | 2026-06-24 | "A small, backend-neutral Modbus connection abstraction (pymodbus / tmodbus)" |
| [tmodbus](https://github.com/wlcrs/tmodbus) | 0.6.2 (2026-08-28) | ≥ 3.12 | BSD-3-Clause | 2025-10 | "A modern, strongly typed Modbus client library." |
| [pyModbusTCP](https://github.com/sourceperl/pyModbusTCP) | 0.3.1 (2026-09-30) | not stated | MIT | 2015 | "A simple Modbus/TCP library for Python" |
| [uModbus](https://github.com/AdvancedClimateSystems/umodbus/) | 1.0.4 (2020-08-27) | not stated | MPL | 2015 | "Implementation of the Modbus protocol in pure Python." |
| [minimalmodbus](https://github.com/pyhys/minimalmodbus) | 2.1.1 (2023-07-17) | ≥ 3.8 | — | 2011 | "Easy-to-use Modbus RTU and Modbus ASCII implementation" (serial only; not usable over TCP) |

Two kinds of library:

- **Transports** (pymodbus, tmodbus, pyModbusTCP, uModbus) move registers. What the numbers mean is up to you.
- **SunSpec-aware** libraries understand the SunSpec model chain, scale factors and point names. **pysunspec2** does this with its own transport. **modbus-connection** has a SunSpec layer on top of pymodbus or tmodbus.

---

## 3. Raw register reads: pros and cons

"Raw" here means reading a register by address, without SunSpec's model chain: either with a transport library or with hand-built frames, as this library does for the extension registers.

**Pros:**
- **The only way to reach the FranklinWH extension registers.** They are outside the SunSpec chain, so no SunSpec client sees them ([extension registers](FRANKLINWH_MODBUS_EXTENSIONS.md)).
- **No dependency on the device's SunSpec map being correct.** You read exactly the address you name.
- **Small and fast:** one request, one reply.

**Cons, with examples from this library:**
- **You own the meaning:** types, scale factors, signs and enum values all come from documentation or testing, not from the device. Example: the 15507 mode values are disputed (#75).
- **Hand-built frames skip protocol checks.** This library's raw requests use transaction id 0 and don't match replies to requests (13 call sites build the frame with `struct.pack('>HHHBBHH', 0, 0, 6, …)`). Each reply is a single `sock.recv(256)`, which assumes the whole reply arrives in one read.
- **Connection handling becomes your problem.** The raw paths call `client.connect()`, which in pysunspec2 closes and reopens the TCP session first: a reconnect on every poll (#53). Disconnects left sockets open (#70).
- **Addressing mistakes fail quietly or confusingly.** Offsetting by 40000 returns exception 2 on the aGate ([Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map)). A wrong address can return a plausible but wrong value.

A transport library (pymodbus, tmodbus, or modbus-connection's unit API) removes the framing and transaction-matching risks. It does not remove the meaning problem.

Example with pymodbus (the unit-id keyword is `device_id` from pymodbus 3.10, `slave` before that; `discovery.py` handles both):

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.0.2.10", port=502)
client.connect()
rr = client.read_holding_registers(15507, count=3, device_id=2)   # PDU address, as listed
if not rr.isError():
    mode_raw, sc_reserve, tou_reserve = rr.registers
client.close()
```

---

## 4. pysunspec2: worked examples

pysunspec2 is the SunSpec Alliance's Python client. It scans the "SunS" model chain and gives every point a name, type and scale factor.

```python
import sunspec2.modbus.client as client

dev = client.SunSpecModbusClientDeviceTCP(slave_id=2, ipaddr="192.0.2.10", ipport=502, timeout=10)
dev.scan()                                   # walks the "SunS" chain; finds it at PDU 0 on the aGate

print(sorted(k for k in dev.models if isinstance(k, int)))   # e.g. [1, 502, 701, ..., 715]

common = dev.models[1][0]                    # Model 1 (Common)
common.read()
print(common.Mn.value, common.Md.value, common.Vr.value)     # manufacturer, model, firmware

batt = dev.models[713][0]                    # DER storage capacity
batt.read()
print(batt.SoC.value, batt.SoC.cvalue)       # raw, and scaled by SoC's scale factor (cvalue)

ctl = dev.models[704][0]                     # DER AC controls
ctl.read()
print(ctl.WSetEna.value, ctl.WSetPct.value)  # remote-control enable and setpoint
```

Writing (⚠️ changes the battery's behaviour; see [Safety Controls](SAFETY_CONTROLS.md)):

```python
ctl.WSetEna.value = 0                        # release remote control
ctl.write()
```

What pysunspec2 does that matters here (from its 1.3.6 source):

- **`scan()` tries PDU 40000, then 0, then 50000** (`base_addr_list = [40000, 0, 50000]`). It records where it found "SunS" in `dev.base_addr`, and **disconnects when the scan ends**.
- **After that, each read or write opens and closes its own TCP connection** if none is open (`ModbusClientTCP.read`).
- **`close()` does nothing on a TCP device**; only `disconnect()` closes the socket (#70).
- **It cannot read the FranklinWH extension registers by model**, because they aren't in the chain.

---

## 5. modbus-connection (Open Home Foundation)

### What it is

"A backend-neutral Modbus connection abstraction with a typed device-modelling framework on top of it" ([R3](#references)), published by the Open Home Foundation's `home-assistant-libs` organisation. It is asyncio-based, runs on pymodbus or tmodbus as interchangeable backends, needs Python ≥ 3.12, and is Apache-2.0 licensed ([R1](#references), [R3](#references)).

```python
from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from modbus_connection.model.sunspec import scan

connection = ModbusConnection(ModbusTcpParams(host="192.0.2.10", port=502))
unit = connection.for_unit(2)

models = await scan(unit, 0)                           # base address is "the zero-based marker address"; the aGate's is 0
ext = await unit.read_holding_registers(15507, 3)      # FranklinWH extension registers, same link
```

(Patterns from its documentation, [R4](#references) and [R5](#references); not yet run against an aGate.)

### Pros (as documented)

- **One persistent link.** "The first request connects on demand. If the link drops, the next request reconnects." `disconnect()` recycles the link, and "unit handles and components keep working across the recycle" ([R4](#references)).
- **Requests can't interleave.** "The backend serializes requests on one connection, so concurrent unit calls cannot interleave" ([R3](#references)).
- **Typed errors**, including **`ModbusDesyncError`**: "the reply belongs to a different exchange". Device refusals become typed subclasses such as `IllegalDataAddressError` ([R6](#references)).
- **Request pacing:** `set_message_spacing()`; and timeouts: `require_timeout()` ([R4](#references)).
- **SunSpec built in:**
  - `scan(unit, base_address)` returns each model's location;
  - `SunSpecMapShiftError` if the device moves a model;
  - scale factors read for you, on writes too;
  - component classes generated from SunSpec's official model JSON ([R5](#references), [R7](#references)).
- **Extension registers on the same link** with `read_holding_registers()`, so the second client is gone ([R6](#references)).

### Cons and limits

- **Async only.** This library, its CLI, TUI and virtual-mode loop are synchronous. A port needs an async core, plus a sync wrapper or async callers.
- **Python ≥ 3.12**, against ≥ 3.10 here.
- **Young.** First release 2026-06-24, 42 releases to 4.12.5 ([R1](#references)). Expect API changes and pin versions.
- **Generated SunSpec classes are "a starting point".** In its own words: "Review it against the manufacturer's implementation and commit the adjusted classes to the device library" ([R7](#references)). The aGate's quirks still have to be written by hand.
- **One process only.** It serialises requests within one program. It can't stop two programs competing for the aGate's single Modbus slot.
- **Not tested on an aGate yet.**

### The boundary: what stays in a device library

The modbus-connection author's survey of about 60 Modbus libraries ([R8](#references)) rates this library **"Friction"**: "auto-reconnect, inter-write sleeps + watchdog + read-back-verify". It rates pysunspec2 **"Blocked"**: "own transport + richer dynamic model". It places heartbeats, keepalives and read-back verification with the device library: they "are owner responsibilities the design accommodates". In other words, modbus-connection replaces the **transport** layer, not the FranklinWH-specific behaviour.

### Direction

The owner set the direction on 2026-10-12, as recorded in the evaluation in PR #32, and restated it on 2026-10-19. The **new FranklinWH Modbus library (API 2.0)** will be built on modbus-connection as its transport, using this library (1.x) as its model. franklinwh-modbus 1.x is not rewritten; its defects are fixed in place.

---

## 6. Is a FranklinWH-specific library needed at all?

### Why not: a generic SunSpec client might be enough

- **Standard data is standard.** Battery SoC, grid power and the M704 setpoint are in SunSpec models. Any SunSpec client (pysunspec2, or modbus-connection's SunSpec layer) can read them by name.
- **Less code to maintain.** With generated SunSpec classes ([R7](#references)), a thin per-device profile could replace a whole library.
- **Generic integrations exist.** Tools that speak SunSpec can read an aGate's standard models without anything FranklinWH-specific.

### Why yes: what a generic client gets wrong on an aGate

Each item below is documented in this repository:

- **Mode and reserves aren't in SunSpec.** The operating mode and SoC reserves are only in extension registers 15507–15509, outside the chain. Without them an integration can't see, or stay in step with, the FranklinWH app ([extension registers](FRANKLINWH_MODBUS_EXTENSIONS.md)).
- **Some standard points mean something different.**
  - M713 `Sta` and M714 `DCA` aren't populated; battery state and current have to be derived from M714 `DCW` ([QUIRKS](FRANKLINWH_SUNSPEC_QUIRKS.md)).
  - 15509 repeats 15508 (#63).
- **Safety rests on the client.**
  - The aGate doesn't range-check setpoints (PICS Issue 5), so the client must clamp them, keeping the requested direction (#28).
  - The M704 revert timer counts down but doesn't release control (PICS Issue 4), so the client must release, and verify the release.
  - A generic client would do neither.
- **The control sequence and verification** (write ordering, pauses, setpoint read-back with M714 power, `verify_dispatch`) are device behaviour. The modbus-connection author places these with the device library ([R8](#references)).
- **Ratings and addressing.** Power ratings come from M702 and need a safe fallback. The map is at PDU 0, and the 40000 base fails.

### Conclusion

A FranklinWH-specific library is needed for control, the extension registers and the quirks; a generic SunSpec client is enough only for read-only access to the standard models. The split that both the evidence and the planned direction point to is:

- **modbus-connection** for the transport;
- **generated SunSpec classes**, reviewed against the aGate, for the standard models;
- **a FranklinWH layer** for the extension registers, the quirks, safety (clamp, release, verify) and the control sequence.

---

## References

- **R1:** PyPI JSON API, checked 2026-10-19: [modbus-connection](https://pypi.org/project/modbus-connection/), [pymodbus](https://pypi.org/project/pymodbus/), [pysunspec2](https://pypi.org/project/pysunspec2/), [tmodbus](https://pypi.org/project/tmodbus/), [pyModbusTCP](https://pypi.org/project/pyModbusTCP/), [uModbus](https://pypi.org/project/uModbus/), [minimalmodbus](https://pypi.org/project/minimalmodbus/).
- **R2:** pysunspec2 1.3.6 source (`sunspec2/modbus/client.py`, `sunspec2/modbus/modbus.py`), as installed.
- **R3:** [modbus-connection documentation, home page](https://home-assistant-libs.github.io/modbus-connection/).
- **R4:** [modbus-connection: Connections and units](https://home-assistant-libs.github.io/modbus-connection/connection/connections-and-units/).
- **R5:** [modbus-connection: SunSpec](https://home-assistant-libs.github.io/modbus-connection/modelling/sunspec/).
- **R6:** [modbus-connection: Reference](https://home-assistant-libs.github.io/modbus-connection/connection/reference/).
- **R7:** [modbus-connection: SunSpec discovery and generation](https://home-assistant-libs.github.io/modbus-connection/modelling/sunspec-discovery/).
- **R8:** balloob, [*Evaluating modbus-connection against real-world Modbus libraries*](https://gist.github.com/balloob/b9fa91ba1a0914a9787f8f6ceb637b83), 2026-07-02.
- This repository: [What is Modbus TCP?](WHAT_IS_MODBUS_TCP.md), [SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md), [FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md), and issues #28, #53, #63, #70 and #75.
