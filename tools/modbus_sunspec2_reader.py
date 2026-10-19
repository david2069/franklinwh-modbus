#!/usr/bin/env python3
"""
SunSpec device reader using Modbus TCP.
Reads model information from a SunSpec-compatible device.
"""

import argparse
import sys
import struct
from typing import Dict, List, Optional, Tuple, Set
import json

# Check for required libraries
missing_libs = []

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
                missing_libs.append("pysunspec2")
                client = None

if missing_libs:
    print("Error: Missing required libraries:", file=sys.stderr)
    for lib in missing_libs:
        print(f"  - {lib}", file=sys.stderr)
    print("\nInstall with: pip install pysunspec2", file=sys.stderr)
    sys.exit(1)


def parse_model_spec(spec: str) -> Set[int]:
    """
    Parse model specification string into set of model IDs.
    
    Supports:
    - Single model: "101"
    - Multiple models: "1,101,103"
    - Range: "101-105"
    - Mixed: "1,101-103,160"
    
    Args:
        spec: Model specification string
        
    Returns:
        Set of model IDs
    """
    models = set()
    parts = spec.split(",")
    
    for part in parts:
        part = part.strip()
        if "-" in part:
            # Handle range
            try:
                start, end = part.split("-")
                start_id = int(start.strip())
                end_id = int(end.strip())
                models.update(range(start_id, end_id + 1))
            except ValueError:
                print(f"Warning: Invalid range format: {part}", file=sys.stderr)
        else:
            # Handle single model
            try:
                models.add(int(part))
            except ValueError:
                print(f"Warning: Invalid model ID: {part}", file=sys.stderr)
    
    return models


def get_model_points(model, device_base_address=0, verbose=False) -> List[Dict]:
    """
    Extract all points from a model with comprehensive metadata including
    register addresses. Supports repeating blocks.
    
    Args:
        model: SunSpec model instance
        device_base_address: Base address of the SunSpec device (usually 40000)
        verbose: Enable debug output
        
    Returns:
        List of point dictionaries with name, value, type, metadata, and
        register address
    """
    points = []
    
    blocks = getattr(model, "blocks", [model])
    
    # Track scale factor values to resolve them correctly across blocks
    sf_cache = {}
    for block in blocks:
        if hasattr(block, "points"):
            for p_name in block.points:
                p_obj = getattr(block, p_name, None)
                if p_obj is not None and getattr(p_obj, "value", None) is not None:
                    pdef = getattr(p_obj, "pdef", getattr(p_obj, "point_type", None))
                    if pdef:
                        def get_val_temp(key):
                            if isinstance(pdef, dict): return pdef.get(key)
                            return getattr(pdef, key, None)
                        if p_name.endswith("_SF") or get_val_temp("type") == "sunssf":
                            sf_cache[p_name] = p_obj.value

    for block_idx, block in enumerate(blocks):
        if not hasattr(block, "points"):
            continue
            
        # Get block base address if available
        block_base_addr = getattr(block, 'addr', None)
        if block_base_addr is None:
            block_base_addr = getattr(block, 'base_addr', None)
        if block_base_addr is None:
            block_base_addr = getattr(block, 'model_addr', None)
        
        # Calculate absolute block base address
        absolute_block_base_addr = block_base_addr
        if absolute_block_base_addr is not None and device_base_address > 0:
            if absolute_block_base_addr < device_base_address:
                # Assume it's an offset if significantly smaller than base
                absolute_block_base_addr += device_base_address
                
        for point_name in block.points:
            point = getattr(block, point_name, None)
            if point is None:
                continue
                
            # Format repeating block point names (e.g. DCW_2 for block 2)
            suffix = ""
            if len(blocks) > 1 and block_idx > 1:
                suffix = f"_{block_idx}"
            display_name = f"{point_name}{suffix}"
            
            point_info = {
                "name": display_name,
                "value": getattr(point, "value", None),
            }
            
            # Add register address information
            if hasattr(point, "addr") and point.addr is not None:
                 point_info["address"] = point.addr
            else: 
                 point_info["address"] = None

            if point_info.get("address") is None and hasattr(point, "offset"):
                # Calculate absolute address from block base + offset
                if absolute_block_base_addr is not None:
                    point_info["address"] = absolute_block_base_addr + point.offset
                point_info["offset"] = point.offset
            
            # Try to resolve metadata definition (pdef or point_type)
            pdef = getattr(point, "pdef", None)
            if pdef is None:
                pdef = getattr(point, "point_type", None)
            
            # Add comprehensive metadata if available
            if pdef:
                # Helper for object vs dict access
                def get_val(key):
                    if isinstance(pdef, dict): return pdef.get(key)
                    return getattr(pdef, key, None)

                # Offset within block
                offset = get_val("offset")
                if offset is not None:
                    point_info["offset"] = offset
                    if absolute_block_base_addr is not None and "address" not in point_info:
                        point_info["address"] = absolute_block_base_addr + offset
                
                # Basic attributes
                for key in ["type", "units", "label", "desc", "access", "mandatory", "min", "max", "default"]:
                    v = get_val(key)
                    if v is not None: point_info[key] = v
                
                # Scale factor information
                sf = get_val("sf")
                if sf:
                    point_info["scale_factor"] = sf
                    point_info["is_scale_factor"] = point_name.endswith("_SF")
                
                # Size in registers (16-bit words)
                size = get_val("size")
                if size:
                    point_info["size"] = size
                    # Calculate end address
                    if "address" in point_info:
                        point_info["address_end"] = point_info["address"] + size - 1
                
                # Symbols for enums and bitmaps
                symbols = get_val("symbols")
                if symbols:
                    try:
                        point_info["symbols"] = dict(symbols)
                        point_info["is_enum_or_bitmap"] = True
                    except (ValueError, TypeError):
                         pass
                    
                    # Try to resolve the value to its symbol meaning
                    if point_info.get("symbols") and point_info["value"] is not None:
                        try:
                            point_info["value_meaning"] = point_info["symbols"].get(
                                point_info["value"], "Unknown"
                            )
                        except (KeyError, TypeError):
                            pass
                
                # Detect bitmap types
                ptype = point_info.get("type")
                if ptype and "bitfield" in str(ptype).lower():
                    point_info["is_bitmap"] = True
            
            # Calculate scaled value if scale factor is available
            if "scale_factor" in point_info and point_info["scale_factor"]:
                sf_name = point_info["scale_factor"]
                sf_value = sf_cache.get(sf_name)
                if sf_value is None:
                    sf_point = getattr(model, sf_name, None)
                    if sf_point is not None:
                        sf_value = getattr(sf_point, "value", None)
                if sf_value is not None and point_info["value"] is not None:
                    try:
                        # Scaled value = value * 10^(scale_factor)
                        point_info["scaled_value"] = (
                            point_info["value"] * (10 ** sf_value)
                        )
                    except (TypeError, ValueError) as e:
                        pass
            
            points.append(point_info)
            
    return points

