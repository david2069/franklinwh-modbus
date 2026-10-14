# SunSpec InfoPoint Sequencer Guide

The **SunSpec InfoPoint Sequencer** is a high-level orchestration engine integrated into `franklinwh-cli`. it enables complex, multi-step Modbus operations defined via JSON configuration files.

## Purpose & Intent

FranklinWH aGate systems often require specific sequences of register writes (e.g., enabling Remote Control before setting a power level) or periodic verification of hardware state transitions. This tool automates those sequences, ensuring that:
1.  **Values are Scaled Correctly**: Human-readable values (like `30%`) are automatically converted to raw Modbus values (like `300`) based on the point's Scale Factor (`_SF`).
2.  **State is Verified**: Every write is followed by a readback loop to confirm the hardware actually accepted and persisted the change.
3.  **Fail-Fast Execution**: Sequences can be configured to abort immediately if a critical step fails.

For a detailed list of supported registers and their compliance status, see the [SunSpec Model Reference](SUNSPEC_MODEL_REFERENCE.md).

---

## Native Addressing

While the SunSpec standard often defaults to `40000`, the FranklinWH native base address is **`1`**. The sequencer automatically handles this based on the `-b` or `--base-address` flag.

---

## Usage

Sequences are executed via the `franklinwh_cli.py` tool. You can run them using a JSON file via `--sequence-file`, or directly as a JSON string via `--sequence`.

### 1. JSON Sequence Files (`--sequence-file`)

```bash
# Execute a sequence from a JSON file
python3 tools/franklinwh_cli.py -i <IP> --sequence-file examples/reversion_limit_example.json

# Run with custom base address and Modbus unit
python3 tools/franklinwh_cli.py -i <IP> -b 1000 -u 1 --sequence-file <PATH>
```

### 2. In-line JSON Sequences (`--sequence`)

For quick, one-off commands or register scans, you can pass a JSON string directly using the `--sequence` flag.

> [!IMPORTANT]
> Since JSON requires keys and string values to be enclosed in **double quotes (`"`)**, the entire sequence string should be wrapped in **single quotes (`'`)** for the terminal shell to parse it correctly. Do **not** use backslashes to escape the double quotes inside single quotes, as doing so will pass the backslashes literally and cause a `JSONDecodeError`.

#### A. Direct Writes (Quick Register Control)
If you pass a flat key-value dictionary, the CLI automatically wraps it into a single write step:
```bash
# Enable Remote Control and set charge rate to 30%
python3 tools/franklinwh_cli.py -i 192.0.2.110 --sequence '{"704.WSetEna": 1, "704.WSetPct": 30}'
```

#### B. In-line Reads (Scan Specific SunSpec Points)
You can read one or more SunSpec registers by providing a dictionary with a `"reads"` key:
```bash
# Read battery power (714.DCW) and grid power (701.W)
python3 tools/franklinwh_cli.py -i 192.0.2.110 --sequence '{"reads": ["714.DCW", "701.W"]}'
```

#### C. Full Single-Step Definition
You can also pass a full single-step definition as a JSON dictionary:
```bash
# Disable Remote Control, wait 2 seconds, and verify
python3 tools/franklinwh_cli.py -i 192.0.2.110 --sequence '{"name": "Disable Remote", "writes": {"704.WSetEna": 0}, "sleep_ms": 2000}'
```

#### D. Full Multi-Step Sequence
You can pass a full multi-step sequence as a JSON array of step dictionaries:
```bash
# Read battery power, enable remote control, set 30% charge, wait 10 seconds, then release remote control
python3 tools/franklinwh_cli.py -i 192.0.2.110 --sequence '[{"reads": ["714.DCW"]}, {"writes": {"704.WSetEna": 1, "704.WSetPct": 30}}, {"sleep_ms": 10000}, {"writes": {"704.WSetEna": 0}}]'
```

---

## JSON Sequence Schema

A sequence is a JSON array of "steps". Each step can perform writes or wait for specific conditions.

### 1. Write Step (Default)
Writes one or more values and optionally verifies them.

```json
{
  "name": "Limit Power to 30%",
  "writes": {
    "704.WSetEna": 1,
    "704.WSetPct": 30
  },
  "verify": true,
  "abort_on_failure": true
}
```

### 2. Wait For Step
Polls a register until it matches a specific value (useful for verifying slow state transitions or dead-man timers).

```json
{
  "name": "Wait for Reversion",
  "type": "wait_for",
  "point": "704.WSetPct",
  "value": 0,
  "timeout": 20,
  "interval": 2
}
```

---

## Conformance Diagnostic Suite

Due to inconsistencies in aGate firmware versions (where some SunSpec registers are declared but not implemented), a **Diagnostic Suite** is provided in `examples/diagnostics/`. 

These examples serve as a "Conformance Test" to track when features become functional in your firmware:

| Test File | Purpose | Intent |
| :--- | :--- | :--- |
| `curtailment_conformance.json` | Tests `WMaxLimPct` | Determines if Global Curtailment is functional. |
| `reactive_power_conformance.json` | Tests `VarSet` | Determines if Reactive Power control is enabled. |
| `heartbeat_conformance.json` | Tests `ControllerHb` | Checks if the hardware safety heartbeat is active. |
| `reversion_conformance.json` | Tests `WSetRvrtTms` | Validates if the dead-man switch actually reverts power. |

---

## Hardware-Specific Learnings

Through development and testing on aGate firmware `V10R01B04D00`, the following patterns were established:

### The "Silent Discard" Pattern
Many registers (like `WMaxLimPctEna` and `ControllerHb`) will return a Modbus **Success (ACK)** when written to, but the internal hardware will **silently discard** the value. The sequencer's verification loop detects this by comparing the readback against the expected value.

### Verified Control Path: WSet (Remote Control)
For curtailing or forcing power, the **Remote Control** group in Model 704 is the only verified working path:
1.  **`704.WSetEna = 1`**: Master switch to enable remote setpoints.
2.  **`704.WSetPct = X`**: Set active power as a percentage of rated capacity.

### Cleanup & Releasing Control

> [!WARNING]
> **Safety Alert & Cleanup Obligation**: Writing setpoints (e.g. `704.WSetPct` or `704.WSetEna`) overrides standard aGate automatic cloud control. If you forget to reset them, the gateway will remain locked in VPP/Remote Control mode forever. Always release the gateway once your tests or sequences are complete!

To release the Modbus client control (stop VPP mode) and return the gateway to standard automatic cloud control, you have two options:

#### Option A: Use the `--stop` flag (Recommended)
This helper command automatically writes `0` to both `704.WSetEna` and `704.WSetPct` and verifies the release:
```bash
python3 tools/franklinwh_cli.py -i <IP> --stop
```

#### Option B: Execute an in-line release sequence
You can reset the registers directly using an in-line sequence command:
```bash
python3 tools/franklinwh_cli.py -i <IP> --sequence '{"704.WSetEna": 0, "704.WSetPct": 0}'
```
