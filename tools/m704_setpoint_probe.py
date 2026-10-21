#!/usr/bin/env python3
"""
M704 setpoint probe: a diagnostic tool for the aGate's SunSpec battery control.

Two subcommands:

  observe   Read-only. Polls M704 (WSetEna..WSetRvrtRem, WSetPct_SF), M714 DCW
            and M713 SoC at a fixed interval and writes JSON Lines. Stops at
            --max-duration or --max-bytes, whichever comes first.

  probe     ⚠️ WRITES to the aGate. For each raw WSetPct value, repeated
            --repeat times: write it the way the library's send_command()
            does (WSetEna=0, WSetMod=0, WSetPct=raw, WSetEna=1), hold for
            --hold seconds while sampling, then release (WSetEna=0,
            WSetPct=0) and wait --gap seconds. Every write is logged with the
            aGate's reply, including the Modbus exception code if it refuses.
            Without --execute it only prints the plan.

Raw values use the hardware convention: positive = discharge, negative =
charge, scaled by WSetPct_SF (-1 on the aGate, so raw 100 = 10.0 %).

Every write is followed by a release, including on error and Ctrl-C. The
probe refuses to start if WSetEna is already 1 (another client is in
control), or if WSetPct_SF isn't the expected value, unless --force.

Output never contains the aGate's IP address or serial number.

Examples:
  python tools/m704_setpoint_probe.py -i 192.0.2.110 observe --interval 1 --max-duration 600
  python tools/m704_setpoint_probe.py -i 192.0.2.110 probe --values 100,101,110,-100,-110 --repeat 2
  python tools/m704_setpoint_probe.py -i 192.0.2.110 probe --values 100,110 --execute
"""

import argparse
import json
import os
import signal
import statistics
import sys
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

# PDU addresses on the aGate (SunSpec map at PDU 0). See docs/FRANKLINWH_SUNSPEC_QUIRKS.md.
M1_VR = 44            # Model 1 Vr, string[8] (16 bytes)
M704_BLOCK = 318      # WSetEna .. WSetRvrtRem
M704_BLOCK_LEN = 13
WSET_ENA, WSET_MOD, WSET_PCT = 318, 319, 324
WSET_PCT_SF = 352
M713_SOC = 1037       # raw, 0.1 %
M714_DCW = 1048       # W, negative = charging

DEFAULT_MAX_BYTES = 5 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def s16(v: Optional[int]) -> Optional[int]:
    return v - 65536 if v is not None and v >= 32768 else v


def u16(v: int) -> int:
    return v & 0xFFFF


class CappedLog:
    """JSON Lines writer with time and size caps. Also echoes to stdout."""

    def __init__(self, path: Optional[str], max_bytes: int, max_duration_s: float,
                 echo: Callable[[str], None] = print):
        self.path = path
        self.max_bytes = max_bytes
        self.deadline = time.monotonic() + max_duration_s
        self.bytes = 0
        self.echo = echo
        self.stop_reason: Optional[str] = None
        self._fh = open(path, "a") if path else None

    def capped(self) -> bool:
        if self.stop_reason:
            return True
        if time.monotonic() >= self.deadline:
            self.stop_reason = "max-duration reached"
        elif self.bytes >= self.max_bytes:
            self.stop_reason = "max-bytes reached"
        return self.stop_reason is not None

    def write(self, rec: dict) -> None:
        line = json.dumps(rec, separators=(",", ":"))
        self.bytes += len(line) + 1
        if self._fh:
            self._fh.write(line + "\n")
            self._fh.flush()
        self.echo(line)

    def close(self) -> None:
        if self._fh:
            self._fh.close()


class Device:
    """Thin wrapper over a pymodbus client: every reply is returned, never raised."""

    def __init__(self, client, unit: int):
        self.c = client
        self.unit = unit

    def read(self, addr: int, count: int) -> dict:
        try:
            r = self.c.read_holding_registers(addr, count=count, device_id=self.unit)
        except Exception as e:  # connection-level failure
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if r.isError():
            return {"ok": False, "exception": getattr(r, "exception_code", None), "error": str(r)}
        return {"ok": True, "regs": list(r.registers)}

    def write(self, addr: int, value: int) -> dict:
        rec = {"addr": addr, "value": value}
        try:
            r = self.c.write_register(addr, u16(value), device_id=self.unit)
        except Exception as e:
            rec.update(ok=False, error=f"{type(e).__name__}: {e}")
            return rec
        if r.isError():
            rec.update(ok=False, exception=getattr(r, "exception_code", None), error=str(r))
        else:
            rec.update(ok=True)
        return rec


