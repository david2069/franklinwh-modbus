# SunSpec Infopoint Sequencer Guide

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

Sequences are executed via the `franklinwh_cli.py` tool:

```bash
# Execute a sequence from a JSON file
python3 tools/franklinwh_cli.py -i <IP> --sequence-file examples/reversion_limit_example.json

# Run with custom base address and Modbus unit
python3 tools/franklinwh_cli.py -i <IP> -b 1000 -u 1 --sequence-file <PATH>
```

---

### 2. JSON Schema Master Reference

| Key | Type | Purpose / Function | Typical Use Case |
|:----|:-----|:-------------------|:-----------------|
| `name` / `step` | string | Descriptive label for the step in logs. | `"Step": "Enable VPP Mode"` |
| `writes` | object | Dictionary of `Model.Point: Value` to write. | `{"704.WSetEna": 1}` |
| `reads` | list | List of `Model.Point` tags to read and log. | `["704.WSetPct", "714.DCW"]` |
| `verify` | bool | Wait for readback to match written value. | `true` (Default) |
| `verify_timeout_ms`| int | Max time to poll for write verification. | `2000` (Default) |
| `abort_on_failure` | bool | Stop sequence if this step fails. | `true` (Default) |
| `sleep_ms` | int | Wait after step completion (settling time). | `500` for hardware propagation. |
| `wait_for` | object | Poll a register until a condition is met. | See "Wait For Configuration" below. |
| `on_error` | string | What to do when the step fails: `abort` (default), `continue` or `retry`. | `"continue"` for a probe where a rejection is the expected result. |
| `retries` / `retry_ms` | int | With `on_error: retry`: attempts and delay. **Transport errors only** (timeout, lost connection). A Modbus exception response is never retried. | `2` / `1000` |

#### Failure handling and cleanup

A sequence can be a plain list of steps, or an object with a `cleanup` block:

```json
{
  "steps":   [ { "step": "Enable", "writes": { "704.WSetEna": 1 } } ],
  "cleanup": [ { "step": "Release", "writes": { "704.WSetEna": 0 } } ]
}
```

- The `cleanup` steps **always run**: after the last step, after an abort, after a rejected write, and after Ctrl-C. A failed cleanup step doesn't stop the rest of the cleanup.
- A rejected write (the device answers with a Modbus exception, e.g. code 3 = illegal value) is reported as `REJECTED (exc 3)`, then `on_error` decides: `abort` skips the remaining steps (cleanup still runs), `continue` goes on.
- A verify failure with no exception still honours `abort_on_failure`.
- At the end the sequencer logs a summary: `OK`, `REJECTED (exc N)`, `TIMEOUT`, `TRANSPORT ERROR`, `FAILED (verify)`, `SKIPPED (abort)`, `CLEANUP …`. The exit code is 0 only if every step succeeded.

#### Wait For Configuration (`wait_for`)

| Sub-Key | Type | Purpose | Example |
|:--------|:-----|:--------|:--------|
| `point` | string | The `Model.Point` tag to poll. | `"704.WSetRvrtRem"` |
| `operator` | string | Comparison: `==`, `!=`, `>`, `<`, `>=`, `<=`. | `"<="` |
| `value` | any | The target value to compare against. | `0` |
| `timeout_ms` | int | Max polling time (default 30s). | `60000` (1 minute) |
| `poll_ms` | int | Time between poll attempts (default 1s). | `500` (twice a second) |

---

### 3. Timing & Settling (`sleep_ms`)

FranklinWH hardware often requires time to process register changes before they reflect in telemetry or physical state. You can add explicit delays using `sleep_ms`.

```json
{
  "step": "Enable Remote Control",
  "writes": { "704.WSetEna": 1 },
  "sleep_ms": 500
}
```

- **`sleep_ms`**: Executed *after* the writes/verification of the current step.
- **`post_sleep_ms`**: An alias for `sleep_ms`.

### 4. Waiting for Conditions (`wait_for`)
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

### 6. Cleanup & Releasing Control

While the CLI provides a dedicated `--stop` flag, you can also include a "Stop" step at the end of your JSON sequences to ensure the gateway returns to its native operating mode automatically.

**A "Clean Release" sequence step:**
```json
{
  "m": 704,
  "p": ["WSetEna", "WSetPct", "WSet"],
  "v": [0, 0, 0],
  "note": "Release Modbus control"
}
```

**Why use the Sequencer to stop?**
- **Atomic Automation**: Charge for N seconds, then release, all in one command without needing a separate `--stop` call.
- **Verification**: The sequencer will verify that `WSetEna` actually returned to `0`, catching any persistent "Zombie States."
- **Custom Fallbacks**: In advanced scenarios, you may want to set a specific power level *before* disabling the master switch.

---

## 📖 Model 704 Battery Control Examples

For a detailed suite of real-world active power, export limiting, power factor control, and arbitrage sequences, refer to the **[Model 704 Control Examples Handbook](MODEL_704_CONTROL_EXAMPLES.md)**. 

All 12 sequence examples are fully mapped to production JSON files under `examples/sequencer/` and utilize safety standby and automatic release steps.

---

## Hardware-Specific Learnings (aGate X)

*Last Updated: 2026-05-15*

Through development and testing on aGate firmware `V10R01B04D00`, the following patterns were established:

### The "Silent Discard" Pattern
Many registers (like `WMaxLimPctEna` and `ControllerHb`) will return a Modbus **Success (ACK)** when written to, but the internal hardware will **silently discard** the value. The sequencer's verification loop detects this by comparing the readback against the expected value.

### Verified Control Path: WSet (Remote Control)
For curtailing or forcing power, the **Remote Control** group in Model 704 is the only verified working path:
1.  **`704.WSetEna = 1`**: Master switch to enable remote setpoints.
2.  **`704.WSetPct = X`**: Set active power as a percentage of rated capacity.

### Cleanup
To release the gateway from a sequence and return it to its normal operating mode, use the `--stop` flag:
```bash
python3 tools/franklinwh_cli.py -i <IP> --stop
```
