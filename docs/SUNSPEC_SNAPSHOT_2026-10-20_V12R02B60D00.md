# SunSpec Snapshot — Firmware V12R02B60D00 (2026-10-20)

A read-only capture of the reference aGate X after a FranklinWH firmware update, compared with the [2026-05-14 baseline](SUNSPEC_DEVICE_SNAPSHOT.md) on V10R01B04D00.

| | |
|---|---|
| Firmware (SunSpec M1 `Vr`) | **V12R02B60D00**. It was V10R01B04D00 on 2026-05-14 and on 2026-10-18 |
| Model (M1 `Md`) | aGate X |
| Captured | (1) 2026-10-20T20:10:45Z: a SunSpec export from the aGate's Modbus client (franklinwh-modbus-bridge 0.2.31). (2) **2026-10-20T20:17:37Z: a franklinwh-modbus re-scan**: a raw FC3 walk of the whole chain, the M714 port block, the extension ranges and sweeps, with the bridge stopped so it was the only client. Reserve values were confirmed by an owner read and the FranklinWH app on 2026-10-21 |
| Method | Read-only (FC3). Serial number redacted |
| Addresses | Modbus **PDU addresses** (0-based); see [Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map) |

## What changed

| Item | V10R01B04D00 | V12R02B60D00 |
|---|---|---|
| **15509 TOU reserve** | Repeated 15508 (a known defect, #63) | **Holds the TOU reserve:** 15 while 15508 = 8, matching the app's TOU reserve (15) |
| SunSpec model map | 17 models (below) | **Unchanged:** same models, same addresses, same lengths |
| Scale factors | as in the baseline | **Unchanged** for every scale factor compared |
| M1 `Mn` | "FranklinWH Technologies Co., Ltd" | "FranklinWH" |
| **Map at PDU 40000** | Exception 2 (2026-03-15) | **Mirrored:** "SunS" at 40000, and 40070–40071 equal 70–71. PDU 50000 still returns exception 2. Clients that probe 40000 first (pysunspec2's default) bind to the mirror, and so does this library (#84). Writes to the mirror are unverified. See [Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map) |
| M714 port block (1062–1086) | Not captured; QUIRKS listed `DCV`/`Tmp` as working | **All zero** except an "ID_String" placeholder in `IDStr`. Port `DCV` (1073) and `Tmp` (1083) read 0 |
| 15500 PVUse / 15501 apBoxPVUse | 15500–15501 "not actively used" | 1 / 0 |
| 15040, 15043 | Not captured (scan stopped at 15039) | 826 / 1 (meaning unknown) |

**Mode readings (owner, read-only, 2026-10-21/22):** in Self-Consumption, 15507 = 2, 15508 = 8, 15509 = 15, 16001 = 8, 16002 = 20. In TOU, 15507 = 3, 15508 = 8, 15509 = 15, **16001 = 15**, 16002 = 20. In Emergency Backup (2026-10-22), 15507 = 1 and **16001 = 100**. So 16001 holds the active mode's reserve in all three modes (#63), and 15507's 1/2/3 are confirmed. No other value has been read (#75). The re-scan answered the rest: the M714 port block reads zero, and PDU 40071 returns data on V12 (so #71's probe happens to work there).

Sweeps of 15044–15099, 15514–15599 and 16003–16099 in 10-register chunks all read without exceptions and found nothing populated.

## Firmware components (relayed)

The aGate's other component versions, as read over the FranklinWH **Direct Connect** local API (:9000) at 2026-10-20T20:09Z by the franklinwh-direct-connect-bridge session. That's a claim from another repo, not read over Modbus. The "old" values are a single earlier snapshot (2026-10-07).

| Component | Before | After |
|---|---|---|
| IBG (gateway) | V12R02B30D06_260304 | **V12R02B60D00_260924** |
| Local/APP | V12R00B07D04_260205 | V12R00B16D00_260825 |
| IoT/AWS | V12R00B06D04_260304 | V12R00B15D00_260918 |
| SL | V12R02B07D81 | V12R02B12D00 |
| DC-DC | V12R02B07D01 | V12R02B10D00 |
| INV | V12R02B09D03 | V12R02B15D00 |
| BMS | V11R50B03D00 | V11R50B07D00 |
| protocolVer | V1.11.03 | V1.12.02 |
| FPGA, BL, TH, METER, SyHdVersion | unchanged | V12R01B00D00, V11R06B00D00, V11R02B01D00, V12R00B11D00, 102 |

**What SunSpec M1 `Vr` reports:** before the update, `Vr` read **V10R01B04D00**, which matched none of the components above (the IBG was V12R02B30D06). After the update, `Vr` reads **V12R02B60D00**, which equals the new IBG version without its date suffix. So `Vr` didn't track the gateway firmware before, and does now. Whether it will keep doing so is unknown. Record the IBG version from the app as well when you quote `Vr`.

## SunSpec model map (unchanged)

| Model | Header PDU | Length | | Model | Header PDU | Length |
|---|---|---|---|---|---|---|
| 1 Common | 2 | 66 | | 709 Trip LF | 679 | 135 |
| 701 AC Measurement | 70 | 153 | | 710 Trip HF | 816 | 135 |
| 702 Capacity | 225 | 50 | | 711 Freq Droop | 953 | 32 |
| 703 Enter Service | 277 | 17 | | 712 Watt-Var | 987 | 44 |
| 704 AC Controls | 296 | 65 | | 713 Storage Capacity | 1033 | 7 |
| 705 Volt-Var | 363 | 67 | | 714 DC Measurement | 1042 | 43 |
| 706 Volt-Watt | 432 | 31 | | 715 DER Control | 1087 | 7 |
| 707 Trip LV | 465 | 105 | | 502 Solar Module | 1096 | 28 |
| 708 Trip HV | 572 | 105 | | End marker 0xFFFF | 1126 | |

Lengths for 705–712 are from the re-scan. The bridge export returned their points as not implemented.

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
