#!/usr/bin/env python3
"""Generate docs/SUNSPEC_POINT_REFERENCE.md.

Sources (nothing is read from a device):

* Model start addresses and lengths: the "SunSpec model map" table in
  docs/SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md.
* Point names, labels, descriptions, types, units, scale factors, access and
  mandatory flags: the SunSpec 2 model JSON shipped with pysunspec2
  (sunspec2/models/json/model_<N>.json).
* Extension registers: the "Register table" in
  docs/FRANKLINWH_MODBUS_EXTENSIONS.md, copied without the library column.

Usage:
    python3 tools/gen_point_reference.py [--json-dir DIR] [--out FILE]

Standard library only. The sunspec2 package is located but not imported.
"""

import argparse
import importlib.metadata
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
SNAPSHOT = "SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md"
EXTENSIONS = "FRANKLINWH_MODBUS_EXTENSIONS.md"
OUT = os.path.join(DOCS, "SUNSPEC_POINT_REFERENCE.md")
MIRROR_OFFSET = 40000


def find_json_dir():
    spec = importlib.util.find_spec("sunspec2")
    if spec is None or not spec.submodule_search_locations:
        sys.exit("sunspec2 not found; pass --json-dir")
    return os.path.join(list(spec.submodule_search_locations)[0], "models", "json")


def pysunspec2_version():
    try:
        return importlib.metadata.version("pysunspec2")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def read_model_map(path):
    """Return [(model_id, title, header_pdu, length)] in chain order."""
    text = open(path, encoding="utf-8").read()
    section = text.split("## SunSpec model map", 1)[1].split("\n## ", 1)[0]
    rows = []
    for m in re.finditer(r"\|\s*(\d+) ([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", section):
        rows.append((int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))))
    rows.sort(key=lambda r: r[2])
    return rows


def read_extension_rows(path):
    """Return the header and rows of the 'Register table' in the extensions page."""
    text = open(path, encoding="utf-8").read()
    section = text.split("## Register table", 1)[1]
    # Take the first table; stop at the first non-table line after it starts.
    out, started = [], False
    for ln in section.splitlines():
        if ln.startswith("|"):
            started = True
            if ln.startswith("|---"):
                continue
            out.append([c.strip() for c in ln.strip().strip("|").split("|")])
        elif started:
            break
    return out[0], out[1:]


def cell(value):
    if value is None:
        return ""
    s = " ".join(str(value).split())
    return s.replace("|", "\\|")


def group_size(g):
    """Register size of one instance of a group, nested groups counted once."""
    n = sum(p.get("size", 1) for p in g["points"])
    for sub in g.get("groups", []):
        n += group_size(sub)
    return n


def has_runtime_count(g):
    return isinstance(g.get("count"), str) or any(
        has_runtime_count(s) for s in g.get("groups", []))


