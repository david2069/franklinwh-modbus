#!/usr/bin/env python3
"""
SunSpec device reader/writer using pysunspec2.
Unified tool for FranklinWH aGate X monitoring and control.
"""

import argparse
import sys
import json
import logging
import time
import threading
from typing import Dict, List, Optional, Tuple, Set, Any, Union

# Import pysunspec2
try:
    import sunspec2.modbus.client as client
except ImportError:
    try:
        from sunspec2.modbus import client
    except ImportError:
        try:
            import pysunspec2.modbus.client as client
        except ImportError:
            try:
                from pysunspec2.modbus import client
            except ImportError:
                print("Error: Missing required library: pysunspec2", file=sys.stderr)
                print("Install with: pip install pysunspec2", file=sys.stderr)
                sys.exit(1)


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging for the application."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# =============================================================================
# CORE FUNCTIONS (from your existing code)
# =============================================================================

def parse_model_spec(spec: str) -> Set[int]:
    """Parse model specification string into set of model IDs."""
    models = set()
    parts = spec.split(",")
    
    for part in parts:
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-")
                models.update(range(int(start.strip()), int(end.strip()) + 1))
            except ValueError:
                logging.warning(f"Invalid range format: {part}")
        else:
            try:
                models.add(int(part))
            except ValueError:
                logging.warning(f"Invalid model ID: {part}")
    
    return models


def get_model_points(model, device_base_address: int = 0, verbose: bool = False) -> List[Dict]:
    """Extract all points from a model with comprehensive metadata."""
    points = []
    
    model_base_addr = getattr(model, 'addr', None) or getattr(model, 'base_addr', None) or getattr(model, 'model_addr', None)
    absolute_base_addr = model_base_addr
    
    if absolute_base_addr is not None and device_base_address > 0:
        if absolute_base_addr < device_base_address:
            absolute_base_addr += device_base_address
    
    if hasattr(model, "points"):
        for point_name in model.points:
            point = getattr(model, point_name, None)
            if point is None:
                continue
                
            point_info = {"name": point_name, "value": getattr(point, "value", None)}
            
            if hasattr(point, "addr"):
                point_info["address"] = point.addr
            elif hasattr(point, "offset") and absolute_base_addr is not None:
                point_info["address"] = absolute_base_addr + point.offset
                point_info["offset"] = point.offset
            
            pdef = getattr(point, "pdef", None) or getattr(point, "point_type", None)
            
            if pdef:
                def get_val(key):
                    return pdef.get(key) if isinstance(pdef, dict) else getattr(pdef, key, None)
                
                for key in ["type", "units", "label", "desc", "access", "mandatory", "min", "max", "default"]:
                    v = get_val(key)
                    if v is not None:
                        point_info[key] = v
                
                sf = get_val("sf")
                if sf:
                    point_info["scale_factor"] = sf
                    point_info["is_scale_factor"] = point_name.endswith("_SF")
                
                size = get_val("size")
                if size:
                    point_info["size"] = size
                    if "address" in point_info:
                        point_info["address_end"] = point_info["address"] + size - 1
                
                symbols = get_val("symbols")
                if symbols:
                    try:
                        point_info["symbols"] = dict(symbols)
                        point_info["is_enum_or_bitmap"] = True
                        if point_info["value"] is not None:
                            point_info["value_meaning"] = point_info["symbols"].get(point_info["value"], "Unknown")
                    except (ValueError, TypeError):
                        pass
                
                if "bitfield" in str(get_val("type", "")).lower():
                    point_info["is_bitmap"] = True
            
            # Calculate scaled value
            if "scale_factor" in point_info and point_info["scale_factor"]:
                sf_name = point_info["scale_factor"]
                sf_point = getattr(model, sf_name, None)
                if sf_point is not None:
                    sf_value = getattr(sf_point, "value", None)
                    if sf_value is not None and point_info["value"] is not None:
                        try:
                            point_info["scaled_value"] = point_info["value"] * (10 ** sf_value)
                        except (TypeError, ValueError):
                            pass
            
            points.append(point_info)
    
    return points


