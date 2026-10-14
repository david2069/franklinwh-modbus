#!/usr/bin/env python3
"""
Example script showing programmatic usage of the network scanner.
"""

import sys
import os
sys.path.insert(0, os.path.expanduser('~/dev/modbus/tools'))

from network_scanner import (
    NetworkScanner, 
    DeviceType, 
    IPRangeGenerator,
    format_results_table,
    format_results_json
)


def example_basic_scan():
    """Example: Basic scan of a single IP."""
    print("=" * 60)
    print("Example 1: Basic Scan")
    print("=" * 60)
    
    scanner = NetworkScanner(
        device_types=[DeviceType.MODBUS_SUNSPEC, DeviceType.HOME_ASSISTANT],
        timeout=3.0,
        max_workers=10,
        verbose=True
    )
    
    # Scan a single IP (use your device's IP here)
    results = scanner.scan(["127.0.0.1"])
    
    print("\nResults:")
    print(format_results_table(results))


def example_ip_range_parsing():
    """Example: Different ways to specify IP ranges."""
    print("\n" + "=" * 60)
    print("Example 2: IP Range Parsing")
    print("=" * 60)
    
    examples = [
        "192.168.1.50",           # Single IP
        "192.168.1.0/30",         # CIDR (small for demo)
        "192.168.1.1-192.168.1.5", # Range
        "10.0.0.*",               # Wildcard (first 5 only for demo)
    ]
    
    for example in examples:
        try:
            ips = IPRangeGenerator.parse(example)
            # Show only first 5 for wildcard
            display_ips = ips[:5] if len(ips) > 5 else ips
            print(f"\n'{example}' -> {len(ips)} IP(s)")
            print(f"  First few: {display_ips}")
        except ValueError as e:
            print(f"\n'{example}' -> Error: {e}")


def example_device_type_filtering():
    """Example: Scanning only specific device types."""
    print("\n" + "=" * 60)
    print("Example 3: Device Type Filtering")
    print("=" * 60)
    
    # Parse device types from strings
    device_strings = ["modbus", "mqtt", "ha"]
    device_types = [DeviceType.from_string(d) for d in device_strings]
    
    print(f"Requested: {device_strings}")
    print(f"Resolved: {[d.value for d in device_types]}")
    
    scanner = NetworkScanner(
        device_types=device_types,
        timeout=2.0,
        max_workers=20
    )
    
    print(f"\nScanner configured for: {[d.value for d in scanner.device_types]}")


def example_custom_ports():
    """Example: Using custom ports."""
    print("\n" + "=" * 60)
    print("Example 4: Custom Ports")
    print("=" * 60)
    
    scanner = NetworkScanner(
        device_types=[DeviceType.MODBUS_SUNSPEC],
        ports=[502, 5020, 1502, 8899],  # Custom Modbus ports
        timeout=2.0,
        max_workers=10
    )
    
    print(f"Custom ports configured: {scanner.custom_ports}")


def example_output_formats():
    """Example: Different output formats."""
    print("\n" + "=" * 60)
    print("Example 5: Output Formats")
    print("=" * 60)
    
    # Create some mock results for demonstration
    from network_scanner import ScanResult
    
    mock_results = [
        ScanResult(
            ip="192.168.1.50",
            port=502,
            device_type=DeviceType.MODBUS_SUNSPEC,
            is_reachable=True,
            response_time_ms=45.2,
            manufacturer="FranklinWH",
            model="aGate X",
            serial_number="0091XXXXXX",
            version="2.1.0"
        ),
        ScanResult(
            ip="192.168.1.100",
            port=8123,
            device_type=DeviceType.HOME_ASSISTANT,
            is_reachable=True,
            response_time_ms=12.5,
            manufacturer="Nabu Casa",
            model="Home Assistant",
            version="2024.1.0"
        ),
    ]
    
    print("\n--- Table Format ---")
    print(format_results_table(mock_results))
    
    print("\n--- JSON Format (first 500 chars) ---")
    json_output = format_results_json(mock_results)
    print(json_output[:500] + "..." if len(json_output) > 500 else json_output)


def example_scan_with_callback():
    """Example: Scan with progress callback (advanced)."""
    print("\n" + "=" * 60)
    print("Example 6: Advanced - Custom Processing")
    print("=" * 60)
    
    # This shows how you could process results as they come in
    # by using the internal methods directly
    
    scanner = NetworkScanner(
        device_types=[DeviceType.MQTT_BROKER],
        timeout=2.0,
        max_workers=10
    )
    
    # Parse some IPs
    ips = IPRangeGenerator.parse("192.168.1.0/29")  # Small range for demo
    
    print(f"Would scan {len(ips)} IPs for MQTT brokers")
    print(f"IPs: {ips}")
    
    # In real usage, you'd call scanner.scan(["192.168.1.0/29"])


if __name__ == "__main__":
    print("Network Scanner - Usage Examples")
    print("=" * 60)
    print()
    
    # Run all examples
    example_ip_range_parsing()
    example_device_type_filtering()
    example_custom_ports()
    example_output_formats()
    example_scan_with_callback()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nTo run an actual scan, use:")
    print("  python3 network_scanner.py <target> [options]")
    print("\nExample:")
    print("  python3 network_scanner.py 192.168.1.0/24 --devices modbus -v")
