#!/bin/bash
# Setup script for network scanner dependencies

set -e

echo "Setting up Network Scanner dependencies..."

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    if [ -d "../venv" ]; then
        source ../venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "No virtual environment found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
    fi
fi

echo "Installing dependencies in: $VIRTUAL_ENV"

# Install required packages
pip install --upgrade pip
pip install pymodbus requests zeroconf

# Optional packages
pip install tabulate colorama 2>/dev/null || echo "Optional packages not installed (okay)"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Test the scanner:"
echo "  python3 tools/network_scanner.py --mdns -v"
echo ""
echo "Or with IP scanning:"
echo "  python3 tools/network_scanner.py 192.0.2.0/24 --devices modbus -v"
