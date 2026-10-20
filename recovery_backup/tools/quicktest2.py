#!/usr/bin/env python3
"""
Test pymodbus 3.11.4 API
"""

from pymodbus.client import ModbusTcpClient
from pymodbus import __version__

print(f"pymodbus version: {__version__}")

client = ModbusTcpClient("192.0.2.110", port=502)

# Check method signature
import inspect
sig = inspect.signature(client.read_holding_registers)
print(f"\nread_holding_registers signature: {sig}")

# Try connecting
if not client.connect():
    print("❌ Connection failed")
    exit(1)

print("✅ Connected")

# Try different calling patterns
patterns = [
    ("address=, count=", lambda: client.read_holding_registers(address=40180-40001, count=1)),
    ("slave= in client", lambda: client.read_holding_registers(address=40180-40001, count=1, slave=2)),
]

for name, func in patterns:
    try:
        result = func()
        print(f"✅ '{name}' works!")
        print(f"   Result: {result.registers}")
        break
    except Exception as e:
        print(f"❌ '{name}' failed: {type(e).__name__}: {e}")

client.close()
