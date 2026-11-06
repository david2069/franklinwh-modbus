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
| 15506 | LoadActiveP | R | uint16, W (~100 W steps on V10R01B04D00; ~1 W on V12R02B60D00) | Home load | `…['home_load_ext_quantized']` | Documented; measured 2026-03-15 (V10), 2026-11-03 (V12) |
| 15507 | OnGridMode | R (writes undocumented) | uint16 enum | Operating mode | `read_native_mode()['mode_raw']`, `['mode_name']`; written by `set_native_mode()` | Measured 2026-10-21/22, V12R02B60D00 (1, 2, 3); see below |
| 15508 | SelfReserve | R (writes undocumented) | uint16, % | Self-consumption SoC reserve | `read_native_mode()['self_reserve_pct']`; `set_self_consumption_reserve()` | Measured 2026-10-18, V10R01B04D00 |
| 15509 | TouReserve | R (writes undocumented) | uint16, % | TOU SoC reserve. **On V12R02B60D00 it holds the TOU reserve** (15 vs SC 8, matching the app). On V10R01B04D00 it repeated 15508 | `read_native_mode()['tou_reserve_pct']`; `set_tou_reserve()` | Measured 2026-10-20/21, V12R02B60D00; the defect measured 2026-10-18, V10R01B04D00 (#63) |
| 15510–15511 | PVOutputWh | R | uint32 (high, low), Wh | PV energy, total (lifetime) | read, not returned | Measured: matches M502 `OutWh` |
| 15512–15513 | proxOutputWh | R | uint32 (high, low), Wh | PV energy, proximal (lifetime) | read, not returned | Measured: matches M502 `OutWh` |
| 16000 | — | R | uint16, W (~1 W) | Home load, high resolution | `…['home_load_ext']` (falls back to 15506) | Undocumented; measured 2026-03-15 |
| 16001 | — | R | uint16, % | **Reserve for the active mode:** 100 in Emergency Backup, 15508's value in Self-Consumption (8), 15509's in TOU (15) | — | Undocumented; measured on V12R02B60D00, one read per mode, 2026-10-21/22 (#63) |
| 16002 | — | R | uint16 | 20 in both Self-Consumption and TOU on the reference site; matches the local API's `BBBackupSoc` | — | Undocumented; **meaning unconfirmed** (#63) |
| 15000–15043 | — | R | uint16 raw; some pairs look like 32-bit values | Undocumented. Several match SunSpec values; see [register by register](#1500015043-register-by-register) and the [mapping](#extension-sunspec-mapping) | — | Undocumented; raw values measured; meanings inferred. Writes accepted but discarded (probe 2026-03-08) |

`…` = `read_solar_status()['extension']`. The raw scans behind the measured rows are in the [Extensions Manifest](FRANKLINWH_EXTENSIONS_MANIFEST.md) (V10R01B04D00) and the [V12R02B60D00 snapshot](SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md).

### 15000–15043, register by register

Raw uint16 values from one site (#132). V10R01B04D00: the undated scan in the [Extensions Manifest](FRANKLINWH_EXTENSIONS_MANIFEST.md). V12R02B60D00: the 2026-10-20 re-scan and an owner read on 2026-10-31 (15000–15039 only). **Candidates are inferred from equal or near values in the same capture, not measured meanings**; none is used by the library. Each register has an entry in `firmware_quirks.json` (`ext_15000` … `ext_15043`; 15013, 15016 and 15035 keep their earlier ids), all with `mapped: false`.

| PDU | V10 | V12 10-20 | V12 10-31 | Meaning |
|---|---|---|---|---|
| 15000 | 0 | 1 | 1 | Meaning unknown: 1 on V12, 0 on V10. |
| 15001 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15002 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15003 | 0 | 800 | 200 | Confirmed 2026-11-03: PV power, equal to M502 `OutPw`. |
| 15004 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15005 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15006 | 0 | 65535 | 65535 | Meaning unknown: high word of a signed pair with 15007 (65535 on V12). |
| 15007 | 257 | 65375 | 65303 | Meaning unknown: low word of a signed pair with 15006 (-161 on 2026-10-20, -233 on 2026-10-31). |
| 15008 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15009 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15010 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15011 | 583 | 195 | 198 | Confirmed 2026-11-03: home load, equal to 16000. |
| 15012 | 65535 | 65535 | 65535 | Read 65535 throughout the 2026-11-03 run (charging). Whether it is the high word of a 32-bit value with 15013 is still open. |
| 15013 | 60538 | 64907 | 65507 | Confirmed: battery power, int16, positive = discharging, negative = charging; tracks M714 `DCW` at ~1 W. |
| 15014 | 0 | 65535 | 65535 | Meaning unknown: high word of a signed pair with 15015 (65535 on V12). |
| 15015 | 61 | 65511 | 65512 | Meaning unknown: low word of a signed pair with 15014 (-25 on 2026-10-20, -24 on 2026-10-31). |
| 15016 | 2 | 2 | 2 | Inferred: status. 2 normal, 6 dispatch, 3 likely off-grid, 1 likely start-up (week of bridge history). |
| 15017 | 20 | 20 | 20 | Candidate: same value as 16002 (20) on every read. |
| 15018 | 65535 | 5000 | 5000 | Candidate: M702 WChaRteMaxRtg (5000 on V12); 65535 on V10. |
| 15019 | 65535 | 5000 | 5000 | Candidate: M702 WDisChaRteMaxRtg (5000 on V12); 65535 on V10. |
| 15020 | 13600 | 13600 | 13600 | Candidate: M713 WHRtg (13600 on every read). |
| 15021 | 1 | 1 | 1 | Meaning unknown: 1 on every read. |
| 15022 | 5581 | 65533 | 65475 | Meaning unknown: varies (5581 on V10; 65533, 65475 on V12). |
| 15023 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15024 | 49969 | 50010 | 50030 | Candidate: grid frequency x 1000 (49969, 50010, 50030). |
| 15025 | 2380 | 2422 | 2416 | Confirmed 2026-11-03: grid voltage × 10, M701 `LNV`. |
| 15026 | 1 | 1 | 1 | Meaning unknown: 1 on every read. |
| 15027 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15028 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15029 | 70 | 91 | 94 | Confirmed 2026-11-03: high word of M701 `TotWhInj` (uint32 with 15030). |
| 15030 | 30761 | 993 | 18367 | Confirmed 2026-11-03: low word of M701 `TotWhInj`. |
| 15031 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15032 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15033 | 22 | 29 | 29 | Confirmed 2026-11-03: high word of M701 `TotWhAbs` (uint32 with 15034). |
| 15034 | 22637 | 18330 | 19910 | Confirmed 2026-11-03: low word of M701 `TotWhAbs`. |
| 15035 | 268 | 325 | 994 | Confirmed 2026-11-03: SoC × 10, 0.1 % steps. |
| 15036 | 956 | 948 | 948 | Candidate: M713 SoH raw (948 = 948 on 2026-10-20). |
| 15037 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15038 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15039 | 0 | 0 | 0 | Meaning unknown; read 0 on every capture. |
| 15040 | 65527 | 826 | — | Inferred: PV power (int16) as Direct Connect reports it; −9 W after dark. |
| 15041 | 0 | 0 | — | Meaning unknown; read 0 on every capture. |
| 15042 | 0 | 0 | — | Meaning unknown; read 0 on every capture. |
| 15043 | 1 | 1 | — | Meaning unknown: 1 on every read. |

A read-only correlation run on 2026-11-03 (charging, 54 samples) confirmed 15003, 15011, 15013, 15025, 15029–15030, 15033–15034 and 15035; see the [mapping](#extension-sunspec-mapping). The rest stay candidate or unknown (#132).

### 15507 operating mode values

| Value | Mode | Evidence |
|---|---|---|
| 1 | Emergency Backup | Measured on V12R02B60D00 with the app in that mode (2026-10-21; again 2026-10-28) |
| 2 | Self-Consumption | Measured on V12R02B60D00 (2026-10-21) |
| 3 | TOU | Measured on V12R02B60D00 (2026-10-21) |

No other value has been read from 15507. This matches the library, the 2026-05-14 device scan and the first QUIRKS table. Earlier docs and code also listed **0 = Emergency** and **4 = Manual**, and one QUIRKS revision had 1 = TOU and 3 = Manual. Those were added without a source and have been removed (#75). Writing 15507 did not take effect on V12R02B60D00 (owner observation, 2026-10-21), so the mapping holds for reading only.

## Extension → SunSpec mapping

One row per register. For each register: the SunSpec point that carries the same quantity, or **none (non-SunSpec)**, and whether a client should prefer the extension value. Non-SunSpec registers are vendor quirks: no SunSpec model holds them.

**Status:**
- **Confirmed:** named in FranklinWH's register list and/or read with a known device state, and equal to the SunSpec point where there is one.
- **Inferred:** equal or near the SunSpec value in a capture, but not read in the same pass as the SunSpec chain under controlled conditions. Equal values are leads, not proof (#132).
- **Unknown:** no candidate, or a lead from a value match only.

Captures: V10 = V10R01B04D00, undated scan ([Extensions Manifest](FRANKLINWH_EXTENSIONS_MANIFEST.md)). V12 = V12R02B60D00: the 2026-10-20 [snapshot](SUNSPEC_SNAPSHOT_2026-10-20_V12R02B60D00.md) (export and re-scan), and owner reads on 2026-10-31 and 2026-11-03 (unit 1, extensions only, no SunSpec read). All from one site. Type is the uint16/int16 reading of the raw register; pairs are (high, low).

### 15000–15043

| PDU | Type, scale, units, sign | SunSpec equivalent | Status and evidence | Prefer the extension? |
|---|---|---|---|---|
| 15000 | uint16 | none (non-SunSpec) | Unknown. 1 on V12 (10-20, 10-31, 11-03), 0 on V10 | — |
| 15001, 15002, 15004, 15005, 15008–15010, 15023, 15027, 15028, 15031, 15032, 15037–15039, 15041, 15042 | uint16 | none known | Unknown. 0 on every capture | — |
| 15003 | uint16, W | M502 `OutPw` | **Confirmed.** Equal to `OutPw` in 54/54 samples, 1700–5600 W, while charging ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)). Earlier: equal to 15502 (10-20, 10-31) | No: same value |
| 15006–15007 | int32 pair, sign unknown | none known | Unknown. −161 (10-20), −233 (10-31), −594 (11-03); −268..−7 while charging ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)); +268..+270 after dark ([run 2026-11-06](https://github.com/david2069/franklinwh-modbus/issues/132)). Flips sign between day and night; no SunSpec point matches. V10 15007 = 257 | — |
| 15011 | uint16, W | none (SunSpec has no home load point) | **Confirmed:** home load. Equal to 16000 in 54/54 samples, 67–945 W ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)) | Use 16000 (same value) |
| 15012–15013 | int16 (15013), W, positive = discharging, negative = charging | M714 `DCW` | **Confirmed both ways.** Charging: tracks `DCW` in 54/54 samples, −1446 to −4740 W, median 10 W apart ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)). Discharging: positive in 28,320/28,320 samples, within 100 W of `DCW` in 99.9 % ([bridge history 2026-10-30–11-06](https://github.com/david2069/franklinwh-modbus/issues/132)); +240..+256 at `DCW` +200..+300 ([run 2026-11-06](https://github.com/david2069/franklinwh-modbus/issues/132)). `DCW` moves in 100 W steps. 15012 read 65535 throughout, so int16 vs int32 is still open | Yes, for resolution: about 1 W vs `DCW`'s 100 W steps |
| 15014–15015 | int32 pair, sign unknown | none known | Unknown. −25 (10-20), −24 (10-31), −22 (11-03); −135..302 while charging, no match ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)); −529..−420 after dark, moving with M701 `Var` (r = −0.98 over a small range) ([run 2026-11-06](https://github.com/david2069/franklinwh-modbus/issues/132)). Lead only. V10 15015 = 61 | — |
| 15016 | uint16 enum | none (non-SunSpec) | Inferred: operating status. Over a week of 10 s samples ([bridge history 2026-10-30–11-06](https://github.com/david2069/franklinwh-modbus/issues/132)): **2** in 53,708 (normal); **6** in 2,482, with the battery discharging ~4.9 kW to the grid (a dispatch); **3** in 631, with grid power 0 and the battery supplying the home (likely off-grid); **1** in 12, all values 0 (likely start-up or unreachable). Earlier bridge reports agree: 6 during a WSet dispatch, 3 off-grid (V10) | Yes, as a vendor status. SunSpec has no equivalent |
| 15017 | uint16 | none known | Unknown. 20 on every read, equal to 16002. An ambient-temperature lead comes from a value match only | — |
| 15018 | uint16, W | M702 `WChaRteMaxRtg` | Inferred. 5000 = 5000 (V12 snapshot). V10: 65535 | No: same value |
| 15019 | uint16, W | M702 `WDisChaRteMaxRtg` | Inferred. 5000 = 5000 (V12 snapshot). V10: 65535 | No: same value |
| 15020 | uint16, Wh | M713 `WHRtg` | Inferred. 13600 = 13600 on every capture (V10 and V12) | No: same value |
| 15021 | uint16 | none known | Unknown. 1 on every read | — |
| 15022 | int16 | none known | Unknown. V10 5581; V12 −3, −61, −295 (10-20, 10-31, 11-03); −342..520 while charging, −13..11 after dark; no match in either run ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132), [run 2026-11-06](https://github.com/david2069/franklinwh-modbus/issues/132)) | — |
| 15024 | uint16, × 0.001, Hz | M701 `Hz` (`Hz_SF` −3, same scale) | Inferred. Close to `Hz` but not equal: within the bracketing reads in only 3/54 samples, up to 0.020 Hz apart ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)). Possibly a different measurement or averaging | No |
| 15025 | uint16, × 0.1, V | M701 `LNV` (`V_SF` −1) | **Confirmed.** Equal to `LNV` raw in 48/54 samples, the rest within 0.2 V ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)) | No: same scale |
| 15026 | uint16 | none known | Unknown. 1 on every read | — |
| 15029–15030 | uint32 pair, Wh | M701 `TotWhInj` | **Confirmed.** Equal in 54/54 samples ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)); also 5964768 = 5964768 (V12 snapshot). 15030 alone is the low word, not a voltage | No: same value |
| 15033–15034 | uint32 pair, Wh | M701 `TotWhAbs` | **Confirmed.** Equal in 54/54 samples ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)); also 1918874 = 1918874 (V12 snapshot) | No: same value |
| 15035 | uint16, × 0.1, % | M713 `SoC` | **Confirmed.** Tracks `SoC` × 10 within ±5 in 54/54 samples ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)); within 1 % of the bridge's SoC in 56,835/56,835 samples over 0–100 % ([bridge history 2026-10-30–11-06](https://github.com/david2069/franklinwh-modbus/issues/132)). `SoC` reads whole percents | Yes, for resolution: 0.1 % steps |
| 15036 | uint16, × 0.1, % | M713 `SoH` | Inferred. 948 = 948 (V12 snapshot); 956 on V10 (`SoH` 95.6 % on 2026-05-14). 948 on 11-03 | No: same value |
| 15040 | int16, W | none (non-SunSpec) | Inferred: PV power as Direct Connect reports it. Equal to the Direct Connect bridge's solar figure (median 1 W apart, 13/17 within 50 W) while M502 `OutPw` read about 59 W lower ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)); −9..−8 W after dark while `OutPw` and 15003 read 0 ([run 2026-11-06](https://github.com/david2069/franklinwh-modbus/issues/132)). V10 65527 (−9) | Yes, if a client wants the figure the app shows; otherwise 15003 / `OutPw` |
| 15043 | uint16 | none known | Unknown. 1 on every read | — |

