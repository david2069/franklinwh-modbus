# SunSpec Device Scan Manifest (Authoritative)

**Date**: 2026-05-14  
**Hardware**: FranklinWH aGate X  
**Firmware**: `V10R01B04D00`  

This document preserves the complete, unedited output of the SunSpec device scans. These commands provide the exhaustive register map for all implemented models.

---

## 1. Standard Addressing Scan (Base 40001)

**Command**:  
`python3 tools/modbus_sunspec2_reader.py -i 192.0.2.110 -u 1 -t 20 -dvalues --vals`

```text
Model 1: common
Addr   Name       Label                  Value                                         RW Type
----------------------------------------------------------------------------------------------------
40002  ID         Model ID               1                                             R  uint16
40003  L          Model Length           66                                            R  uint16
40004  Mn         Manufacturer           FranklinWH Technologies Co., Ltd              R  string
40020  Md         Model                  aGate X                                       R  string
40036  Opt        Options                Option Name                                   R  string
40044  Vr         Version                V10R01B04D00                                  R  string
40052  SN         Serial Number          SN-REDACTED-XXXX                          R  string
40068  DA         Device Address         1                                             RW uint16
40069  Pad                               32768                                         R  pad

Model 502: solar_module
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
41096  ID                   Model ID                         502               R  -          uint16
41097  L                    Model Length                      28               R  -          uint16
41098  A_SF                                                    0               R  -          sunssf
41099  V_SF                                                    0               R  -          sunssf
41100  W_SF                                                    0               R  -          sunssf
41101  Wh_SF                                                   0               R  -          sunssf
41102  Stat                 Status                             0               R  -          enum16
41103  StatVend             Vendor Status                      0               R  -          enum16
41104  Evt                  Events                             0               R  -          bitfield32
41106  EvtVend              Vendor Module Event Flags          0               R  -          bitfield32
41108  Ctl                  Control                         None               RW -          enum16
41109  CtlVend              Vendor Control                  None               RW -          enum32
41111  CtlVal               Control Value                   None               RW -          int32
41113  Tms                  Timestamp                          0  Secs         R  -          uint32
41115  OutA                 Output Current                     0  A        S   R  -          int16
41116  OutV                 Output Voltage                     0  V        S   R  -          int16
41117  OutWh                Output Energy               12959408  Wh       S   R  -          acc32
41119  OutPw                Output Power                       0  W        S   R  -          int16
41120  Tmp                  Temp                               0  C            R  -          int16
41121  InA                  Input Current                      0  A        S   R  -          int16
41122  InV                  Input Voltage                      0  V        S   R  -          int16
41123  InWh                 Input Energy                    None  Wh       S   R  -          acc32
41125  InW                  Input Power                        0  W        S   R  -          int16

Model 701: DERMeasureAC
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40070  ID                   Model ID                         701               R  -          uint16
40071  L                    Model Length                     153               R  -          uint16
40072  ACType               AC Wiring Type                     0               R  -          enum16
40073  St                   Operating State                    1               R  -          enum16
40074  InvSt                Inverter State                     3               R  -          enum16
40075  ConnSt               Grid Connection State              1               R  -          enum16
40076  Alrm                 Alarm Bitfield                     0               R  -          bitfield32
40078  DERMode              DER Operational Character          1               R  -          bitfield32
40080  W                    Active Power                      -2  W        S   R  -          int16
40081  VA                   Apparent Power                   833  VA       S   R  -          int16
40082  Var                  Reactive Power                  -718  Var      S   R  -          int16
40083  PF                   Power Factor                   0.018           S   R  18         int16
40084  A                    Total AC Current                 3.4  A        S   R  34         int16
40085  LLV                  Voltage LL                     241.8  V        S   R  2418       uint16
40086  LNV                  Voltage LN                     241.8  V        S   R  2418       uint16
40087  Hz                   Frequency                      49.96  Hz       S   R  49960      uint32
40089  TotWhInj             Total Energy Injected        4614656  Wh       S   R  -          uint64
40093  TotWhAbs             Total Energy Absorbed        1463431  Wh       S   R  -          uint64
40097  TotVarhInj           Total Reactive Energy Inj          0  Varh     S   R  -          uint64
40101  TotVarhAbs           Total Reactive Energy Abs          0  Varh     S   R  -          uint64
40105  TmpAmb               Ambient Temperature             18.3  C        S   R  183        int16
40106  TmpCab               Cabinet Temperature             26.9  C        S   R  269        int16
40107  TmpSnk               Heat Sink Temperature              0  C        S   R  -          int16
40108  TmpTrns              Transformer Temperature            0  C        S   R  -          int16
40109  TmpSw                IGBT/MOSFET Temperature           25  C        S   R  250        int16
40110  TmpOt                Other Temperature                  0  C        S   R  -          int16
40111  WL1                  Watts L1                          15  W        S   R  -          int16
40112  VAL1                 VA L1                            833  VA       S   R  -          int16
40113  VarL1                Var L1                          -718  Var      S   R  -          int16
40114  PFL1                 PF L1                          0.018           S   R  18         int16
40115  AL1                  Amps L1                          3.4  A        S   R  34         int16
40116  VL1L2                Phase Voltage L1-L2            241.8  V        S   R  2418       uint16
40117  VL1                  Phase Voltage L1-N             241.8  V        S   R  2418       uint16
40118  TotWhInjL1           Total Watt-Hours Inj L1      4614941  Wh       S   R  -          uint64
40122  TotWhAbsL1           Total Watt-Hours Abs L1      1463790  Wh       S   R  -          uint64
40126  TotVarhInjL1         Total Var-Hours Inj L1             0  Varh     S   R  -          uint64
40130  TotVarhAbsL1         Total Var-Hours Abs L1             0  Varh     S   R  -          uint64
40134  WL2                  Watts L2                           0  W        S   R  -          int16
40135  VAL2                 VA L2                              0  VA       S   R  -          int16
40136  VarL2                Var L2                             0  Var      S   R  -          int16
40137  PFL2                 PF L2                              0           S   R  -          int16
40138  AL2                  Amps L2                            0  A        S   R  -          int16
40139  VL2L3                Phase Voltage L2-L3                0  V        S   R  -          uint16
40140  VL2                  Phase Voltage L2-N                 0  V        S   R  -          uint16
40141  TotWhInjL2           Total Watt-Hours Inj L2            0  Wh       S   R  -          uint64
40145  TotWhAbsL2           Total Watt-Hours Abs L2            0  Wh       S   R  -          uint64
40149  TotVarhInjL2         Total Var-Hours Inj L2             0  Varh     S   R  -          uint64
40153  TotVarhAbsL2         Total Var-Hours Abs L2             0  Varh     S   R  -          uint64
40157  WL3                  Watts L3                           0  W        S   R  -          int16
40158  VAL3                 VA L3                              0  VA       S   R  -          int16
40159  VarL3                Var L3                             0  Var      S   R  -          int16
40160  PFL3                 PF L3                              0           S   R  -          int16
40161  AL3                  Amps L3                            0  A        S   R  -          int16
40162  VL3L1                Phase Voltage L3-L1                0  V        S   R  -          uint16
40163  VL3                  Phase Voltage L3-N                 0  V        S   R  -          uint16
40164  TotWhInjL3           Total Watt-Hours Inj L3            0  Wh       S   R  -          uint64
40168  TotWhAbsL3           Total Watt-Hours Abs L3            0  Wh       S   R  -          uint64
40172  TotVarhInjL3         Total Var-Hours Inj L3             0  Varh     S   R  -          uint64
40176  TotVarhAbsL3         Total Var-Hours Abs L3             0  Varh     S   R  -          uint64
40180  ThrotPct             Throttling In Pct               None  Pct          R  -          uint16
40181  ThrotSrc             Throttle Source Informati       None               R  -          bitfield32
40183  A_SF                 Current Scale Factor              -1               R  -          sunssf
40184  V_SF                 Voltage Scale Factor              -1               R  -          sunssf
40185  Hz_SF                Frequency Scale Factor            -3               R  -          sunssf
40186  W_SF                 Active Power Scale Factor          0               R  -          sunssf
40187  PF_SF                Power Factor Scale Factor         -3               R  -          sunssf
40188  VA_SF                Apparent Power Scale Fact          0               R  -          sunssf
40189  Var_SF               Reactive Power Scale Fact          0               R  -          sunssf
40190  TotWh_SF             Active Energy Scale Facto          0               R  -          sunssf
40191  TotVarh_SF           Reactive Energy Scale Fac          3               R  -          sunssf
40192  Tmp_SF               Temperature Scale Factor          -1               R  -          sunssf
40193  MnAlrmInfo           Manufacturer Alarm Info   Manufacturer custom error info               R  -          string

Model 702: DERCapacity
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40225  ID                   Model ID                         702               R  -          uint16
40226  L                    Model Length                      50               R  -          uint16
40227  WMaxRtg              Active Power Max Rating            0  W        S   R  -          uint16
40228  WOvrExtRtg           Active Power (Over-Excite       5000  W        S   R  -          uint16
40229  WOvrExtRtgPF         Specified Over-Excited PF       0.85           S   R  850        uint16
40230  WUndExtRtg           Active Power (Under-Excit       5000  W        S   R  -          uint16
40231  WUndExtRtgPF         Specified Under-Excited P       0.85           S   R  850        uint16
40232  VAMaxRtg             Apparent Power Max Rating       5800  VA       S   R  -          uint16
40233  VarMaxInjRtg         Reactive Power Injected R       2940  Var      S   R  -          uint16
40234  VarMaxAbsRtg         Reactive Power Absorbed R       2940  Var      S   R  -          uint16
40235  WChaRteMaxRtg        Charge Rate Max Rating          5000  W        S   R  -          uint16
40236  WDisChaRteMaxRtg     Discharge Rate Max Rating       5000  W        S   R  -          uint16
40237  VAChaRteMaxRtg       Charge Rate Max VA Rating       5800  VA       S   R  -          uint16
40238  VADisChaRteMaxRtg    Discharge Rate Max VA Rat       5800  VA       S   R  -          uint16
40239  VNomRtg              AC Voltage Nominal Rating        240  V        S   R  -          uint16
40240  VMaxRtg              AC Voltage Max Rating            288  V        S   R  -          uint16
40241  VMinRtg              AC Voltage Min Rating            192  V        S   R  -          uint16
40242  AMaxRtg              AC Current Max Rating           24.5  A        S   R  245        uint16
40243  PFOvrExtRtg          PF Over-Excited Rating (U       0.85           S   R  850        uint16
40244  PFUndExtRtg          PF Under-Excited Rating (       0.85           S   R  850        uint16
40245  ReactSusceptRtg      Reactive Susceptance            3725  S        S   R  -          uint16
40246  NorOpCatRtg          Normal Operating Category          1               R  -          enum16
40247  AbnOpCatRtg          Abnormal Operating Catego          2               R  -          enum16
40248  CtrlModes            Supported Control Modes        14271               R  -          bitfield32
40250  IntIslandCatRtg      Intentional Island Catego          1               R  -          bitfield16
40251  WMax                 Active Power Max Setting           0  W        S   RW -          uint16
40252  WMaxOvrExt           Active Power (Over-Excite       None  W        S   RW -          uint16
40253  WOvrExtPF            Specified Over-Excited PF       None           S   RW -          uint16
40254  WMaxUndExt           Active Power (Under-Excit       None  W        S   RW -          uint16
40255  WUndExtPF            Specified Under-Excited P       None           S   RW -          uint16
40256  VAMax                Apparent Power Max Settin          0  VA       S   RW -          uint16
40257  VarMaxInj            Reactive Power Injected S       None  Var      S   RW -          uint16
40258  VarMaxAbs            Reactive Power Absorbed S       None  Var      S   RW -          uint16
40259  WChaRteMax           Charge Rate Max Setting         None  W        S   RW -          uint16
40260  WDisChaRteMax        Discharge Rate Max Settin       None  W        S   RW -          uint16
40261  VAChaRteMax          Charge Rate Max VA Settin       None  VA       S   RW -          uint16
40262  VADisChaRteMax       Discharge Rate Max VA Set       None  VA       S   RW -          uint16
40263  VNom                 Nominal AC Voltage Settin       None  V        S   RW -          uint16
40264  VMax                 AC Voltage Max Setting          None  V        S   RW -          uint16
40265  VMin                 AC Voltage Min Setting          None  V        S   RW -          uint16
40266  AMax                 AC Current Max Setting          None  A        S   RW -          uint16
40267  PFOvrExt             PF Over-Excited Setting (       None           S   RW -          uint16
40268  PFUndExt             PF Under-Excited Setting        None           S   RW -          uint16
40269  IntIslandCat         Intentional Island Catego       None               RW -          bitfield16
40270  W_SF                 Active Power Scale Factor          0               R  -          sunssf
40271  PF_SF                Power Factor Scale Factor         -3               R  -          sunssf
40272  VA_SF                Apparent Power Scale Fact          0               R  -          sunssf
40273  Var_SF               Reactive Power Scale Fact          0               R  -          sunssf
40274  V_SF                 Voltage Scale Factor               0               R  -          sunssf
40275  A_SF                 Current Scale Factor              -1               R  -          sunssf
40276  S_SF                 Susceptance Scale Factor           0               R  -          sunssf

Model 703: DEREnterService
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40277  ID                   Model ID                         703               R  -          uint16
40278  L                    Model Length                      17               R  -          uint16
40279  ES                   Permit Enter Service               1               RW -          enum16
40280  ESVHi                Enter Service Voltage Hig        253  Pct      S   RW 2530       uint16
40281  ESVLo                Enter Service Voltage Low        205  Pct      S   RW 2050       uint16
40282  ESHzHi               Enter Service Frequency H      50.15  Hz       S   RW 5015       uint32
40284  ESHzLo               Enter Service Frequency L       47.5  Hz       S   RW 4750       uint32
40286  ESDlyTms             Enter Service Delay Time          60  Secs         RW -          uint32
40288  ESRndTms             Enter Service Random Dela       None  Secs         RW -          uint32
40290  ESRmpTms             Enter Service Ramp Time          360  Secs         RW -          uint32
40292  ESDlyRemTms          Enter Service Delay Remai       None  Secs         R  -          uint32
40294  V_SF                 Voltage Scale Factor              -1               R  -          sunssf
40295  Hz_SF                Frequency Scale Factor            -2               R  -          sunssf

Model 704: DERCtlAC
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40296  ID                   Model ID                         704               R  -          uint16
40297  L                    Model Length                      65               R  -          uint16
40298  PFWInjEna            Power Factor Enable (W In          1               RW -          enum16
40299  PFWInjEnaRvrt        Power Factor Reversion En       None               RW -          enum16
40300  PFWInjRvrtTms        PF Reversion Time (W Inj)       None  Secs         RW -          uint32
40302  PFWInjRvrtRem        PF Reversion Time Rem (W        None  Secs         R  -          uint32
40304  PFWAbsEna            Power Factor Enable (W Ab       None               RW -          enum16
40305  PFWAbsEnaRvrt        Power Factor Reversion En       None               RW -          enum16
40306  PFWAbsRvrtTms        PF Reversion Time (W Abs)       None  Secs         RW -          uint32
40308  PFWAbsRvrtRem        PF Reversion Time Rem (W        None  Secs         R  -          uint32
40310  WMaxLimPctEna        Limit Max Power Pct Enabl          0               RW -          enum16
40311  WMaxLimPct           Limit Max Power Pct Setpo        100  Pct      S   RW 1000       uint16
40312  WMaxLimPctRvrt       Reversion Limit Max Power       None  Pct      S   RW -          uint16
40313  WMaxLimPctEnaRvrt    Reversion Limit Max Power       None               RW -          enum16
40314  WMaxLimPctRvrtTms    Limit Max Power Pct Rever       None  Secs         RW -          uint32
40316  WMaxLimPctRvrtRem    Limit Max Power Pct Rev T       None  Secs         R  -          uint32
40318  WSetEna              Set Active Power Enable            0               RW -          enum16
40319  WSetMod              Set Active Power Mode              0               RW -          enum16
40320  WSet                 Active Power Setpoint (W)          0  W        S   RW -          int32
40322  WSetRvrt             Reversion Active Power (W          0  W        S   RW -          int32
40324  WSetPct              Active Power Setpoint (Pc          0  Pct      S   RW -          int16
40325  WSetPctRvrt          Reversion Active Power (P          0  Pct      S   RW -          int16
40326  WSetEnaRvrt          Reversion Active Power En          1               RW -          enum16
40327  WSetRvrtTms          Active Power Reversion Ti         60  Secs         RW -          uint32
40329  WSetRvrtRem          Active Power Rev Time Rem          0  Secs         R  -          uint32
40331  VarSetEna            Set Reactive Power Enable          0               RW -          enum16
40332  VarSetMod            Set Reactive Power Mode            1               RW -          enum16
40333  VarSetPri            Reactive Power Priority            2               RW -          enum16
40334  VarSet               Reactive Power Setpoint (          0  Var      S   RW -          int32
40336  VarSetRvrt           Reversion Reactive Power        None  Var      S   RW -          int32
40338  VarSetPct            Reactive Power Setpoint (       None  Pct      S   RW -          int16
40339  VarSetPctRvrt        Reversion Reactive Power        None  Pct      S   RW -          int16
40340  VarSetEnaRvrt        Reversion Reactive Power        None               RW -          enum16
40341  VarSetRvrtTms        Reactive Power Reversion        None  Secs         RW -          uint32
40343  VarSetRvrtRem        Reactive Power Rev Time R       None  Secs         R  -          uint32
40345  WRmp                 Normal Ramp Rate                None  %Max/Sec     RW -          uint16
40346  WRmpRef              Normal Ramp Rate Referenc       None               RW -          enum16
40347  VarRmp               Reactive Power Ramp Rate        None  %Max/Sec     RW -          uint16
40348  AntiIslEna           Anti-Islanding Enable           None               RW -          enum16
40349  PF_SF                Power Factor Scale Factor         -3               R  -          sunssf
40350  WMaxLimPct_SF        Limit Max Power Scale Fac         -1               R  -          sunssf
40351  WSet_SF              Active Power Scale Factor          0               R  -          sunssf
40352  WSetPct_SF           Active Power Pct Scale Fa         -1               R  -          sunssf
40353  VarSet_SF            Reactive Power Scale Fact          0               R  -          sunssf
40354  VarSetPct_SF         Reactive Power Pct Scale          -1               R  -          sunssf

Model 705: DERVoltVar
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40363  ID                   Model ID                         705               R  -          uint16
40364  L                    Model Length                      67               R  -          uint16
40365  Ena                  DER Volt-Var Module Enabl          1               RW -          enum16
40366  AdptCrvReq           Adopt Curve Request                0               RW -          uint16
40367  AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
40368  NPt                  Number Of Points                   4               R  -          uint16
40369  NCrv                 Stored Curve Count                 3               R  -          uint16
40370  RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
40372  RvrtRem              Reversion Time Remaining        None  Secs         R  -          uint32
40374  RvrtCrv              Reversion Curve                 None               RW -          uint16
40375  V_SF                 Voltage Scale Factor              -2               R  -          sunssf
40376  DeptRef_SF           Var Scale Factor                  -2               R  -          sunssf
40377  RspTms_SF            Open-Loop Scale Factor             0               R  -          sunssf

Model 706: DERVoltWatt
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40432  ID                   Model ID                         706               R  -          uint16
40433  L                    Model Length                      31               R  -          uint16
40434  Ena                  DER Volt-Watt Module Enab          1               RW -          enum16
40435  AdptCrvReq           Adopt Curve Request                0               RW -          uint16
40436  AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
40437  NPt                  Number Of Points                   2               R  -          uint16
40438  NCrv                 Stored Curve Count                 2               R  -          uint16
40439  RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
40441  RvrtRem              Reversion Time Remaining        None  Secs         R  -          uint32
40443  RvrtCrv              Reversion Curve                 None               RW -          uint16
40444  V_SF                 Voltage Scale Factor               0               R  -          sunssf
40445  DeptRef_SF           Watt Scale Factor                  0               R  -          sunssf
40446  RspTms_SF            Open-Loop Scale Factor            -1               R  -          sunssf

Model 707: DERTripLV
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40465  ID                   Model ID                         707               R  -          uint16
40466  L                    Model Length                     105               R  -          uint16
40467  Ena                  DER Trip LV Module Enable          1               RW -          enum16
40468  AdptCrvReq           Adopt Curve Request                0               RW -          uint16
40469  AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
40470  NPt                  Number Of Points                   5               R  -          uint16
40471  NCrvSet              Stored Curve Count                 2               R  -          uint16
40472  V_SF                 Voltage Scale Factor              -1               R  -          sunssf
40473  Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 708: DERTripHV
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40572  ID                   Model ID                         708               R  -          uint16
40573  L                    Model Length                     105               R  -          uint16
40574  Ena                  DER Trip HV Module Enable          1               RW -          enum16
40575  AdptCrvReq           Adopt Curve Request                0               RW -          uint16
40576  AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
40577  NPt                  Number Of Points                   5               R  -          uint16
40578  NCrvSet              Stored Curve Count                 2               R  -          uint16
40579  V_SF                 Voltage Scale Factor              -1               R  -          sunssf
40580  Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 709: DERTripLF
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40679  ID                   Model ID                         709               R  -          uint16
40680  L                    Model Length                     135               R  -          uint16
40681  Ena                  DER Trip LF Module Enable          1               RW -          enum16
40682  AdptCrvReq           Adopt Curve Request                0               RW -          uint16
40683  AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
40684  NPt                  Number Of Points                   5               R  -          uint16
40685  NCrvSet              Stored Curve Count                 2               R  -          uint16
40686  Hz_SF                Frequency Scale Factor            -1               R  -          sunssf
40687  Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 710: DERTripHF
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40816  ID                   Model ID                         710               R  -          uint16
40817  L                    Model Length                     135               R  -          uint16
40818  Ena                  DER Trip HF Module Enable          1               RW -          enum16
40819  AdptCrvReq           Adopt Curve Request                0               RW -          uint16
40820  AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
40821  NPt                  Number Of Points                   5               R  -          uint16
40822  NCrvSet              Stored Curve Count                 2               R  -          uint16
40823  Hz_SF                Frequency Scale Factor            -1               R  -          sunssf
40824  Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 711: DERFreqDroop
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40953  ID                   Model ID                         711               R  -          uint16
40954  L                    Model Length                      32               R  -          uint16
40955  Ena                  DER Frequency Droop Modul          1               RW -          enum16
40956  AdptCtlReq           Set Active Control Reques          0               RW -          uint16
40957  AdptCtlRslt          Set Active Control Result          0               R  -          enum16
40958  NCtl                 Stored Control Count               2               R  -          uint16
40959  RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
40961  RvrtRem              Reversion Time Left             None  Secs         R  -          uint32
40963  RvrtCtl              Reversion Control               None               RW -          uint16
40964  Db_SF                Deadband Scale Factor             -3               R  -          sunssf
40965  K_SF                 Frequency Change Scale Fa         -3               R  -          sunssf
40966  RspTms_SF            Open-Loop Scale Factor            -1               R  -          sunssf

Model 712: DERWattVar
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
40987  ID                   Model ID                         712               R  -          uint16
40988  L                    Model Length                      44               R  -          uint16
40989  Ena                  DER Watt-Var Module Enabl          0               RW -          enum16
40990  AdptCrvReq           Set Active Curve Request           0               RW -          uint16
40991  AdptCrvRslt          Set Active Curve Result            0               R  -          enum16
40992  NPt                  Number Of Points                   6               R  -          uint16
40993  NCrv                 Stored Curve Count                 2               R  -          uint16
40994  RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
40996  RvrtRem              Reversion Time Left             None  Secs         R  -          uint32
40998  RvrtCrv              Reversion Curve                 None               RW -          uint16
40999  W_SF                 Active Power Scale Factor         -1               R  -          sunssf
41000  DeptRef_SF           Var Scale Factor                  -1               R  -          sunssf

Model 713: DERStorageCapacity
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
41033  ID                   Model ID                         713               R  -          uint16
41034  L                    Model Length                       7               R  -          uint16
41035  WHRtg                Energy Rating                  13600  WH       S   R  -          uint16
41036  WHAvail              Energy Available                7501  WH       S   R  -          uint16
41037  SoC                  State of Charge                   55  Pct      S   R  550        uint16
41038  SoH                  State of Health                 95.6  Pct      S   R  956        uint16
41039  Sta                  Status                             0               R  -          enum16
41040  WH_SF                Energy Scale Factor                0               R  -          sunssf
41041  Pct_SF               Percent Scale Factor              -1               R  -          sunssf

Model 714: DERMeasureDC
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
41042  ID                   Model ID                         714               R  -          uint16
41043  L                    Model Length                      43               R  -          uint16
41044  PrtAlrms             Port Alarms                        0               R  -          bitfield32
41046  NPrt                 Number Of Ports                    1               R  -          uint16
41047  DCA                  DC Current                         0  A        S   R  -          int16
41048  DCW                  DC Power                         500  W        S   R  -          int16
41049  DCWhInj              DC Energy Injected           6344500  Wh       S   R  -          uint64
41053  DCWhAbs              DC Energy Absorbed           6478740  Wh       S   R  -          uint64
41057  DCA_SF               DC Current Scale Factor            0               R  -          sunssf
41058  DCV_SF               DC Voltage Scale Factor            0               R  -          sunssf
41059  DCW_SF               DC Power Scale Factor              0               R  -          sunssf
41060  DCWH_SF              DC Energy Scale Factor             0               R  -          sunssf
41061  Tmp_SF               Temperature Scale Factor           0               R  -          sunssf

Model 715: DERCtl
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
41087  ID                   Model ID                         715               R  -          uint16
41088  L                    Model Length                       7               R  -          uint16
41089  LocRemCtl            Control Mode                       1               R  -          enum16
41090  DERHb                DER Heartbeat                      0               R  -          uint32
41092  ControllerHb         Controller Heartbeat               0               RW -          uint32
41094  AlarmReset           Alarm Reset                        0               RW -          uint16
41095  OpCtl                Set Operation                      0               RW -          enum16

---

## 2. Native Addressing Scan (Base 1)

**Command**:  
`python3 tools/modbus_sunspec2_reader.py -i 192.0.2.110 -u 1 -t 20 -b 1 -dvalues --vals`

```text
Model 1: common
Addr   Name       Label                  Value                                         RW Type
----------------------------------------------------------------------------------------------------
2      ID         Model ID               1                                             R  uint16
3      L          Model Length           66                                            R  uint16
4      Mn         Manufacturer           FranklinWH Technologies Co., Ltd              R  string
20     Md         Model                  aGate X                                       R  string
36     Opt        Options                Option Name                                   R  string
44     Vr         Version                V10R01B04D00                                  R  string
52     SN         Serial Number          SN-REDACTED-XXXX                          R  string
68     DA         Device Address         1                                             RW uint16
69     Pad                               32768                                         R  pad

