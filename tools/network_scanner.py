#!/usr/bin/env python3
"""
Network Scanner for IoT and Energy Devices

Scans local networks for:
- Modbus TCP devices (SunSpec compliant Model 1)
- SSH servers (banner identification)
- DNS resolvers
- Enphase Solar Inverters (Modbus/REST API)
- SolarEdge Solar Inverters (Modbus/REST API)
- Home Assistant instances
- MQTT Brokers
- Homey Smart Home Hub

Usage:
    python3 network_scanner.py 192.168.1.0/24
    python3 network_scanner.py 192.168.1.1-192.168.1.100 --devices modbus,enphase
    python3 network_scanner.py 192.168.1.50 --timeout 10 -o json
"""

import argparse
import asyncio
import csv
import ipaddress
import json
import os
import re
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from urllib.parse import urljoin

# Try to import optional dependencies
try:
    from pymodbus.client import ModbusTcpClient  # noqa: F401  (availability check)
    PYMUSBUS_AVAILABLE = True
except ImportError:
    PYMUSBUS_AVAILABLE = False

# The SunSpec probe lives in the library (franklinwh_modbus.discovery); run
# from a checkout, like franklinwh_cli.py, so prefer the in-repo package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
try:
    from franklinwh_modbus import discovery as _discovery
except ImportError:
    _discovery = None

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False

try:
    from zeroconf import Zeroconf, ServiceBrowser, IPVersion
    # ServiceListener is a protocol class in newer zeroconf versions
    try:
        from zeroconf import ServiceListener
    except ImportError:
        # Define our own base class for compatibility
        class ServiceListener:
            """Base class for service listener."""
            def add_service(self, zc, type_, name):
                pass
            def remove_service(self, zc, type_, name):
                pass
            def update_service(self, zc, type_, name):
                pass
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    # Define dummy classes
    class Zeroconf:
        pass
    class ServiceListener:
        pass
    class IPVersion:
        V4Only = None


class DeviceType(Enum):
    """Supported device types for scanning."""
    MODBUS_SUNSPEC = "modbus_sunspec"
    SSH = "ssh"
    DNS = "dns"
    ENPHASE = "enphase"
    SOLAREDGE = "solaredge"
    HOME_ASSISTANT = "home_assistant"
    MQTT_BROKER = "mqtt_broker"
    HOMEY = "homey"
    SPAN = "span"  # SPAN Smart Panel
    FRANKLINWH_EM = "franklinwh_em"    # FranklinWH Energy Manager (port 9091)
    FRANKLINWH_HA = "franklinwh_ha"   # FranklinWH HA Integrator (port 8099)
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, s: str) -> "DeviceType":
        """Parse device type from string."""
        mapping = {
            "modbus": cls.MODBUS_SUNSPEC,
            "sunspec": cls.MODBUS_SUNSPEC,
            "ssh": cls.SSH,
            "sftp": cls.SSH,
            "dns": cls.DNS,
            "enphase": cls.ENPHASE,
            "solaredge": cls.SOLAREDGE,
            "ha": cls.HOME_ASSISTANT,
            "homeassistant": cls.HOME_ASSISTANT,
            "home_assistant": cls.HOME_ASSISTANT,
            "span": cls.SPAN,
            "spanpanel": cls.SPAN,
            "mqtt": cls.MQTT_BROKER,
            "broker": cls.MQTT_BROKER,
            "homey": cls.HOMEY,
            "franklinwh_em": cls.FRANKLINWH_EM,
            "fem": cls.FRANKLINWH_EM,
            "energy_manager": cls.FRANKLINWH_EM,
            "franklinwh_ha": cls.FRANKLINWH_HA,
            "fha": cls.FRANKLINWH_HA,
            "ha_integrator": cls.FRANKLINWH_HA,
        }
        return mapping.get(s.lower().strip(), cls.UNKNOWN)


@dataclass
class ScanResult:
    """Result of scanning a single device."""
    ip: str
    port: int
    device_type: DeviceType
    is_reachable: bool
    response_time_ms: float
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    version: Optional[str] = None
    sunspec_model: Optional[int] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['device_type'] = self.device_type.value
        return result


class PortChecker:
    """Fast TCP port checker."""
    
    @staticmethod
    def is_port_open(ip: str, port: int, timeout: float = 2.0) -> Tuple[bool, float]:
        """
        Check if a TCP port is open.
        
        Returns:
            Tuple of (is_open, response_time_ms)
        """
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            elapsed = (time.time() - start_time) * 1000
            return result == 0, elapsed
        except Exception:
            return False, 0.0


class ModbusSunspecProber:
    """Probes for SunSpec compliant Modbus devices.

    A thin wrapper over the library's ``franklinwh_modbus.discovery.probe`` so
    the CLI and other projects share one implementation of the SunSpec probe.
    Keeps this tool's behaviour: 3 attempts, for a device that is slow or
    briefly busy.
    """

    # Common SunSpec base addresses to try. 0 first: FranklinWH aGate,
    # SolarEdge and other inverters commonly use base 0; 40000 is the
    # canonical SunSpec default.
    SUNSPEC_BASE_ADDRESSES = list(_discovery.SUNSPEC_BASES) if _discovery else [0, 40000, 50000, 30000]
    MAX_PROBE_ATTEMPTS = 3

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    def probe(self, ip: str, port: int = 502) -> Optional[ScanResult]:
        """
        Probe for SunSpec Modbus device.

        Returns:
            ScanResult if SunSpec device found, None otherwise
        """
        if not PYMUSBUS_AVAILABLE or _discovery is None:
            return None
        res = _discovery.probe(
            ip,
            port=port,
            timeout=min(self.timeout, 3.0),  # fast fail on a wrong base address
            attempts=self.MAX_PROBE_ATTEMPTS,
            bases=self.SUNSPEC_BASE_ADDRESSES,
        )
        if res.status != _discovery.SUNSPEC:
            return None
        return ScanResult(
            ip=ip,
            port=port,
            device_type=DeviceType.MODBUS_SUNSPEC,
            is_reachable=True,
            response_time_ms=res.response_time_ms,
            manufacturer=res.manufacturer,
            model=res.model,
            serial_number=res.serial,
            version=res.version,
            sunspec_model=1,
            extra_data={'sunspec_base_addr': res.base_address},
        )


