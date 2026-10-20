# What is Modbus TCP?

This page covers four things you need before using this library:

- **Modbus**, the protocol;
- **SunSpec**, the standard register maps for energy devices built on Modbus;
- **conformance**, meaning how a device declares and proves what it supports;
- **the FranklinWH extension registers**, and where they sit in all of that.

---

## Modbus

### Origins

- **1979:** Modicon introduced the Modbus protocol for its programmable logic controllers. In the Modbus Organization's words, "Modicon, today Schneider Electric, introduced the Modbus protocol to the market in 1979."
- **1997:** Schneider Electric acquired Modicon.
- **1999:** an open Modbus TCP/IP specification was developed, carrying Modbus over Ethernet.
- **April 2004:** Schneider Electric transferred the protocol to the **[Modbus Organization](https://www.modbus.org)**, "an independent, member-based, non-profit organization".
- **Licensing:** the specifications are free to download, with no licensing fees.

Sources: [modbus.org FAQ](https://www.modbus.org/faq); [Wikipedia: Modbus](https://en.wikipedia.org/wiki/Modbus) for the 1997 acquisition.

### The specifications

The Modbus Organization is the **source of truth for Modbus terms** in these docs. Both specifications are at [modbus.org/specifications](https://www.modbus.org/specifications); download requires accepting the Modbus EULA.

| Document | Version | Covers |
|---|---|---|
| MODBUS Application Protocol Specification | V1.1b3 (2012-04-26) | Data model, function codes, PDU addressing, exceptions |
| MODBUS Messaging on TCP/IP Implementation Guide | V1.0b (2006-10-24) | TCP framing (MBAP header), port 502, unit identifier |

### How it works, in four terms

| Term | Meaning |
|---|---|
| **Client / server** | The client (this library) sends requests; the server (the aGate's **Modbus TCP Server**, port 502) answers. One request, one response, no subscriptions. |
| **Holding registers** | 16-bit values the server exposes. Read with function code 3; write with 6 (one register) or 16 (several). Everything on the aGate is a holding register. |
| **PDU address** | The 0-based register number sent in the request (0–65535). The register *number* in the data model counts from 1, so register *N* is PDU address *N*−1. |
| **4xxxx reference** | A legacy Modicon notation, not an address: 40001 means holding register 1, which is PDU address 0. |

Modbus itself knows nothing about watts, batteries or scale factors: a register is just 16 bits. What the numbers mean is defined by the device vendor, or by a standard such as SunSpec. Every address in these docs is a PDU address; see [Register Addressing](FRANKLINWH_SUNSPEC_QUIRKS.md#register-addressing-pdu-addresses-modbus-and-the-sunspec-map).

---

## SunSpec

### The SunSpec Alliance

The **[SunSpec Alliance](https://sunspec.org)** is an industry alliance of solar, storage and distributed-energy companies. It was founded in 2009, according to trade-press sources. It specifies open communication standards (information models, data formats and protocols) and runs test and certification programmes for them. Its best-known standard is **SunSpec Modbus**: a common way to lay out an energy device's data on Modbus registers, so one client can read any compliant inverter or battery.

### What SunSpec adds on top of Modbus

- **A self-describing register map.** The map starts with the marker **"SunS"** (0x53756E53) at one of a few well-known PDU addresses (0, 40000 or 50000). It is followed by **Model 1 (Common)**, which every compliant device must include first. Then come further models, each a block of `ID`, `L` (length) and `L` registers of points. The chain ends with model ID 0xFFFF. A client finds everything by walking this chain, with no vendor-specific addresses needed.
- **Information models.** Each model defines its points: name, type, units, **scale factors** (a power-of-ten multiplier stored in another register), and enumerations.
- **Model series.** The 100-series inverter models date from 2009. They have been superseded for distributed energy resources (DER) by the **700-series DER models** (701–715), which SunSpec approved in **April 2021**. The aGate implements Model 1, 502 and 701–715.

### Where SunSpec Modbus fits in grid standards

**IEEE 1547-2018** (interconnection of DER with the grid) names SunSpec Modbus as one of its communication interfaces, alongside **IEEE 2030.5** and **IEEE 1815 (DNP3)**. **IEEE 1547.1-2020** is the matching test standard. SunSpec's "SunSpec Modbus for 1547" certification checks a device's SunSpec Modbus interface against those requirements. ([SunSpec: 700-series approval](https://sunspec.org/sunspec-modbus-700-series-der-information-models-are-now-approved/), [SunSpec 1547 initiative](https://sunspec.org/sunspec-1547-initiative/))

### Relevant SunSpec publications

All are at [sunspec.org](https://sunspec.org). Check there for current versions.

| Publication | What it is |
|---|---|
| SunSpec Device Information Model Specification | The core rules: the "SunS" map, the model chain, data types and scale factors |
| SunSpec DER Information Model Specification (700-series) | The DER models 701–715 that the aGate implements |
| SunSpec Modbus Conformance Test Procedures | How a server's SunSpec Modbus interface is tested |
| SunSpec Modbus for 1547 Test Procedures | Certification testing against IEEE 1547-2018 requirements |
| Model definitions (JSON/SMDX) | Machine-readable model definitions. This library uses the copy shipped with pysunspec2. |

---

## Conformance: PICS and certification

### What a PICS is

A **PICS** (Protocol Implementation Conformance Statement) is the vendor's declaration of what its device supports. For SunSpec it is an Excel workbook listing the **models and points implemented, with their supported value ranges**, built from a SunSpec template. SunSpec's SVP Dashboard can probe a device and generate a first draft; the vendor completes the rest by hand. Certification testing then checks the device against its PICS. Per SunSpec's test procedures, only SunSpec-standardised models are considered during certification testing.

### FranklinWH's PICS

FranklinWH's PICS is the spreadsheet *UPDATED_FranklinWH_Modbus_PICS_SM-000028.xlsx*. It is FranklinWH's own document and is **not distributed in this repository**. It lists points by PDU address (e.g. ControllerHb at 1092) and has a tab named SPAN that lists the extension registers. That tab does not confirm that any of them is writable on current firmware; FranklinWH has not documented these registers in any public specification.

**A PICS states what a device claims, not what it does.** Testing against the live aGate found differences, recorded here:

- [PICS Conformance Cross-Reference](PICS_CONFORMANCE_CROSS_REFERENCE.md): register-by-register, PICS claim against observed behaviour;
- [Non-Compliance Assessment](NON_COMPLIANCE_ASSESSMENT.md) and [SunSpec Compliance Basis](SUNSPEC_COMPLIANCE_BASIS.md): which standards we test against;
- [SunSpec Quirks](FRANKLINWH_SUNSPEC_QUIRKS.md). Examples: the Model 704 revert timer counts down but doesn't revert, setpoints aren't range-checked, and M713 `Sta` and M714 `DCA` aren't populated.

---

## FranklinWH extensions in the SunSpec context

Some of what you need to integrate with an aGate isn't in any SunSpec model: the **operating mode**, the **SoC reserves**, the **solar breakdown by input**, and the **home load**. FranklinWH exposes these as **proprietary holding registers**, mainly 15500–15513 and 16000–16002. The full list is on [FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md).

How they relate to SunSpec:

| | SunSpec models (Model 1, 502, 701–715 on the aGate) | FranklinWH extension registers |
|---|---|---|
| Found by | Walking the "SunS" model chain | Knowing the address in advance |
| Described by | The published model definition: names, types, units, scale factors | FranklinWH's proprietary PICS (SPAN tab) and testing |
| In certification testing | Yes | No (only SunSpec-standardised models are considered) |
| Read with | Any SunSpec client (e.g. pysunspec2) | A plain Modbus FC3 read at the PDU address |
| Stability | Fixed by the published standard | Vendor-defined; can change with firmware |

**SunSpec does allow vendor data inside the map, as vendor-specific models.** pysunspec2 1.3.6 ships several, such as model 64101 "Eltek Inverter Extension". A model like that sits in the chain and is self-describing. FranklinWH didn't take that route: its extensions are plain registers outside the chain. So:

- a generic SunSpec client won't find them;
- nothing on the device describes them;
- their meaning rests on FranklinWH's PICS and on testing, which is why the extensions page marks every row as **documented**, **measured** or **inferred**.

They still matter in practice. Without 15507–15509 your integration can't see, or stay in step with, the mode and reserves set in the FranklinWH app.

---

## ⚠️ The reality of Modbus: challenges and complexity

1. **Many variants and implementations.** Data types, register alignment, byte order and scaling differ between vendors, even when they follow SunSpec.
2. **Minimal conformance.** SunSpec defines the standard, but vendors often implement the minimum, and a PICS can claim more than the device does.
3. **Little worked documentation.** Standards and vendor documents give few real-world examples. This project's [API Cookbook](API_COOKBOOK.md) exists to fill that gap.
4. **A low-level interface.** You read and write numbered 16-bit registers, not named objects.
5. **Real risk.** Wrong power limits or mode changes act on real hardware. Writes are marked ⚠️ throughout these docs.

---

## ✅ Modbus TCP vs the cloud API

Both this library and [franklinwh-cloud](https://david2069.github.io/franklinwh-cloud/) work with the same aGate, by different paths. Field-by-field: [Modbus vs Cloud API](MODBUS_CLOUD_COMPARISON.md).

| Aspect | Modbus TCP (this library) | Cloud API (franklinwh-cloud) |
|--------|--------------------------|------------------------------|
| **Path** | Direct to the aGate on your LAN | Internet and FranklinWH servers |
| **Latency** | ~100 ms round trip (98 ms average measured) | Higher; via the cloud |
| **Availability** | Works without internet, and off-grid | Needs internet and the FranklinWH service |
| **Clients** | **One Modbus client at a time** | Rate limits shared per account |
| **Setup** | Installer must enable Modbus TCP | Standard FranklinWH credentials |
| **Battery control** | ✅ Charge, discharge, standby | ✅ Charge, discharge, standby |
| **TOU schedules** | ❌ Not available (only the mode and reserves, 15507–15509) | ✅ Full read/write |
| **Mode and reserve writes** | ❌ Undocumented and unconfirmed; not applied on V12R02B60D00 (2026-10-21) | ✅ Full support |
| **Daily energy totals** | ❌ Lifetime counters only | ✅ |
| **Risk profile** | Direct hardware access; mistakes persist | Cloud-mediated guardrails |

!!! tip "When to use which"
    **Modbus TCP** for real-time monitoring, low-latency control, and working without internet. **The cloud API** for TOU schedules, daily totals, accessories, and access from outside your network.

### Key benefits of Modbus TCP

- **No cloud dependency:** no subscription, no internet, and no surprise API changes.
- **An open standard:** Modbus and SunSpec are published and free to use.
- **Local and fast:** about 100 ms per request on your LAN.
- **Direct control:** battery setpoints through SunSpec Model 704, and the mode and reserves through the extension registers.

---

## ⚠️ FranklinWH specifics

- **Extension registers are required to stay in step with the app.** The mode and reserves live only in 15507–15509. See [FranklinWH Extension Registers](FRANKLINWH_MODBUS_EXTENSIONS.md).
- **Remote control takes over the aGate ("VPP mode").** While a Modbus command is active, the FranklinWH app shows VPP mode and you lose manual control in the app.

  ![App showing VPP Mode override](images/vpp_mode.png){ width="300" }
- **You must release control yourself.** The SunSpec revert timer doesn't release control on the aGate (PICS Issue 4), so your client must end every command it starts. See [Safety Controls](SAFETY_CONTROLS.md).
- **No accessory data.** The Generator Module, Smart Circuits and Vehicle-to-Load (V2L) can't be monitored or controlled over Modbus.
