"""
SunSpec InfoPoint Sequencer
Executes deterministic sequences of SunSpec register operations with verification.
"""

import logging
import time
import struct
from typing import Dict, List, Any, Optional, Tuple
from .constants import EXTENSION_REGISTRY

try:
    import sunspec2.modbus.client as client
except ImportError:
    client = None

logger = logging.getLogger(__name__)

class TransitionValidationError(Exception):
    """Raised when a mandatory state transition is not observed."""
    pass

class SunSpecSequencer:
    """Orchestrates multi-step SunSpec operations."""
    
    def __init__(self, device: Any, base_address: int = 0):
        """
        Initialize with a sunspec2 device object.
        
        Args:
            device: An instance of SunSpecModbusClientDeviceTCP (or similar)
                   that has already been scanned.
            base_address: The starting Modbus address used for scanning.
        """
        self.device = device
        self.base_address = base_address
        self.verbose = False

    def _raw_socket(self):
        """Return a connected socket for raw-address access, or None.

        pysunspec2 closes the socket after a scan, so connect first
        (as the controller's raw helpers do).
        """
        client_obj = getattr(self.device, 'client', None)
        if client_obj is None:
            return None
        try:
            client_obj.connect()
        except Exception as e:
            logger.error(f"  Raw access: connect failed: {e}")
            return None
        return client_obj.socket

    def _raw_write(self, sock, addr: int, raw_val: int, reg_type: str) -> bool:
        """Write one raw register (FC06) or a 32-bit pair (FC16). True on a normal response."""
        unit_id = getattr(self.device, 'slave_id', 1)
        if reg_type in ('uint32', 'int32'):
            fmt = '>I' if reg_type == 'uint32' else '>i'
            req = struct.pack('>HHHBBHHB', 0, 0, 11, unit_id, 16, addr, 2, 4) + struct.pack(fmt, raw_val)
            func = 16
        else:
            req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 6, addr, int(raw_val))
            func = 6
        sock.sendall(req)
        resp = sock.recv(256)
        if len(resp) < 12 or resp[7] != func:
            logger.error(f"  ✗ Raw write to {addr} failed (Response: {resp.hex()})")
            return False
        return True

    def get_point(self, tag: Any) -> Tuple[Optional[Any], Any]:
        """Resolve 'Model.Point', 'RawAddress' tag, or a config dict."""
        tag_str = tag
        if isinstance(tag, dict):
            tag_str = str(tag.get('point', tag.get('addr', tag.get('address', ''))))

        if '.' not in tag_str:
            # Assume raw address
            try:
                addr = int(tag_str)
                return None, addr
            except ValueError:
                raise ValueError(f"Invalid tag format '{tag}'. Use 'ModelID.PointName' or 'Address'")

        try:
            model_id_str, point_name = tag_str.split('.')
            model_id = int(model_id_str)
        except ValueError:
            raise ValueError(f"Invalid tag format '{tag_str}'. Use 'ModelID.PointName' (e.g. 704.WSetPct)")

        model = self.device.models.get(model_id)
        if model is None:
            model = self.device.models.get(str(model_id))
        
        if model is None:
            raise ValueError(f"Model {model_id} not found on device")
        
        if isinstance(model, list):
            model = model[0]
            
        # Parse potential block index suffix (e.g. "DCW_2")
        block_idx = 1
        base_point_name = point_name
        has_suffix = False
        if '_' in point_name:
            parts = point_name.rsplit('_', 1)
            if parts[1].isdigit():
                block_idx = int(parts[1])
                base_point_name = parts[0]
                has_suffix = True
                
        # Resolve the point object
        point = None
        if has_suffix and hasattr(model, 'blocks') and block_idx < len(model.blocks):
            point = getattr(model.blocks[block_idx], base_point_name, None)
        else:
            point = getattr(model, point_name, None)
            
        if point is None:
            raise ValueError(f"Point '{point_name}' not found in Model {model_id}")
            
        return model, point

    def get_point_val(self, model: Any, point: Any) -> Any:
        """Helper to get scaled value from a point."""
        val = point.value
        if val is None:
            return None
            
        # Robust point definition attribute access
        pdef = point.pdef
        def get_attr(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)
            
        sf_name = get_attr(pdef, 'sf')
        if sf_name:
            sf_point = getattr(model, sf_name, None)
            if sf_point:
                sf_val = sf_point.value
                if sf_val is not None:
                    # Apply scale factor: value * 10^sf
                    return val * (10 ** sf_val)
        return val

    def read_value(self, tag: Any) -> Any:
        model, point = self.get_point(tag)
        if model is None:
            # Raw address read - Uses raw socket to bypass sunspec2 remapping
            addr = point
            
            # Determine properties: check inline dict, then registry defaults
            reg_config = {}
            if isinstance(tag, dict):
                reg_config = tag
            else:
                reg_config = EXTENSION_REGISTRY.get(addr, {})
                
            reg_type = reg_config.get('type', 'uint16')
            sf = reg_config.get('sf', 0)
            count = 2 if reg_type in ('uint32', 'int32') else 1
            
            sock = self._raw_socket()
            if sock:
                try:
                    unit_id = getattr(self.device, 'slave_id', 1)
                    # Raw Modbus TCP: Transaction(2) Protocol(2) Length(2) Unit(1) Func(1) Addr(2) Count(2)
                    req = struct.pack('>HHHBBHH', 0, 0, 6, unit_id, 3, addr, count)
                    sock.sendall(req)
                    resp = sock.recv(256)
                    if len(resp) >= 9 + count * 2: # 9 header + data
                        data_bytes = resp[9:9+count*2]
                        if reg_type == 'uint32':
                            raw_val = struct.unpack('>I', data_bytes)[0]
                        elif reg_type == 'int32':
                            raw_val = struct.unpack('>i', data_bytes)[0]
                        elif reg_type == 'int16':
                            raw_val = struct.unpack('>h', data_bytes)[0]
                        else: # uint16
                            raw_val = struct.unpack('>H', data_bytes)[0]
                        
                        return raw_val * (10 ** sf) if sf else raw_val
                except Exception as e:
                    logger.debug(f"Raw socket read at {addr} failed: {e}")
            return None

        model.read()
        return self.get_point_val(model, point)

    def write_value(self, tag: Any, human_val: Any) -> Any:
        """Write a value, applying scale factor conversion if needed."""
        model, point = self.get_point(tag)
        
        if model is None:
            # Raw address write
            addr = point
            
            # Determine properties
            reg_config = {}
            actual_val = human_val
            if isinstance(tag, dict):
                reg_config = tag
            elif isinstance(human_val, dict):
                reg_config = human_val
                actual_val = human_val.get('value')
                
            if not reg_config:
                reg_config = EXTENSION_REGISTRY.get(addr, {})
                
            reg_type = reg_config.get('type', 'uint16')
            sf = reg_config.get('sf', 0)
            
            raw_val = actual_val
            if sf:
                raw_val = int(actual_val / (10 ** sf))
            else:
                raw_val = int(actual_val)
                
            sock = self._raw_socket()
            if sock:
                try:
                    if self._raw_write(sock, addr, raw_val, reg_type):
                        return actual_val
                except Exception as e:
                    logger.error(f"  ✗ Raw write at {addr} failed: {e}")
            return None

        raw_val = human_val
        pdef = point.pdef
        
        def get_attr(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)
            
        sf_name = get_attr(pdef, 'sf')
        if sf_name:
            sf_point = getattr(model, sf_name, None)
            if sf_point:
                model.read() # Ensure we have the latest SF
                sf_val = sf_point.value
                if sf_val is not None:
                    # Inverse scale factor: raw = human / 10^sf
                    raw_val = int(human_val / (10 ** sf_val))
                    
        point.value = raw_val
        model.write()
        return raw_val

    def run_sequence(self, sequence: List[Dict[str, Any]], dry_run: bool = False) -> bool:
        """Execute a list of step dictionaries."""
        total_steps = len(sequence)
        logger.info(f"Starting sequence with {total_steps} steps...")
        
        for i, step in enumerate(sequence):
            step_name = step.get('name', step.get('step', f"Step {i+1}"))
            logger.info(f"\n--- [{i+1}/{total_steps}] {step_name} ---")
            
            # 1. Handle Writes
            writes = step.get('writes', {})
            if writes:
                if not self.execute_writes(writes, step, dry_run):
                    if step.get('abort_on_failure', True):
                        logger.error(f"Aborting sequence due to write failure in '{step_name}'")
                        return False

            # 2. Handle Wait For (Polling Loop)
            wait_for = step.get('wait_for')
            if wait_for:
                if not self.execute_wait_for(wait_for, step_name):
                    if step.get('abort_on_failure', True):
                        logger.error(f"Aborting sequence due to wait condition failure in '{step_name}'")
                        return False

            # 3. Handle Reads
            reads = step.get('reads', [])
            if reads:
                self.execute_reads(reads)

            # 4. Handle Sleep
            sleep_ms = step.get('sleep_ms', step.get('post_sleep_ms', 0))
            if sleep_ms > 0:
                logger.info(f"Sleeping for {sleep_ms}ms...")
                time.sleep(sleep_ms / 1000.0)
            
            # Step completion summary (especially useful if logs are suppressed)
            if logger.level > logging.INFO:
                print(f"DONE: {step_name}")

        logger.info("\nSequence complete.")
        return True

    def execute_writes(self, writes: Dict[str, Any], step: Dict[str, Any], dry_run: bool) -> bool:
        verify = step.get('verify', True)
        timeout_ms = step.get('verify_timeout_ms', 2000)
        
        # Capture "Before" state
        before_vals = {}
        for tag in writes:
            try:
                before_vals[tag] = self.read_value(tag)
            except Exception as e:
                logger.warning(f"  Could not read initial value for {tag}: {e}")
                before_vals[tag] = "Unknown"

        if dry_run:
            for tag, val in writes.items():
                compare_val = val.get('value') if isinstance(val, dict) else val
                logger.info(f"  [DRY RUN] Would write {tag}: {before_vals[tag]} -> {compare_val}")
            return True

        # Perform writes (grouped by model for efficiency)
        models_to_write = {}
        write_attempted = {} # Tracks which tags actually triggered a Modbus write
        
        def get_attr(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)

        require_transition = step.get('require_transition', False)

        for tag, val in writes.items():
            compare_val = val.get('value') if isinstance(val, dict) else val
            initial = before_vals.get(tag)
            
            # Mandatory State Transition Validation
            if require_transition and initial == compare_val:
                raise TransitionValidationError(f"Step '{step.get('name')}' failed transition requirement: "
                                               f"{tag} already matches target {compare_val}")

            if initial == compare_val:
                logger.info(f"  Skipping {tag}: already matches target {compare_val} [MATCHED - NO TRANSITION]")
                write_attempted[tag] = False
                continue

            write_attempted[tag] = True
            model, point = self.get_point(tag)
            if model is None:
                model_id = 0
            else:
                tag_str = tag.get('point', tag.get('addr', tag.get('address', ''))) if isinstance(tag, dict) else tag
                model_id = int(tag_str.split('.')[0])
                
            if model not in models_to_write:
                models_to_write[model] = []
            
            # Resolve raw value
            raw_val = compare_val
            if model is not None:
                pdef = point.pdef
                sf_name = get_attr(pdef, 'sf')
                if sf_name:
                    sf_point = getattr(model, sf_name, None)
                    if sf_point:
                        model.read()
                        sf_val = sf_point.value
                        if sf_val is not None:
                            raw_val = int(compare_val / (10 ** sf_val))
            else:
                reg_config = val if isinstance(val, dict) else EXTENSION_REGISTRY.get(point, {})
                sf = reg_config.get('sf', 0)
                if sf:
                    raw_val = int(compare_val / (10 ** sf))
                else:
                    raw_val = int(compare_val)
            
            # Get address for logging
            if model is not None:
                pdef = point.pdef
                offset = getattr(point, 'offset', get_attr(pdef, 'offset'))
                
                # Derive absolute address
                addr = getattr(point, 'addr', None)
                if addr is None:
                    # Calculate: Device Base + Model Offset + Point Offset
                    d_base = getattr(self.device, 'base_addr', 0)
                    if d_base == 0:
                        d_base = getattr(self, 'base_address', 0)
                    
                    m_off = getattr(model, 'model_addr', getattr(model, 'addr', 0))
                    if offset is not None:
                        addr = d_base + m_off + offset
            else:
                addr = point
            
            addr_str = f"{addr}" if addr is not None else "???"
            logger.info(f"  Writing {tag} = {compare_val} [Raw: {raw_val}, Addr: {addr_str}]")
            models_to_write[model].append((point, raw_val, val))

        for model, points in models_to_write.items():
            if model is not None:
                for point, raw_val, _ in points:
                    point.value = raw_val
                model.write()
            else:
                # Raw Modbus writes - Uses raw socket to bypass sunspec2 remapping
                sock = self._raw_socket()
                if not sock:
                    logger.error("  ✗ Raw write skipped: no connection")
                else:
                    for addr, raw_val, val_obj in points:
                        reg_config = val_obj if isinstance(val_obj, dict) else EXTENSION_REGISTRY.get(addr, {})
                        self._raw_write(sock, addr, raw_val, reg_config.get('type', 'uint16'))

        # Verification
        if not verify:
            for tag, val in writes.items():
                compare_val = val.get('value') if isinstance(val, dict) else val
                logger.info(f"  Write {tag}: {before_vals.get(tag)} -> {compare_val} [SENT]")
            return True

        start_time = time.time()
        deadline = start_time + (timeout_ms / 1000.0)
        pending = list(writes.keys())
        
        logger.info("  Verifying transitions...")
        while pending and time.time() < deadline:
            for tag in list(pending):
                current = self.read_value(tag)
                val = writes[tag]
                target = val.get('value') if isinstance(val, dict) else val
                
                if current == target:
                    elapsed = int((time.time() - start_time) * 1000)
                    
                    # Differentiated Labeling based on write_attempted
                    if write_attempted.get(tag, True):
                        label = f"[VERIFIED in {elapsed}ms]"
                    else:
                        label = "[MATCHED - NO TRANSITION]"
                        
                    logger.info(f"  ✓ {tag}: {before_vals.get(tag)} -> {current} {label}")
                    pending.remove(tag)
            
            if pending:
                time.sleep(0.1)

        if pending:
            for tag in pending:
                current = self.read_value(tag)
                val = writes[tag]
                target = val.get('value') if isinstance(val, dict) else val
                logger.error(f"  ✗ {tag}: Update failure. Current: {current}, Expected: {target}")
            return False
        
        return True

    def execute_wait_for(self, config: Dict[str, Any], step_name: str) -> bool:
        """Poll a point until a condition is met."""
        tag = config.get('point')
        op = config.get('operator', '==')
        target = config.get('value')
        timeout_ms = config.get('timeout_ms', 30000)
        poll_ms = config.get('poll_ms', 1000)
        
        if not tag:
            logger.error("  wait_for missing 'point'")
            return False
            
        logger.info(f"  Waiting for {tag} {op} {target} (timeout: {timeout_ms}ms)...")
        
        start_time = time.time()
        deadline = start_time + (timeout_ms / 1000.0)
        
        while time.time() < deadline:
            try:
                current = self.read_value(tag)
                
                # Evaluation
                satisfied = False
                if op == '==': satisfied = (current == target)
                elif op == '!=': satisfied = (current != target)
                elif op == '>': satisfied = (current > target)
                elif op == '<': satisfied = (current < target)
                elif op == '>=': satisfied = (current >= target)
                elif op == '<=': satisfied = (current <= target)
                elif op == 'in': satisfied = (current in target)
                elif op == 'not in': satisfied = (current not in target)
                else:
                    logger.error(f"  Unsupported operator '{op}'")
                    return False
                    
                if satisfied:
                    elapsed = int((time.time() - start_time) * 1000)
                    logger.info(f"  ✓ Condition met: {current} {op} {target} [after {elapsed}ms]")
                    return True
                
                if self.verbose:
                    logger.info(f"    Current: {current} (target: {target})")
                    
            except Exception as e:
                logger.warning(f"  Polling {tag} failed: {e}")
                
            time.sleep(poll_ms / 1000.0)
            
        logger.error(f"  ✗ Timeout waiting for {tag} {op} {target}")
        return False

    def execute_reads(self, tags: List[Any]):
        for tag in tags:
            try:
                val = self.read_value(tag)
                model, point = self.get_point(tag)
                meaning = ""
                if model is not None:
                    if hasattr(point, 'pdef') and hasattr(point.pdef, 'symbols'):
                        meaning = f" ({point.pdef.symbols.get(val, 'Unknown')})"
                else:
                    addr = point
                    reg_config = tag if isinstance(tag, dict) else EXTENSION_REGISTRY.get(addr, {})
                    symbols = reg_config.get('symbols')
                    if symbols and val in symbols:
                        meaning = f" ({symbols[val]})"
                logger.info(f"  Read {tag}: {val}{meaning}")
            except Exception as e:
                logger.error(f"  Read {tag} failed: {e}")
