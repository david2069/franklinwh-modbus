# SunSpec Snapshot — Firmware V12R02B60D00 (2026-10-20)

A read-only capture of the reference aGate X after a FranklinWH firmware update, compared with the [2026-05-14 baseline](SUNSPEC_DEVICE_SNAPSHOT.md) on V10R01B04D00.

| | |
|---|---|
| Firmware (SunSpec M1 `Vr`) | **V12R02B60D00**. It was V10R01B04D00 on 2026-05-14 and on 2026-10-18 |
| Model (M1 `Md`) | aGate X |
| Captured | 2026-10-20T20:10:45Z: a SunSpec export from the aGate's Modbus client (franklinwh-modbus-bridge 0.2.31). Reserve values were confirmed by an owner read and the FranklinWH app on 2026-10-21 |
| Method | Read-only (FC3). Serial number redacted |
| Addresses | Modbus **PDU addresses** (0-based); see [Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map) |

## What changed

| Item | V10R01B04D00 | V12R02B60D00 |
|---|---|---|
| **15509 TOU reserve** | Repeated 15508 (a known defect, #63) | **Holds the TOU reserve:** 15 while 15508 = 8, matching the app's TOU reserve (15) |
| SunSpec model map | 17 models (below) | **Unchanged:** same models, same addresses, same lengths |
| Scale factors | as in the baseline | **Unchanged** for every scale factor compared |
| M1 `Mn` | "FranklinWH Technologies Co., Ltd" | "FranklinWH" |

Not yet checked on V12R02B60D00: what 15508 and 16001 hold in TOU mode (every reading so far was in Self-Consumption); the 15507 mode values (#75); model 714's per-port block (1062–1086), which this export doesn't include; and PDU 40071 → exception 2 (#71).

## SunSpec model map (unchanged)

| Model | Header PDU | Length | | Model | Header PDU | Length |
|---|---|---|---|---|---|---|
| 1 Common | 2 | 66 | | 709 Trip LF | 679 | — |
| 701 AC Measurement | 70 | 153 | | 710 Trip HF | 816 | — |
| 702 Capacity | 225 | 50 | | 711 Freq Droop | 953 | — |
| 703 Enter Service | 277 | 17 | | 712 Watt-Var | 987 | — |
| 704 AC Controls | 296 | 65 | | 713 Storage Capacity | 1033 | 7 |
| 705 Volt-Var | 363 | — | | 714 DC Measurement | 1042 | 43 |
| 706 Volt-Watt | 432 | — | | 715 DER Control | 1087 | 7 |
| 707 Trip LV | 465 | — | | 502 Solar Module | 1096 | 28 |
| 708 Trip HV | 572 | — | | | | |

"—": the export returned no values for models 705–712, whose points read as not implemented. Their headers are where the 2026-05-14 baseline found them.

## Selected values at capture

| Point (PDU) | Raw | Scaled | Notes |
|---|---|---|---|
| M701 `InvSt` (74) / `ConnSt` (75) / `DERMode` (78) | 3 / 1 / 1 | Running / Connected / Grid Following | |
| M701 `W` (80) | −1 | −1 W | |
| M701 `LNV` (86), `V_SF` −1 | 2425 | 242.5 V | |
| M701 `Hz` (87), `Hz_SF` −3 | 49980 | 49.98 Hz | |
| M701 `TotWhInj` (89) / `TotWhAbs` (93) | 5964768 / 1918874 | Wh, lifetime | |
| M702 `WChaRteMaxRtg` (235) / `WDisChaRteMaxRtg` (236) | 5000 / 5000 | W | `WMaxRtg` (227) reads **0**; the library falls back to the charge/discharge ratings |
| M704 `WSetEna` (318) | 0 | Not under remote control | |
| M713 `SoC` (1037) / `SoH` (1038), `Pct_SF` −1 | 320 / 948 | 32.0 % / 94.8 % | SoH was 95.6 % on 2026-05-14 |
| M713 `WHRtg` (1035) / `WHAvail` (1036) | 13600 / 4394 | Wh | |
| M714 `DCW` (1048) | −100 | −100 W (charging) | |
| M714 `DCWhInj` (1049) / `DCWhAbs` (1053) | 7861360 / 8039960 | Wh, lifetime | |
| M715 `LocRemCtl` (1089) | 1 | Local | |
| M502 `OutPw` (1119) / `OutWh` (1117) | 300 / 15882870 | W / Wh | `OutWh` equals extension 15510 |

## FranklinWH extension registers

Meanings are on [FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md).

| PDU | Value | | PDU | Value |
|---|---|---|---|---|
| 15500, 15501 | not returned by the export | | 15507 mode | 2 |
| 15502 PV total | 300 W | | 15508 SC reserve | 8 % |
| 15503 PV proximal | 300 W | | **15509 TOU reserve** | **15 %** |
| 15504 / 15505 PV remote | 0 / 0 W | | 15510 PV energy (uint32) | 15882870 Wh |
| 15506 home load | 185 W | | 15512 PV proximal energy | 15882870 Wh |
| 16000 home load (~1 W) | 185 W | | 16001 | 8 |
| | | | 16002 | 20 |

### 15000–15039 (undocumented), raw values

| PDU | Raw | PDU | Raw | PDU | Raw | PDU | Raw |
|---|---|---|---|---|---|---|---|
| 15000 | 1 | 15010 | 0 | 15020 | 13600 | 15030 | 992 |
| 15001 | 0 | 15011 | 185 | 15021 | 1 | 15031 | 0 |
| 15002 | 0 | 15012 | 65535 | 15022 | 0 | 15032 | 0 |
| 15003 | 300 | 15013 | 65397 | 15023 | 0 | 15033 | 29 |
| 15004 | 0 | 15014 | 65535 | 15024 | 50000 | 15034 | 18330 |
| 15005 | 0 | 15015 | 65363 | 15025 | 2425 | 15035 | 323 |
| 15006 | 65535 | 15016 | 2 | 15026 | 1 | 15036 | 948 |
| 15007 | 65249 | 15017 | 20 | 15027 | 0 | 15037 | 0 |
| 15008 | 0 | 15018 | 5000 | 15028 | 0 | 15038 | 0 |
| 15009 | 0 | 15019 | 5000 | 15029 | 91 | 15039 | 0 |

These match values elsewhere in the same capture. They are **inferred correspondences, not definitions**:

| Register | Matches |
|---|---|
| 15003 = 300 | PV power (15502) |
| 15011 = 185 | Home load (15506) |
| 15018, 15019 = 5000 | M702 charge and discharge ratings |
| 15020 = 13600 | M713 `WHRtg` |
| 15025 = 2425 | M701 `LNV` raw |
| 15035 = 323 | SoC ×10. M713 shows 32.0 %, so this is a finer value |
| 15036 = 948 | M713 `SoH` raw |
| 15013 = 65397 | −139 as int16: near M714 `DCW` (−100 W), so possibly battery power |