class HTTPProber:
    """Probes for HTTP-based devices."""

    def __init__(self, timeout: float = 3.0, pool_size: int = 10):
        self.timeout = timeout
        # Per-request HTTP timeout cap — prevents individual requests from
        # hanging the full --timeout duration (e.g. 30s). LAN devices should
        # respond within 5s; this cap applies per GET, not per device.
        self.http_timeout = min(timeout, 5.0)
        self.session = None
        if REQUESTS_AVAILABLE:
            self.session = requests.Session()
            # pool_size must match concurrent thread count to avoid connection
            # pool exhaustion — the root cause of flaky detection in full scans.
            adapter = HTTPAdapter(
                max_retries=0,
                pool_connections=pool_size,
                pool_maxsize=pool_size,
            )
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)

    def probe_enphase(self, ip: str, port: int = 80) -> Optional[ScanResult]:
        """Probe for Enphase Envoy."""
        if not REQUESTS_AVAILABLE:
            return None
            
        start_time = time.time()
        
        # Enphase Envoy specific detection
        # Try /info endpoint first - most reliable
        try:
            url = f"http://{ip}:{port}/info"
            response = self.session.get(url, timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                content = response.text
                
                # Strict check: must contain "envoy" AND specific Enphase fields
                content_lower = content.lower()
                if 'envoy' in content_lower and any(x in content_lower for x in ['serialnumber', 'device_type', 'enphase']):
                    # Try to parse JSON for more info
                    info = self._parse_enphase_info(content)
                    
                    return ScanResult(
                        ip=ip,
                        port=port,
                        device_type=DeviceType.ENPHASE,
                        is_reachable=True,
                        response_time_ms=elapsed,
                        manufacturer="Enphase",
                        model=info.get('model', 'Envoy'),
                        serial_number=info.get('serial_number'),
                        version=info.get('version'),
                        extra_data=info
                    )
                    
        except requests.RequestException:
            pass
        
        # Fallback: Try /api/v1/production with strict validation
        try:
            url = f"http://{ip}:{port}/api/v1/production"
            response = self.session.get(url, timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                content = response.text.lower()
                # Must have Enphase-specific production data structure
                if 'watt_hours' in content and ('inverters' in content or 'production' in content):
                    # Verify it's actually Enphase by checking for specific fields
                    try:
                        data = response.json()
                        if isinstance(data, dict) and any(k in data for k in ['wattHoursToday', 'wattsNow', 'production']):
                            return ScanResult(
                                ip=ip,
                                port=port,
                                device_type=DeviceType.ENPHASE,
                                is_reachable=True,
                                response_time_ms=elapsed,
                                manufacturer="Enphase",
                                model="Envoy",
                                extra_data={'production_data': True}
                            )
                    except ValueError:
                        pass
                        
        except requests.RequestException:
            pass
                
        return None
    
    def _parse_enphase_info(self, content: str) -> Dict[str, Any]:
        """Parse Enphase /info endpoint response."""
        info = {}
        try:
            data = json.loads(content)
            info['raw'] = data
            
            # Extract known Enphase fields
            if isinstance(data, dict):
                info['serial_number'] = data.get('serialNumber') or data.get('serialnumber')
                info['version'] = data.get('software_version') or data.get('softwareVersion')
                info['model'] = data.get('device_type') or data.get('envoy_model') or 'Envoy'
                
        except json.JSONDecodeError:
            # Try regex extraction for non-JSON responses
            serial_match = re.search(r'serialnumber["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', content, re.I)
            if serial_match:
                info['serial_number'] = serial_match.group(1)
                
        return info
    
    def _get_enphase_info(self, ip: str, port: int) -> Dict[str, Any]:
        """Get additional Enphase device info."""
        info = {}
        
        try:
            # Try info endpoint
            response = self.session.get(
                f"http://{ip}:{port}/info",
                timeout=self.http_timeout
            )
            if response.status_code == 200:
                # Try parsing as JSON
                try:
                    data = response.json()
                    info['envoy_info'] = data
                except ValueError:
                    pass
        except Exception:
            pass
            
        return info
    
    def probe_solaredge(self, ip: str, port: int = 80) -> Optional[ScanResult]:
        """Probe for SolarEdge inverter."""
        if not REQUESTS_AVAILABLE:
            return None
            
        start_time = time.time()
        
        # SolarEdge SetApp specific detection
        # Try known SolarEdge endpoints with strict validation
        
        # First check: SolarEdge has a very specific SetApp interface
        try:
            url = f"http://{ip}:{port}/web/v1/maintenance"
            response = self.session.get(url, timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                content = response.text.lower()
                # Strict check: must contain "solaredge" specifically
                if 'solaredge' in content:
                    return ScanResult(
                        ip=ip,
                        port=port,
                        device_type=DeviceType.SOLAREDGE,
                        is_reachable=True,
                        response_time_ms=elapsed,
                        manufacturer="SolarEdge",
                        extra_data={'endpoint': '/web/v1/maintenance'}
                    )
                    
        except requests.RequestException:
            pass
        
        # Second check: Settings page with SolarEdge-specific content
        try:
            url = f"http://{ip}:{port}/settings"
            response = self.session.get(url, timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                content = response.text.lower()
                # Must have SolarEdge branding
                if 'solaredge' in content or 'setapp' in content:
                    return ScanResult(
                        ip=ip,
                        port=port,
                        device_type=DeviceType.SOLAREDGE,
                        is_reachable=True,
                        response_time_ms=elapsed,
                        manufacturer="SolarEdge",
                        extra_data={'endpoint': '/settings'}
                    )
                    
        except requests.RequestException:
            pass
        
        # Third check: Optimizer data endpoint (returns JSON)
        try:
            url = f"http://{ip}:{port}/api/v1/optimizerData"
            response = self.session.get(url, timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                content = response.text.lower()
                # Optimizer data should contain SolarEdge-specific fields
                if 'optimizer' in content and any(x in content for x in ['serialnumber', 'inverter']):
                    return ScanResult(
                        ip=ip,
                        port=port,
                        device_type=DeviceType.SOLAREDGE,
                        is_reachable=True,
                        response_time_ms=elapsed,
                        manufacturer="SolarEdge",
                        extra_data={'endpoint': '/api/v1/optimizerData'}
                    )
                    
        except requests.RequestException:
            pass
                
        return None
    
    def probe_home_assistant(self, ip: str, port: int = 8123) -> Optional[ScanResult]:
        """Probe for Home Assistant."""
        if not REQUESTS_AVAILABLE:
            return None
            
        start_time = time.time()
        
        try:
            # Try API endpoint first
            response = self.session.get(
                f"http://{ip}:{port}/api/",
                timeout=self.http_timeout
            )
            elapsed = (time.time() - start_time) * 1000
            
            # Check for HA API response
            if response.status_code in [200, 401]:  # 401 is also valid (unauthorized)
                try:
                    data = response.json()
                    if 'message' in data:
                        return ScanResult(
                            ip=ip,
                            port=port,
                            device_type=DeviceType.HOME_ASSISTANT,
                            is_reachable=True,
                            response_time_ms=elapsed,
                            manufacturer="Nabu Casa",
                            model="Home Assistant",
                            version=data.get('version'),
                            extra_data={'api_message': data.get('message')}
                        )
                except ValueError:
                    pass
            
            # Try main page
            response = self.session.get(
                f"http://{ip}:{port}",
                timeout=self.http_timeout
            )
            
            if 'home assistant' in response.text.lower():
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.HOME_ASSISTANT,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    manufacturer="Nabu Casa",
                    model="Home Assistant"
                )
                
        except requests.RequestException:
            pass
            
        return None
    
    def probe_homey(self, ip: str, port: int = 80) -> Optional[ScanResult]:
        """Probe for Homey Smart Hub."""
        if not REQUESTS_AVAILABLE:
            return None
            
        start_time = time.time()
        
        try:
            response = self.session.get(
                f"http://{ip}:{port}/api/",
                timeout=self.http_timeout
            )
            elapsed = (time.time() - start_time) * 1000
            
            # Check for Homey-specific content
            content = response.text.lower()
            headers = dict(response.headers)
            
            # Homey typically returns JSON with specific structure
            # or has Athom-specific headers
            is_homey = False
            
            # Check headers for Athom/Homey
            server_header = headers.get('Server', '').lower()
            powered_by = headers.get('X-Powered-By', '').lower()
            
            if 'athom' in server_header or 'athom' in powered_by:
                is_homey = True
            
            # Check content for Homey API structure
            if 'homey' in content and any(x in content for x in ['api', 'version', 'athom']):
                is_homey = True
            
            # Try to parse JSON response - Homey API returns specific structure
            if not is_homey and response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and any(k in data for k in ['homey', 'version', 'apiVersion']):
                        is_homey = True
                        extra = {'api_response': data}
                    else:
                        extra = {}
                except ValueError:
                    extra = {}
            else:
                extra = {}
            
            if is_homey:
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.HOMEY,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    manufacturer="Athom",
                    model="Homey",
                    extra_data=extra
                )
                
        except requests.RequestException:
            pass
            
        return None
    
    def probe_mqtt_http(self, ip: str, port: int = 8080) -> Optional[ScanResult]:
        """
        Probe for MQTT broker with HTTP web interface.
        Many MQTT brokers (Mosquitto, HiveMQ, etc.) have web UIs.
        """
        if not REQUESTS_AVAILABLE:
            return None
            
        start_time = time.time()
        
        # Common MQTT web interface ports and endpoints
        checks = [
            (port, '/'),  # Custom port
            (8080, '/'),  # Mosquitto WebSocket
            (9001, '/'),  # Mosquitto WebSocket alternative
            (1884, '/'),  # MQTT over WebSocket
        ]
        
        for check_port, endpoint in checks:
            try:
                url = f"http://{ip}:{check_port}{endpoint}"
                response = self.session.get(url, timeout=self.http_timeout)
                elapsed = (time.time() - start_time) * 1000
                
                if response.status_code in [200, 401]:
                    content = response.text.lower()
                    headers = str(response.headers).lower()
                    
                    # Check for MQTT broker signatures
                    is_mqtt = False
                    broker_type = None
                    
                    # Mosquitto
                    if 'mosquitto' in content or 'mosquitto' in headers:
                        is_mqtt = True
                        broker_type = "Mosquitto"
                    # HiveMQ
                    elif 'hivemq' in content or 'hivemq' in headers:
                        is_mqtt = True
                        broker_type = "HiveMQ"
                    # EMQX
                    elif 'emqx' in content or 'emqx' in headers:
                        is_mqtt = True
                        broker_type = "EMQX"
                    # VerneMQ
                    elif 'vernemq' in content or 'vernemq' in headers:
                        is_mqtt = True
                        broker_type = "VerneMQ"
                    # RabbitMQ MQTT plugin
                    elif 'rabbitmq' in content and 'mqtt' in content:
                        is_mqtt = True
                        broker_type = "RabbitMQ (MQTT)"
                    # Generic MQTT WebSocket
                    elif 'mqtt' in content and any(x in content for x in ['websocket', 'ws', 'broker']):
                        is_mqtt = True
                        broker_type = "MQTT Broker"
                    # Home Assistant MQTT (web interface)
                    elif check_port == 8123 and 'home assistant' in content:
                        # This is Home Assistant, not a standalone MQTT broker
                        continue
                    
                    if is_mqtt:
                        return ScanResult(
                            ip=ip,
                            port=1883,  # Standard MQTT port even if web UI is on different port
                            device_type=DeviceType.MQTT_BROKER,
                            is_reachable=True,
                            response_time_ms=elapsed,
                            manufacturer=broker_type,
                            model="MQTT Broker (HTTP/WebSocket)",
                            extra_data={
                                'http_port': check_port,
                                'web_interface': True,
                                'endpoint': endpoint
                            }
                        )
                        
            except requests.RequestException:
                continue
                
        return None
    
    def probe_span(self, ip: str, port: int = 80) -> Optional[ScanResult]:
        """
        Probe for SPAN Smart Panel (MAIN 32, MAIN 40, MLO 48).

        Detection hierarchy (most → least reliable):
          1. /api/v1/status — strict JSON schema: requires panel.serial + circuits + feeders
          2. /api/v1/circuits — strict JSON: requires list of circuit dicts
          3. gRPC Content-Type header (Gen 3)

        Port 8883 (MQTTS/Homie) is in the default port list and will be tried
        before port 80 by the scanner orchestrator.

        NOTE: Generic content-matching (HTML 'span' tag, loose keyword checks) has been
        deliberately removed — it caused false positives on any device with port 80 open.
        See DEF-SCANNER-SPAN in docs/backlog.md.
        """
        if not REQUESTS_AVAILABLE:
            return None

        start_time = time.time()

        # Tier 1: SPAN-specific REST API endpoints with strict JSON schema
        api_endpoints = [
            '/api/v1/status',
            '/api/v1/circuits',
        ]

        for endpoint in api_endpoints:
            try:
                url = f"http://{ip}:{port}{endpoint}"
                response = self.session.get(url, timeout=self.http_timeout)
                elapsed = (time.time() - start_time) * 1000

                if response.status_code != 200:
                    continue

                # Tier 1a: gRPC header check (Gen 3 panels)
                content_type = response.headers.get('Content-Type', '')
                if 'application/grpc' in content_type:
                    return ScanResult(
                        ip=ip,
                        port=port,
                        device_type=DeviceType.SPAN,
                        is_reachable=True,
                        response_time_ms=elapsed,
                        manufacturer="SPAN",
                        model="SPAN Smart Panel",
                        extra_data={'generation': 'Gen 3 (gRPC)', 'endpoint': endpoint}
                    )

                # Tier 1b: Strict JSON schema validation
                try:
                    data = response.json()
                except (ValueError, TypeError):
                    continue

                if not isinstance(data, dict):
                    continue

                # /api/v1/status must have panel.serial AND circuits AND feeders
                if endpoint == '/api/v1/status':
                    panel = data.get('panel', {})
                    if (
                        isinstance(panel, dict)
                        and panel.get('serial')
                        and 'circuits' in data
                        and 'feeders' in data
                    ):
                        return ScanResult(
                            ip=ip,
                            port=port,
                            device_type=DeviceType.SPAN,
                            is_reachable=True,
                            response_time_ms=elapsed,
                            manufacturer="SPAN",
                            model=panel.get('model', 'SPAN Smart Panel'),
                            serial_number=panel.get('serial'),
                            version=panel.get('firmwareVersion'),
                            extra_data={
                                'generation': 'Gen 2 (REST)',
                                'endpoint': endpoint,
                                'protocol': 'REST',
                            }
                        )

                # /api/v1/circuits must be a non-empty list of circuit dicts
                if endpoint == '/api/v1/circuits':
                    circuits = data.get('circuits', data) if isinstance(data, dict) else data
                    if (
                        isinstance(circuits, (list, dict))
                        and circuits
                        and any(
                            isinstance(v, dict) and ('id' in v or 'name' in v or 'circuitId' in v)
                            for v in (circuits.values() if isinstance(circuits, dict) else circuits)
                        )
                    ):
                        return ScanResult(
                            ip=ip,
                            port=port,
                            device_type=DeviceType.SPAN,
                            is_reachable=True,
                            response_time_ms=elapsed,
                            manufacturer="SPAN",
                            model="SPAN Smart Panel",
                            extra_data={
                                'generation': 'Gen 2 (REST)',
                                'endpoint': endpoint,
                                'protocol': 'REST',
                                'circuit_count': len(circuits),
                            }
                        )

            except requests.RequestException:
                continue

        return None

    def probe_franklinwh_em(self, ip: str, port: int = 9091) -> Optional[ScanResult]:
        """
        Probe for FranklinWH Energy Manager (franklinwh-cloud / FEM).

        Detection: GET /api/status returns JSON with FEM-specific keys:
          agate, controlSource, currentDispatch, currentWave, capabilities
        """
        if not REQUESTS_AVAILABLE:
            return None

        start_time = time.time()
        try:
            response = self.session.get(f"http://{ip}:{port}/api/status", timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000

            if response.status_code != 200:
                return None

            try:
                data = response.json()
            except (ValueError, TypeError):
                return None

            if not isinstance(data, dict):
                return None

            # FEM-specific keys — very unlikely in any other JSON API
            fem_keys = {'agate', 'controlSource', 'currentDispatch', 'currentWave', 'capabilities'}
            if len(fem_keys & set(data.keys())) >= 2:
                version = (
                    (data.get('agate') or {}).get('firmware')
                    or (data.get('capabilities') or {}).get('version')
                )
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.FRANKLINWH_EM,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    manufacturer="FranklinWH",
                    model="Energy Manager",
                    version=version,
                    extra_data={'matched_keys': list(fem_keys & set(data.keys()))}
                )

        except requests.RequestException:
            pass

        return None

    def probe_franklinwh_ha(self, ip: str, port: int = 8099) -> Optional[ScanResult]:
        """
        Probe for FranklinWH HA Integrator (franklinwh-ha-integrator / FHAI).

        Detection hierarchy:
          1. GET /api/health — custom health endpoint (JSON with 'status' key)
          2. GET /docs      — FastAPI Swagger UI containing 'FranklinWH'
        """
        if not REQUESTS_AVAILABLE:
            return None

        start_time = time.time()

        # Tier 1: custom health endpoint
        try:
            response = self.session.get(f"http://{ip}:{port}/api/health", timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000

            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and 'status' in data:
                        return ScanResult(
                            ip=ip,
                            port=port,
                            device_type=DeviceType.FRANKLINWH_HA,
                            is_reachable=True,
                            response_time_ms=elapsed,
                            manufacturer="FranklinWH",
                            model="HA Integrator",
                            version=data.get('version'),
                            extra_data={'endpoint': '/api/health'}
                        )
                except (ValueError, TypeError):
                    pass
        except requests.RequestException:
            pass

        # Tier 2: FastAPI Swagger docs containing FranklinWH branding
        try:
            response = self.session.get(f"http://{ip}:{port}/docs", timeout=self.http_timeout)
            elapsed = (time.time() - start_time) * 1000

            if response.status_code == 200 and 'franklinwh' in response.text.lower():
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.FRANKLINWH_HA,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    manufacturer="FranklinWH",
                    model="HA Integrator",
                    extra_data={'endpoint': '/docs'}
                )
        except requests.RequestException:
            pass

        return None


class MQTTProber:
    """Probes for MQTT brokers."""
    
    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
    
    def probe(self, ip: str, port: int = 1883) -> Optional[ScanResult]:
        """
        Probe for MQTT broker.
        
        Sends MQTT CONNECT packet and checks for CONNACK.
        """
        start_time = time.time()
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            sock.connect((ip, port))
            
            # Build MQTT CONNECT packet
            # Fixed header
            packet_type = 0x10  # CONNECT
            
            # Variable header (Protocol Name, Level, Connect Flags, Keep Alive)
            protocol_name = b'\x00\x04MQTT'  # Protocol name "MQTT" with length
            protocol_level = b'\x04'  # MQTT v3.1.1
            connect_flags = b'\x00'  # Clean session, no auth
            keep_alive = b'\x00\x3c'  # 60 seconds
            
            variable_header = protocol_name + protocol_level + connect_flags + keep_alive
            
            # Payload (Client ID)
            client_id = b'scanner_' + str(int(time.time())).encode()
            client_id_length = struct.pack('!H', len(client_id))
            payload = client_id_length + client_id
            
            # Remaining length
            remaining_length = len(variable_header) + len(payload)
            
            # Build packet
            packet = bytes([packet_type, remaining_length]) + variable_header + payload
            
            # Send CONNECT
            sock.send(packet)
            
            # Receive CONNACK
            response = sock.recv(4)
            elapsed = (time.time() - start_time) * 1000
            sock.close()
            
            # Check if response is valid CONNACK
            if len(response) >= 2 and response[0] == 0x20:
                # 0x20 = CONNACK, second byte is remaining length
                return_code = response[3] if len(response) > 3 else 0
                
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.MQTT_BROKER,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    model="MQTT Broker",
                    extra_data={
                        'return_code': return_code,
                        'return_code_meaning': self._get_mqtt_return_code_meaning(return_code)
                    }
                )
                
        except socket.timeout:
            pass
        except Exception:
            pass
            
        return None
    
    @staticmethod
    def _get_mqtt_return_code_meaning(code: int) -> str:
        """Get meaning of MQTT CONNACK return code."""
        meanings = {
            0: "Connection Accepted",
            1: "Unacceptable Protocol Version",
            2: "Identifier Rejected",
            3: "Server Unavailable",
            4: "Bad Username or Password",
            5: "Not Authorized"
        }
        return meanings.get(code, f"Unknown ({code})")


class MDNSDiscovery:
    """
    Cross-platform mDNS/Bonjour service discovery using zeroconf.
    Works on Linux, macOS, and Windows.
    """
    
    # Common IoT service types to discover
    SERVICE_TYPES = {
        DeviceType.HOME_ASSISTANT: "_home-assistant._tcp.local.",
        DeviceType.ENPHASE: "_enphase-envoy._tcp.local.",
        DeviceType.HOMEY: "_homey._tcp.local.",
        DeviceType.MQTT_BROKER: "_mqtt._tcp.local.",
        DeviceType.MODBUS_SUNSPEC: "_modbus._tcp.local.",
        DeviceType.SPAN: "_span._tcp.local.",
        # Additional common services
        "sonos": "_sonos._tcp.local.",
        "nut": "_nut._tcp.local.",
        "http": "_http._tcp.local.",
        "https": "_https._tcp.local.",
        "esphome": "_esphomelib._tcp.local.",
        "matter": "_matter._tcp.local.",
        "spotify": "_spotify-connect._tcp.local.",
        "airplay": "_airplay._tcp.local.",
    }
    
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.discovered: List[ScanResult] = []
        
    def discover(self, device_types: Optional[List[DeviceType]] = None) -> List[ScanResult]:
        """
        Discover devices via mDNS.
        
        Args:
            device_types: List of device types to discover (None = all)
            
        Returns:
            List of ScanResult objects for discovered devices
        """
        if not ZEROCONF_AVAILABLE:
            print("Warning: zeroconf not installed. Install with: pip install zeroconf", file=sys.stderr)
            return []
            
        self.discovered = []
        
        # Determine which services to browse
        services_to_browse = []
        if device_types:
            for dt in device_types:
                if dt in self.SERVICE_TYPES:
                    services_to_browse.append((dt, self.SERVICE_TYPES[dt]))
        else:
            # Browse all known device type services
            for dt, service in self.SERVICE_TYPES.items():
                if isinstance(dt, DeviceType):
                    services_to_browse.append((dt, service))
        
        if not services_to_browse:
            return []
            
        # Create zeroconf instance
        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        
        try:
            # Create listeners for each service type
            listeners = []
            browsers = []
            
            for device_type, service_type in services_to_browse:
                listener = MDNSListener(device_type, service_type, self.discovered)
                listeners.append(listener)
                browser = ServiceBrowser(zeroconf, service_type, listener)
                browsers.append(browser)
            
            # Wait for discovery
            time.sleep(self.timeout)
            
        finally:
            zeroconf.close()
            
        return self.discovered
    
    def discover_all_services(self) -> List[ScanResult]:
        """
        Discover all mDNS services on the network (comprehensive scan).
        
        Returns:
            List of ScanResult objects
        """
        if not ZEROCONF_AVAILABLE:
            print("Warning: zeroconf not installed. Install with: pip install zeroconf", file=sys.stderr)
            return []
            
        self.discovered = []
        
        # Extended list of IoT-related services
        all_services = [
            (DeviceType.HOME_ASSISTANT, "_home-assistant._tcp.local."),
            (DeviceType.ENPHASE, "_enphase-envoy._tcp.local."),
            (DeviceType.HOMEY, "_homey._tcp.local."),
            (DeviceType.MQTT_BROKER, "_mqtt._tcp.local."),
            (None, "_http._tcp.local."),
            (None, "_https._tcp.local."),
            (None, "_sonos._tcp.local."),
            (None, "_nut._tcp.local."),
            (None, "_esphomelib._tcp.local."),
            (None, "_matter._tcp.local."),
            (None, "_matterc._udp.local."),
            (None, "_matterd._udp.local."),
            (None, "_spotify-connect._tcp.local."),
            (None, "_airplay._tcp.local."),
            (None, "_raop._tcp.local."),
            (None, "_hap._tcp.local."),
            (None, "_meshcop._udp.local."),
            (None, "_googlecast._tcp.local."),
            (None, "_dkapi._tcp.local."),
            (None, "_axis-video._tcp.local."),
            (None, "_printer._tcp.local."),
            (None, "_ipp._tcp.local."),
            (None, "_ssh._tcp.local."),
        ]
        
        zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        
        try:
            listeners = []
            browsers = []
            
            for device_type, service_type in all_services:
                listener = MDNSListener(device_type, service_type, self.discovered)
                listeners.append(listener)
                browser = ServiceBrowser(zeroconf, service_type, listener)
                browsers.append(browser)
            
            # Wait longer for comprehensive scan
            time.sleep(self.timeout)
            
        finally:
            zeroconf.close()
            
        return self.discovered


class MDNSListener(ServiceListener):
    """Listener for mDNS service discovery events."""
    
    def __init__(self, device_type: Optional[DeviceType], service_type: str, results_list: List[ScanResult]):
        self.device_type = device_type
        self.service_type = service_type
        self.results = results_list
        self.start_time = time.time()
        
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is discovered."""
        info = zc.get_service_info(type_, name)
        if info:
            self._process_service_info(info, name)
            
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is removed."""
        pass
        
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Called when a service is updated."""
        info = zc.get_service_info(type_, name)
        if info:
            self._process_service_info(info, name)
    
    def _process_service_info(self, info, name: str) -> None:
        """Process discovered service info and create ScanResult."""
        # Get IP addresses
        addresses = info.parsed_addresses(IPVersion.V4Only)
        if not addresses:
            return
            
        ip = addresses[0]
        port = info.port or 80
        
        # Determine device type from service type if not provided
        device_type = self.device_type
        if not device_type:
            device_type = self._infer_device_type(self.service_type, name)
            
        # Extract properties
        props = {}
        if info.properties:
            for key, value in info.properties.items():
                try:
                    props[key.decode('utf-8', errors='ignore')] = value.decode('utf-8', errors='ignore')
                except:
                    props[str(key)] = str(value)
        
        # Build ScanResult
        elapsed = (time.time() - self.start_time) * 1000
        
        result = ScanResult(
            ip=ip,
            port=port,
            device_type=device_type or DeviceType.UNKNOWN,
            is_reachable=True,
            response_time_ms=elapsed,
            manufacturer=props.get('manufacturer') or self._get_manufacturer(device_type),
            model=props.get('model') or self._extract_model(name),
            serial_number=props.get('serial') or props.get('serialNumber'),
            version=props.get('version') or props.get('fw'),
            extra_data={
                'mdns_name': name,
                'mdns_service': self.service_type,
                'mdns_properties': props,
                'hostname': info.server,
                'discovery_method': 'mDNS'
            }
        )
        
        self.results.append(result)
    
    def _infer_device_type(self, service_type: str, name: str) -> Optional[DeviceType]:
        """Infer device type from service type or name."""
        service_lower = service_type.lower()
        name_lower = name.lower()
        
        if 'home-assistant' in service_lower or 'homeassistant' in name_lower:
            return DeviceType.HOME_ASSISTANT
        elif 'enphase' in service_lower or 'envoy' in name_lower:
            return DeviceType.ENPHASE
        elif 'homey' in service_lower or 'athom' in name_lower:
            return DeviceType.HOMEY
        elif 'mqtt' in service_lower:
            return DeviceType.MQTT_BROKER
        elif 'modbus' in service_lower:
            return DeviceType.MODBUS_SUNSPEC
        elif 'span' in service_lower or 'span' in name_lower:
            return DeviceType.SPAN
            
        return DeviceType.UNKNOWN
    
    def _get_manufacturer(self, device_type: Optional[DeviceType]) -> Optional[str]:
        """Get default manufacturer for device type."""
        mapping = {
            DeviceType.HOME_ASSISTANT: "Nabu Casa",
            DeviceType.ENPHASE: "Enphase",
            DeviceType.HOMEY: "Athom",
            DeviceType.SPAN: "SPAN",
        }
        return mapping.get(device_type)
    
    def _extract_model(self, name: str) -> Optional[str]:
        """Extract model from mDNS service name."""
        # Remove instance numbers and suffixes
        if '@' in name:
            return name.split('@')[1].split('.')[0].strip()
        return name.split('.')[0].strip()


class IPRangeGenerator:
    """Generates IP addresses from various range specifications."""
    
    @staticmethod
    def parse(target: str) -> List[str]:
        """
        Parse IP range specification and return list of IPs.
        
        Supports:
        - Single IP: 192.168.1.1
        - CIDR: 192.168.1.0/24
        - Range: 192.168.1.1-192.168.1.100
        - Wildcard: 192.168.1.*
        """
        ips = []
        
        # CIDR notation
        if '/' in target:
            try:
                network = ipaddress.ip_network(target, strict=False)
                ips = [str(ip) for ip in network.hosts()]
            except ValueError as e:
                raise ValueError(f"Invalid CIDR notation: {e}")
                
        # Range notation
        elif '-' in target:
            try:
                start_ip, end_ip = target.split('-')
                start = ipaddress.ip_address(start_ip.strip())
                end = ipaddress.ip_address(end_ip.strip())
                
                current = int(start)
                end_int = int(end)
                
                while current <= end_int:
                    ips.append(str(ipaddress.ip_address(current)))
                    current += 1
                    
            except ValueError as e:
                raise ValueError(f"Invalid IP range: {e}")
                
        # Wildcard notation
        elif '*' in target:
            base = target.replace('*', '')
            for i in range(1, 255):
                ips.append(f"{base}{i}")
                
        # Single IP
        else:
            try:
                ipaddress.ip_address(target)
                ips = [target]
            except ValueError as e:
                raise ValueError(f"Invalid IP address: {e}")
                
        return ips


class NetworkScanner:
    """Main network scanner orchestrator."""
    
    # Default ports to scan for each device type
    DEFAULT_PORTS = {
        DeviceType.MODBUS_SUNSPEC: [502, 5020, 1502],
        DeviceType.SSH: [22, 2222],
        DeviceType.DNS: [53],
        DeviceType.ENPHASE: [80, 443],
        DeviceType.SOLAREDGE: [80, 502],
        DeviceType.HOME_ASSISTANT: [8123],
        DeviceType.MQTT_BROKER: [1883, 8883, 1884, 8080, 9001],  # Including WebSocket ports
        DeviceType.HOMEY: [80, 443],
        DeviceType.SPAN: [80, 443, 50058],  # SPAN Panel REST (mDNS/8883 is separate discovery path)
        # FRANKLINWH_EM and FRANKLINWH_HA are NOT in the default scan — their ports
        # are deployment-specific (9091, 8099 are defaults but can change).
        # Use --devices fem,fha or --probe to target them explicitly.
    }
    
    def __init__(
        self,
        device_types: Optional[List[DeviceType]] = None,
        ports: Optional[List[int]] = None,
        timeout: float = 3.0,
        max_workers: int = 50,
        verbose: bool = False
    ):
        self.device_types = device_types or [
            dt for dt in DeviceType
            if dt not in (DeviceType.UNKNOWN, DeviceType.FRANKLINWH_EM, DeviceType.FRANKLINWH_HA)
        ]
        self.timeout = timeout
        self.max_workers = max_workers
        self.verbose = verbose
        self.custom_ports = ports
        self.custom_probes: List[Dict] = []  # populated from --probe args

        # Initialize probers — pool_size matches thread count to prevent pool exhaustion
        self.modbus_prober = ModbusSunspecProber(timeout) if PYMUSBUS_AVAILABLE else None
        self.http_prober = HTTPProber(timeout, pool_size=max_workers) if REQUESTS_AVAILABLE else None
        self.mqtt_prober = MQTTProber(timeout)
        
    def discover_mdns(self, timeout: Optional[float] = None, comprehensive: bool = False) -> List[ScanResult]:
        """
        Discover devices using mDNS/Bonjour (cross-platform).
        
        This works on Linux, macOS, and Windows (requires zeroconf).
        
        Args:
            timeout: Discovery timeout in seconds (default: self.timeout + 2)
            comprehensive: If True, scan for all known IoT services
            
        Returns:
            List of ScanResult objects for discovered devices
        """
        if not ZEROCONF_AVAILABLE:
            print("Warning: zeroconf not installed. Install with: pip install zeroconf", file=sys.stderr)
            return []
            
        mdns_timeout = timeout or (self.timeout + 2)
        
        if self.verbose:
            print(f"Starting mDNS discovery (timeout: {mdns_timeout}s)...")
            
        mdns = MDNSDiscovery(timeout=mdns_timeout)
        
        if comprehensive:
            results = mdns.discover_all_services()
        else:
            # Filter to requested device types
            device_types = [dt for dt in self.device_types if dt != DeviceType.UNKNOWN]
            results = mdns.discover(device_types)
            
        if self.verbose:
            print(f"mDNS discovery found {len(results)} device(s)")
            
        return results
        
    def scan(self, targets: List[str]) -> List[ScanResult]:
        """
        Scan network targets for devices.
        
        Args:
            targets: List of IP addresses or range specifications
            
        Returns:
            List of ScanResult objects for found devices
        """
        results = []
        
        # Expand all targets to individual IPs
        all_ips = []
        for target in targets:
            try:
                ips = IPRangeGenerator.parse(target)
                all_ips.extend(ips)
            except ValueError as e:
                print(f"Warning: {e}", file=sys.stderr)
                
        if not all_ips:
            print("No valid IP addresses to scan", file=sys.stderr)
            return results
            
        # Remove duplicates while preserving order
        all_ips = list(dict.fromkeys(all_ips))
        
        if self.verbose:
            print(f"Scanning {len(all_ips)} IP addresses...")
            print(f"Device types: {[d.value for d in self.device_types]}")
            print(f"Timeout: {self.timeout}s, Workers: {self.max_workers}")
            
        # Perform scan with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scan tasks
            future_to_ip = {}
            
            for ip in all_ips:
                future = executor.submit(self._scan_ip, ip)
                future_to_ip[future] = ip
                
            # Collect results
            completed = 0
            for future in as_completed(future_to_ip):
                completed += 1
                ip = future_to_ip[future]
                
                try:
                    ip_results = future.result()
                    results.extend(ip_results)
                    
                    if self.verbose and ip_results:
                        for r in ip_results:
                            print(f"  Found: {r.device_type.value} at {r.ip}:{r.port}")
                            
                except Exception as e:
                    if self.verbose:
                        print(f"  Error scanning {ip}: {e}")
                        
                if self.verbose and completed % 10 == 0:
                    print(f"  Progress: {completed}/{len(all_ips)} IPs scanned")
                    
        return results
    
    def _scan_ip(self, ip: str) -> List[ScanResult]:
        """Scan a single IP for all configured device types."""
        results = []
        seen_ip_port = set()

        # Create a per-thread HTTPProber so each of the 50 scan threads has its
        # own requests.Session. Sharing one session across threads causes silent
        # probe failures (connection reuse race, response body corruption).
        http = HTTPProber(self.timeout, pool_size=1) if REQUESTS_AVAILABLE else None

        for device_type in self.device_types:
            if device_type == DeviceType.UNKNOWN:
                continue

            ports = self.custom_ports or self.DEFAULT_PORTS.get(device_type, [])

            for port in ports:
                if (ip, port) in seen_ip_port:
                    continue

                is_open, _ = PortChecker.is_port_open(ip, port, timeout=min(self.timeout, 2.0))
                if not is_open:
                    continue

                result = self._probe_device(ip, port, device_type, http_prober=http)
                if result:
                    results.append(result)
                    seen_ip_port.add((ip, port))
                    break

        # Run any custom --probe specs against this IP
        for spec in self.custom_probes:
            for port in spec['ports']:  # ports is always a list (range/comma/single)
                if (ip, port) in seen_ip_port:
                    continue

                is_open, _ = PortChecker.is_port_open(ip, port, timeout=min(self.timeout, 2.0))
                if not is_open:
                    continue

                result = self._probe_custom(ip, port, spec, http_prober=http)
                if result:
                    results.append(result)
                    seen_ip_port.add((ip, port))
                    break  # stop at first matching port in this probe spec

        return results
    
    def _probe_device(self, ip: str, port: int, device_type: DeviceType,
                      http_prober: Optional['HTTPProber'] = None) -> Optional[ScanResult]:
        """Probe specific device type at IP:port."""
        # Use caller-supplied prober (per-thread) when available, otherwise fall
        # back to the shared singleton (used for direct API calls).
        http = http_prober if http_prober is not None else self.http_prober

        if device_type == DeviceType.MODBUS_SUNSPEC:
            if self.modbus_prober:
                return self.modbus_prober.probe(ip, port)

        elif device_type == DeviceType.ENPHASE:
            if http:
                return http.probe_enphase(ip, port)

        elif device_type == DeviceType.SOLAREDGE:
            if http and port == 80:
                return http.probe_solaredge(ip, port)
            elif self.modbus_prober and port == 502:
                return self.modbus_prober.probe(ip, port)

        elif device_type == DeviceType.HOME_ASSISTANT:
            if http:
                return http.probe_home_assistant(ip, port)

        elif device_type == DeviceType.MQTT_BROKER:
            result = self.mqtt_prober.probe(ip, port)
            if result:
                return result
            if http and port in [8080, 9001, 1884]:
                return http.probe_mqtt_http(ip, port)
            return None

        elif device_type == DeviceType.HOMEY:
            if http:
                return http.probe_homey(ip, port)

        elif device_type == DeviceType.SPAN:
            if http and port in [80, 443]:
                return http.probe_span(ip, port)

        elif device_type == DeviceType.FRANKLINWH_EM:
            if http:
                return http.probe_franklinwh_em(ip, port)

        elif device_type == DeviceType.FRANKLINWH_HA:
            if http:
                return http.probe_franklinwh_ha(ip, port)

        elif device_type == DeviceType.SSH:
            return self._probe_ssh(ip, port)

        elif device_type == DeviceType.DNS:
            return self._probe_dns(ip, port)

        return None

    def _probe_custom(self, ip: str, port: int, spec: Dict,
                      http_prober: Optional['HTTPProber'] = None) -> Optional[ScanResult]:
        """
        Execute a user-defined --probe spec against an IP:port.

        spec keys:
          ports   (list) — TCP ports (caller passes the specific port to try)
          path    (str)  — HTTP GET path, or 'tcp' for raw port-open check
          keys    (list) — JSON keys that must be present (any match is enough)
          label   (str)  — display label
        """
        path = spec.get('path', 'tcp')
        keys = spec.get('keys', [])
        label = spec.get('label', f'custom:{port}')
        start_time = time.time()

        http = http_prober if http_prober is not None else self.http_prober

        if path == 'tcp':
            # TCP-only: port open is sufficient — already confirmed by caller
            elapsed = (time.time() - start_time) * 1000
            return ScanResult(
                ip=ip, port=port,
                device_type=DeviceType.UNKNOWN,
                is_reachable=True,
                response_time_ms=elapsed,
                model=label,
                extra_data={'probe': 'tcp'},
            )

        if not self.http_prober:
            return None

        try:
            url = f'http://{ip}:{port}{path}'
            response = self.http_prober.session.get(url, timeout=self.timeout)
            elapsed = (time.time() - start_time) * 1000

            if response.status_code not in (200, 401, 403):
                return None

            # If no key check required, any 2xx/auth response is a hit
            if not keys:
                return ScanResult(
                    ip=ip, port=port,
                    device_type=DeviceType.UNKNOWN,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    model=label,
                    extra_data={'probe': 'http', 'path': path, 'status': response.status_code},
                )

            # Key check: response must be JSON and contain at least one expected key
            try:
                data = response.json()
                if isinstance(data, dict) and any(k in data for k in keys):
                    matched = [k for k in keys if k in data]
                    return ScanResult(
                        ip=ip, port=port,
                        device_type=DeviceType.UNKNOWN,
                        is_reachable=True,
                        response_time_ms=elapsed,
                        model=label,
                        extra_data={'probe': 'http', 'path': path, 'matched_keys': matched},
                    )
            except (ValueError, TypeError):
                # Key check required but response is not JSON — no match
                pass

        except Exception:
            pass

        return None
    
    def _probe_ssh(self, ip: str, port: int) -> Optional[ScanResult]:
        """Probe for SSH server by reading the banner."""
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((ip, port))
            banner = sock.recv(256).decode('utf-8', errors='replace').strip()
            sock.close()
            elapsed = (time.time() - start_time) * 1000
            
            if banner.startswith('SSH-'):
                # Parse SSH banner: SSH-2.0-dropbear_2015.71
                parts = banner.split('-', 2)
                version_str = parts[2] if len(parts) > 2 else banner
                # Extract software name
                software = version_str.split(' ')[0] if version_str else 'Unknown'
                
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.SSH,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    version=software,
                    extra_data={'banner': banner}
                )
        except Exception:
            pass
        return None
    
    def _probe_dns(self, ip: str, port: int) -> Optional[ScanResult]:
        """Probe for DNS resolver by sending a simple query (TCP then UDP)."""
        start_time = time.time()
        
        # Build a minimal DNS query for 'localhost' A record
        query = (
            b'\x12\x34'     # Transaction ID
            b'\x01\x00'     # Flags: standard query, recursion desired
            b'\x00\x01'     # Questions: 1
            b'\x00\x00'     # Answers: 0
            b'\x00\x00'     # Authority: 0
            b'\x00\x00'     # Additional: 0
            b'\x09localhost\x00'  # QNAME: localhost
            b'\x00\x01'     # QTYPE: A
            b'\x00\x01'     # QCLASS: IN
        )
        
        # Try TCP first (DNS over TCP uses 2-byte length prefix)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((ip, port))
            # TCP DNS: 2-byte big-endian length + query
            tcp_msg = len(query).to_bytes(2, 'big') + query
            sock.send(tcp_msg)
            # Read 2-byte length then response
            try:
                length_data = sock.recv(2)
                if length_data and len(length_data) == 2:
                    resp_len = int.from_bytes(length_data, 'big')
                    data = sock.recv(resp_len)
                    sock.close()
                    elapsed = (time.time() - start_time) * 1000
                    
                    if data and len(data) > 2 and data[:2] == b'\x12\x34':
                        return ScanResult(
                            ip=ip,
                            port=port,
                            device_type=DeviceType.DNS,
                            is_reachable=True,
                            response_time_ms=elapsed,
                            model='DNS Resolver',
                            extra_data={'protocol': 'TCP', 'response_size': len(data)}
                        )
            except (socket.timeout, ConnectionResetError):
                pass
            
            # TCP port 53 connected — DNS service is present even if no query response
            # (common for embedded DNS proxies like dnsmasq)
            sock.close()
            elapsed = (time.time() - start_time) * 1000
            return ScanResult(
                ip=ip,
                port=port,
                device_type=DeviceType.DNS,
                is_reachable=True,
                response_time_ms=elapsed,
                model='DNS Service',
                extra_data={'protocol': 'TCP', 'note': 'port open, no query response'}
            )
        except Exception:
            pass
        
        # Fall back to UDP
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            sock.sendto(query, (ip, port))
            data, _ = sock.recvfrom(512)
            sock.close()
            elapsed = (time.time() - start_time) * 1000
            
            if data and len(data) > 2 and data[:2] == b'\x12\x34':
                return ScanResult(
                    ip=ip,
                    port=port,
                    device_type=DeviceType.DNS,
                    is_reachable=True,
                    response_time_ms=elapsed,
                    model='DNS Resolver',
                    extra_data={'protocol': 'UDP', 'response_size': len(data)}
                )
        except Exception:
            pass
        return None


def format_results_table(results: List[ScanResult]) -> str:
    """Format results as a human-readable table."""
    if not results:
        return "No devices found."
    
    def get_protocol(r: ScanResult) -> str:
        """Get discovery protocol from extra_data."""
        method = r.extra_data.get('discovery_method', 'TCP')
        if method == 'mDNS':
            return 'mDNS'
        elif r.device_type == DeviceType.MODBUS_SUNSPEC:
            return 'Modbus'
        elif r.device_type == DeviceType.MQTT_BROKER:
            return 'MQTT'
        elif r.port in [80, 443, 8123]:
            return 'HTTP'
        return 'TCP'
        
    if TABULATE_AVAILABLE:
        headers = ["IP Address", "Port", "Protocol", "Device Type", "Manufacturer", "Model", "Serial", "Version"]
        rows = []
        
        for r in sorted(results, key=lambda x: (x.ip, x.port)):
            # Truncate long strings for display
            mfr = (r.manufacturer or "-")[:20]
            model = (r.model or "-")[:16]
            serial = (r.serial_number or "-")[:16]
            version = (r.version or "-")[:12]
            
            rows.append([
                r.ip,
                r.port,
                get_protocol(r),
                r.device_type.value,
                mfr,
                model,
                serial,
                version
            ])
            
        return tabulate(rows, headers=headers, tablefmt="grid")
    else:
        # Fallback to simple formatting
        lines = [f"{'IP Address':<16} {'Port':<6} {'Proto':<8} {'Device Type':<18} {'Manufacturer':<16} {'Model':<12} {'Serial':<14} {'Version':<10}",
                 "-" * 115]
        
        for r in sorted(results, key=lambda x: (x.ip, x.port)):
            mfr = str(r.manufacturer or '-')[:16]
            model = str(r.model or '-')[:12]
            serial = str(r.serial_number or '-')[:14]
            version = str(r.version or '-')[:10]
            lines.append(f"{r.ip:<16} {r.port:<6} {get_protocol(r):<8} {r.device_type.value:<18} {mfr:<16} {model:<12} {serial:<14} {version:<10}")
            
        return "\n".join(lines)


def format_results_json(results: List[ScanResult]) -> str:
    """Format results as JSON."""
    return json.dumps([r.to_dict() for r in results], indent=2)


def format_results_csv(results: List[ScanResult]) -> str:
    """Format results as CSV."""
    if not results:
        return "ip,port,device_type,is_reachable,response_time_ms,manufacturer,model,serial_number,version"
        
    output = []
    output.append("ip,port,device_type,is_reachable,response_time_ms,manufacturer,model,serial_number,version")
    
    for r in results:
        output.append(f"{r.ip},{r.port},{r.device_type.value},{r.is_reachable},{r.response_time_ms:.1f},\"{r.manufacturer or ''}\",\"{r.model or ''}\",\"{r.serial_number or ''}\",\"{r.version or ''}\"")
        
    return "\n".join(output)


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Network Scanner for IoT and Energy Devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # mDNS Discovery (recommended - cross-platform)
  %(prog)s --mdns
  %(prog)s --mdns --devices ha,enphase,homey
  %(prog)s --mdns-all

  # IP Scanning
  %(prog)s 192.168.1.0/24
  %(prog)s 192.168.1.0/24 --devices modbus,enphase
  %(prog)s 192.168.1.50 --timeout 10
  %(prog)s 192.168.1.1-192.168.1.100
  %(prog)s 192.168.1.0/24 --ports 502,80,443,1883,8123

  # Output formats
  %(prog)s --mdns -o json > devices.json
  %(prog)s 192.168.1.0/24 -o csv > devices.csv

  # Custom HTTP probe (PORTS:PATH[:KEYS[:LABEL]]) — repeatable
  %(prog)s 192.168.1.0/24 --probe 9091:/api/status:agate,controlSource:FranklinWH_EM
  %(prog)s 192.168.1.0/24 --probe 8099:/docs:franklinwh:FranklinWH_HA
  %(prog)s 192.168.1.0/24 --probe 9090-9095:/api/status:agate:FEM_range
  %(prog)s 192.168.1.0/24 --probe 9090,9091,9099:/api/status:agate:FEM_list
  %(prog)s 192.168.1.0/24 --probe 3000:/:grafana:Grafana
  %(prog)s 192.168.1.0/24 --probe 50001:tcp:Custom_Modbus
  %(prog)s 192.168.1.0/24 --probe 9091:/api/status:agate:FEM --probe 8099:/docs:franklinwh:FHAI

  # Known FranklinWH services (opt-in, port-configurable via --probe)
  %(prog)s 192.168.1.0/24 --devices fem,fha

Supported Device Types:
  modbus, sunspec    - Modbus TCP SunSpec compliant devices
  enphase            - Enphase Envoy/Solar Inverters
  solaredge          - SolarEdge Inverters
  ha, homeassistant  - Home Assistant instances
  mqtt, broker       - MQTT Brokers
  homey              - Homey Smart Home Hub
  span               - SPAN Smart Panel (MAIN 32/40, MLO 48)
  fem, franklinwh_em - FranklinWH Energy Manager *opt-in, use --probe or --devices fem*
  fha, franklinwh_ha - FranklinWH HA Integrator  *opt-in, use --probe or --devices fha*

--probe FORMAT:  PORTS:PATH[:KEYS[:LABEL]]
  PORTS  = single port (9091), range (9090-9099), or comma-list (9090,9091,9095)
  PATH   = HTTP GET path, or 'tcp' for raw TCP-only check
  KEYS   = comma-separated JSON keys (any match confirms device) [optional]
  LABEL  = display name in output table [optional, default: custom:PORTS]

mDNS/Bonjour Discovery:
  Uses zeroconf library for cross-platform service discovery.
  Install: pip install zeroconf
  Works on Linux, macOS, and Windows.
        """
    )
    
    parser.add_argument(
        "targets",
        nargs="*",
        default=[],
        help="IP addresses, CIDR ranges (e.g., 192.168.1.0/24), or ranges (e.g., 192.168.1.1-192.168.1.100). Not needed for --mdns mode."
    )
    
    parser.add_argument(
        "--devices",
        type=str,
        default=None,
        help="Comma-separated list of device types to scan (default: all)"
    )
    
    parser.add_argument(
        "--ports",
        type=str,
        default=None,
        help="Comma-separated list of ports to scan (overrides defaults)"
    )
    
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Timeout in seconds for each probe (default: 3.0)"
    )
    
    parser.add_argument(
        "--threads",
        type=int,
        default=50,
        help="Number of concurrent threads (default: 50)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--no-ping",
        action="store_true",
        help="Skip ping check (faster but may miss some devices)"
    )
    
    parser.add_argument(
        "--mdns",
        action="store_true",
        help="Use mDNS/Bonjour discovery instead of IP scanning (cross-platform)"
    )
    
    parser.add_argument(
        "--mdns-all",
        action="store_true",
        help="Discover all mDNS services (comprehensive IoT scan)"
    )
    
    parser.add_argument(
        "--mdns-timeout",
        type=float,
        default=5.0,
        help="mDNS discovery timeout in seconds (default: 5.0)"
    )

    parser.add_argument(
        "--probe",
        action="append",
        dest="probes",
        metavar="SPEC",
        default=[],
        help=(
            "Custom HTTP probe: PORT:PATH[:KEYS[:LABEL]]. Repeatable. "
            "PATH='tcp' for raw TCP check. KEYS=comma-separated JSON keys. "
            "Example: --probe 9091:/api/status:agate,controlSource:FranklinWH_EM"
        ),
    )

    return parser