def sample(dev: Device) -> dict:
    """One snapshot of the control state. Fields are None when a read fails."""
    out = {"t": utc_now()}
    blk = dev.read(M704_BLOCK, M704_BLOCK_LEN)
    if blk["ok"]:
        r = blk["regs"]
        wset = (r[2] << 16) | r[3]
        out.update(WSetEna=r[0], WSetMod=r[1], WSet=wset - (1 << 32) if wset >= (1 << 31) else wset,
                   WSetPct=s16(r[6]), WSetEnaRvrt=r[8],
                   WSetRvrtTms=(r[9] << 16) | r[10], WSetRvrtRem=(r[11] << 16) | r[12])
    else:
        out["m704_error"] = blk
    for name, addr, conv in (("DCW", M714_DCW, s16), ("SoC_raw", M713_SOC, lambda v: v)):
        res = dev.read(addr, 1)
        out[name] = conv(res["regs"][0]) if res["ok"] else None
    return out


def read_firmware(dev: Device) -> Optional[str]:
    res = dev.read(M1_VR, 8)
    if not res["ok"]:
        return None
    raw = b"".join(v.to_bytes(2, "big") for v in res["regs"])
    return raw.split(b"\x00")[0].decode("ascii", "replace").strip()


def read_sf(dev: Device) -> Optional[int]:
    res = dev.read(WSET_PCT_SF, 1)
    return s16(res["regs"][0]) if res["ok"] else None


def release(dev: Device, log: CappedLog, why: str) -> List[dict]:
    writes = [dev.write(WSET_ENA, 0), dev.write(WSET_PCT, 0)]
    log.write({"t": utc_now(), "event": "release", "why": why, "writes": writes})
    return writes


def apply_setpoint(dev: Device, raw: int, settle_s: float = 0.3) -> List[dict]:
    """Same order as FranklinWHController.send_command(). Stops at the first refusal."""
    writes = []
    for addr, value in ((WSET_ENA, 0), (WSET_MOD, 0), (WSET_PCT, raw), (WSET_ENA, 1)):
        rec = dev.write(addr, value)
        writes.append(rec)
        if not rec["ok"]:
            break
        time.sleep(settle_s)
    return writes


def run_observe(dev: Device, log: CappedLog, interval: float) -> None:
    log.write({"t": utc_now(), "event": "start", "mode": "observe", "firmware": read_firmware(dev),
               "WSetPct_SF": read_sf(dev), "interval_s": interval})
    while not log.capped():
        log.write({"event": "sample", **sample(dev)})
        time.sleep(interval)
    log.write({"t": utc_now(), "event": "stop", "reason": log.stop_reason})


def plan_steps(values: List[int], repeat: int) -> List[int]:
    return [v for _ in range(repeat) for v in values]