# =============================================================================
# WRITE FUNCTIONS (your new code)
# =============================================================================

def write_sunspec_point(
    ip: str,
    model_id: int,
    point_name: str,
    value: Any,
    port: int = 502,
    unit: int = 1,
    timeout: float = 2.0,
    base_address: int = 40000,
    validate: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Write a value to a specific SunSpec point with validation."""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Write request: {ip}:{port} Model {model_id}.{point_name} = {value}")
        
        modbus_client = client.SunSpecModbusClientDeviceTCP(
            slave_id=unit, ipaddr=ip, ipport=port, timeout=timeout,
        )
        
        # Scan
        for scan_method in [
            lambda: modbus_client.scan(base_addr=base_address),
            lambda: modbus_client.scan(base_address),
            lambda: modbus_client.scan(address=base_address),
            lambda: modbus_client.scan(),
        ]:
            try:
                scan_method()
                break
            except TypeError:
                continue
        
        # Get model
        m = modbus_client.models.get(model_id) or modbus_client.models.get(str(model_id))
        if m is None:
            return False, f"Model {model_id} not found"
        
        if isinstance(m, list):
            m = m[0] if m else None
        if m is None:
            return False, f"Model {model_id} is empty"
        
        m.read()
        
        point = getattr(m, point_name, None)
        if point is None:
            return False, f"Point {point_name} not found"
        
        # Validation
        if validate and hasattr(point, "pdef"):
            pdef = point.pdef
            
            if hasattr(pdef, "access") and pdef.access not in ["rw", "w"]:
                return False, f"Point is read-only (access={pdef.access})"
            
            if hasattr(pdef, "min") and pdef.min is not None and value < pdef.min:
                return False, f"Value {value} below minimum {pdef.min}"
            
            if hasattr(pdef, "max") and pdef.max is not None and value > pdef.max:
                return False, f"Value {value} above maximum {pdef.max}"
        
        if dry_run:
            modbus_client.close()
            return True, "Dry run successful"
        
        old_value = getattr(point, "value", None)
        point.value = value
        m.write()
        
        logger.info(f"Write successful: {point_name} {old_value} -> {value}")
        modbus_client.close()
        return True, None
        
    except Exception as e:
        logger.exception("Write failed")
        return False, str(e)


def batch_write_points(
    ip: str,
    points_to_write: List[Tuple[int, str, Any]],
    port: int = 502,
    unit: int = 1,
    timeout: float = 2.0,
    base_address: int = 40000,
    validate: bool = True,
    dry_run: bool = False,
    atomic: bool = True,
) -> Tuple[Dict[str, bool], Optional[str]]:
    """Write multiple points efficiently."""
    logger = logging.getLogger(__name__)
    
    try:
        modbus_client = client.SunSpecModbusClientDeviceTCP(
            slave_id=unit, ipaddr=ip, ipport=port, timeout=timeout,
        )
        
        # Scan
        for scan_method in [
            lambda: modbus_client.scan(base_addr=base_address),
            lambda: modbus_client.scan(base_address),
            lambda: modbus_client.scan(address=base_address),
            lambda: modbus_client.scan(),
        ]:
            try:
                scan_method()
                break
            except TypeError:
                continue
        
        # Group by model
        by_model = {}
        for mid, pname, val in points_to_write:
            by_model.setdefault(mid, []).append((pname, val))
        
        results = {}
        
        # Validate all first if atomic
        if atomic and validate:
            for mid, pvals in by_model.items():
                m = modbus_client.models.get(mid) or modbus_client.models.get(str(mid))
                if isinstance(m, list):
                    m = m[0] if m else None
                if m is None:
                    for pname, _ in pvals:
                        results[f"{mid}.{pname}"] = False
                    continue
                
                m.read()
                for pname, val in pvals:
                    p = getattr(m, pname, None)
                    if p is None:
                        results[f"{mid}.{pname}"] = False
                        continue
                    if hasattr(p, "pdef") and hasattr(p.pdef, "access"):
                        if p.pdef.access not in ["rw", "w"]:
                            results[f"{mid}.{pname}"] = False
        
        if dry_run:
            modbus_client.close()
            return {k: True for k in results}, None
        
        # Write
        for mid, pvals in by_model.items():
            m = modbus_client.models.get(mid) or modbus_client.models.get(str(mid))
            if isinstance(m, list):
                m = m[0] if m else None
            if m is None:
                for pname, _ in pvals:
                    results[f"{mid}.{pname}"] = False
                continue
            
            m.read()
            for pname, val in pvals:
                p = getattr(m, pname, None)
                if p is None:
                    results[f"{mid}.{pname}"] = False
                    continue
                p.value = val
                results[f"{mid}.{pname}"] = True
            
            try:
                m.write()
            except Exception as e:
                logger.error(f"Model {mid} write failed: {e}")
                for pname, _ in pvals:
                    results[f"{mid}.{pname}"] = False
        
        modbus_client.close()
        return results, None
        
    except Exception as e:
        logger.exception("Batch write failed")
        return {}, str(e)


# =============================================================================
# FRANKLINWH SPECIFIC CONTROLS
# =============================================================================

class AGateController:
    """High-level controller for FranklinWH aGate X"""
    
    # Key points for common operations
    POINTS = {
        'throttle_pct': (701, 'ThrotPct'),
        'throttle_src': (701, 'ThrotSrc'),
        'power_limit_pct': (704, 'WMaxLimPct'),
        'power_limit_timeout': (704, 'WMaxLimPctRvrtTms'),
        'fixed_power_enable': (704, 'WSetEna'),
        'fixed_power_watts': (704, 'WSet'),
        'charge_rate_max': (702, 'WChaRteMax'),
        'discharge_rate_max': (702, 'WDisChaRteMax'),
        'heartbeat': (715, 'ControllerHb'),
        'op_ctl': (715, 'OpCtl'),
        'soc': (713, 'SoC'),
        'soh': (713, 'SoH'),
        'dc_power': (714, 'DCW'),
    }
    
    def __init__(self, ip: str, unit: int = 2, timeout: float = 5.0):
        self.ip = ip
        self.unit = unit
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
    def read_status(self) -> Dict:
        """Read comprehensive status"""
        points = ['throttle_pct', 'throttle_src', 'soc', 'soh', 'dc_power']
        # Implementation using batch read...
        # For now, use individual reads
        status = {}
        for name in points:
            mid, pname = self.POINTS[name]
            # Simplified - would use batch in production
            status[name] = f"Would read {mid}.{pname}"
        return status
    
    def set_power_limit(self, percent: float, timeout_sec: Optional[int] = None) -> bool:
        """Set power limit percentage"""
        value = int(percent * 10)  # Scale factor -1
        success, error = write_sunspec_point(
            self.ip, 704, 'WMaxLimPct', value,
            unit=self.unit, timeout=self.timeout
        )
        if not success:
            self.logger.error(f"Failed to set power limit: {error}")
            return False
        
        if timeout_sec is not None:
            write_sunspec_point(
                self.ip, 704, 'WMaxLimPctRvrtTms', timeout_sec,
                unit=self.unit, timeout=self.timeout
            )
        
        return True
    
    def emergency_stop(self) -> bool:
        """Trigger emergency stop"""
        success, error = write_sunspec_point(
            self.ip, 715, 'OpCtl', 1,
            unit=self.unit, timeout=self.timeout
        )
        return success


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FranklinWH aGate X SunSpec2 Reader/Writer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Read all models:        %(prog)s -i 192.0.2.110 -u 2 --scan
  Read specific point:    %(prog)s -i 192.0.2.110 --point 701.ThrotPct
  Write power limit:      %(prog)s -i 192.0.2.110 --write 704.WMaxLimPct=500
  Batch write:            %(prog)s -i 192.0.2.110 --batch-write writes.json
  Emergency stop:         %(prog)s -i 192.0.2.110 --emergency-stop
  Monitor mode:           %(prog)s -i 192.0.2.110 --monitor
        """
    )
    
    # Connection
    parser.add_argument('-i', '--ip', required=True, help='Device IP address')
    parser.add_argument('-p', '--port', type=int, default=502, help='Modbus port')
    parser.add_argument('-u', '--unit', type=int, default=2, help='Modbus unit ID')
    parser.add_argument('-t', '--timeout', type=float, default=5.0, help='Timeout seconds')
    parser.add_argument('-b', '--base-address', type=int, default=40000, help='Base address')
    
    # Operations
    parser.add_argument('--scan', action='store_true', help='Scan and display all models')
    parser.add_argument('--point', help='Read specific point (format: model.point)')
    parser.add_argument('--write', help='Write point (format: model.point=value)')
    parser.add_argument('--batch-write', help='JSON file with points to write')
    parser.add_argument('--emergency-stop', action='store_true', help='Trigger emergency stop')
    parser.add_argument('--monitor', action='store_true', help='Continuous monitoring mode')
    parser.add_argument('--limit', type=float, help='Set power limit percentage')
    
    # Options
    parser.add_argument('-d', '--detail', default='values', 
                       choices=['minimal', 'basic', 'values', 'detailed', 'full'],
                       help='Detail level for scan')
    parser.add_argument('--dry-run', action='store_true', help='Validate only, don\'t write')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--log-file', help='Log file path')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)
    
    # Execute command
    try:
        if args.emergency_stop:
            ctrl = AGateController(args.ip, args.unit, args.timeout)
            if ctrl.emergency_stop():
                print("🛑 Emergency stop triggered")
            else:
                print("❌ Failed to trigger emergency stop")
                sys.exit(1)
        
        elif args.limit is not None:
            ctrl = AGateController(args.ip, args.unit, args.timeout)
            if ctrl.set_power_limit(args.limit):
                print(f"🎯 Power limit set to {args.limit}%")
            else:
                print("❌ Failed to set power limit")
                sys.exit(1)
        
        elif args.write:
            # Parse model.point=value
            try:
                model_point, value_str = args.write.split('=')
                model_id, point_name = model_point.split('.')
                model_id = int(model_id)
                
                # Try to parse value
                try:
                    value = int(value_str)
                except ValueError:
                    try:
                        value = float(value_str)
                    except ValueError:
                        value = value_str
                
                success, error = write_sunspec_point(
                    args.ip, model_id, point_name, value,
                    port=args.port, unit=args.unit, timeout=args.timeout,
                    base_address=args.base_address, dry_run=args.dry_run,
                    verbose=args.verbose
                )
                
                if success:
                    print(f"✅ Wrote {model_id}.{point_name} = {value}")
                    if error:
                        print(f"   Note: {error}")
                else:
                    print(f"❌ Write failed: {error}")
                    sys.exit(1)
                    
            except ValueError as e:
                print(f"❌ Invalid write format. Use: model.point=value")
                sys.exit(1)
        
        elif args.batch_write:
            with open(args.batch_write) as f:
                batch_data = json.load(f)
            
            points = [(int(p['model']), p['point'], p['value']) for p in batch_data['points']]
            
            results, error = batch_write_points(
                args.ip, points,
                port=args.port, unit=args.unit, timeout=args.timeout,
                base_address=args.base_address, dry_run=args.dry_run
            )
            
            success_count = sum(results.values())
            print(f"Batch write: {success_count}/{len(results)} successful")
            if error:
                print(f"Error: {error}")
                sys.exit(1)
        
        elif args.monitor:
            print(f"📈 Monitoring {args.ip} (Ctrl+C to stop)...")
            ctrl = AGateController(args.ip, args.unit, args.timeout)
            try:
                while True:
                    status = ctrl.read_status()
                    print(f"[{time.strftime('%H:%M:%S')}] {status}")
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n⛔ Stopped")
        
        elif args.point:
            # Read specific point
            try:
                model_id, point_name = args.point.split('.')
                model_id = int(model_id)
                
                # Use existing read infrastructure...
                print(f"Would read {model_id}.{point_name}")
                
            except ValueError:
                print("❌ Invalid point format. Use: model.point")
                sys.exit(1)
        
        else:
            # Default: scan all models
            print(f"Scanning {args.ip}...")
            # Call existing scan function...
            print("Use --scan to perform full scan")
    
    except Exception as e:
        logger.exception("Command failed")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