### 15500–15513 and 16000–16002

| PDU | Type, scale, units, sign | SunSpec equivalent | Status and evidence | Prefer the extension? |
|---|---|---|---|---|
| 15500, 15501 | uint16 flags | none (non-SunSpec) | Confirmed: PV installed (proximal, remote). Listed by FranklinWH; 15500 = 1, 15501 = 0 (V12 10-20) | Yes: no SunSpec equivalent |
| 15502 | uint16, W | M502 `OutPw` | Confirmed. Listed by FranklinWH as total PV, all sources; 300 = 300 (V12 snapshot) | No on a site with proximal PV only. With remote PV the two may differ: untested |
| 15503 | uint16, W | none (non-SunSpec) | Confirmed: PV proximal. Listed by FranklinWH; 300 (V12 snapshot) | Yes: SunSpec has no per-source split |
| 15504, 15505 | uint16, W | none (non-SunSpec) | Listed by FranklinWH as PV remote 1/2. 0 on a site with no remote PV, so the values are untested | Yes: SunSpec has no per-source split |
| 15506 | uint16, W | none (SunSpec has no home load point) | Confirmed: home load. Listed by FranklinWH; 185 = 16000 (V12 snapshot); within 100 W of 16000 in 54/54 samples ([run 2026-11-03](https://github.com/david2069/franklinwh-modbus/issues/132)). Resolution: ~100 W steps on V10 (2026-03-15), ~1 W on V12 (2026-11-03) | Use 16000 |
| 15507 | uint16 enum | none (non-SunSpec) | Confirmed: 1 Emergency Backup, 2 Self-Consumption, 3 TOU, read with the app in each mode (V12, 2026-10-21/28) | Yes: no SunSpec equivalent |
| 15508 | uint16, % | none (non-SunSpec) | Confirmed: Self-Consumption reserve (V10 2026-10-18; V12 2026-10-21) | Yes |
| 15509 | uint16, % | none (non-SunSpec) | Confirmed on V12: TOU reserve (2026-10-21). On V10 it repeated 15508 (#63) | Yes, on V12 |
| 15510–15511 | uint32 pair, Wh | M502 `OutWh` | Confirmed. Listed by FranklinWH; 15882870 = 15882870 (V12 snapshot); equal on V10 | No: same value |
| 15512–15513 | uint32 pair, Wh | none (proximal only) | Confirmed: PV energy, proximal. Listed by FranklinWH; equal to M502 `OutWh` on a site with proximal PV only | Yes, for the per-source split |
| 16000 | uint16, W, ~1 W | none (SunSpec has no home load point) | Confirmed: home load, ~1 W steps (V10 2026-03-15); 185 = 15506 (V12 snapshot) | Yes, over 15506: finer resolution. The library already does this |
| 16001 | uint16, % | none (non-SunSpec) | Confirmed on V12: reserve of the active mode. 8 in Self-Consumption, 15 in TOU, 100 in Emergency Backup (2026-10-21/28) | Yes: no SunSpec equivalent |
| 16002 | uint16, % | none (non-SunSpec) | Unknown. 20 in all three modes (V12 2026-10-21). Equal to the local API's `BBBackupSoc` (V10 2026-10-17): a value match, unconfirmed | — |

**Not mapped:** 15044–15099, 15514–15599 and 16003–16099 read without exceptions but nothing is populated (V12 2026-10-20).

**Correlation run 2026-11-03 (V12R02B60D00, one site):** read-only, sole client, 3 runs × 18 samples while charging. Each sample read the extension blocks, the SunSpec chain, then the extension blocks again. Positive controls 15510–15511 = M502 `OutWh` and 15502 = M502 `OutPw` passed. 16000 ≈ 15506 passed once the check compared both bracketing reads; it was changed after the run because 15506 updated mid-pass in 1 sample. **Evening run 2026-11-06:** read-only, 3 runs × 18 samples after dark (M714 `DCW` +200..+300 W, PV 0). The other Modbus clients were left running at the owner's call; every read succeeded and all three positive controls passed. **Bridge point history 2026-10-30–11-06:** the Modbus bridge's 10 s history of 15013, 15035 and 15016 alongside its SunSpec points (charging values of 15013 were missing because of a bridge defect, since fixed). **Direct Connect bridge metrics:** 30 s samples overlapping the 2026-11-03 run. Still open: the unknown signed pairs (15006–15007, 15014–15015, 15022), whether 15012–15013 is int16 or int32, and whether 15024 is the same frequency measurement (#132).

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