def run_probe(dev: Device, log: CappedLog, args) -> List[dict]:
    fw, sf = read_firmware(dev), read_sf(dev)
    first = sample(dev)
    log.write({"t": utc_now(), "event": "start", "mode": "probe", "firmware": fw, "WSetPct_SF": sf,
               "values": args.values, "repeat": args.repeat, "hold_s": args.hold, "gap_s": args.gap,
               "baseline": first})
    if sf != args.expect_sf and not args.force:
        log.write({"t": utc_now(), "event": "abort", "why": f"WSetPct_SF is {sf}, expected {args.expect_sf}"})
        return []
    if first.get("WSetEna") != 0 and not args.force:
        log.write({"t": utc_now(), "event": "abort", "why": "WSetEna is not 0: another client may be in control"})
        return []

    results = []
    for step, raw in enumerate(plan_steps(args.values, args.repeat), 1):
        if log.capped():
            break
        soc = sample(dev).get("SoC_raw")
        soc_pct = soc / 10 if soc is not None else None
        if raw > 0 and soc_pct is not None and soc_pct < args.min_soc:
            log.write({"t": utc_now(), "event": "skip", "step": step, "raw": raw,
                       "why": f"SoC {soc_pct} % below --min-soc {args.min_soc}"})
            continue
        writes = apply_setpoint(dev, raw)
        accepted = all(w["ok"] for w in writes)
        log.write({"t": utc_now(), "event": "write", "step": step, "raw": raw, "accepted": accepted,
                   "writes": writes})
        samples = []
        try:
            end = time.monotonic() + (args.hold if accepted else 0)
            while time.monotonic() < end and not log.capped():
                s = sample(dev)
                samples.append(s)
                log.write({"event": "hold", "step": step, **s})
                time.sleep(args.interval)
        finally:
            release(dev, log, f"end of step {step}")
        latched = any(s.get("WSetEna") == 1 and s.get("WSetPct") == raw for s in samples)
        dcw = [s["DCW"] for s in samples[len(samples) // 2:] if s.get("DCW") is not None]
        res = {"step": step, "raw": raw, "pct": raw * 10 ** (sf if sf is not None else -1),
               "accepted": accepted, "latched": latched,
               "exception": next((w.get("exception") for w in writes if not w["ok"]), None),
               "dcw_median_w": statistics.median(dcw) if dcw else None}
        results.append(res)
        log.write({"t": utc_now(), "event": "result", **res})
        gap_end = time.monotonic() + args.gap
        while time.monotonic() < gap_end and not log.capped():
            log.write({"event": "gap", "step": step, **sample(dev)})
            time.sleep(args.interval)
    log.write({"t": utc_now(), "event": "stop", "reason": log.stop_reason or "plan complete",
               "after": sample(dev)})
    return results


def parse_values(text: str) -> List[int]:
    return [int(v) for v in text.split(",") if v.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-i", "--ip", required=True, help="aGate IP (never written to the output)")
    p.add_argument("-p", "--port", type=int, default=502)
    p.add_argument("-u", "--unit", type=int, default=1)
    p.add_argument("--timeout", type=float, default=3.0)
    p.add_argument("--out", help="JSON Lines output file (default: tests/results/m704_<mode>_<UTC>.jsonl)")
    p.add_argument("--max-duration", type=float, default=1800, help="stop after this many seconds (default 1800)")
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="stop when the output reaches this size")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between samples (default 1.0, minimum 0.5)")
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("observe", help="read-only sampling")
    pr = sub.add_parser("probe", help="⚠️ write raw WSetPct values and record the aGate's replies")
    pr.add_argument("--values", type=parse_values, required=True, help="comma-separated raw WSetPct values")
    pr.add_argument("--repeat", type=int, default=1)
    pr.add_argument("--hold", type=float, default=30.0, help="seconds to hold each accepted setpoint")
    pr.add_argument("--gap", type=float, default=15.0, help="seconds to observe after each release")
    pr.add_argument("--max-raw", type=int, default=1000, help="refuse any |raw| above this (default 1000)")
    pr.add_argument("--min-soc", type=float, default=20.0, help="skip discharge steps below this SoC %%")
    pr.add_argument("--expect-sf", type=int, default=-1, help="expected WSetPct_SF (default -1)")
    pr.add_argument("--force", action="store_true", help="run even if WSetEna=1 or the SF differs")
    pr.add_argument("--execute", action="store_true", help="actually write; without it only the plan is shown")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.interval = max(args.interval, 0.5)
    if args.mode == "probe":
        bad = [v for v in args.values if abs(v) > args.max_raw]
        if bad:
            print(f"Refusing: {bad} exceed --max-raw {args.max_raw}", file=sys.stderr)
            return 2
        steps = plan_steps(args.values, args.repeat)
        est = len(steps) * (args.hold + args.gap + 2)
        print(f"Plan: {len(steps)} steps {steps}, hold {args.hold}s, gap {args.gap}s, about {est:.0f}s total")
        if est > args.max_duration:
            print(f"Note: --max-duration {args.max_duration}s will stop the run early", file=sys.stderr)
        if not args.execute:
            print("Dry run: nothing written. Add --execute to run it (⚠️ writes to the aGate).")
            return 0

    from pymodbus.client import ModbusTcpClient
    out = args.out or os.path.join("tests", "results",
                                   f"m704_{args.mode}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.jsonl")
    client = ModbusTcpClient(args.ip, port=args.port, timeout=args.timeout)
    if not client.connect():
        print("Connect failed", file=sys.stderr)
        return 1
    dev = Device(client, args.unit)
    log = CappedLog(out, args.max_bytes, args.max_duration)

    def _sigint(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, _sigint)
    try:
        if args.mode == "observe":
            run_observe(dev, log, args.interval)
        else:
            results = run_probe(dev, log, args)
            print("\nstep  raw    pct    accepted  latched  exception  DCW median")
            for r in results:
                print(f"{r['step']:>4}  {r['raw']:>5}  {r['pct']:>5.1f}  {str(r['accepted']):>8}  "
                      f"{str(r['latched']):>7}  {str(r['exception']):>9}  {r['dcw_median_w']}")
    except KeyboardInterrupt:
        if args.mode == "probe":
            release(dev, log, "interrupted")
        log.write({"t": utc_now(), "event": "stop", "reason": "interrupted"})
    finally:
        log.close()
        client.close()
    print(f"\nLog: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