class Renderer:
    def __init__(self):
        self.lines = []
        self.points = 0

    def table(self, rows):
        self.lines.append("| Point | Label | Description | Type | Units | SF | Access | M/O | PDU (base-0) | PDU mirror (+40000) |")
        self.lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for path, p, addr in rows:
            self.points += 1
            mirror = addr + MIRROR_OFFSET
            self.lines.append("| `{}` | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                path, cell(p.get("label")), cell(p.get("desc")), cell(p.get("type")),
                cell(p.get("units")), cell(p.get("sf")), p.get("access", "R"),
                p.get("mandatory", "O"), addr, mirror))
        self.lines.append("")

    def group(self, g, prefix, addr, model_len, top_fixed, depth):
        """Render group g starting at addr (its first instance). Returns size."""
        rows = []
        a = addr
        for p in g["points"]:
            rows.append((prefix + p["name"], p, a))
            a += p.get("size", 1)
        if depth > 0:
            count = g.get("count")
            if isinstance(count, str):
                note = "Repeats `{}` times (the value of point `{}`, read at run time).".format(count, count)
                if depth == 1 and not g.get("groups") and model_len is not None:
                    rest = model_len + 2 - top_fixed
                    size = group_size(g)
                    if size and rest % size == 0:
                        note += (" From the model length in the snapshot ({} registers), "
                                 "this aGate has **{}** instance(s) (computed: ({} - {}) / {}; "
                                 "inferred from the length, not read from `{}`).").format(
                                     model_len, rest // size, model_len + 2, top_fixed, size, count)
            elif count is None or count == 1:
                note = "One instance."
            else:
                note = "Repeats {} times.".format(count)
            if isinstance(count, str):
                note += " Addresses below are for the **first instance only**."
            self.lines.append("#### Group `{}`".format(prefix.rstrip(".")))
            self.lines.append("")
            self.lines.append(note)
            self.lines.append("")
        if rows:
            self.table(rows)
        for sub in g.get("groups", []):
            a += self.group(sub, prefix + sub["name"] + ".", a, model_len, top_fixed, depth + 1)
        return group_size(g)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json-dir", default=None, help="sunspec2 models/json directory")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    json_dir = args.json_dir or find_json_dir()
    models = read_model_map(os.path.join(DOCS, SNAPSHOT))
    ext_head, ext_rows = read_extension_rows(os.path.join(DOCS, EXTENSIONS))

    r = Renderer()
    missing = []
    body = []
    summary = []
    for mid, title, header, length in models:
        path = os.path.join(json_dir, "model_{}.json".format(mid))
        if not os.path.exists(path):
            missing.append(mid)
            continue
        g = json.load(open(path, encoding="utf-8"))["group"]
        start = len(r.lines)
        before = r.points
        r.lines.append("## Model {} — {}".format(mid, cell(g.get("label") or title)))
        r.lines.append("")
        if g.get("desc"):
            r.lines.append("> {}".format(cell(g["desc"])))
            r.lines.append("")
        r.lines.append("Header (`ID`) at PDU **{}** (mirror {}); length **{}** registers (snapshot). "
                       "SunSpec group name `{}`.".format(header, header + MIRROR_OFFSET, length, g["name"]))
        r.lines.append("")
        top_fixed = sum(p.get("size", 1) for p in g["points"])
        r.group(g, "", header, length, top_fixed, 0)
        summary.append((mid, cell(g.get("label") or title), header, length, r.points - before))
        body.extend(r.lines[start:])
        del r.lines[start:]

    v = pysunspec2_version()
    out = []
    out.append("# SunSpec Point Reference")
    out.append("")
    out.append("<!-- Generated by tools/gen_point_reference.py. Do not edit by hand; rerun the script. -->")
    out.append("")
    out.append("Every SunSpec point in the models the aGate reports, with its label and description, "
               "and the FranklinWH extension registers. Use it to look up what a point is and where it sits.")
    out.append("")
    out.append("- **Labels, descriptions, types, units, scale factors (SF), access and M/O** (mandatory/optional) "
               "are from the SunSpec 2 model JSON shipped with **pysunspec2 {}** "
               "(`sunspec2/models/json/model_<N>.json`), copied verbatim. A blank cell means the JSON has no value; where the JSON omits access or M/O, "
               "the pysunspec2 defaults (`R`, `O`, from `sunspec2/mdef.py`) are shown. "
               "Access `R`/`RW` is what the SunSpec model defines, not what the aGate accepts.".format(v))
    out.append("- **Models, start addresses and lengths** are from the "
               "[V12R02B60D00 snapshot](SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md) (captured 2026-10-20). "
               "Addresses are Modbus **PDU addresses** (0-based, as sent on the wire); see "
               "[Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map).")
    out.append("- **PDU mirror (+40000):** on V12R02B60D00 the snapshot found the map mirrored at PDU 40000 "
               "(base-0 + 40000). Writes to the mirror are unverified (snapshot).")
    out.append("- A point's PDU address is the model header address plus the point's offset in the model JSON "
               "(`ID` is offset 0, `L` offset 1). Repeating groups show their first instance.")
    out.append("- The snapshot notes that the bridge export returned the points of models 705–712 as "
               "not implemented; their lengths are from the raw re-scan.")
    out.append("- **One Modbus client per aGate.** Stop other clients before reading.")
    out.append("")
    out.append("## Models")
    out.append("")
    out.append("| Model | Label | Header PDU | Mirror | Length | Points listed |")
    out.append("|---|---|---|---|---|---|")
    total = 0
    for mid, label, header, length, n in summary:
        total += n
        anchor = "#model-{}".format(mid)
        out.append("| [{}]({}) | {} | {} | {} | {} | {} |".format(
            mid, anchor, label, header, header + MIRROR_OFFSET, length, n))
    out.append("")
    out.append("{} models, {} points (each point in a repeating group is counted once). "
               "The end marker (0xFFFF) is at PDU 1126 (snapshot).".format(len(summary), total))
    if missing:
        out.append("")
        out.append("No pysunspec2 JSON for model(s): {}.".format(", ".join(map(str, missing))))
    out.append("")
    for ln in body:
        if ln.startswith("## Model "):
            mid = ln.split()[2]
            out.append('<a id="model-{}"></a>'.format(mid))
            out.append("")
        out.append(ln)

    out.append("## Extension registers")
    out.append("")
    out.append("The FranklinWH registers outside the SunSpec chain. sunspec2 can't see them; read them with a plain "
               "FC3 request at the PDU address shown, without the 40000 offset. The rows below are copied from "
               "[FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md) (without its library column); "
               "that page is the authority for meanings, evidence and the notes on writing. "
               "The evidence terms (Documented, Measured, Inferred) are defined there.")
    out.append("")
    keep = [i for i, h in enumerate(ext_head) if h != "In the library"]
    out.append("| " + " | ".join(ext_head[i] for i in keep) + " |")
    out.append("|" + "---|" * len(keep))
    for row in ext_rows:
        row = [c.replace("; see below", "; see [15507 values](FRANKLINWH_MODBUS_EXTENSIONS.md#15507-operating-mode-values)")
               for c in row]
        out.append("| " + " | ".join(row[i] for i in keep) + " |")
    out.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("wrote {}: {} models, {} points, {} extension rows{}".format(
        os.path.relpath(args.out, ROOT), len(summary), total, len(ext_rows),
        "; missing JSON: {}".format(missing) if missing else ""))


if __name__ == "__main__":
    main()
