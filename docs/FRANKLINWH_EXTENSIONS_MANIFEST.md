# FranklinWH Proprietary Extensions Manifest

This document records the discovered proprietary Modbus registers outside the SunSpec 40001+ range. These include the so-called "SPAN Extensions" (15500+) and internal diagnostic registers (15000+).

---

## 1. Discovered Correlation Table

Several proprietary registers map directly to standard SunSpec Info Points. This correlation suggests FranklinWH uses this internal memory space to mirror or aggregate data for their own cloud/UI services.

| Proprietary Addr | FranklinWH Name | SunSpec M | Map | Units | SF | Notes |
|:-----------------|:----------------|:-----------|:----|:------|:---|:------|
| **15011**        | ModelID (Internal) | **707**    | `ID`   | - | - | Matches Model 707 ID |
| **15013**        | ModelID (Internal) | **701**    | `ID`   | - | - | Matches Model 701 ID |
| **15017**        | BBBackupSoc?     | -          | -      | % | - | **Candidate: Direct Connect 1405 `BBBackupSoc`, unconfirmed.** Reads 20 on two sites, and `BBBackupSoc` is 20 on both; neither has changed it. Not 1901 `genStartElec` (another site, #18: 15017 stayed 20 while `genStartElec` was 10). Not TmpAmb: constant 20 on 2026-10-14 while 701.TmpAmb rose 16.2 → 17.0 °C |
| **15020**        | WHRtg (Internal) | **713**    | `WHRtg`| Wh | - | Matches 13600 WH |
| **15022**        | NPt (Internal)   | **705**    | `NPt`  | - | - | Matches 705.NPt |
| **15025**        | V_LNV (Internal) | **701**    | `LNV`  | V | -1 | Matches 241.8V (2380-2418) |
| **15036**        | SoH (Internal)   | **713**    | `SoH`  | % | -1 | Matches 95.6% (956) |
| **15506**        | LoadActiveP      | **714**    | `DCW`? | W | 0 | **Speculation**: Often matches 714.DCW when IDLE/balanced. |
| **15507**        | OnGridMode       | **715**    | `St`   | Enum | - | Maps to native DER states |
| **15508**        | SelfReserve      | **712**    | `NPt`  | % | - | Matches 712.NPt (Number of points) |
| **15509**        | TouReserve       | -          | -      | % | - | Vendor name (PICS SPAN tab), but reads the same value as 15508 — the known firmware defect in the PICS. On 2026-10-14 it read 5 (the active Self-Consumption reserve) while the TOU reserve was 15. Not related to 712.NPt (earlier note removed) |
| **15510**        | PVOutputWh (H)   | **502**    | `OutWh`| Wh | - | Matches PV Total Energy |
| **15512**        | proxOutputWh (H) | **502**    | `OutWh`| Wh | - | Matches PV Proximal Energy |
| **16000**        | HomeLoadHighRes  | **None**   | N/A | W | 0 | High-precision home load (1W) |
| **16001**        | Active reserve   | -          | -      | % | - | Same value as 15508/15509: the active mode's reserve. Read 5 on 2026-10-13/14; Direct Connect 1726 gives Self-Consumption (active) `reserved_soc` 5, TOU 15, Emergency Backup 100 (read 2026-10-15) |
| **16002**        | GenStartSoc      | -          | -      | % | - | **Generator auto-start SoC (Direct Connect 1901 `genStartElec`), supported on one site.** Reported in #18: on that site 16002 followed `genStartElec` 10 → 30 → 10 in the same sample and equalled it in 885 of 885 samples. Here both read 20 (consistent, but `BBBackupSoc` is also 20, so this site cannot separate them). Not TmpAmb, not the TOU reserve (refuted 2026-10-14) |

---

## 2. Raw Scan Output: Diagnostic Space (15000+)

**Command**:  
`python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -u 1 -t 20 --raw 15000:514 -dvalues --nz --match`

```text
Addr     Hex    UInt16   Int16    Value           Acc Bits (Binary)      Guess/Notes
--------------------------------------------------------------------------------------------------------------
15007    0101   257      257      257                 0000000100000001   
15011    0247   583      583      583                 0000001001000111   
15012    FFFF   65535    -1       -1                  1111111111111111   
15013    EC7A   60538    -4998    -4998               1110110001111010   
15015    003D   61       61       61                  0000000000111101   
15016    0002   2        2        2                   0000000000000010   [Matches: 702.AbnOpCatRtg (raw), 704.VarSetPri (raw)...]
15017    0014   20       20       20                  0000000000010100   
15018    FFFF   65535    -1       -1                  1111111111111111   
15019    FFFF   65535    -1       -1                  1111111111111111   
15020    3520   13600    13600    13600               0011010100100000   [Matches: 713.WHRtg (raw)]
15021    0001   1        1        1                   0000000000000001   
15022    15CD   5581     5581     5581                0001010111001101   
15024    C331   49969    -15567   -15567              1100001100110001   
15025    094C   2380     2380     2380                0000100101001100   [Matches: 701.LLV (raw), 701.LNV (raw)...]
15026    0001   1        1        1                   0000000000000001   
15029    0046   70       70       70                  0000000001000110   
15030    7829   30761    30761    30761               0111100000101001   
15033    0016   22       22       22                  0000000000010110   
15034    586D   22637    22637    22637               0101100001101101   
15035    010C   268      268      268                 0000000100001100   
15036    03BC   956      956      956                 0000001110111100   [Matches: 713.SoH (raw)]
15040    FFF7   65527    -9       -9                  1111111111110111   
15043    0001   1        1        1                   0000000000000001   
```

---

## 3. Raw Scan Output: SPAN Extensions (15500+)

**Command**:  
`python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -u 1 -t 20 --raw 15500:15 -dvalues --nz --match`

```text
Addr     Hex    UInt16   Int16    Value           Acc Bits (Binary)      Guess/Notes
--------------------------------------------------------------------------------------------------------------
15506    0258   600      600      600             R   0000001001011000   Home Load (LoadActiveP) W
15507    0003   3        3        3               RW  0000000000000011   Operating Mode (OnGridMode). 1: Backup, 2: Self-Consumption, 3: TOU. Verified 1-indexed mapping. NOTE: Hardware may echo success but silently discard writes if "SPAN Modbus" is locked.
15508    000A   10       10       10              RW  0000000000001010   Self-Consumption SOC Reserve (SelfReserve) %
15509    000A   10       10       10              RW  0000000000001010   TOU SOC Reserve (TouReserve) %
15510    00C5   197      197      12959408        R   0000000011000101   PV Energy Total (PVOutputWh) [Matches: 502.OutWh (raw)]
15511    BEB0   48816    -        -               -   -                    -> Low Word
15512    00C5   197      197      12959408        R   0000000011000101   PV Energy Proximal (proximalOutputWh) [Matches: 502.OutWh (raw)]
15513    BEB0   48816    -        -               -   -                    -> Low Word
```

---

## 4. Unknown Range (16000+)

**Command**:  
`python3 tools/modbus_sunspec2_reader.py -i 192.168.0.110 -u 1 -t 20 --raw 16000:500 -dvalues --nz --match`

```text
Addr     Hex    UInt16   Int16    Value           Acc Bits (Binary)      Guess/Notes
--------------------------------------------------------------------------------------------------------------
16000    028C   652      652      652                 0000001010001100   
16001    000A   10       10       10                  0000000000001010   
16002    0014   20       20       20                  0000000000010100
```
