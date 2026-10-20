#!/usr/bin/env python3
"""
Hardware Test Runner for FranklinWH Battery Control

This script provides a guided interface for running live hardware tests
with explicit user confirmation and safety checks.

Usage:
    python run_hardware_tests.py [options]

Options:
    --read-only       Run only read-only tests (safest)
    --low-power       Include low-power write tests (500W charge/discharge)
    --full            Include all tests including high-power tests
    --list            List available tests without running
    --results-file    Custom path for test results JSON

Examples:
    # Check current status only (no writes)
    python run_hardware_tests.py --read-only
    
    # Run low-power tests with confirmation
    python run_hardware_tests.py --low-power
    
    # List all available tests
    python run_hardware_tests.py --list
"""

import sys
import os
import argparse
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path

# Add project root to path (at the beginning to override system packages)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from franklinwh import FranklinWHController


def get_current_status():
    """Get current aGate status for user review."""
    print("\n" + "="*60)
    print("CURRENT AGATE STATUS")
    print("="*60)
    
    ctrl = FranklinWHController(ip_address='192.0.2.110', port=502, unit_id=2)
    if not ctrl.connect():
        print("❌ Could not connect to aGate!")
        return None
    
    try:
        bat = ctrl.read_battery_status()
        grid = ctrl.read_grid_status()
        native = ctrl.read_native_mode()
        alarms = ctrl.read_alarms()
        
        print(f"\n🔋 Battery:")
        print(f"   SoC: {bat.get('soc', 0):.1f}%")
        print(f"   SoH: {bat.get('soh', 0):.1f}%")
        print(f"   Power: {bat.get('dc_power_w', 0):.0f}W")
        print(f"   Status: {bat.get('status', 'Unknown')}")
        
        print(f"\n⚡ Grid:")
        print(f"   Voltage: {grid.get('voltage_v', 0):.1f}V")
        print(f"   Frequency: {grid.get('frequency_hz', 0):.2f}Hz")
        print(f"   Power: {grid.get('grid_power_w', 0):.0f}W")
        print(f"   Connection: {grid.get('connection_state', 'Unknown')}")
        
        print(f"\n🎛️  aGate Mode:")
        print(f"   Mode: {native.get('mode_name', 'Unknown')}")
        print(f"   Self Reserve: {native.get('self_reserve_pct', 0)}%")
        print(f"   TOU Reserve: {native.get('tou_reserve_pct', 0)}%")
        
        print(f"\n🚨 Alarms:")
        active = alarms.get('active_alarms', [])
        if active:
            for alarm in active:
                print(f"   ⚠️  {alarm.get('name', 'Unknown')}: {alarm.get('description', '')}")
        else:
            print(f"   ✓ No active alarms")
        
        return {
            'soc': bat.get('soc', 0),
            'grid_connected': grid.get('connection_state') == 'Connected',
            'voltage': grid.get('voltage_v', 0),
            'has_critical_alarms': any(a.get('severity') == 'CRITICAL' for a in active),
        }
        
    finally:
        ctrl.disconnect()


def validate_safe_conditions(status):
    """Validate system is safe for testing."""
    if status is None:
        return False, "Could not read status"
    
    issues = []
    
    if status['soc'] < 10 or status['soc'] > 95:
        issues.append(f"SoC {status['soc']:.1f}% outside safe range (10-95%)")
    
    if not status['grid_connected']:
        issues.append("Grid not connected")
    
    if status['voltage'] < 200 or status['voltage'] > 270:
        issues.append(f"Voltage {status['voltage']:.1f}V outside safe range")
    
    if status['has_critical_alarms']:
        issues.append("Critical alarms are active")
    
    if issues:
        return False, "; ".join(issues)
    
    return True, "All safety checks passed"


def list_tests():
    """List all available hardware tests."""
    print("\n" + "="*60)
    print("AVAILABLE HARDWARE TESTS")
    print("="*60)
    
    tests = {
        "Read-Only Tests (Safe)": [
            ("test_read_all_models", "Read all SunSpec models"),
            ("test_battery_status_consistency", "Verify consistent readings over time"),
            ("test_alarms_clear", "Verify no critical alarms"),
        ],
        "Low-Power Write Tests (500W)": [
            ("test_charge_low_power", "Charge at 500W for 10 seconds"),
            ("test_discharge_low_power", "Discharge at 500W for 10 seconds"),
            ("test_standby", "Set to standby (0W)"),
            ("test_release_control", "Release control to Cloud API"),
        ],
        "Advanced Tests (Conditional)": [
            ("test_soc_ramping_near_limit", "Test SoC ramping (only runs if SoC > 85%)"),
        ],
    }
    
    for category, test_list in tests.items():
        print(f"\n{category}:")
        for name, desc in test_list:
            print(f"  • {name}")
            print(f"    {desc}")
    
    print("\n" + "="*60)


