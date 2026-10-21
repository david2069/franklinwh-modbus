# Sequencer Raw Data Types & Extension Registers Analysis

**Status:** Draft / Analysis  
**Date:** 2026-06-15  
**Topic:** Sequencer support for proprietary extension registers, scale factors, data widths (32-bit registers), and symbols.

---

## 1. Background

The FranklinWH aGate Modbus TCP interface exposes standard SunSpec models (40001+) and proprietary manufacturer extension ranges (15000+ and 16000+).
The [SunSpecSequencer](/src/franklinwh_modbus/sequencer.py#L22) in the `franklinwh-modbus` library executes deterministic sequences of reads and writes. However, it handles SunSpec Model.Point references and raw register addresses differently.

---

## 2. Current Architecture & Gaps

### 2.1 SunSpec Model.Point Resolution
For tags containing a dot (e.g. `"701.W"`), the sequencer maps the point to its `sunspec2` model definition:
* **Scaling:** Scale factors (`sf`) are read dynamically and applied transparently:
  * **Reads:** `value × 10^sf`
  * **Writes:** `human / 10^sf`
* **Symbols:** Enum values are automatically resolved to their descriptions if defined in the SunSpec PICS schema.

### 2.2 Raw Register Resolution
For tags without a dot (e.g. `"15507"`, `"15510"`), the sequencer assumes they are raw Modbus register addresses and completely bypasses the SunSpec model engine:
* **Reads:** Queries exactly 1 holding register (Modbus Function 3, `Count = 1`) and unpacks the 2 bytes as a 16-bit unsigned integer (`uint16`, `>H`).
* **Writes:** Queries Modbus Function 6 (Write Single Register) to update exactly 1 register with a 16-bit integer.
* **Limitations:**
  * **32-Bit Register Truncation:** Proprietary registers such as `15510` (`PVOutputWh`) and `15512` (`proxOutputWh`) are 32-bit values (`uint32`) spanning two registers. Read operations only query 1 register, obtaining the high word and truncating the low word. Writes only write the first word, leaving the low-word register un-updated.
  * **No Scaling or Signs:** Signed 16-bit integers (`int16`) or scaled raw values are not scaled or signed-extended.
  * **No Symbol Resolution:** Raw registers that map to enums (like `"15507"` representing `OnGridMode`) print as raw numbers instead of descriptive strings.

---

## 3. Structural Design Options

### Option A: Upstream Registry in the Library (Recommended)
Embed a proprietary register definition registry directly within the `franklinwh-modbus` library (e.g. inside `src/franklinwh_modbus/constants.py` or `sequencer.py`):
```python
EXTENSION_REGISTRY = {
    15506: {"name": "LoadActiveP", "type": "uint16", "sf": 0},
    15507: {"name": "OnGridMode", "type": "uint16", "sf": 0, "symbols": {1: "Backup", 2: "Self-Consumption", 3: "TOU"}},
    15508: {"name": "SelfReserve", "type": "uint16", "sf": 0},
    15509: {"name": "TouReserve", "type": "uint16", "sf": 0},
    15510: {"name": "PVOutputWh", "type": "uint32", "sf": 0},
    15512: {"name": "proxOutputWh", "type": "uint32", "sf": 0},
    16000: {"name": "HomeLoadHighRes", "type": "uint16", "sf": 0},
}
```

* **Pros:** Complete encapsulation within the library. Reusable across CLI and Modbus-bridge callers without schema modifications.
* **Cons:** Requires a library version bump for new proprietary registers.

### Option B: Step-Level Schema Extensions
Extend the sequence JSON step schema to allow inline specification of register structures:
```json
{
  "step": "Read Cumulative Generation",
  "reads": [
    {
      "addr": 15510,
      "type": "uint32",
      "sf": 0,
      "label": "PVOutputWh"
    }
  ]
}
```

* **Pros:** High flexibility; callers can query arbitrary, undocumented Modbus registers on any model.
* **Cons:** Verbose step definitions; duplicates structural data across different sequence files.

### Option C: Hybrid Approach (Proposed Solution)
Combine both solutions: use a built-in `EXTENSION_REGISTRY` in the library for all known proprietary registers, while also upgrading the sequencer parse engine to accept inline object/dictionary definitions in sequence steps to override or define new registers dynamically.

---

## 4. Why `"reads"` is a list `[]` and `"writes"` is an object `{}`

In the sequence step JSON schema:
1. **`reads` is a List (`[]` / JSON Array):** A read step only requires the sequencer to fetch and display the current value of a point or address. No target value or parameter is needed, so a simple sequence of strings (e.g. `["701.W", "15507"]`) is sufficient.
2. **`writes` is an Object (`{}` / JSON Object):** A write step requires a pair containing the target register *and* the value to be written to that register. A key-value map (e.g. `{"15508": 20, "704.WSetPct": 30}`) is necessary to represent this.

Because of this structural difference, the constructs are **not** interchangeable. The sequencer codebase calls `.items()` on `"writes"` objects to iterate over tag-value pairs, and iterates directly over elements in `"reads"` lists.