def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Validate arguments
    if not args.mdns and not args.mdns_all and not args.targets:
        parser.error("targets are required (unless using --mdns or --mdns-all)")
    
    # Parse device types
    device_types = None
    if args.devices:
        device_types = []
        for d in args.devices.split(','):
            dt = DeviceType.from_string(d.strip())
            if dt != DeviceType.UNKNOWN:
                device_types.append(dt)
            else:
                print(f"Warning: Unknown device type '{d}'", file=sys.stderr)

        if not device_types:
            print("Error: No valid device types specified", file=sys.stderr)
            sys.exit(1)

    # Parse --probe specs: PORTS:PATH[:KEYS[:LABEL]]
    # PORTS can be: single (9091), range (9090-9099), or comma-list (9090,9091,9095)
    custom_probes = []
    for spec_str in (args.probes or []):
        parts = spec_str.split(':')
        if len(parts) < 1:
            print(f"Warning: invalid --probe spec '{spec_str}' (need at least PORT)", file=sys.stderr)
            continue

        # Expand port spec into a list of ints
        port_spec = parts[0].strip()
        try:
            if '-' in port_spec:
                lo, hi = port_spec.split('-', 1)
                probe_ports = list(range(int(lo), int(hi) + 1))
            elif ',' in port_spec:
                probe_ports = [int(p.strip()) for p in port_spec.split(',')]
            else:
                probe_ports = [int(port_spec)]
        except ValueError:
            print(f"Warning: invalid port spec '{port_spec}' in --probe '{spec_str}'", file=sys.stderr)
            continue

        path  = parts[1] if len(parts) > 1 else 'tcp'
        keys  = [k.strip() for k in parts[2].split(',')] if len(parts) > 2 and parts[2] else []
        label = parts[3] if len(parts) > 3 and parts[3] else f'custom:{port_spec}'
        custom_probes.append({'ports': probe_ports, 'path': path, 'keys': keys, 'label': label})
    
    # Parse ports
    ports = None
    if args.ports:
        try:
            ports = [int(p.strip()) for p in args.ports.split(',')]
        except ValueError:
            print("Error: Invalid port specification", file=sys.stderr)
            sys.exit(1)
    
    # Print configuration
    if args.verbose:
        print(f"Network Scanner v1.0")
        if args.mdns or args.mdns_all:
            print(f"Mode: mDNS Discovery")
            print(f"Device types: {[d.value for d in device_types] if device_types else 'all'}")
            print(f"mDNS Timeout: {args.mdns_timeout}s")
        else:
            print(f"Mode: IP Scanning")
            print(f"Targets: {', '.join(args.targets)}")
            print(f"Device types: {[d.value for d in device_types] if device_types else 'all'}")
            print(f"Ports: {ports if ports else 'default'}")
            print(f"Timeout: {args.timeout}s")
            print(f"Threads: {args.threads}")
        print(f"Output: {args.output}")
        print("-" * 50)
    
    # Create scanner
    scanner = NetworkScanner(
        device_types=device_types,
        ports=ports,
        timeout=args.timeout,
        max_workers=args.threads,
        verbose=args.verbose
    )
    scanner.custom_probes = custom_probes
    
    # Run scan (mDNS or IP scanning)
    start_time = time.time()
    
    if args.mdns or args.mdns_all:
        # mDNS discovery mode
        results = scanner.discover_mdns(
            timeout=args.mdns_timeout,
            comprehensive=args.mdns_all
        )
    else:
        # IP scanning mode
        results = scanner.scan(args.targets)
        
    elapsed = time.time() - start_time
    
    # Format and output results
    if args.output == "json":
        print(format_results_json(results))
    elif args.output == "csv":
        print(format_results_csv(results))
    else:
        print(format_results_table(results))
        print(f"\nFound {len(results)} device(s) in {elapsed:.1f} seconds")
    
    # Return appropriate exit code
    sys.exit(0 if results else 1)


if __name__ == "__main__":
    main()