Model 502: solar_module
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
1096   ID                   Model ID                         502               R  -          uint16
1097   L                    Model Length                      28               R  -          uint16
1098   A_SF                                                    0               R  -          sunssf
1099   V_SF                                                    0               R  -          sunssf
1100   W_SF                                                    0               R  -          sunssf
1101   Wh_SF                                                   0               R  -          sunssf
1102   Stat                 Status                             0               R  -          enum16
1103   StatVend             Vendor Status                      0               R  -          enum16
1104   Evt                  Events                             0               R  -          bitfield32
1106   EvtVend              Vendor Module Event Flags          0               R  -          bitfield32
1108   Ctl                  Control                         None               RW -          enum16
1109   CtlVend              Vendor Control                  None               RW -          enum32
1111   CtlVal               Control Value                   None               RW -          int32
1113   Tms                  Timestamp                          0  Secs         R  -          uint32
1115   OutA                 Output Current                     0  A        S   R  -          int16
1116   OutV                 Output Voltage                     0  V        S   R  -          int16
1117   OutWh                Output Energy               12959408  Wh       S   R  -          acc32
1119   OutPw                Output Power                       0  W        S   R  -          int16
1120   Tmp                  Temp                               0  C            R  -          int16
1121   InA                  Input Current                      0  A        S   R  -          int16
1122   InV                  Input Voltage                      0  V        S   R  -          int16
1123   InWh                 Input Energy                    None  Wh       S   R  -          acc32
1125   InW                  Input Power                        0  W        S   R  -          int16