def run_pytest_tests(test_pattern, destructive=False, results_file=None):
    """Run pytest with the specified pattern."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/hardware/test_live_battery_control.py",
        "-v",
        "-m", test_pattern,
    ]
    
    if destructive:
        cmd.append("--destructive-enabled")
    
    if results_file:
        os.environ['TEST_RECORD_FILE'] = results_file
    
    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description='Hardware Test Runner for FranklinWH Battery Control',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Safety Notes:
  • Read-only tests are completely safe and only read data
  • Low-power tests write 500W commands for ~10 seconds each
  • All write tests automatically rollback after completion
  • Tests only run if SoC is between 10-95% and grid is connected
  
Examples:
  # Check status only
  python run_hardware_tests.py --read-only
  
  # Run low-power tests
  python run_hardware_tests.py --low-power
  
  # List all tests
  python run_hardware_tests.py --list
        """
    )
    
    parser.add_argument('--read-only', action='store_true',
                       help='Run only read-only tests (safest)')
    parser.add_argument('--low-power', action='store_true',
                       help='Include low-power write tests (500W)')
    parser.add_argument('--full', action='store_true',
                       help='Include all tests (requires explicit confirmation)')
    parser.add_argument('--list', action='store_true',
                       help='List available tests without running')
    parser.add_argument('--results-file', type=str,
                       help='Custom path for test results JSON')
    parser.add_argument('--yes', action='store_true',
                       help='Auto-confirm without prompting (use with caution)')
    parser.add_argument('--release', action='store_true',
                       help='Release control to Cloud API and exit (cleanup mode)')
    
    args = parser.parse_args()
    
    # Release control and exit
    if args.release:
        print("\n" + "="*60)
        print("RELEASING AGATE CONTROL TO CLOUD API")
        print("="*60)
        
        try:
            ctrl = FranklinWHController(ip_address='192.0.2.110', port=502, unit_id=2)
            if not ctrl.connect():
                print("❌ Could not connect to aGate!")
                return 1
            
            # Read current state
            ctl = ctrl.read_control_status()
            print(f"\nBefore release:")
            print(f"  WSetEna: {ctl.get('wset_enabled', 'Unknown')}")
            print(f"  WSetPct: {ctl.get('wset_pct', 'Unknown')}%")
            
            # Release control
            print(f"\nReleasing control...")
            success = ctrl.reset_control_state()
            
            # Verify release
            time.sleep(2)
            ctl_after = ctrl.read_control_status()
            print(f"\nAfter release:")
            print(f"  WSetEna: {ctl_after.get('wset_enabled', 'Unknown')}")
            print(f"  WSetPct: {ctl_after.get('wset_pct', 'Unknown')}%")
            
            ctrl.disconnect()
            
            if success and ctl_after.get('wset_enabled') == 0:
                print("\n✅ Control successfully released to Cloud API")
                return 0
            else:
                print("\n⚠️  Release may not have completed - verify with --status")
                return 1
                
        except Exception as e:
            print(f"\n❌ Error releasing control: {e}")
            return 1
    
    # List tests and exit
    if args.list:
        list_tests()
        return 0
    
    # Default to read-only if no mode specified
    if not (args.read_only or args.low_power or args.full):
        print("No test mode specified. Use --read-only, --low-power, or --full")
        print("Run with --help for more information")
        return 1
    
    # Get current status
    status = get_current_status()
    
    # Validate safe conditions
    safe, message = validate_safe_conditions(status)
    if not safe:
        print(f"\n❌ SAFETY CHECK FAILED: {message}")
        print("Tests cannot proceed until conditions are safe.")
        return 1
    
    print(f"\n✅ {message}")
    
    # Determine test pattern based on mode
    if args.read_only:
        print("\n📋 Running READ-ONLY tests (no writes to battery)...")
        test_pattern = "hardware and not destructive"
        destructive = False
        
    elif args.low_power:
        print("\n⚡ Running LOW-POWER tests (500W charge/discharge)...")
        print("Each test will:")
        print("  1. Send command to battery")
        print("  2. Wait ~5 seconds for stabilization")
        print("  3. Validate response")
        print("  4. Automatically rollback control state")
        test_pattern = "hardware"
        destructive = True
        
    elif args.full:
        print("\n🔥 FULL TEST MODE requested")
        print("This includes all tests including high-power operations.")
        test_pattern = "hardware"
        destructive = True
    
    # Get user confirmation
    if not args.yes:
        print("\n" + "="*60)
        response = input("Do you want to proceed? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("Tests cancelled by user.")
            return 0
    
    # Set results file
    if not args.results_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.results_file = f"data/test_results_{timestamp}.json"
    
    print(f"\nResults will be saved to: {args.results_file}")
    print("="*60 + "\n")
    
    # Run tests
    success = run_pytest_tests(test_pattern, destructive, args.results_file)
    
    # Display results summary
    if os.path.exists(args.results_file):
        try:
            with open(args.results_file, 'r') as f:
                results = json.load(f)
            
            summary = results.get('test_session', {})
            print("\n" + "="*60)
            print("TEST SUMMARY")
            print("="*60)
            print(f"Total:  {summary.get('total_tests', 0)}")
            print(f"Passed: {summary.get('passed', 0)} ✅")
            print(f"Failed: {summary.get('failed', 0)} ❌")
            print(f"Skipped: {summary.get('skipped', 0)} ⏭️")
            print(f"\nResults saved to: {args.results_file}")
            print("="*60)
            
        except Exception as e:
            print(f"\nCould not read results file: {e}")
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
