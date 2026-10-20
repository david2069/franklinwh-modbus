# Network Scanner - mDNS Discovery Guide

## Overview

The network scanner now supports **cross-platform mDNS/Bonjour discovery** using the `zeroconf` library. This works on:
- ✅ Linux (replaces avahi-browse)
- ✅ macOS (uses native Bonjour)
- ✅ Windows (uses native Bonjour or zeroconf)

## Installation

```bash
pip install zeroconf

# Or with all optional dependencies:
pip install -r network_scanner_requirements.txt
```

## Usage

### mDNS Discovery (No IP Range Needed)

```bash
# Discover all known IoT device types
python3 network_scanner.py --mdns

# Discover specific device types only
python3 network_scanner.py --mdns --devices ha,enphase,homey

# Comprehensive scan (all mDNS services)
python3 network_scanner.py --mdns-all

# Custom mDNS timeout
python3 network_scanner.py --mdns --mdns-timeout 10

# JSON output
python3 network_scanner.py --mdns -o json > discovered_devices.json
```

### Traditional IP Scanning

```bash
# Scan specific IP range
python3 network_scanner.py 192.0.2.0/24

# Scan specific devices
python3 network_scanner.py 192.0.2.0/24 --devices modbus,enphase
```

## Supported mDNS Service Types

| Device Type | mDNS Service Type | Port |
|-------------|-------------------|------|
| Home Assistant | `_home-assistant._tcp.local.` | 8123 |
| Enphase Envoy | `_enphase-envoy._tcp.local.` | 80 |
| Homey | `_homey._tcp.local.` | 80 |
| MQTT Broker | `_mqtt._tcp.local.` | 1883 |
| Modbus TCP | `_modbus._tcp.local.` | 502 |

### Additional Services (with --mdns-all)

| Service | mDNS Type | Description |
|---------|-----------|-------------|
| Sonos | `_sonos._tcp.local.` | Speakers |
| NUT UPS | `_nut._tcp.local.` | UPS monitoring |
| ESPHome | `_esphomelib._tcp.local.` | DIY IoT |
| Matter | `_matter._tcp.local.` | Smart home |
| Spotify | `_spotify-connect._tcp.local.` | Audio |
| AirPlay | `_airplay._tcp.local.` | Audio/Video |
| HomeKit | `_hap._tcp.local.` | Apple HomeKit |
| Chromecast | `_googlecast._tcp.local.` | Streaming |
| SSH | `_ssh._tcp.local.` | Remote access |
| HTTP/HTTPS | `_http._tcp.local.` | Web servers |

## Why Use mDNS?

### Advantages:
1. **Cross-platform** - Same command works everywhere
2. **No IP configuration** - Discovers devices automatically
3. **Fast** - Typically 3-5 seconds vs 30+ seconds for IP scanning
4. **Accurate** - Devices self-identify with correct service types
5. **Low network impact** - Uses multicast, not aggressive port scanning

### Limitations:
1. Requires devices to advertise via mDNS (most modern IoT devices do)
2. May not work across network subnets (depends on router mDNS relay)
3. Some devices (older Modbus-only) don't support mDNS

## Recommended Workflow

```bash
# Step 1: Quick mDNS discovery (fast, accurate)
python3 network_scanner.py --mdns -v

# Step 2: If needed, deep scan specific IPs with port scanning
# (for Modbus devices or devices without mDNS)
python3 network_scanner.py 192.0.2.110 --devices modbus -v
```

## Example Output

```
$ python3 network_scanner.py --mdns -v
Network Scanner v1.0
Mode: mDNS Discovery
Device types: all
mDNS Timeout: 5.0s
Output: table
--------------------------------------------------
Starting mDNS discovery (timeout: 5.0s)...
mDNS discovery found 6 device(s)
+--------------+------+------------------+------------------+------------------+
| IP Address   | Port | Device Type      | Manufacturer     | Model            |
+==============+======+==================+==================+==================+
| 192.0.2.4  | 80   | enphase          | Enphase          | Envoy            |
| 192.0.2.7  | 80   | enphase          | Enphase          | Envoy            |
| 192.0.2.10 | 80   | enphase          | Enphase          | Envoy            |
| 192.0.2.109| 8123 | home_assistant   | Nabu Casa        | Home Assistant   |
| 192.0.2.11 | 1883 | mqtt_broker      | None             | MQTT Broker      |
| 192.0.2.253| 80   | homey            | Athom            | Homey            |
+--------------+------+------------------+------------------+------------------+

Found 6 device(s) in 5.2 seconds
```

## JSON Output Example

```json
[
  {
    "ip": "192.0.2.109",
    "port": 8123,
    "device_type": "home_assistant",
    "manufacturer": "Nabu Casa",
    "model": "Home Assistant",
    "extra_data": {
      "mdns_name": "Home Assistant._home-assistant._tcp.local.",
      "mdns_service": "_home-assistant._tcp.local.",
      "mdns_properties": {
        "version": "2024.1.0",
        "base_url": "http://192.0.2.109:8123"
      },
      "hostname": "homeassistant.local.",
      "discovery_method": "mDNS"
    }
  }
]
```

## Programmatic Usage

```python
from network_scanner import NetworkScanner, DeviceType

# Create scanner
scanner = NetworkScanner(
    device_types=[DeviceType.HOME_ASSISTANT, DeviceType.ENPHASE],
    verbose=True
)

# mDNS discovery
devices = scanner.discover_mdns(timeout=5.0)

for device in devices:
    print(f"{device.manufacturer} {device.model} at {device.ip}:{device.port}")
    print(f"  mDNS Name: {device.extra_data.get('mdns_name')}")
```

## Troubleshooting

### "zeroconf not installed" warning
```bash
pip install zeroconf
```

### No devices found with mDNS
1. Check if devices actually advertise mDNS (use `avahi-browse -a` on Linux)
2. Some devices may need mDNS enabled in settings
3. Check firewall rules (UDP port 5353)
4. Try increasing timeout: `--mdns-timeout 10`

### mDNS across subnets
mDNS typically doesn't cross routers. Solutions:
1. Enable mDNS relay/reflector on your router
2. Use IP scanning for other subnets
3. Run scanner on each subnet

## Comparison: mDNS vs IP Scanning

| Feature | mDNS Discovery | IP Scanning |
|---------|---------------|-------------|
| Speed | ⚡ 3-5 seconds | 🐢 15-60 seconds |
| Accuracy | ✅ Device self-identifies | ❌ May have false positives |
| Network load | Low (multicast) | High (TCP probes) |
| IP configuration | None needed | Must specify range |
| Cross-platform | ✅ Yes | ✅ Yes |
| Modbus devices | ❌ No mDNS | ✅ Port 502 scan |
| All devices | Modern IoT only | Any TCP device |

## Summary

**Use `--mdns` when:**
- You want fast, accurate discovery
- You have modern IoT devices
- You don't know the IP ranges
- You want cross-platform compatibility

**Use IP scanning when:**
- You need to find Modbus-only devices
- Devices don't advertise mDNS
- You're scanning specific known ranges
- You need to verify TCP port availability