Model 701: DERMeasureAC
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
70     ID                   Model ID                         701               R  -          uint16
71     L                    Model Length                     153               R  -          uint16
72     ACType               AC Wiring Type                     0               R  -          enum16
73     St                   Operating State                    1               R  -          enum16
74     InvSt                Inverter State                     3               R  -          enum16
75     ConnSt               Grid Connection State              1               R  -          enum16
76     Alrm                 Alarm Bitfield                     0               R  -          bitfield32
78     DERMode              DER Operational Character          1               R  -          bitfield32
80     W                    Active Power                       3  W        S   R  -          int16
81     VA                   Apparent Power                   777  VA       S   R  -          int16
82     Var                  Reactive Power                  -638  Var      S   R  -          int16
83     PF                   Power Factor                  -0.011           S   R  -11        int16
84     A                    Total AC Current                 3.2  A        S   R  32         int16
85     LLV                  Voltage LL                     240.9  V        S   R  2409       uint16
86     LNV                  Voltage LN                     240.9  V        S   R  2409       uint16
87     Hz                   Frequency                      49.96  Hz       S   R  49960      uint32
89     TotWhInj             Total Energy Injected        4615466  Wh       S   R  -          uint64
93     TotWhAbs             Total Energy Absorbed        1463923  Wh       S   R  -          uint64
97     TotVarhInj           Total Reactive Energy Inj          0  Varh     S   R  -          uint64
101    TotVarhAbs           Total Reactive Energy Abs          0  Varh     S   R  -          uint64
105    TmpAmb               Ambient Temperature             18.6  C        S   R  186        int16
106    TmpCab               Cabinet Temperature             36.6  C        S   R  366        int16
107    TmpSnk               Heat Sink Temperature              0  C        S   R  -          int16
108    TmpTrns              Transformer Temperature            0  C        S   R  -          int16
109    TmpSw                IGBT/MOSFET Temperature           25  C        S   R  250        int16
110    TmpOt                Other Temperature                  0  C        S   R  -          int16
111    WL1                  Watts L1                          -9  W        S   R  -          int16
112    VAL1                 VA L1                            777  VA       S   R  -          int16
113    VarL1                Var L1                          -638  Var      S   R  -          int16
114    PFL1                 PF L1                         -0.011           S   R  -11        int16
115    AL1                  Amps L1                          3.2  A        S   R  32         int16
116    VL1L2                Phase Voltage L1-L2            240.9  V        S   R  2409       uint16
117    VL1                  Phase Voltage L1-N             240.9  V        S   R  2409       uint16
118    TotWhInjL1           Total Watt-Hours Inj L1      4615751  Wh       S   R  -          uint64
122    TotWhAbsL1           Total Watt-Hours Abs L1      1464282  Wh       S   R  -          uint64
126    TotVarhInjL1         Total Var-Hours Inj L1             0  Varh     S   R  -          uint64
130    TotVarhAbsL1         Total Var-Hours Abs L1             0  Varh     S   R  -          uint64
134    WL2                  Watts L2                           0  W        S   R  -          int16
135    VAL2                 VA L2                              0  VA       S   R  -          int16
136    VarL2                Var L2                             0  Var      S   R  -          int16
137    PFL2                 PF L2                              0           S   R  -          int16
138    AL2                  Amps L2                            0  A        S   R  -          int16
139    VL2L3                Phase Voltage L2-L3                0  V        S   R  -          uint16
140    VL2                  Phase Voltage L2-N                 0  V        S   R  -          uint16
141    TotWhInjL2           Total Watt-Hours Inj L2            0  Wh       S   R  -          uint64
145    TotWhAbsL2           Total Watt-Hours Abs L2            0  Wh       S   R  -          uint64
149    TotVarhInjL2         Total Var-Hours Inj L2             0  Varh     S   R  -          uint64
153    TotVarhAbsL2         Total Var-Hours Abs L2             0  Varh     S   R  -          uint64
157    WL3                  Watts L3                           0  W        S   R  -          int16
158    VAL3                 VA L3                              0  VA       S   R  -          int16
159    VarL3                Var L3                             0  Var      S   R  -          int16
160    PFL3                 PF L3                              0           S   R  -          int16
161    AL3                  Amps L3                            0  A        S   R  -          int16
162    VL3L1                Phase Voltage L3-L1                0  V        S   R  -          uint16
163    VL3                  Phase Voltage L3-N                 0  V        S   R  -          uint16
164    TotWhInjL3           Total Watt-Hours Inj L3            0  Wh       S   R  -          uint64
168    TotWhAbsL3           Total Watt-Hours Abs L3            0  Wh       S   R  -          uint64
172    TotVarhInjL3         Total Var-Hours Inj L3             0  Varh     S   R  -          uint64
176    TotVarhAbsL3         Total Var-Hours Abs L3             0  Varh     S   R  -          uint64
180    ThrotPct             Throttling In Pct               None  Pct          R  -          uint16
181    ThrotSrc             Throttle Source Informati       None               R  -          bitfield32
183    A_SF                 Current Scale Factor              -1               R  -          sunssf
184    V_SF                 Voltage Scale Factor              -1               R  -          sunssf
185    Hz_SF                Frequency Scale Factor            -3               R  -          sunssf
186    W_SF                 Active Power Scale Factor          0               R  -          sunssf
187    PF_SF                Power Factor Scale Factor         -3               R  -          sunssf
188    VA_SF                Apparent Power Scale Fact          0               R  -          sunssf
189    Var_SF               Reactive Power Scale Fact          0               R  -          sunssf
190    TotWh_SF             Active Energy Scale Facto          0               R  -          sunssf
191    TotVarh_SF           Reactive Energy Scale Fac          3               R  -          sunssf
192    Tmp_SF               Temperature Scale Factor          -1               R  -          sunssf
193    MnAlrmInfo           Manufacturer Alarm Info   Manufacturer custom error info               R  -          string

