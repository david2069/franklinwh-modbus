# Modbus SunSpec2 Reader Reference

*Last Updated: 2026-05-15 18:57*

The `modbus_sunspec2_reader.py` tool is a high-performance diagnostic utility for scanning, discovering, and monitoring SunSpec-compliant devices. It includes specific enhancements for FranklinWH aGate systems, such as extension register matching and non-zero filtering.

## 1. Connection Options

| Option | Alias | Default | Description |
|:-------|:------|:--------|:------------|
| `-i` | `--ip` | **Required** | Target device IP address. |
| `-p` | `--port` | `502` | Modbus TCP port. |
| `-u` | `--unit` | `1` | Modbus Unit ID (Slave ID). |
| `-b` | `--base-address` | `40000` | Start address for SunSpec discovery. |
| `-t` | `--timeout` | `2.0` | Connection timeout in seconds. |

## 2. Scanning & Discovery

| Option | Description |
|:-------|:------------|
| `-m`, `--models` | Filter models to scan. Supports lists (`1,103`) or ranges (`101-105`). Omit to scan all available models. |
| `--point` | Query a single point (e.g., `103.W` for Inverter Watts). Returns the value and exits. |
| `--raw` | Perform a raw register read (format: `start:count`). Example: `15500:14`. |
| `--match` | Try to match raw register values with known SunSpec points. Requires a full scan to build the database. |

## 3. Output Formats

| Option | Level / Mode | Description |
|:-------|:-------------|:------------|
| `-d` | `--detail` | Set verbosity: `minimal`, `basic`, `values`, `detailed`, `full`. |
| `-c` | `--compact` | One-line summary of discovered Model IDs. |
| `--map` | Columnar list of `model-id` and `string-key`. |
| `--vals` | One-liner per point: `name = scaled-value [units] (type)`. |
| `--json` | Output all results as structured JSON (useful for integration). |
| `--nz` | Non-Zero filter for raw reads. Only shows registers with non-zero values. |

## 4. Performance & Logging

| Option | Description |
|:-------|:------------|
| `--multi-thread` | Enable multi-threading for faster discovery (recommended for full scans). |
| `-v`, `--verbose` | Enable verbose debug logging of Modbus transactions. |

---

## Examples

### Discover all models (Full Detail)
```bash
python3 tools/modbus_sunspec2_reader.py -i 192.0.2.110 -d full
```

### Scan specific Inverter models (Values only)
```bash
python3 tools/modbus_sunspec2_reader.py -i 192.0.2.110 -m 101,103 -d values
```

### Raw extension scan with Non-Zero filtering
```bash
python3 tools/modbus_sunspec2_reader.py -i 192.0.2.110 --raw 15500:20 --nz
```

### Search for a value in raw memory (Match mode)
```bash
# Finds which standard SunSpec point matches the value in raw register 15020
python3 tools/modbus_sunspec2_reader.py -i 192.0.2.110 --raw 15000:100 --match --nz
```
