# Finding an aGate on the network

`franklinwh_modbus.discovery` finds SunSpec Modbus devices — FranklinWH aGates
in particular — on a host or a subnet. It is **read-only**: it never writes a
register.

It is the same probe `tools/network_scanner.py` uses, made importable so other
projects (a setup wizard, a dashboard) don't need their own Modbus code.

## One host

```python
from franklinwh_modbus import discovery

res = discovery.probe("192.168.1.50")
print(res.status, res.is_franklinwh, res.model, res.serial)
# sunspec True aGate X 10060006A01234
```

`probe()` connects, looks for the SunSpec marker `SunS` at base **0**, then
**40000**, **50000** and **30000**, reads the Common model (1) nameplate in a
single request, and disconnects.

| `status` | Meaning |
|---|---|
| `sunspec` | SunSpec device found; `manufacturer`, `model`, `serial`, `version`, `base_address` are set. `is_franklinwh` tells an aGate from another vendor's inverter or meter. |
| `no_response` | Port 502 is open but nothing answered Modbus. On an aGate this usually means **another client holds its single Modbus session** (Home Assistant, another tool), or it is rebooting. |
| `not_sunspec` | A Modbus device answered, but has no SunSpec marker at any base. |
| `closed` | Port 502 isn't open (or the host is unreachable). |

Parameters: `port=502`, `unit_id=1`, `timeout=2.0` (per read), `attempts=1`
(retry the whole sequence — useful to catch a gap in another client's polling),
`bases=(0, 40000, 50000, 30000)`.

If a host gives no Modbus answer at all on the first base, the remaining bases
are skipped: they would only time out too.

## A subnet

```python
results = discovery.scan("192.168.1.0/24", on_result=lambda r: print(r.host, r.status))
agates = [r for r in results if r.is_franklinwh]
```

`scan()` runs a TCP check on port 502 against every host in parallel
(`workers=64`, `connect_timeout=0.3`), then probes only the hosts that answer.
It returns every host with the port open (never `closed` ones), sorted by
address; `on_result` is called as each completes, for progress reporting.

Safety limits:

- **Private ranges only** (RFC 1918 and similar) unless `allow_public=True`.
  Tailscale's `100.64.0.0/10` counts as public, so pass `allow_public=True` to
  scan a tailnet.
- **At most `max_hosts=254`** — one /24 — so a mistyped `/16` doesn't start a
  65,000-host sweep.
- IPv4 only.

## The aGate's single Modbus session

An aGate accepts **one Modbus TCP client at a time**. Discovery is built
around that:

- each probe holds the session for two reads (marker, nameplate) and then
  disconnects;
- `no_response` is reported separately from `closed`, so a tool can say
  *"found something on 502 that didn't answer — another app may be connected"*
  rather than *"nothing found"*.

Don't probe an aGate that your own poller is connected to: the probe would be
refused (`no_response`), or, if it got in first, briefly block the poller.
