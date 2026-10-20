# FranklinWH aGate Network Profile

**Device:** FranklinWH aGate X (Serial: <SERIAL>)
**Firmware:** V10R01B04D
**SoC:** NXP i.MX6ULL (ARM Cortex-A7)
**mDNS Hostname:** `imx6ull14x14evk` (default NXP EVK hostname)
**WiFi MAC:** `<AGATE_MAC>`
**LAN IP:** `192.0.2.110`

## Open Ports

| Port | Protocol | Service | Details |
|------|----------|---------|---------|
| 22 | TCP | SSH | Dropbear 2015.71 (`SSH-2.0-dropbear_2015.71`) |
| 53 | UDP/TCP | DNS | Local resolver (responds to queries) |
| 111 | TCP | RPC | Sun RPC / portmapper |
| 502 | TCP | Modbus TCP | SunSpec compliant — primary control interface |
| 9000 | TCP | Unknown | Accepts connections, no banner, not HTTP |

## Network Interfaces

| Interface | Status | Notes |
|-----------|--------|-------|
| Ethernet | Available | Primary LAN connection (preferred) |
| WiFi | Auto-connect | Fallback if Ethernet unavailable |
| 4G/LTE | Built-in modem | Last-resort backup for cloud connectivity |

**Priority:** Ethernet → WiFi → 4G. If the app shows 4G as primary, the LAN interfaces have failed.

## mDNS Discovery

```
Service: _ssh._tcp.local.
Instance: imx6ull14x14evk
```

The aGate advertises SSH via mDNS but does **not** advertise `_modbus._tcp`.

## Key Observations

- **SSH (port 22)** — Dropbear is a lightweight SSH server for embedded Linux. Password unknown; likely requires installer/factory credentials.
- **DNS (port 53)** — The aGate runs its own DNS resolver, possibly dnsmasq for local name resolution.
- **RPC (port 111)** — Sun RPC portmapper suggests NFS or other RPC services may be available.
- **Port 9000** — Unknown service. Accepts TCP connections but sends no banner and doesn't respond to HTTP. Could be an internal management or firmware update interface.
- **No HTTP/HTTPS** — The aGate has no web interface; all configuration is via the FranklinWH mobile app (cloud API) or Modbus TCP.

## Bluetooth Connectivity (aGate v1.2+)

aGate firmware v1.2 and above supports **Bluetooth Low Energy (BLE)** connectivity for:
- Installer commissioning and configuration
- Customer setup where no local WiFi or network infrastructure exists
- Direct device-to-phone communication without cloud dependency

## Connectivity Troubleshooting

If the aGate becomes unreachable via Modbus TCP:

1. **Check the FranklinWH app → Network Settings** — if it shows "4G" as the primary connection, WiFi/Ethernet have dropped
2. **Check WiFi IP** — if `0.0.0.0`, the DHCP lease was lost. Reconfigure WiFi via the app
3. **Recommend:** Set a DHCP reservation in your router for MAC `<AGATE_MAC>` → `192.0.2.110`

See [WiFi DHCP Failure — 2026-03-21](troubleshooting/2026-03-21_wifi_dhcp_failure.md) for a documented example.