def read_sunspec_device(
    ip: str,
    port: int = 502,
    unit: int = 1,
    timeout: float = 2.0,
    base_address: int = 40000,
    models_to_scan: Optional[Set[int]] = None,
    detail_level: str = "basic",
    specific_point: Optional[str] = None,
    verbose: bool = False,
    raw_read_spec: Optional[str] = None,
    scan_models: bool = True,
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Read SunSpec device information via Modbus TCP.

    Args:
        ip: Device IP address
        port: Modbus TCP port
        unit: Modbus unit ID
        timeout: Connection timeout in seconds
        base_address: Starting Modbus address
        models_to_scan: Set of specific model IDs to scan (None = all)
        detail_level: Level of detail (minimal, basic, values, detailed, full)
        specific_point: Specific point name to extract (format: "model.point")
        verbose: Enable verbose output
        raw_read_spec: Modbus range to read (e.g. "15000:10")
        scan_models: Whether to scan/read SunSpec models (default True)

    Returns:
        Tuple of (device_info dict, error message)
    """
    try:
        if verbose:
            print(f"Connecting to {ip}:{port} (unit={unit}, "
                  f"base={base_address}, timeout={timeout}s)")

        # Create Modbus TCP client
        modbus_client = client.SunSpecModbusClientDeviceTCP(
            slave_id=unit,
            ipaddr=ip,
            ipport=port,
            timeout=timeout,
        )

        # Try different parameter names for scan method
        try:
            modbus_client.scan(base_addr=base_address)
        except TypeError:
            try:
                modbus_client.scan(base_address)
            except TypeError:
                try:
                    modbus_client.scan(address=base_address)
                except TypeError:
                    modbus_client.scan()

        device_info = {
            "ip": ip,
            "port": port,
            "unit": unit,
            "base_address": base_address,
        }

        # Handle specific point query
        if specific_point:
            try:
                model_id_str, point_name = specific_point.split(".", 1)
                model_id = int(model_id_str)
                
                model = modbus_client.models.get(model_id)
                if not model:
                    model = modbus_client.models.get(str(model_id))
                if not model:
                    return None, f"Model {model_id} not found"
                
                # Handle list of models (take first instance)
                if isinstance(model, list):
                    if len(model) == 0:
                        return None, f"Model {model_id} list is empty"
                    model = model[0]
                
                model.read()
                # ---------------  DEBUG  ---------------
                # print(f"DEBUG: after read()  model {model_id}  has points attr? {hasattr(model,'points')}")
                # if hasattr(model, 'points'):
                #     print(f"DEBUG: model.points = {list(model.points)}")
                # -------------  end DEBUG  ---------------
                
                point = getattr(model, point_name, None)
                if point is None:
                    return None, f"Point {point_name} not found in model {model_id}"
                
                device_info["specific_point"] = {
                    "model": model_id,
                    "point": point_name,
                    "value": getattr(point, "value", None),
                }
                
                if hasattr(point, "pdef"):
                    pdef = point.pdef
                    if hasattr(pdef, "type"):
                        device_info["specific_point"]["type"] = pdef.type
                    if hasattr(pdef, "units"):
                        device_info["specific_point"]["units"] = pdef.units
                
                return device_info, None
                
            except ValueError:
                return None, f"Invalid point format. Use 'model_id.point_name'"

        # Handle raw read spec
        if raw_read_spec:
            try:
                if ":" in raw_read_spec:
                    start_str, count_str = raw_read_spec.split(":")
                    start_addr = int(start_str)
                    count = int(count_str)
                else:
                    start_addr = int(raw_read_spec)
                    count = 1

                if verbose:
                    print(f"Reading raw registers: Start={start_addr}, Count={count}")
                
                # Ensure connected
                # modbus_client.connect() # typically handled by read implicitly but good to be safe if needed
                
                # Raw read (returns bytes)
                data_bytes = modbus_client.read(start_addr, count)
                
                if data_bytes:
                    device_info["raw_read"] = {
                        "start": start_addr,
                        "count": count,
                        "data": data_bytes
                    }
                    if not scan_models:
                         modbus_client.disconnect()
                         return device_info, None
                else:
                    if not scan_models:
                        modbus_client.disconnect()
                        return None, "No data returned (None)"
            except Exception as e:
                modbus_client.disconnect()
                return None, f"Raw read failed: {str(e)}"

        if not scan_models:
            modbus_client.disconnect()
            return device_info, None

        # keep both numeric and string keys
        raw_models = list(modbus_client.models.keys())
        numeric_models, string_keys = [], []
        for k in raw_models:
            try:
                numeric_models.append(int(k))
            except (ValueError, TypeError):
                string_keys.append(str(k))
        device_info["_raw_keys"] = raw_models   # save originals for --map
        available_models = numeric_models       # rest of code unchanged
        
        if models_to_scan:
            # Only read specified models that exist
            models_to_read = [m for m in models_to_scan if m in available_models]
            if verbose:
                missing = models_to_scan - set(available_models)
                if missing:
                    print(f"Requested models not found: {sorted(missing)}")
        else:
            models_to_read = available_models

        if not models_to_read:
            return None, "No models found to read"

        device_info["models"] = {}

        # Build identity map for model aliases (same layout as scan_modbus2.py)
        identity_map = {}
        for k, v in modbus_client.models.items():
            if isinstance(v, list):
                v = v[0] if v else None
            if v and isinstance(k, str) and not k.isdigit():
                identity_map[id(v)] = k

        # Read each model based on detail level
        for model_id in sorted(models_to_read):
            # Try to get model with both int and str keys
            model_obj = modbus_client.models.get(model_id)
            if model_obj is None:
                model_obj = modbus_client.models.get(str(model_id))
            if model_obj is None:
                if verbose:
                    print(f"Warning: Could not access model {model_id}")
                continue
            
            # Handle list of models (multiple instances)
            models_list = [model_obj] if not isinstance(model_obj, list) else model_obj
            
            # Process each instance (if multiple, we'll add suffix to key)
            for idx, model in enumerate(models_list):
                model.read()
                
                # Create unique key for multiple instances
                model_key = model_id if len(models_list) == 1 else f"{model_id}_{idx}"
                model_info = {"id": model_id, "instance": idx}

                # Determine model name/label
                name = "Unknown"
                if hasattr(model, "model_type") and getattr(model.model_type, "label", None):
                    name = model.model_type.label
                
                # Fallback to alias if name is Unknown or numeric
                if name == "Unknown" or str(name).isdigit():
                    name = identity_map.get(id(model), name)
                
                # print(f"DEBUG: Model {model_id} resolved name: {name}")
                model_info["name"] = name
                
                # Minimal: just model ID and name
                if detail_level == "minimal":
                    device_info["models"][model_key] = model_info
                    continue
                
                # Basic: ID, name, and key info for Model 1
                if detail_level == "basic":
                    # Add common model info
                    if model_id == 1:
                        model_info["manufacturer"] = getattr(model, "Mn", "Unknown")
                        model_info["model"] = getattr(model, "Md", "Unknown")
                        model_info["version"] = getattr(model, "Vr", "Unknown")
                        model_info["serial"] = getattr(model, "SN", "Unknown")
                    
                    device_info["models"][model_key] = model_info
                    continue
                
                if detail_level == "values":
                    # Pass verbose flag to enable debug
                    model_info["points"] = get_model_points(model, device_base_address=base_address, verbose=verbose)   
                    device_info["models"][model_key] = model_info
                    continue

                
                # Detailed: Add point names and values
                if detail_level == "detailed":
                    if hasattr(model, "model_type"):
                        model_info["name"] = model.model_type.label
                    
                    points = {}
                    for point_name in model.points:
                        point = getattr(model, point_name, None)
                        if point is not None:
                            points[point_name] = getattr(point, "value", None)
                    
                    model_info["points"] = points
                    device_info["models"][model_key] = model_info
                    continue
                
                # Full: everything including metadata
                # Full: everything including metadata
                if detail_level == "full":
                    # Pass verbose flag to enable debug
                    model_info["points"] = get_model_points(model, device_base_address=base_address, verbose=verbose)   
                    device_info["models"][model_key] = model_info
                    continue
        modbus_client.disconnect()
        return device_info, None

    except Exception as e:
        return None, str(e)

def print_device_info(
    info: Dict, detail_level: str,
    compact: bool = False, map_mode: bool = False, show_vals: bool = False,
    show_nonzero: bool = False, do_match: bool = False
) -> None:
    if compact:
        # collect numeric model ids (ignore string keys like 'common')
        ids = sorted(int(str(k).split('_')[0])
                    for k in info.get("models", {})
                    if str(k).split('_')[0].isdigit())
        # collapse consecutive numbers into ranges   1-3, 5, 7-9
        out, start, prev = [], None, None
        for i in ids + [None]:          # None is a sentinel
            if start is None:          # first iter
                start = prev = i
                continue
            if i == prev + 1:            # still consecutive
                prev = i
                continue
            # emit accumulated range
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = i
        print("Models:", ",".join(out))
        return

    if map_mode:
        raw = info.get("_raw_keys", [])
        pairs = zip(raw[::2], raw[1::2])          # (id, alias) tuples
        print("ID   Alias")
        for mid, alias in sorted(pairs, key=lambda x: x[0]):
            print(f"{mid:<4} {alias}")
        return
    if show_vals:
        # print(f"DEBUG show_vals block entered, models found: {list(info.get('models', {}).keys())}")
        for model_key in sorted(info.get("models", {})):
            model = info["models"][model_key]
            # print(f"DEBUG keys: {model.keys()}, name value: {model.get('name')}")
            points = model.get("points", [])
            model_name = model.get("name")
            print(f"\nModel {model_key}{': ' + model_name if model_name else ''}")
            
            # Special formatting for Common Model 1 (Detailed strings)
            if str(model_key) == "1":
                print(f"{'Addr':<6} {'Name':<10} {'Label':<22} {'Value':<45} {'RW':<2} {'Type'}")
                print("-" * 100)
                
                for p in points:
                    addr = p.get("address", "")
                    name = p["name"]
                    label = p.get("label", "")[:22]
                    access = p.get("access", "R")
                    if isinstance(access, str):
                        access = access.upper()
                    
                    raw = p.get("value", "None")
                    typ = p.get("type", "")
                    val_str = str(raw)
                    
                    print(f"{addr:<6} {name:<10} {label:<22} {val_str:<45} {access:<2} {typ}")
                continue

            # Header
            print(f"{'Addr':<6} {'Name':<20} {'Label':<25} {'Value':>10}  {'Units':<8} {'F':<3} {'RW':<2} {'Raw':<10} {'Type'}")
            print("-" * 105)

            for p in points:
                if not isinstance(p, dict):
                    continue
                addr = p.get("address", "")
                name = p["name"]
                # Default to empty if missing
                label = p.get("label", "")[:25]  # Truncate if too long
                access = p.get("access", "R")
                if isinstance(access, str):
                    access = access.upper()
                
                raw  = p.get("value", "None")
                sf   = p.get("scale_factor")
                scaled = p.get("scaled_value", raw)
                units = p.get("units", "")
                typ   = p.get("type", "")
                
                if isinstance(scaled, float):
                    scaled = f"{scaled:g}"
                
                marker = "S" if sf else ""
                
                # Format columns
                val_str = str(scaled)
                units_str = f"{units}" if units else ""
                raw_str = str(raw)
                typ_str = f"{typ}" if typ else ""
                
                # Highlight if raw != val
                raw_display = raw_str
                if raw == scaled or (isinstance(raw, int) and str(raw) == val_str):
                     raw_display = "-"
                
                print(f"{addr:<6} {name:<20} {label:<25} {val_str:>10}  {units_str:<8} {marker:<3} {access:<2} {raw_display:<10} {typ_str}")
        return
    
    """Print formatted device information with full metadata."""
    print("\n" + "=" * 70)
    print(f"Device: {info['ip']}:{info['port']}")
    print("=" * 70)
    print(f"Unit ID:        {info['unit']}")
    print(f"Base Address:   {info['base_address']}")

    # Handle specific point query
    if "specific_point" in info:
        point = info["specific_point"]
        print("\n" + "-" * 70)
        print(f"Point Query: Model {point['model']}.{point['point']}")
        print("-" * 70)
        print(f"Value:          {point['value']}")
        if "type" in point:
            print(f"Type:           {point['type']}")
        if "units" in point:
            print(f"Units:          {point['units']}")
        print("=" * 70)
        return
    
    # Handle Raw Read
    if "raw_read" in info:
        rr = info["raw_read"]
        start = rr["start"]
        count = rr["count"]
        data = rr["data"]
        
        # Build Match Lookup if requested
        match_db = {} # value -> list(description strings)
        if do_match and "models" in info:
            print(f"Building match database from {len(info['models'])} models...")
            count_pts = 0
            for mk, m_data in info['models'].items():
                pts = m_data.get("points", [])
                # If pts is dict, convert to list
                if isinstance(pts, dict):
                    pts_iter = [{"name": k, "value": v} for k,v in pts.items()]
                else:
                    pts_iter = pts
                
                for p in pts_iter:
                    # Capture both raw value and scaled value
                    p_name = p.get("name", "?")
                    p_val_raw = p.get("value")
                    p_val_scaled = p.get("scaled_value")
                    
                    # Helper to add to db
                    def add_match(val, type_label):
                        if val is None: return
                        # Normalize types for comparison: strings, ints, floats
                        # We store as string, int, and float if applicable
                        vs = [val]
                        try:
                            if isinstance(val, (int, float)):
                                vs.append(str(val))
                                if isinstance(val, int):
                                    vs.append(float(val))
                                elif isinstance(val, float) and val.is_integer():
                                    vs.append(int(val))
                        except: pass
                        
                        for v in vs:
                            if v not in match_db: match_db[v] = []
                            desc = f"{mk}.{p_name} ({type_label})"
                            if desc not in match_db[v]:
                                match_db[v].append(desc)

                    # Ignore strict 0 or 1 matches? They are too common.
                    # User request: "duplication for some reason". So maybe include them but user knows they are noisy.
                    # Let's include everything but maybe filter at display time or just let it be verbose.
                    # But 0 matches 1500 fields. That's useless.
                    # Let's skip 0, 1, -1 for matching unless it's a very specific float?
                    # No, let's just skip 0. '1' might be significant (e.g. enable).
                    
                    if p_val_raw not in [0, 1, -1, 65535, 32768, "0", "1"]:
                         add_match(p_val_raw, "raw")
                    
                    if p_val_scaled != p_val_raw and p_val_scaled != 0 and p_val_scaled != "0":
                         add_match(p_val_scaled, "scaled")
                    count_pts += 1
            print(f"Database built: {len(match_db)} unique values from {count_pts} points.")

        print("\n" + "=" * 80)
        print(f"Raw Read: Start {start}, Count {count}")
        print("-" * 80)
        print(f"{'Addr':<8} {'Hex':<6} {'UInt16':<8} {'Int16':<8} {'Value':<15} {'Acc':<3} {'Bits (Binary)':<18} {'Guess/Notes'}")
        print("-" * 110)
        
        # Define known Franklin/SPAN registers for decoding with permissions
        # ID: (Name, Units/Type, Access)
        known_map = {
            # (ShortName, DescriptiveName, Units/Type, Access)
            15500: ("PVUse", "PV Installed", "enum:0=NotUsed,1=Used", "R"),
            15501: ("apBoxPVUse", "Remote PV Installed", "enum:0=NotUsed,1=Used", "R"),
            15502: ("PVOutputP", "PV Total Power", "W", "R"),
            15503: ("proximalPVOutputP", "PV Proximal Power", "W", "R"),
            15504: ("Remote1PV", "PV Remote 1 Power", "W", "R"),
            15505: ("Remote2PV", "PV Remote 2 Power", "W", "R"),
            15506: ("LoadActiveP", "Home Load", "W", "R"),
            15507: ("OnGridMode", "Operating Mode", "enum:1=Backup,2=Self,3=TOU", "RW"),
            15508: ("SelfReserve", "Self-Consumption SOC Reserve", "%", "RW"),
            15509: ("TouReserve", "TOU SOC Reserve", "%", "RW"),
            15510: ("PVOutputWh", "PV Energy Total", "uint32", "R"),
            15512: ("proximalOutputWh", "PV Energy Proximal", "uint32", "R"),
            # 15514?
        }
        
        # Unpack as uint16s
        # data is bytes. 2 bytes per register. big endian standard modbus
        
        regs = []
        for i in range(0, len(data), 2):
            if i + 2 <= len(data):
                regs.append(struct.unpack(">H", data[i:i+2])[0])
        
        skip_next = False
        
        for idx, val_uint16 in enumerate(regs):
            addr = start + idx
            
            if skip_next:
                skip_next = False
                continue
                
            val_int16 = struct.unpack(">h", struct.pack(">H", val_uint16))[0]
            hex_str = f"{val_uint16:04X}"
            bin_str = f"{val_uint16:016b}"
            
            note = ""
            access_str = ""
            
            # Default to signed integer for the Value column unless known otherwise
            final_val_str = str(val_int16)
            
            val32 = None # for matching
            
            # Check for known map
            if addr in known_map:
                short_name, desc_name, units, access = known_map[addr]
                access_str = access
                
                # Refine Value based on type
                if "uint" in units or "enum" in units:
                    final_val_str = str(val_uint16)
                
                # handle 32-bit types
                if units == "uint32" and idx + 1 < len(regs):
                    low_word = regs[idx+1]
                    val32 = (val_uint16 << 16) | regs[idx+1]
                    final_val_str = str(val32)
                    note = f"{desc_name} ({short_name})"
                    
                    # Perform Match on val32 if enabled
                    if do_match and val32 != 0:
                         matches = match_db.get(val32, [])
                         matches += match_db.get(str(val32), [])
                         # Deduplicate
                         matches = sorted(list(set(matches)))
                         if matches:
                             # Limit output
                             match_str = ", ".join(matches[:3])
                             if len(matches) > 3: match_str += "..."
                             note += f" [Matches: {match_str}]"
                    
                    print(f"{addr:<8} {hex_str:<6} {val_uint16:<8} {val_int16:<8} {final_val_str:<15} {access_str:<3} {bin_str:<18} {note} (High Word)")
                    
                    # Print next line as Low Word
                    addr_next = addr + 1
                    hex_next = f"{regs[idx+1]:04X}"
                    print(f"{addr_next:<8} {hex_next:<6} {regs[idx+1]:<8} {'-':<8} {'-':<15} {'-':<3} {'-':<18}   -> Low Word")
                    skip_next = True
                    continue
                else:
                    note = f"{desc_name} ({short_name})"
                    if units and not units.startswith("enum") and not units.startswith("uint"):
                        note += f" {units}"
                    elif "enum" in units:
                        # Value is in the column, just append the enum meaning to note
                        part = units.split(':')[1] # 0=NotUsed,1=Used
                        pairs = part.split(',')
                        meaning = ""
                        for pair in pairs:
                            k, v = pair.split('=')
                            # Check against both signed and unsigned string representation just in case
                            if str(val_uint16) == k or str(val_int16) == k:
                                meaning = v
                                break
                        if meaning:
                            note += f" ({meaning})"
                        else:
                            note += f" ({part})"

            # Check filtering
            if show_nonzero:
                # Filter if the value is effectively zero (both as unsigned and signed)
                # and no 32-bit combination happened that was non-zero
                if val_uint16 == 0 and val_int16 == 0 and final_val_str in ["0", "0.0"]:
                    pass
                    continue
            
            # Perform Match for non-32bit values
            if do_match:
                 # Try matching uint16, int16
                 # We avoid 0
                 vals_to_check = []
                 if val_uint16 != 0: vals_to_check.append(val_uint16)
                 if val_int16 != 0 and val_int16 != val_uint16: vals_to_check.append(val_int16)
                 
                 found_matches = []
                 for v in vals_to_check:
                     ms = match_db.get(v, []) + match_db.get(str(v), [])
                     for m in ms:
                         if m not in found_matches: found_matches.append(m)
                 
                 if found_matches:
                        match_str = ", ".join(sorted(found_matches)[:2]) # show fewer for single reg
                        if len(found_matches) > 2: match_str += "..."
                        if note: note += f" "
                        note += f"[Matches: {match_str}]"


            print(f"{addr:<8} {hex_str:<6} {val_uint16:<8} {val_int16:<8} {final_val_str:<15} {access_str:<3} {bin_str:<18} {note}")
            
        return
    print(f"\nModels Found:   {len(info['models'])}")
    
    for model_id in sorted(info['models'].keys()):
        model = info['models'][model_id]
        print("\n" + "-" * 70)
        print(f"Model {model_id}", end="")
        if "name" in model:
            print(f": {model['name']}", end="")
        if "instance" in model and model["instance"] > 0:
            print(f" (Instance {model['instance']})", end="")
        print()
        print("-" * 70)
        
        if detail_level == "minimal":
            continue
        
        # Print basic info for Model 1
        if model_id == 1 and detail_level in ["basic", "values", "detailed", "full"]:
            for key in ["manufacturer", "model", "version", "serial"]:
                if key in model:
                    print(f"{key.capitalize():15} {model[key]}")
        
        # Print points
        if "points" in model:
            # Values detail level - formatted current values with types
            if detail_level == "values":
                # Handle both list (new format) and dict (old format)
                points_list = model["points"] if isinstance(model["points"], list) else []
                
                print(f"\nPoints: {len(points_list)}")
                for point in points_list:
                    # Skip if no name
                    if "name" not in point:
                        continue
                    
                    # Build the display value with proper formatting
                    display_parts = []
                    
                    # Determine which value to show (scaled if available)
                    if "scaled_value" in point and point["scaled_value"] is not None:
                        # Format scaled value nicely
                        scaled = point["scaled_value"]
                        if isinstance(scaled, float):
                            # Show appropriate decimal places
                            if abs(scaled) >= 100:
                                value_str = f"{scaled:.1f}"
                            elif abs(scaled) >= 10:
                                value_str = f"{scaled:.2f}"
                            else:
                                value_str = f"{scaled:.3f}"
                        else:
                            value_str = str(scaled)
                        display_parts.append(value_str)
                    else:
                        # Show raw value
                        value_str = str(point.get("value", "None"))
                        display_parts.append(value_str)
                    
                    # Add units if present
                    if "units" in point and point["units"]:
                        display_parts.append(point["units"])
                    
                    # Add value meaning for enums
                    if "value_meaning" in point:
                        display_parts.append(f"[{point['value_meaning']}]")
                    
                    # Build type string
                    type_parts = []
                    if "type" in point:
                        type_parts.append(str(point["type"]))
                    if point.get("is_scale_factor"):
                        type_parts.append("SF")
                    
                    type_str = f"({', '.join(type_parts)})" if type_parts else ""
                    
                    
                    # Format output line
                    value_display = " ".join(display_parts)
                    addr_str = str(point.get("address", ""))
                    print(f"  {addr_str:<6} {point['name']:30} = {value_display:25} {type_str}")
            
            # Detailed: simple point names and values
            elif detail_level == "detailed":
                # Handle dict format for detailed
                if isinstance(model["points"], dict):
                    print(f"\nPoints: {len(model['points'])}")
                    for name, value in model["points"].items():
                        print(f"  {name:30} = {value}")
                else:
                    # List format
                    print(f"\nPoints: {len(model['points'])}")
                    for point in model["points"]:
                        if "name" in point:
                            print(f"  {point['name']:30} = {point.get('value', 'None')}")
            
            # Full: all metadata
            elif detail_level == "full":
                points_list = model["points"] if isinstance(model["points"], list) else []
                print(f"\nPoints: {len(points_list)}")
                for point in points_list:
                    if "name" not in point:
                        continue
                        
                    print(f"\n  {point['name']}:")
                    
                    # Register address information (first, most important)
                    if "address" in point:
                        addr_str = f"{point['address']}"
                        if "address_end" in point and point["address_end"] != point["address"]:
                            addr_str += f"-{point['address_end']}"
                        print(f"    Address:    {addr_str}")
                    elif "offset" in point:
                        print(f"    Offset:     {point['offset']}")
                    
                    # Value
                    print(f"    Value:      {point.get('value', 'None')}")
                    
                    # Type and basic attributes
                    if "type" in point:
                        print(f"    Type:       {point['type']}")
                    if "size" in point:
                        print(f"    Size:       {point['size']} registers")
                    
                    # Units and scaling
                    if "units" in point:
                        print(f"    Units:      {point['units']}")
                    if "scaled_value" in point:
                        print(f"    Scaled:     {point['scaled_value']}")
                    if "scale_factor" in point:
                        print(f"    Scale By:   {point['scale_factor']}")
                    if point.get("is_scale_factor"):
                        print(f"    Role:       Scale Factor")
                    
                    # Labels and descriptions
                    if "label" in point:
                        print(f"    Label:      {point['label']}")
                    if "desc" in point:
                        print(f"    Desc:       {point['desc']}")
                    
                    # Access and requirements
                    if "access" in point:
                        print(f"    Access:     {point['access']}")
                    if "mandatory" in point:
                        req = "Mandatory" if point["mandatory"] else "Optional"
                        print(f"    Required:   {req}")
                    
                    # Value constraints
                    if "min" in point:
                        print(f"    Min:        {point['min']}")
                    if "max" in point:
                        print(f"    Max:        {point['max']}")
                    if "default" in point:
                        print(f"    Default:    {point['default']}")
                    
                    # Enums and bitmaps
                    if point.get("is_enum_or_bitmap") and "symbols" in point:
                        print(f"    Symbols:    (enum/bitmap)")
                        if point["symbols"]:
                            for sym_key, sym_val in sorted(
                                point["symbols"].items()
                            ):
                                indicator = " *" if sym_key == point.get("value") else ""
                                print(f"      {sym_key}: {sym_val}{indicator}")
                    
                    if "value_meaning" in point:
                        print(f"    Meaning:    {point['value_meaning']}")
                    
                    if point.get("is_bitmap"):
                        print(f"    Type:       Bitmap/Bitfield")
    
    print("\n" + "=" * 70)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Read SunSpec device information via Modbus TCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
epilog="""
Detail Levels:
  minimal   - Model IDs and names only
  basic     - Model info + common model (Model 1) details (default)
  values    - Current values with datatypes and units in brackets
  detailed  - All point names and raw values
  full      - All points with complete metadata (type, units, labels, etc.)

Model Specification Examples:
  -m 1              - Read only Model 1
  -m 1,101,103      - Read Models 1, 101, and 103
  -m 101-105        - Read Models 101 through 105
  -m 1,101-103,160  - Mixed: Models 1, 101-103, and 160
  (omit -m to scan all available models)

Point Query Example:
  --point 1.Mn      - Read Manufacturer (Mn) from Model 1
  --point 103.W     - Read Watts (W) from Model 103 (Inverter)
""",
    )

    parser.add_argument(
        "-i", "--ip", 
        type=str, 
        required=True,
        help="Device IP address"
    )
    parser.add_argument(
        "-p", "--port", 
        type=int, 
        default=502, 
        help="Modbus TCP port (default: 502)"
    )
    parser.add_argument(
        "-u", "--unit", 
        type=int, 
        default=1, 
        help="Modbus unit ID (default: 1)"
    )
    parser.add_argument(
        "-b",
        "--base-address",
        type=int,
        default=40000,
        help="Base Modbus address (default: 40000)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=2.0,
        help="Connection timeout in seconds (default: 2.0)",
    )
    parser.add_argument(
        "-m",
        "--models",
        type=str,
        help="Models to scan (e.g., '1,101,103' or '101-105' or '1,101-103,160')",
    )
    parser.add_argument(
        "-d",
        "--detail",
        type=str,
        choices=["minimal", "basic", "values", "detailed", "full"],
        default="basic",
        help="Detail level (default: basic)",
    )
    parser.add_argument(
        "--point",
        type=str,
        help="Query specific point (format: 'model_id.point_name', e.g., '1.Mn')",
    )
    parser.add_argument(
        "--raw",
        type=str,
        help="Read raw registers (format: 'start:count', e.g., '15500:14')",
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--multi-thread",
        action="store_true",
        help="Enable multi-threading (currently single device only)",
    )
    parser.add_argument(
        "--compact", 
        "-c",
        action="store_true",
        help="One-line summary of model IDs (no headers, no empty sections)",
    )
    parser.add_argument(
        "--map",
        action="store_true",
        help="Columnar list: model-id  string-key",
    )
    parser.add_argument(
        "--vals",
        action="store_true",
        help="One-liner per point: name = scaled-value [units] (type)",
    )
    parser.add_argument(
        "--nz",
        action="store_true",
        help="Only show non-zero values in raw read"
    )
    parser.add_argument(
        "--match",
        action="store_true",
        help="Try to match raw values with known model points (forces full scan)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    args = parser.parse_args()

    # Force detail level 'values' if matching is requested
    if args.match and args.detail in ["minimal", "basic"]:
        if args.verbose:
            print("Upgrading detail level to 'values' to support matching")
        args.detail = "values"

    if args.multi_thread:
        print("Note: Multi-threading for single device read has no effect")

    # Parse model specification
    models_to_scan = None
    if args.models:
        models_to_scan = parse_model_spec(args.models)
        if args.verbose:
            print(f"Scanning for models: {sorted(models_to_scan)}")

    # Determine if we should scan models
    # Default is True, but if raw read is requested without explicit model instructions,
    # we default to False to keep it fast/focused, unless --match is used.
    should_scan_models = True
    if args.raw and not args.models and not args.match:
        should_scan_models = False

    # Read device
    device_info, error = read_sunspec_device(
        ip=args.ip,
        port=args.port,
        unit=args.unit,
        timeout=args.timeout,
        base_address=args.base_address,
        models_to_scan=models_to_scan,
        detail_level=args.detail,
        specific_point=args.point,
        verbose=args.verbose,
        raw_read_spec=args.raw,
        scan_models=should_scan_models
    )

    if error:
        if args.json:
             print(json.dumps({"error": error}), file=sys.stdout)
        else:
             print(f"Error reading device {args.ip}:{args.port} - {error}", file=sys.stderr)
        sys.exit(1)

    if device_info:
        if args.json:
            import json
            # Helper for bytes serialization
            def json_serial(obj):
                if isinstance(obj, bytes):
                    return obj.hex()
                return str(obj)
            print(json.dumps(device_info, indent=2, default=json_serial))
        else:
            print_device_info(
                device_info, 
                args.detail, 
                args.compact, 
                args.map, 
                args.vals, 
                show_nonzero=args.nz,
                do_match=args.match
            ) 
        sys.exit(0)
    else:
        if args.json:
             print(json.dumps({"error": "No device found"}), file=sys.stdout)
        else:
             print(f"No SunSpec device found at {args.ip}:{args.port}", file=sys.stderr)
        sys.exit(1)




if __name__ == "__main__":
    main()
