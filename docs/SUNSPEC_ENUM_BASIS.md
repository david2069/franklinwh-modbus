# SunSpec Enum Values: Basis and Cross-Reference

*Recorded 2026-10-12. Every value below cites its source document and page, or a dated device read.*

This page records which SunSpec document the library uses to decode enum registers (M701.ConnSt, M713.Sta, and so on), why, and where each decoding lives in this repository. Read it before changing any enum map.

## Ruling

**Decode enum registers with the numbering in the SunSpec DER Information Model Specification V1.2 (Approved). It numbers values from 0.**

Reasons:

1. V1.2 is the approved edition. The 1-based numbering comes from the 2021 edition, which is marked **Draft**.
2. The aGate reports V1.2 numbering. See [Device evidence](#device-evidence).
3. pysunspec2 1.3.3, the model definitions this library reads registers through, uses the same numbering as V1.2.

The FranklinWH PICS (SM-000028) does not settle the question. It lists symbol names without numbers for status enums. Where it does give numbers (702 ratings), they follow the Draft numbering, and the device does not. See [The PICS](#the-pics-sm-000028).

## Sources

| Document | Version / status | Notes |
|---|---|---|
| SunSpec DER Information Model Specification | **V1.2, Approved**, © SunSpec Alliance 2024 | Authoritative. 0-based enums. |
| SunSpec DER Information Model Specification | V1.0-02-01-2021, **Draft**, © 2021 | Superseded. 1-based enums for 701/702. Model 713 is *DC Measurement* in this draft. |
| SunSpec Information Models (12041) | v1.9, Approved | Data type rules: an enum16 that is not implemented reads `0xFFFF` (range 0…65534). |
| FranklinWH Modbus PICS | SM-000028 (`UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx`) | Supported points and symbol names; certification-unit ratings. |
| pysunspec2 model JSON | pysunspec2 1.3.3, `sunspec2/models/json/model_7xx.json` | Machine-readable symbol values; matches V1.2 for every point in the table below. |

The SunSpec PDFs are published by the SunSpec Alliance (sunspec.org). They are not committed to this repository; the owner keeps local copies. Page numbers below are the printed page numbers of those PDFs.

## Edition comparison

| Point | V1.2 (Approved) | V1.0-2021 (Draft) | pysunspec2 1.3.3 |
|---|---|---|---|
| 701.ACType | SINGLE_PHASE 0, SPLIT_PHASE 1, THREE_PHASE 2 (p. 21) | 1, 2, 3 (p. 20) | 0, 1, 2 |
| 701.St | OFF 0, ON 1 (p. 21) | OFF 1, ON 2, WARNING 3, ERROR 4 (p. 20) | 0, 1 |
| 701.InvSt | OFF 0, SLEEPING 1, STARTING 2, RUNNING 3, THROTTLED 4, SHUTTING_DOWN 5, FAULT 6, STANDBY 7 (p. 21) | not in the model | 0…7 |
| 701.ConnSt | DISCONNECTED 0, CONNECTED 1 (p. 21) | DISCONNECTED 1, CONNECTED 2 (p. 20) | 0, 1 |
| 701.DERMode | **bitfield32**: GRID_FOLLOWING bit 0, GRID_FORMING bit 1, PV_CLIPPED bit 2 | — | bitfield32, bits 0–2 |
| 702.NorOpCatRtg | CAT_A 0, CAT_B 1 (p. 34) | CAT_A 1, CAT_B 2 (p. 31) | 0, 1 |
| 702.AbnOpCatRtg | CAT_1 0, CAT_2 1, CAT_3 2 (p. 34) | CAT_1 1, CAT_2 2, CAT_3 3 (p. 31–32) | 0, 1, 2 |
| 702.IntIslandCatRtg / IntIslandCat | **bitfield16** | — | bitfield16 |
| 703.ES, 704.*Ena, 704.AntiIslEna | DISABLED 0, ENABLED 1 | — | 0, 1 |
| 704.WSetMod | W_MAX_PCT 0, WATTS 1 | — | 0, 1 |
| 713.Sta (Storage Capacity) | OK 0, WARNING 1, ERROR 2 (p. 75) | **no such point**: model 713 is DC Measurement (p. 69) | 0, 1, 2 |
| 715.LocRemCtl | REMOTE 0, LOCAL 1 | — | 0, 1 |

"—" means not checked in that edition.

## Device evidence

aGate X, firmware V10R01B04D00, serial ending 24170091.

| Point | Raw value | Source | V1.2 reading | Draft reading |
|---|---|---|---|---|
| 701.ACType | 0 | Full scan 2026-05-14 (`AGATE_FULL_SCAN_2026-05-14.txt:61`) | SINGLE_PHASE ✅ (AU single-phase site) | invalid |
| 701.St | 1 | same, line 62 | ON ✅ | OFF ❌ (device was running) |
| 701.InvSt | 3 | same, line 63 | RUNNING | point not in Draft |
| 701.ConnSt | 1 | same, line 64; also REST read 2026-10-12 16:08 AEDT | CONNECTED ✅ (site was grid-connected) | DISCONNECTED ❌ |
| 701.InvSt | 7 | REST read 2026-10-12 16:08 AEDT | STANDBY ✅ (battery idle at 100% SoC) | point not in Draft |
| 702.NorOpCatRtg | 1 | Full scan, line 158 | CAT_B | CAT_A |
| 702.AbnOpCatRtg | 2 | Full scan, line 159 | CAT_3 | CAT_2 |
| 713.Sta | 0 | Full scan, line 404; REST 2026-10-12 | OK | point not in Draft |

The PICS states this product's ratings as NorOpCatRtg **2** and AbnOpCatRtg **3**: CAT_B and CAT_3 in Draft numbering. The device reports **1** and **2**: CAT_B and CAT_3 in V1.2 numbering. Both describe the same categories. The device numbers from 0; the PICS from 1.

The REST reads of 2026-10-12 were taken through the franklinwh-modbus-bridge REST API (`GET /api/gateways/default/points`), which uses this library's `read_grid_status()` and `read_battery_status()`.

## The PICS (SM-000028)

- For 701.ACType, St, InvSt, ConnSt, 703.ES, 704.WSetEna, 713.Sta and 715.LocRemCtl, the PICS lists **symbol names only** (e.g. 713.Sta: OK, WARNING, ERROR, all "supported"). It gives no numeric values for them.
- For 702.NorOpCatRtg and 702.AbnOpCatRtg it states values (2 and 3), which follow Draft numbering (above).
- 701.DERMode is marked **unimplemented**, all three bits.
- The 702 ratings in the PICS (e.g. 10000 / 11000 / 50 A) are for the certification unit, not a particular site.

## Where this repository decodes these values

State of `develop` at `8af8301` (2026-10-12). Entries marked ❌ disagree with V1.2. None are fixed by this document; they are queued (see [Open items](#open-items)).

| Location | What it does | Basis | Status |
|---|---|---|---|
| `src/franklinwh_modbus/constants.py` `PICS_ENUMS` | Value→name maps behind `get_pics_enum_desc()` and `FranklinWHController.get_enum_desc()` | 701 ACType/St/InvSt/ConnSt, 703 ES and the 704 `*Ena` points are 1-based (Draft numbering, which the Draft does not even use for InvSt). WSetMod, VarSetMod, VarSetPri, WRmpRef, the `.Ext` points, AdptCrvRslt and 715 are 0-based. | ❌ Off by one for the 1-based points: `get_pics_enum_desc(701, "ConnSt", 1)` returns `"DISCONNECTED"` for a connected site. Also: NorOpCatRtg / AbnOpCatRtg / IntIslandCat* are filed under 703 (V1.2 puts the ratings in 702); DERMode and IntIslandCat* are bitfields, not enums. Added in `304b04f` (2026-06-10, released in 0.9.3 as FEAT-PICS-ENUM-RESOLVER). |
| `tests/unit/test_pics_enums.py` | Asserts the `PICS_ENUMS` values | Same as above | ❌ Asserts the 1-based values (e.g. ACType 1 = SINGLE_PHASE, InvSt 8 = STANDBY) |
| `controller.py` `read_grid_status()` `CONN_STATES` / `INVERTER_STATES` | Produces `connection_state` / `inverter_state` | 0-based | ✅ Matches V1.2. Extra keys not in V1.2 (ConnSt 2 = Fault; InvSt 8 = Test, 9 = Manufacturing) are unreachable on a conforming device. |
| `controller.py` `read_grid_status()` DERMode | Produces `grid_mode` from bits 0–2 | V1.2 bitfield | ✅ (the PICS marks DERMode unimplemented; the device reads 1 = bit 0 GRID_FOLLOWING) |
| `controller.py` `read_grid_status()` `ac_type` | Guesses wiring from line voltage | None (does not read 701.ACType) | ❌ Should come from 701.ACType. Reports "Single-Phase (230V Nominal)". |
| `controller.py` `read_battery_status()` `status_raw` | Returns raw 713.Sta | — | The docstring and comment ("always 0 … quirk, do not use") predate this ruling. Under V1.2, 0 means **OK**, so a constant 0 is the expected value for a healthy battery, not a defect. Battery charge direction is not what 713.Sta reports; deriving it from M714.DCW is still correct. |
| `tools/franklinwh_control_standalone.py` (lines ~484–535) | Copy of the `read_grid_status()` maps and `ac_type` guess | 0-based | Same as `controller.py` |
| `tools/log_throttling_1hour.py:40` `INVERTER_STATES` | InvSt names | 0-based | ✅ |
| `docs/FRANKLINWH_SUNSPEC_QUIRKS.md` "Model 713 – Sta" | Describes 713.Sta | Superseded table (OFF/EMPTY/DISCHARGING/CHARGING/FULL/HOLDING/TESTING), which is not the 713.Sta enum in any edition checked | Corrected 2026-10-12 to point here |
| `docs/FRANKLINWH_OFFICIAL_DOCS_REFERENCE.md` model table (local-only, gitignored) | "Sta always 0 — quirk" | Same | Corrected 2026-10-12 |

## Other projects

Recorded for cross-reference only; this repository does not change them.

- **franklinwh-modbus-bridge**, GitHub `main` at `f359b7f`, checked 2026-10-12 and reported to that project's maintainer session the same day:
  - `src/franklinwh_bridge/modbus/poller.py:481-485`, `_STA_MAP = {0: "OK", 1: "Warning", 3: "Error"}`: V1.2 has ERROR = 2.
  - `src/franklinwh_bridge/store/alarms.py:62-71`, `_M713_STA_NAMES` (Idle, Charging, … Sleep): not the 713.Sta enum in either edition. Deployed alarm events from 2026-07-05 show labels "State400" (raw 400, invalid) and "Idle" (raw 0, which V1.2 calls OK).
  - The bridge's `connection_state` and `inverter_state` come from this library's `read_grid_status()` and are correct.

## Open items

These are queued under the change management policy, with no code change yet:

1. Make `PICS_ENUMS` 0-based per V1.2, move the 702 ratings under 702, and handle DERMode / IntIslandCat* as bitfields; update `tests/unit/test_pics_enums.py`. Callers relying on the current numbers get different names, so this needs an upgrade note.
2. Read `ac_type` from 701.ACType instead of guessing from voltage (controller and standalone tool).
3. Update the `status_raw` docstring and comment in `read_battery_status()`.

## Change history

| Date | Change |
|---|---|
| 2026-03-08 | `1680f81` added the M713.Sta "always 0" quirk and the superseded enum table. |
| 2026-06-10 | `304b04f` added `PICS_ENUMS` / `get_pics_enum_desc()` with 1-based values (released 0.9.3). |
| 2026-10-12 | This page: V1.2 ruling, device evidence, cross-reference; quirk docs corrected. |
