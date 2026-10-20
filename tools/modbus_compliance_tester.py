#!/usr/bin/env python3
"""
FranklinWH Modbus Compliance Tester

Automated test tool to verify Modbus model capability, discover register
discrepancies, check extension register writes by read-back (undocumented by FranklinWH),
and generate a comprehensive Markdown compatibility report scorecard.
"""

import argparse
import sys
import os
import time
from typing import Dict, Any, List

# Add src to path for development
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from franklinwh_modbus import FranklinWHController

def run_compliance_check(ip: str, port: int, unit: int, base_address: int, timeout: float, output_file: str) -> bool:
    """Connect to aGate, scan models, query schema points, and generate a scorecard."""
    print(f"\n⚡ Starting FranklinWH Modbus Compliance Test on {ip}:{port} (Unit {unit}, Base {base_address}, Timeout {timeout}s)")
    print("=" * 70)

    ctrl = FranklinWHController(
        ip_address=ip,
        port=port,
        unit_id=unit,
        base_address=base_address,
        timeout=timeout
    )
    
    print("1. Connecting to Modbus Gateway...")
    if not ctrl.connect():
        print("❌ FAILED to connect to Modbus device.")
        return False
    print("✓ Connected successfully.")

    # Load schema
    print("\n2. Loading capability schema...")
    schema = ctrl.load_capability_schema()
    if not schema:
        print("❌ FAILED to load capability schema modbus_capability.json.")
        ctrl.disconnect()
        return False
    print(f"✓ Loaded capability schema for: {schema.get('device', {}).get('model', 'aGate X')}")

    # Discover ratings
    print("\n3. Discovering ratings...")
    ctrl.discover_ratings()
    print(f"✓ Rated Max: {ctrl.RATED_MAX_W}W (Charge: {ctrl.RATED_MAX_CHARGE_W}W, Discharge: {ctrl.RATED_MAX_DISCHARGE_W}W)")

    # Read system metadata
    print("\n4. Reading device metadata...")
    system_sn = "UNKNOWN"
    system_mn = "UNKNOWN"
    system_md = "UNKNOWN"
    
    m1 = ctrl.get_model(1)
    if m1:
        try:
            m1.read()
            system_sn = str(m1.SN.value).strip() if getattr(m1, 'SN', None) else "UNKNOWN"
            system_mn = str(m1.Mn.value).strip() if getattr(m1, 'Mn', None) else "UNKNOWN"
            system_md = str(m1.Md.value).strip() if getattr(m1, 'Md', None) else "UNKNOWN"
        except Exception as e:
            print(f"⚠️ Failed to read metadata: {e}")

    # Run extension writability test
    print("\n5. Probing extension register writability...")
    write_results = ctrl._test_extension_writability()
    
    ongrid_mode_writable = write_results.get('ongrid_mode', {}).get('writable', False)
    self_reserve_writable = write_results.get('self_reserve', {}).get('writable', False)
    tou_reserve_writable = write_results.get('tou_reserve', {}).get('writable', False)
    
    span_writable_count = sum([ongrid_mode_writable, self_reserve_writable, tou_reserve_writable])
    print(f"✓ Extension writability results: {span_writable_count}/3 registers writable.")
    if span_writable_count == 3:
        print("  ✅ All three test writes read back as applied.")
    elif span_writable_count > 0:
        print("  ⚠️  Partial Write Access detected.")
    else:
        print("  🔒 Extension writes were not applied (read-only; writes undocumented).")

    # Audit SunSpec points
    print("\n6. Auditing SunSpec model implementation points...")
    audit_results: Dict[str, Dict[str, Any]] = {}
    
    for model_id_str, model_info in schema.get("models", {}).items():
        model_id = int(model_id_str)
        m = ctrl.get_model(model_id)
        
        audit_results[model_id_str] = {
            "name": model_info.get("name", f"Model {model_id}"),
            "discovered": m is not None,
            "points": {}
        }
        
        if m:
            try:
                m.read()
                sf = 0
                # Try getting scaling factor
                for sf_candidate in ['W_SF', 'V_SF', 'A_SF', 'TotWh_SF']:
                    if hasattr(m, sf_candidate):
                        sf = ctrl._get_scale_factor(m, sf_candidate)
                        break
                
                for point_name, point_info in model_info.get("points", {}).items():
                    pt = getattr(m, point_name, None)
                    if pt is None:
                        audit_results[model_id_str]["points"][point_name] = {
                            "status": "unsupported",
                            "value": "N/A"
                        }
                    elif pt.value is None:
                        audit_results[model_id_str]["points"][point_name] = {
                            "status": "unimplemented",
                            "value": "None (Null)"
                        }
                    else:
                        val = pt.value
                        if isinstance(val, (int, float)) and sf != 0:
                            val_scaled = val * (10 ** sf)
                            val_str = f"{val_scaled} (raw: {val})"
                        else:
                            val_str = str(val)
                            
                        # Detect unimplemented markers (0xFFFF or 0 under specific points)
                        if val == 65535 or val == 0xFFFF:
                            status = "unimplemented"
                        elif point_name == "WMaxRtg" and val == 0:
                            status = "broken"
                        elif point_name == "Sta" and val == 0:
                            status = "broken"
                        else:
                            status = "implemented"
                            
                        audit_results[model_id_str]["points"][point_name] = {
                            "status": status,
                            "value": val_str,
                            "quirk": point_info.get("quirk"),
                            "observed": point_info.get("observed")
                        }
            except Exception as e:
                print(f"  ⚠️ Error reading Model {model_id}: {e}")
                for point_name in model_info.get("points", {}):
                    audit_results[model_id_str]["points"][point_name] = {
                        "status": "error",
                        "value": str(e)
                    }
        else:
            for point_name in model_info.get("points", {}):
                audit_results[model_id_str]["points"][point_name] = {
                    "status": "unsupported",
                    "value": "Model absent"
                }

    # Generate Markdown Scorecard
    print("\n7. Formatting Markdown report scorecard...")
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    report = []
    report.append(f"# FranklinWH Modbus Conformance & Compliance Scorecard")
    report.append(f"\n*Generated on: {timestamp}*")
    report.append(f"\n## Device Metadata")
    report.append(f"- **Manufacturer**: {system_mn}")
    report.append(f"- **Model**: {system_md}")
    report.append(f"- **Serial Number**: {system_sn}")
    report.append(f"- **IP Address**: {ip}:{port}")
    report.append(f"- **Slave Unit ID**: {unit}")

    # Writability status alert box
    report.append(f"\n## Write plane Status (Extension Registers)")
    if span_writable_count == 3:
        report.append(f"> [!NOTE]\n> **✅ EXTENSION WRITES READ BACK AS APPLIED**: Test writes to 15507-15509 read back as applied on this Gateway during this run. FranklinWH has not documented these registers as writable.")
    else:
        report.append(f"> [!IMPORTANT]\n> **🔒 EXTENSION WRITES NOT APPLIED**: Proprietary extension registers (15507-15509) are **read-only** on this unit. FranklinWH has not documented them or any mechanism that enables writes.\n> \n> **⚠️ CRITICAL MODBUS BEHAVIOR**: When writes are not applied, **write transactions to these registers are silently accepted at the protocol level (returning standard Modbus success/FC06 echoes), but are discarded internally by the Gateway and no error is returned**. Consequently, active read-back verification is *mandatory* to confirm if a write actually took effect. Active power control (Model 704) remains fully writable.")

    report.append(f"\n## Compliance Audit Results")
    report.append(f"| Model | Register Point | Expected Status | Live Verified | Observed Value / Details |")
    report.append(f"|:---|:---|:---|:---|:---|")
    
    # Process models
    for model_id_str, audit in audit_results.items():
        m_info = schema["models"][model_id_str]
        disc_symbol = "✅" if audit["discovered"] else "❌"
        
        # Add entry for model discovery
        report.append(f"| **Model {model_id_str}** ({audit['name']}) | *Discovery* | Implemented | {disc_symbol} | {'Model present' if audit['discovered'] else 'Model absent'} |")
        
        # Add points
        for pt_name, pt_audit in audit["points"].items():
            schema_pt_info = m_info["points"][pt_name]
            expected_status = schema_pt_info.get("status", "implemented")
            
            # Icon selection
            if pt_audit["status"] == "implemented":
                icon = "✅ Implemented"
            elif pt_audit["status"] == "unimplemented":
                icon = "❌ Unimplemented"
            elif pt_audit["status"] == "broken":
                icon = "⚠️ Broken (Firmware Defect)"
            else:
                icon = f"❓ {pt_audit['status']}"
                
            obs_details = pt_audit["value"]
            if pt_audit.get("quirk"):
                obs_details += f" <br>*Quirk: {pt_audit['quirk']}*"
            elif pt_audit.get("observed") and pt_audit["status"] != "implemented":
                obs_details += f" <br>*Known Issue: {pt_audit['observed']}*"
                
            report.append(f"| | `{pt_name}` | {expected_status.title()} | {icon} | {obs_details} |")

    # Extensions
    report.append(f"\n## Extensions & Mirrors Audit")
    report.append(f"| Extension Register | Purpose | Live Status | Details |")
    report.append(f"|:---|:---|:---|:---|")
    
    for reg_str, ext_info in schema.get("extensions", {}).items():
        reg_addr = int(reg_str)
        ext_name = ext_info["name"]
        
        try:
            val = ctrl.read_native_mode().get('mode_raw') if reg_addr == 15507 else None
            if reg_addr == 15508:
                val = ctrl.read_native_mode().get('self_reserve_pct')
            elif reg_addr == 15509:
                val = ctrl.read_native_mode().get('tou_reserve_pct')
            elif reg_addr == 15506:
                val = ctrl.read_solar_status().get('extension', {}).get('home_load')
            elif reg_addr == 16000:
                val = ctrl.read_solar_status().get('extension', {}).get('home_load_ext')
            
            if val is not None:
                icon = "✅ Readable"
                # Add write-status if it's writable
                if reg_addr == 15507 and ongrid_mode_writable:
                    icon += " / ✍️ Writable"
                elif reg_addr == 15508 and self_reserve_writable:
                    icon += " / ✍️ Writable"
                elif reg_addr == 15509 and tou_reserve_writable:
                    icon += " / ⚠️ Mirrors 15508"
                obs = f"Value: {val}"
            else:
                icon = "❓ Unread"
                obs = "No telemetry returned"
        except Exception as e:
            icon = "❌ Failed"
            obs = str(e)
            
        report.append(f"| `{reg_str}` ({ext_name}) | {ext_info.get('description', '')} | {icon} | {obs} |")

    # Recommendations & Mitigations
    report.append(f"\n## Safety & Orchestration Recommendations")
    report.append(f"1. **Software watchdogs are mandatory**: Since `WSetRvrtTms` countdown does not revert power setpoints and `ControllerHb` is non-functional, always provide safe timeouts `duration_s` on all power commands.")
    report.append(f"2. **Calculated Current**: `M714.DCA` is 0. Use calculated current: `I = Power / Voltage`.")
    report.append(f"3. **Battery State**: `M713.Sta` is 0. Rely on dynamic power direction: Positive is charging, negative is discharging.")
    if span_writable_count < 3:
        report.append(f"4. **Reserve Controls**: Extension write registers are read-only. For battery throttling and reserve limits, rely entirely on the library's **software-based Virtual Mode Controller (VMC)**.")

    # Save to file
    try:
        with open(output_file, 'w') as f:
            f.write("\n".join(report))
        print(f"✓ Conformance report written to: {output_file}")
    except Exception as e:
        print(f"❌ Failed to write scorecard report: {e}")

    ctrl.disconnect()
    print("\n✓ Compliance test run completed successfully.")
    return True

def main():
    parser = argparse.ArgumentParser(description="FranklinWH Modbus Conformance & Compliance Tester")
    parser.add_argument("-i", "--ip", required=True, help="aGate IP address")
    parser.add_argument("-p", "--port", type=int, default=502, help="Modbus port (default: 502)")
    parser.add_argument("-u", "--unit", type=int, default=2, help="Modbus unit ID (default: 2)")
    parser.add_argument("-b", "--base-address", type=int, default=40000, help="Base Modbus address (default: 40000)")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="Connection timeout (default: 10.0)")
    parser.add_argument("-o", "--output", default="modbus_compliance_report.md", help="Output report scorecard file")
    
    args = parser.parse_args()
    
    success = run_compliance_check(
        ip=args.ip,
        port=args.port,
        unit=args.unit,
        base_address=args.base_address,
        timeout=args.timeout,
        output_file=args.output
    )
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
