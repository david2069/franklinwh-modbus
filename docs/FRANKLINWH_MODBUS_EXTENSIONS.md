# FranklinWH Extension Registers

Besides the SunSpec models, the aGate's **Modbus TCP Server (aGate :502)** has **FranklinWH-specific holding registers**: the operating mode, the SoC reserves, the solar breakdown and the home load. This page is the one place they are listed.

## How they work

- **Outside the SunSpec model chain.** sunspec2 can't see them. Read them with a plain FC3 request at the **PDU address** below. FC6 writes are undocumented; see [Writing](#writing).
- **Use the address as listed.** These are Modbus PDU addresses, 0-based, as sent on the wire. Don't offset by 40000 or 40001: untested for these registers, and an exception 2 on V10R01B04D00 for the SunSpec map. See [Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map).
- **Vendor-specific and partly undocumented.** Behaviour can change with firmware. Each row says what it rests on: **Documented** (listed on the SPAN tab of FranklinWH's PICS, which is proprietary, not distributed and not a public specification; it does not confirm writability on current firmware), **Measured** (read on the device, with date and firmware), or **Inferred**.
- **One Modbus client per aGate.** Stop other clients before reading.

## Register table

| PDU | Name | Access | Type, unit | Meaning | In the library | Evidence |
|---|---|---|---|---|---|---|
| 15500 | PVUse | R | uint16 flag | Proximal (aGate) PV installed | read, not returned | Documented |
| 15501 | apBoxPVUse | R | uint16 flag | Remote (aPbox/aHub) PV installed | read, not returned | Documented |
| 15502 | PVOutputP | R | uint16, W | Total PV power, all sources | `read_solar_status()['extension']['pv_total']` | Documented; measured |
| 15503 | — | R | uint16, W | PV proximal | `…['pv_proximal']` | Documented |
| 15504 | — | R | uint16, W | PV remote 1 | `…['pv_remote1']` | Documented |
| 15505 | — | R | uint16, W | PV remote 2 | `…['pv_remote2']` | Documented |
| 15506 | LoadActiveP | R | uint16, W (~100 W steps) | Home load | `…['home_load_ext_quantized']` | Documented; measured 2026-03-15 |
| 15507 | OnGridMode | R (writes undocumented) | uint16 enum | Operating mode | `read_native_mode()['mode_raw']`, `['mode_name']`; written by `set_native_mode()` | Measured 2026-10-21/22, V12R02B60D00 (1, 2, 3); see below |
| 15508 | SelfReserve | R (writes undocumented) | uint16, % | Self-consumption SoC reserve | `read_native_mode()['self_reserve_pct']`; `set_self_consumption_reserve()` | Measured 2026-10-18, V10R01B04D00 |
| 15509 | TouReserve | R (writes undocumented) | uint16, % | TOU SoC reserve. **On V12R02B60D00 it holds the TOU reserve** (15 vs SC 8, matching the app). On V10R01B04D00 it repeated 15508 | `read_native_mode()['tou_reserve_pct']`; `set_tou_reserve()` | Measured 2026-10-20/21, V12R02B60D00; the defect measured 2026-10-18, V10R01B04D00 (#63) |
| 15510–15511 | PVOutputWh | R | uint32 (high, low), Wh | PV energy, total (lifetime) | read, not returned | Measured: matches M502 `OutWh` |
| 15512–15513 | proxOutputWh | R | uint32 (high, low), Wh | PV energy, proximal (lifetime) | read, not returned | Measured: matches M502 `OutWh` |
| 16000 | — | R | uint16, W (~1 W) | Home load, high resolution | `…['home_load_ext']` (falls back to 15506) | Undocumented; measured 2026-03-15 |
| 16001 | — | R | uint16, % | **Reserve for the active mode:** 100 in Emergency Backup, 15508's value in Self-Consumption (8), 15509's in TOU (15) | — | Undocumented; measured on V12R02B60D00, one read per mode, 2026-10-21/22 (#63) |
| 16002 | — | R | uint16 | 20 in both Self-Consumption and TOU on the reference site; matches the local API's `BBBackupSoc` | — | Undocumented; **meaning unconfirmed** (#63) |
| 15000–15043 | — | R | various | Mirrors of SunSpec values (e.g. 15020 = M713 `WHRtg`, 15036 = M713 `SoH` raw, 15025 ≈ M701 `LNV`, 15024 ≈ grid frequency) | — | Undocumented; measured. Writes accepted but discarded (probe 2026-03-08) |

`…` = `read_solar_status()['extension']`. The raw scans behind the measured rows are in the [Extensions Manifest](FRANKLINWH_EXTENSIONS_MANIFEST.md) (V10R01B04D00) and the [V12R02B60D00 snapshot](SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md).

### 15507 operating mode values

| Value | Mode | Evidence |
|---|---|---|
| 1 | Emergency Backup | Measured on V12R02B60D00 with the app in that mode (2026-10-21; again 2026-10-28) |
| 2 | Self-Consumption | Measured on V12R02B60D00 (2026-10-21) |
| 3 | TOU | Measured on V12R02B60D00 (2026-10-21) |

No other value has been read from 15507. This matches the library, the 2026-05-14 device scan and the first QUIRKS table. Earlier docs and code also listed **0 = Emergency** and **4 = Manual**, and one QUIRKS revision had 1 = TOU and 3 = Manual. Those were added without a source and have been removed (#75). Writing 15507 did not take effect on V12R02B60D00 (owner observation, 2026-10-21), so the mapping holds for reading only.

## Reading

Use the library methods:

```python
solar = ctrl.read_solar_status()
ext   = solar.get("extension") or {}          # 15500–15509, 16000
mode  = ctrl.read_native_mode()               # 15507–15509
print(ext.get("pv_total"), ext.get("home_load_ext"), mode.get("mode_name"))
```

For registers the library doesn't return, use a raw FC3 read; see [API Cookbook §8.3](API_COOKBOOK.md#83-reading-them-yourself).

## Writing ⚠️

- Writes to the FranklinWH extension registers are undocumented and unconfirmed. FranklinWH has not documented these registers and has never documented any of them as writable. Whether FranklinWH must authorise a Modbus client to write them, and how, is unknown. On `V12R02B60D00` (owner observation, 2026-10-21), writes to 15507–15509 did not take effect: the mode did not switch and the reserves did not change. **Re-tested 2026-10-23 with two independent tools** (plain pymodbus, and the sequencer after the raw-write fix in #100): 15508 8→9, 15509 15→16 and 15507 2→3 were each acknowledged with a normal FC06 echo, and none changed within 30 s (90 s for the mode); 16001 stayed 8. All restored. Treat them as read-only.
- The library writes only 15507–15509, through `set_native_mode()`, `set_self_consumption_reserve()` and `set_tou_reserve()`. Each attempts the write, reads back, and returns `(ok, message)` with the read-back result; a failed write is reported, not assumed. Use `dry_run=True` to preview.
- `connect()` never writes. `test_extension_writability()` **does**: it writes test values to the mode and reserves, then restores them.
- 15509 can only be read back as the TOU reserve on V12R02B60D00. On V10R01B04D00 it reads the same value as 15508. On V12R02B60D00, writes to it did not take effect (owner observation, 2026-10-21).

## Not available over Modbus

Smart circuits, the generator, V2L and per-MPPT telemetry aren't in any register found so far. Use the FranklinWH app or the [cloud API](https://david2069.github.io/franklinwh-cloud/).
