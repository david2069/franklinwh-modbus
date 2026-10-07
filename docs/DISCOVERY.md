# Finding an aGate on the network

`franklinwh_modbus.discovery` finds SunSpec Modbus devices — FranklinWH aGates
in particular — on a host or a subnet. It is **read-only**: it never writes a
register.

**A FranklinWH Modbus device** is a SunSpec device that returns the Common
model (1), with a manufacturer string containing "FranklinWH". Anything else
listening on the port is reported as an *unknown device*.

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
**40000**, **50000** and **30000**, checks that the first model after it is the
Common model (1), reads that model's nameplate in a single request, and
disconnects.

| `status` | Meaning |
|---|---|
| `sunspec` | SunSpec device with model 1 found; `manufacturer`, `model`, `serial`, `version`, `base_address` are set. `is_franklinwh` tells an aGate from another vendor's inverter or meter. |
| `unknown` | Something is listening on the port, but it isn't a SunSpec device: no Modbus reply, no `SunS` marker at any base, or a first model other than 1. `error` says which. |
| `closed` | Nothing is listening on the port (or the host is unreachable). |

`summary` gives one line for a person — *"FranklinWH Technologies Co., Ltd aGate X
at 192.168.0.110:502"*, or *"Unknown device listening on TCP port 502 at
192.168.0.20"*.

Parameters: `port=502`, `unit_id=1`, `timeout=2.0` (per read), `attempts=1`
(retry the whole sequence — for a device that is slow or briefly busy),
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

## Probing an aGate that is in use

Each probe makes two short reads (header, nameplate) and disconnects. On
2026-10-07 a real aGate X (firmware V10R01B04D00) was identified correctly both
while two bridges were polling it and with them stopped.
