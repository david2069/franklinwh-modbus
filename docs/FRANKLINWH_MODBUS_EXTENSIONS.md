# FranklinWH Extension Registers

Besides the SunSpec models, the aGate's **Modbus TCP Server (aGate :502)** has **FranklinWH-specific holding registers**: the operating mode, the SoC reserves, the solar breakdown and the home load. This page is the one place they are listed.

## How they work

- **Outside the SunSpec model chain.** sunspec2 can't see them. Read them with a plain FC3 request at the **PDU address** below; write with FC6.
- **Use the address as listed.** These are Modbus PDU addresses, 0-based, as sent on the wire. Never offset by 40000 or 40001, which returns exception 2. See [Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map).
- **Vendor-specific and partly undocumented.** Behaviour can change with firmware. Each row says what it rests on: **Documented** (FranklinWH PICS, SPAN tab), **Measured** (read on the device, with date and firmware), or **Inferred**.
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
| 15507 | OnGridMode | R/W ⚠️ | uint16 enum | Operating mode | `read_native_mode()['mode_raw']`, `['mode_name']`; written by `set_native_mode()` | **Values under review (#75)**; see below |
| 15508 | SelfReserve | R/W ⚠️ | uint16, % | Self-consumption SoC reserve | `read_native_mode()['self_reserve_pct']`; `set_self_consumption_reserve()` | Measured 2026-10-18, V10R01B04D00 |
| 15509 | TouReserve | R/W ⚠️ | uint16, % | **Reads the same value as 15508**, not the TOU reserve | `read_native_mode()['tou_reserve_pct']`; `set_tou_reserve()` | Documented defect; measured 2026-10-18, V10R01B04D00 (#63) |
| 15510–15511 | PVOutputWh | R | uint32 (high, low), Wh | PV energy, total (lifetime) | read, not returned | Measured: matches M502 `OutWh` |
| 15512–15513 | proxOutputWh | R | uint32 (high, low), Wh | PV energy, proximal (lifetime) | read, not returned | Measured: matches M502 `OutWh` |
| 16000 | — | R | uint16, W (~1 W) | Home load, high resolution | `…['home_load_ext']` (falls back to 15506) | Undocumented; measured 2026-03-15 |
| 16001 | — | R | uint16, % | Same value as 15508 | — | Undocumented; measured 2026-10-18 |
| 16002 | — | R | uint16 | 20 on the reference site; matches the local API's `BBBackupSoc` | — | Undocumented; **unconfirmed** (#63) |
| 15000–15043 | — | R | various | Mirrors of SunSpec values (e.g. 15020 = M713 `WHRtg`, 15036 = M713 `SoH` raw, 15025 ≈ M701 `LNV`, 15024 ≈ grid frequency) | — | Undocumented; measured. Writes accepted but discarded (probe 2026-03-08) |

`…` = `read_solar_status()['extension']`. The raw scans behind the measured rows are in the [Extensions Manifest](FRANKLINWH_EXTENSIONS_MANIFEST.md).

### 15507 operating mode values

The sources disagree, so compare modes by **name** and **don't write modes 1, 3 or 4** until #75 is settled:

| Value | Library (`NATIVE_MODES`) | Device scan 2026-05-14 (Manifest) | Older QUIRKS table |
|---|---|---|---|
| 0 | — | — | Emergency |
| 1 | Emergency Backup | Backup | TOU |
| 2 | Self-Consumption | Self-Consumption | Self-Consumption |
| 3 | TOU | TOU | Manual |
| 4 | Manual | — | — |

The 2026-05-14 scan notes "Verified 1-indexed mapping", which agrees with the library. A dated read of 15507 in each mode on current firmware will settle it (#68 item 21).

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

- Only 15507–15509 take writes, through `set_native_mode()`, `set_self_consumption_reserve()` and `set_tou_reserve()`. Each writes, reads back, and returns `(ok, message)`. Use `dry_run=True` to preview.
- **Writes only take effect when FranklinWH has enabled them on the unit** (QUIRKS calls this the "SPAN Modbus" unlock in the installer app). Otherwise they are silently ignored, which is why the setters read back.
- `connect()` never writes. `test_extension_writability()` **does**: it writes test values to the mode and reserves, then restores them.
- Writing the TOU reserve (15509) can't be confirmed by reading it back, because 15509 reads the same value as 15508.

## Not available over Modbus

Smart circuits, the generator, V2L and per-MPPT telemetry aren't in any register found so far. Use the FranklinWH app or the [cloud API](https://david2069.github.io/franklinwh-cloud/).