Model 702: DERCapacity
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
225    ID                   Model ID                         702               R  -          uint16
226    L                    Model Length                      50               R  -          uint16
227    WMaxRtg              Active Power Max Rating            0  W        S   R  -          uint16
228    WOvrExtRtg           Active Power (Over-Excite       5000  W        S   R  -          uint16
229    WOvrExtRtgPF         Specified Over-Excited PF       0.85           S   R  850        uint16
230    WUndExtRtg           Active Power (Under-Excit       5000  W        S   R  -          uint16
231    WUndExtRtgPF         Specified Under-Excited P       0.85           S   R  850        uint16
232    VAMaxRtg             Apparent Power Max Rating       5800  VA       S   R  -          uint16
233    VarMaxInjRtg         Reactive Power Injected R       2940  Var      S   R  -          uint16
234    VarMaxAbsRtg         Reactive Power Absorbed R       2940  Var      S   R  -          uint16
235    WChaRteMaxRtg        Charge Rate Max Rating          5000  W        S   R  -          uint16
236    WDisChaRteMaxRtg     Discharge Rate Max Rating       5000  W        S   R  -          uint16
237    VAChaRteMaxRtg       Charge Rate Max VA Rating       5800  VA       S   R  -          uint16
238    VADisChaRteMaxRtg    Discharge Rate Max VA Rat       5800  VA       S   R  -          uint16
239    VNomRtg              AC Voltage Nominal Rating        240  V        S   R  -          uint16
240    VMaxRtg              AC Voltage Max Rating            288  V        S   R  -          uint16
241    VMinRtg              AC Voltage Min Rating            192  V        S   R  -          uint16
242    AMaxRtg              AC Current Max Rating           24.5  A        S   R  245        uint16
243    PFOvrExtRtg          PF Over-Excited Rating (U       0.85           S   R  850        uint16
244    PFUndExtRtg          PF Under-Excited Rating (       0.85           S   R  850        uint16
245    ReactSusceptRtg      Reactive Susceptance            3725  S        S   R  -          uint16
246    NorOpCatRtg          Normal Operating Category          1               R  -          enum16
247    AbnOpCatRtg          Abnormal Operating Catego          2               R  -          enum16
248    CtrlModes            Supported Control Modes        14271               R  -          bitfield32
250    IntIslandCatRtg      Intentional Island Catego          1               R  -          bitfield16
251    WMax                 Active Power Max Setting           0  W        S   RW -          uint16
252    WMaxOvrExt           Active Power (Over-Excite       None  W        S   RW -          uint16
253    WOvrExtPF            Specified Over-Excited PF       None           S   RW -          uint16
254    WMaxUndExt           Active Power (Under-Excit       None  W        S   RW -          uint16
255    WUndExtPF            Specified Under-Excited P       None           S   RW -          uint16
256    VAMax                Apparent Power Max Settin          0  VA       S   RW -          uint16
257    VarMaxInj            Reactive Power Injected S       None  Var      S   RW -          uint16
258    VarMaxAbs            Reactive Power Absorbed S       None  Var      S   RW -          uint16
259    WChaRteMax           Charge Rate Max Setting         None  W        S   RW -          uint16
260    WDisChaRteMax        Discharge Rate Max Settin       None  W        S   RW -          uint16
261    VAChaRteMax          Charge Rate Max VA Settin       None  VA       S   RW -          uint16
262    VADisChaRteMax       Discharge Rate Max VA Set       None  VA       S   RW -          uint16
263    VNom                 Nominal AC Voltage Settin       None  V        S   RW -          uint16
264    VMax                 AC Voltage Max Setting          None  V        S   RW -          uint16
265    VMin                 AC Voltage Min Setting          None  V        S   RW -          uint16
266    AMax                 AC Current Max Setting          None  A        S   RW -          uint16
267    PFOvrExt             PF Over-Excited Setting (       None           S   RW -          uint16
268    PFUndExt             PF Under-Excited Setting        None           S   RW -          uint16
269    IntIslandCat         Intentional Island Catego       None               RW -          bitfield16
270    W_SF                 Active Power Scale Factor          0               R  -          sunssf
271    PF_SF                Power Factor Scale Factor         -3               R  -          sunssf
272    VA_SF                Apparent Power Scale Fact          0               R  -          sunssf
273    Var_SF               Reactive Power Scale Fact          0               R  -          sunssf
274    V_SF                 Voltage Scale Factor               0               R  -          sunssf
275    A_SF                 Current Scale Factor              -1               R  -          sunssf
276    S_SF                 Susceptance Scale Factor           0               R  -          sunssf

Model 703: DEREnterService
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
277    ID                   Model ID                         703               R  -          uint16
278    L                    Model Length                      17               R  -          uint16
279    ES                   Permit Enter Service               1               RW -          enum16
280    ESVHi                Enter Service Voltage Hig        253  Pct      S   RW 2530       uint16
281    ESVLo                Enter Service Voltage Low        205  Pct      S   RW 2050       uint16
282    ESHzHi               Enter Service Frequency H      50.15  Hz       S   RW 5015       uint32
284    ESHzLo               Enter Service Frequency L       47.5  Hz       S   RW 4750       uint32
286    ESDlyTms             Enter Service Delay Time          60  Secs         RW -          uint32
288    ESRndTms             Enter Service Random Dela       None  Secs         RW -          uint32
290    ESRmpTms             Enter Service Ramp Time          360  Secs         RW -          uint32
292    ESDlyRemTms          Enter Service Delay Remai       None  Secs         R  -          uint32
294    V_SF                 Voltage Scale Factor              -1               R  -          sunssf
295    Hz_SF                Frequency Scale Factor            -2               R  -          sunssf

Model 704: DERCtlAC
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
296    ID                   Model ID                         704               R  -          uint16
297    L                    Model Length                      65               R  -          uint16
298    PFWInjEna            Power Factor Enable (W In          1               RW -          enum16
299    PFWInjEnaRvrt        Power Factor Reversion En       None               RW -          enum16
300    PFWInjRvrtTms        PF Reversion Time (W Inj)       None  Secs         RW -          uint32
302    PFWInjRvrtRem        PF Reversion Time Rem (W        None  Secs         R  -          uint32
304    PFWAbsEna            Power Factor Enable (W Ab       None               RW -          enum16
305    PFWAbsEnaRvrt        Power Factor Reversion En       None               RW -          enum16
306    PFWAbsRvrtTms        PF Reversion Time (W Abs)       None  Secs         RW -          uint32
308    PFWAbsRvrtRem        PF Reversion Time Rem (W        None  Secs         R  -          uint32
310    WMaxLimPctEna        Limit Max Power Pct Enabl          0               RW -          enum16
311    WMaxLimPct           Limit Max Power Pct Setpo        100  Pct      S   RW 1000       uint16
312    WMaxLimPctRvrt       Reversion Limit Max Power       None  Pct      S   RW -          uint16
313    WMaxLimPctEnaRvrt    Reversion Limit Max Power       None               RW -          enum16
314    WMaxLimPctRvrtTms    Limit Max Power Pct Rever       None  Secs         RW -          uint32
316    WMaxLimPctRvrtRem    Limit Max Power Pct Rev T       None  Secs         R  -          uint32
318    WSetEna              Set Active Power Enable            0               RW -          enum16
319    WSetMod              Set Active Power Mode              0               RW -          enum16
320    WSet                 Active Power Setpoint (W)          0  W        S   RW -          int32
322    WSetRvrt             Reversion Active Power (W          0  W        S   RW -          int32
324    WSetPct              Active Power Setpoint (Pc          0  Pct      S   RW -          int16
325    WSetPctRvrt          Reversion Active Power (P          0  Pct      S   RW -          int16
326    WSetEnaRvrt          Reversion Active Power En          1               RW -          enum16
327    WSetRvrtTms          Active Power Reversion Ti         60  Secs         RW -          uint32
329    WSetRvrtRem          Active Power Rev Time Rem          0  Secs         R  -          uint32
331    VarSetEna            Set Reactive Power Enable          0               RW -          enum16
332    VarSetMod            Set Reactive Power Mode            1               RW -          enum16
333    VarSetPri            Reactive Power Priority            2               RW -          enum16
334    VarSet               Reactive Power Setpoint (          0  Var      S   RW -          int32
336    VarSetRvrt           Reversion Reactive Power        None  Var      S   RW -          int32
338    VarSetPct            Reactive Power Setpoint (       None  Pct      S   RW -          int16
339    VarSetPctRvrt        Reversion Reactive Power        None  Pct      S   RW -          int16
340    VarSetEnaRvrt        Reversion Reactive Power        None               RW -          enum16
341    VarSetRvrtTms        Reactive Power Reversion        None  Secs         RW -          uint32
343    VarSetRvrtRem        Reactive Power Rev Time R       None  Secs         R  -          uint32
345    WRmp                 Normal Ramp Rate                None  %Max/Sec     RW -          uint16
346    WRmpRef              Normal Ramp Rate Referenc       None               RW -          enum16
347    VarRmp               Reactive Power Ramp Rate        None  %Max/Sec     RW -          uint16
348    AntiIslEna           Anti-Islanding Enable           None               RW -          enum16
349    PF_SF                Power Factor Scale Factor         -3               R  -          sunssf
350    WMaxLimPct_SF        Limit Max Power Scale Fac         -1               R  -          sunssf
351    WSet_SF              Active Power Scale Factor          0               R  -          sunssf
352    WSetPct_SF           Active Power Pct Scale Fa         -1               R  -          sunssf
353    VarSet_SF            Reactive Power Scale Fact          0               R  -          sunssf
354    VarSetPct_SF         Reactive Power Pct Scale          -1               R  -          sunssf

Model 705: DERVoltVar
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
363    ID                   Model ID                         705               R  -          uint16
364    L                    Model Length                      67               R  -          uint16
365    Ena                  DER Volt-Var Module Enabl          1               RW -          enum16
366    AdptCrvReq           Adopt Curve Request                0               RW -          uint16
367    AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
368    NPt                  Number Of Points                   4               R  -          uint16
369    NCrv                 Stored Curve Count                 3               R  -          uint16
370    RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
372    RvrtRem              Reversion Time Remaining        None  Secs         R  -          uint32
374    RvrtCrv              Reversion Curve                 None               RW -          uint16
375    V_SF                 Voltage Scale Factor              -2               R  -          sunssf
376    DeptRef_SF           Var Scale Factor                  -2               R  -          sunssf
377    RspTms_SF            Open-Loop Scale Factor             0               R  -          sunssf

Model 706: DERVoltWatt
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
432    ID                   Model ID                         706               R  -          uint16
433    L                    Model Length                      31               R  -          uint16
434    Ena                  DER Volt-Watt Module Enab          1               RW -          enum16
435    AdptCrvReq           Adopt Curve Request                0               RW -          uint16
436    AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
437    NPt                  Number Of Points                   2               R  -          uint16
438    NCrv                 Stored Curve Count                 2               R  -          uint16
439    RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
441    RvrtRem              Reversion Time Remaining        None  Secs         R  -          uint32
443    RvrtCrv              Reversion Curve                 None               RW -          uint16
444    V_SF                 Voltage Scale Factor               0               R  -          sunssf
445    DeptRef_SF           Watt Scale Factor                  0               R  -          sunssf
446    RspTms_SF            Open-Loop Scale Factor            -1               R  -          sunssf

Model 707: DERTripLV
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
465    ID                   Model ID                         707               R  -          uint16
466    L                    Model Length                     105               R  -          uint16
467    Ena                  DER Trip LV Module Enable          1               RW -          enum16
468    AdptCrvReq           Adopt Curve Request                0               RW -          uint16
469    AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
470    NPt                  Number Of Points                   5               R  -          uint16
471    NCrvSet              Stored Curve Count                 2               R  -          uint16
472    V_SF                 Voltage Scale Factor              -1               R  -          sunssf
473    Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 708: DERTripHV
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
572    ID                   Model ID                         708               R  -          uint16
573    L                    Model Length                     105               R  -          uint16
574    Ena                  DER Trip HV Module Enable          1               RW -          enum16
575    AdptCrvReq           Adopt Curve Request                0               RW -          uint16
576    AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
577    NPt                  Number Of Points                   5               R  -          uint16
578    NCrvSet              Stored Curve Count                 2               R  -          uint16
579    V_SF                 Voltage Scale Factor              -1               R  -          sunssf
580    Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 709: DERTripLF
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
679    ID                   Model ID                         709               R  -          uint16
680    L                    Model Length                     135               R  -          uint16
681    Ena                  DER Trip LF Module Enable          1               RW -          enum16
682    AdptCrvReq           Adopt Curve Request                0               RW -          uint16
683    AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
684    NPt                  Number Of Points                   5               R  -          uint16
685    NCrvSet              Stored Curve Count                 2               R  -          uint16
686    Hz_SF                Frequency Scale Factor            -1               R  -          sunssf
687    Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 710: DERTripHF
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
816    ID                   Model ID                         710               R  -          uint16
817    L                    Model Length                     135               R  -          uint16
818    Ena                  DER Trip HF Module Enable          1               RW -          enum16
819    AdptCrvReq           Adopt Curve Request                0               RW -          uint16
820    AdptCrvRslt          Adopt Curve Result                 0               R  -          enum16
821    NPt                  Number Of Points                   5               R  -          uint16
822    NCrvSet              Stored Curve Count                 2               R  -          uint16
823    Hz_SF                Frequency Scale Factor            -1               R  -          sunssf
824    Tms_SF               Time Point Scale Factor           -2               R  -          sunssf

Model 711: DERFreqDroop
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
953    ID                   Model ID                         711               R  -          uint16
954    L                    Model Length                      32               R  -          uint16
955    Ena                  DER Frequency Droop Modul          1               RW -          enum16
956    AdptCtlReq           Set Active Control Reques          0               RW -          uint16
957    AdptCtlRslt          Set Active Control Result          0               R  -          enum16
958    NCtl                 Stored Control Count               2               R  -          uint16
959    RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
961    RvrtRem              Reversion Time Left             None  Secs         R  -          uint32
963    RvrtCtl              Reversion Control               None               RW -          uint16
964    Db_SF                Deadband Scale Factor             -3               R  -          sunssf
965    K_SF                 Frequency Change Scale Fa         -3               R  -          sunssf
966    RspTms_SF            Open-Loop Scale Factor            -1               R  -          sunssf

Model 712: DERWattVar
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
987    ID                   Model ID                         712               R  -          uint16
988    L                    Model Length                      44               R  -          uint16
989    Ena                  DER Watt-Var Module Enabl          0               RW -          enum16
990    AdptCrvReq           Set Active Curve Request           0               RW -          uint16
991    AdptCrvRslt          Set Active Curve Result            0               R  -          enum16
992    NPt                  Number Of Points                   6               R  -          uint16
993    NCrv                 Stored Curve Count                 2               R  -          uint16
994    RvrtTms              Reversion Timeout               None  Secs         RW -          uint32
996    RvrtRem              Reversion Time Left             None  Secs         R  -          uint32
998    RvrtCrv              Reversion Curve                 None               RW -          uint16
999    W_SF                 Active Power Scale Factor         -1               R  -          sunssf
1000   DeptRef_SF           Var Scale Factor                  -1               R  -          sunssf

Model 713: DERStorageCapacity
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
1033   ID                   Model ID                         713               R  -          uint16
1034   L                    Model Length                       7               R  -          uint16
1035   WHRtg                Energy Rating                  13600  WH       S   R  -          uint16
1036   WHAvail              Energy Available                6828  WH       S   R  -          uint16
1037   SoC                  State of Charge                   50  Pct      S   R  500        uint16
1038   SoH                  State of Health                 95.6  Pct      S   R  956        uint16
1039   Sta                  Status                             0               R  -          enum16
1040   WH_SF                Energy Scale Factor                0               R  -          sunssf
1041   Pct_SF               Percent Scale Factor              -1               R  -          sunssf

Model 714: DERMeasureDC
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
1042   ID                   Model ID                         714               R  -          uint16
1043   L                    Model Length                      43               R  -          uint16
1044   PrtAlrms             Port Alarms                        0               R  -          bitfield32
1046   NPrt                 Number Of Ports                    1               R  -          uint16
1047   DCA                  DC Current                         0  A        S   R  -          int16
1048   DCW                  DC Power                         400  W        S   R  -          int16
1049   DCWhInj              DC Energy Injected           6345540  Wh       S   R  -          uint64
1053   DCWhAbs              DC Energy Absorbed           6479160  Wh       S   R  -          uint64
1057   DCA_SF               DC Current Scale Factor            0               R  -          sunssf
1058   DCV_SF               DC Voltage Scale Factor            0               R  -          sunssf
1059   DCW_SF               DC Power Scale Factor              0               R  -          sunssf
1060   DCWH_SF              DC Energy Scale Factor             0               R  -          sunssf
1061   Tmp_SF               Temperature Scale Factor           0               R  -          sunssf

Model 715: DERCtl
Addr   Name                 Label                          Value  Units    F   RW Raw        Type
---------------------------------------------------------------------------------------------------------
1087   ID                   Model ID                         715               R  -          uint16
1088   L                    Model Length                       7               R  -          uint16
1089   LocRemCtl            Control Mode                       1               R  -          enum16
1090   DERHb                DER Heartbeat                      0               R  -          uint32
1092   ControllerHb         Controller Heartbeat               0               RW -          uint32
1094   AlarmReset           Alarm Reset                        0               RW -          uint16
1095   OpCtl                Set Operation                      0               RW -          enum16
```
