# Network Troubleshooting — 2026-03-21

**Date:** 2026-03-21 08:24–08:30 AEDT
**Device:** FranklinWH aGate X @ 192.0.2.110
**Issue:** aGate WiFi lost DHCP lease, fell back to 4G cellular

## Symptom

CLI Modbus TCP connections failing with "Connection reset by peer" and monitor showing all-zero readings. The aGate was unreachable on the LAN.

## Root Cause

The aGate's WiFi had IP `0.0.0.0` — associated with SSID but no DHCP lease obtained. The aGate fell back to its built-in **4G cellular** modem for cloud connectivity.

### Network Settings — 4G Fallback Active

![4G Fallback](media__1774041853875.png)

The connection indicator shows **4G → Internet** (green ✓), confirming the LAN interfaces have failed and the device is on cellular backup.

### WiFi Details — IP 0.0.0.0

![WiFi IP 0.0.0.0](media__1774042008823.png)

- **SSID:** <SSID> (connected, normal signal)
- **NIC MAC:** <AGATE_MAC>
- **IP Address:** 0.0.0.0 ← No DHCP lease
- **DNS:** 8.8.8.8

## Resolution

Reconfigured WiFi via the FranklinWH mobile app (WiFi Configuration wizard):

### Step 1–3: WiFi Configuration Wizard

![Step 1 — Router check](media__1774042059815.png)
![Step 2 — Network list](media__1774042099514.png)
![Step 3 — Enter password](media__1774042128438.png)

### Step 4: Connection Success

![Connection success](media__1774042157845.png)

### Step 5–6: Back Online

![Refreshing settings](media__1774042174268.png)
![WiFi connected](media__1774042226523.png)

Connection indicator now shows **WiFi → Internet** (green ✓). The aGate is back on the LAN.

## Verification

Network scan confirmed the aGate is back at `192.0.2.110`:

```
IP Address       Port   Proto    Device Type        Manufacturer     Model        Serial         Version
--------------------------------------------------------------------------------------------------------------
192.0.2.109    1883   MQTT     mqtt_broker        -                MQTT Broker  -              -
192.0.2.110    502    Modbus   modbus_sunspec     FranklinWH Techn aGate X      <SERIAL>.. V10R01B04D
192.0.2.17     1883   MQTT     mqtt_broker        -                MQTT Broker  -              -
192.0.2.247    1884   MQTT     mqtt_broker        -                MQTT Broker  -              -
```

## Recommendation

Set a **DHCP reservation** in the router for MAC `<AGATE_MAC>` → `192.0.2.110` to prevent this from recurring.
