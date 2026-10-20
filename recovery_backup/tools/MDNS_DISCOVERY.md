# mDNS Discovery via Avahi (Recommended)

Your Avahi Discovery screenshot shows you already have the best tool for device discovery! mDNS (Bonjour/Avahi) is much more reliable than HTTP port scanning.

## What Your Avahi Shows

From your screenshot, your network has:

| Service | Description | Device Type |
|---------|-------------|-------------|
| `_homey._tcp` | Homey Smart Home Hub | Athom Homey |
| `_enphase-envoy._tcp` | Enphase Envoy | Solar Inverter |
| `_home-assistant._tcp` | Home Assistant | Home Automation |
| `_matter._tcp` | Matter/Thread devices | Smart Home |
| `_sonos._tcp` | Sonos Speakers | Audio |
| `_nut._tcp` | Network UPS Tools | UPS monitoring |
| `_esphomelib._tcp` | ESPHome devices | DIY IoT |

## Using Avahi from Command Line

```bash
# Browse all services
avahi-browse -a

# Browse specific service
avahi-browse _home-assistant._tcp
avahi-browse _enphase-envoy._tcp
avahi-browse _homey._tcp

# Resolve IP addresses
avahi-browse -r _home-assistant._tcp

# Get JSON output
avahi-browse -a -p
```

## Python mDNS Discovery

Install `zeroconf` for cross-platform mDNS:

```bash
pip install zeroconf
```

```python
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener

class MyListener(ServiceListener):
    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        print(f"Found: {name} at {info.parsed_addresses()}")

zeroconf = Zeroconf()
browser = ServiceBrowser(zeroconf, "_home-assistant._tcp.local.", MyListener())
```

## Services to Monitor

| Service Type | Port | Use Case |
|-------------|------|----------|
| `_home-assistant._tcp` | 8123 | Home Assistant |
| `_enphase-envoy._tcp` | 80 | Enphase Solar |
| `_homey._tcp` | 80 | Homey Hub |
| `_http._tcp` | 80 | Generic web servers |
| `_mqtt._tcp` | 1883 | MQTT brokers |
| `_modbus._tcp` | 502 | Modbus devices (rare) |

## Why mDNS is Better Than Port Scanning

1. **Accurate**: Devices self-identify with correct service type
2. **Fast**: No need to probe multiple ports
3. **Low traffic**: Multicast, not directed scans
4. **Works across subnets**: If routers allow mDNS
5. **Standard**: Industry standard for IoT discovery

## Integrating with Network Scanner

Your scanner could use mDNS first, then fall back to port scanning:

```bash
# 1. Quick mDNS discovery
avahi-browse -a -t 5 | grep IPv4

# 2. Deep scan specific IPs found
python3 network_scanner.py 192.168.0.XXX --devices modbus -v
```

## Recommended Approach

1. **Use Avahi GUI** (what you have) for visual browsing
2. **Use avahi-browse** for scripting
3. **Use network_scanner.py** only for:
   - Modbus TCP devices (no mDNS)
   - Verification of found devices
   - Devices that don't advertise via mDNS

## Your Network Map (from Avahi)

Based on your screenshot, you have:
- **Home Assistant** at `192.0.2.109` (confirmed by scanner)
- **Enphase Envoy** at one of: `192.0.2.4, 0.7, 0.10, 0.35, 0.224, 0.253`
- **Homey** at `192.0.2.253` (confirmed by scanner)
- **Sonos** speakers in Living Room
- **Various** ESPHome, Matter devices

## Cross-Platform Note

Your Avahi Discovery tool is Linux-specific. For cross-platform mDNS:

| Platform | Tool |
|----------|------|
| Linux | avahi-browse, mDNS tools |
| macOS | dns-sd (built-in) |
| Windows | Bonjour SDK, or Python zeroconf |
| All | Python zeroconf library |

The network scanner can be enhanced to optionally use zeroconf when available.
