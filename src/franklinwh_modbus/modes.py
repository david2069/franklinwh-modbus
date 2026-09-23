"""
FranklinWH Modbus Battery Manager - Virtual Mode Controller

This module provides software-based battery mode control for FranklinWH aGate.
"""

import logging
import signal
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Tuple

from .types import VirtualMode, BatteryCommand, ControlMode
from .schedule import TOUSchedule

logger = logging.getLogger(__name__)


class VirtualModeController:
    """Software-based battery mode controller for FranklinWH aGate.
    
    Provides virtual control modes that calculate optimal battery power
    based on system state, solar production, and user preferences.
    
    Usage:
        controller = VirtualModeController(hw)
        modes = VirtualModeController(hw)
        modes.set_mode(VirtualMode.TIME_OF_USE)
        modes.run_continuous(duration_seconds=3600)
    """
    
    def __init__(
        self,
        franklinwh_controller,
        max_charge_soc: int = 100,
        min_discharge_soc: Optional[int] = None,
        soc_ramp_window: int = 10,
        force_soc_limits: bool = False,
        grid_import_limit_w: Optional[float] = None,
        grid_export_limit_w: Optional[float] = None,
        battery_charge_limit_w: Optional[float] = None,
        battery_discharge_limit_w: Optional[float] = None,
    ):
        """Initialize virtual mode controller.
        
        Args:
            franklinwh_controller: Connected FranklinWHController instance
            max_charge_soc: Maximum SoC for charging (with ramping)
            min_discharge_soc: Minimum SoC for discharging (with ramping)
            soc_ramp_window: SoC percentage for ramping before hard limit
            force_soc_limits: If True, allows override of SoC limits
        """
        self.ctrl = franklinwh_controller
        self.mode = VirtualMode.SELF_CONSUMPTION
        self.tou = TOUSchedule()
        
        # Mode-specific parameters
        self.self_reserve_pct = 20
        self.backup_target_soc = 95
        self.target_soc = 100
        self.grid_zero_buffer = 100
        self.peak_shave_threshold = 2000
        self.manual_power_w = 0
        
        # SoC limit parameters
        self.max_charge_soc = max_charge_soc
        self.soc_ramp_window = soc_ramp_window
        self.force_soc_limits = force_soc_limits
        
        # PCS limits
        self.grid_import_limit_w = grid_import_limit_w
        self.grid_export_limit_w = grid_export_limit_w
        self.battery_charge_limit_w = battery_charge_limit_w
        self.battery_discharge_limit_w = battery_discharge_limit_w
        
        # Track last commanded power to avoid feedback loops
        # (hardware DC power reading is always 0, so we track our own commands)
        self._last_commanded_power = 0.0
        
        if min_discharge_soc is None:
            self.min_discharge_soc = self._read_agate_reserve_soc()
        else:
            self.min_discharge_soc = min_discharge_soc
    
    def _read_agate_reserve_soc(self) -> int:
        """Read aGate reserve SoC from native mode registers."""
        try:
            native = self.ctrl.read_native_mode()
            if native:
                ongrid_mode = native.get('mode_raw', -1)
                if ongrid_mode in (1, 2):  # Backup or Self-Consumption
                    return native.get('self_reserve_pct', 20)
                elif ongrid_mode == 3:  # TOU
                    return native.get('tou_reserve_pct', 20)
        except Exception as e:
            logger.debug(f"Could not read aGate reserve: {e}")
        return 20
    
    def set_mode(self, mode: VirtualMode, dry_run: bool = False, **kwargs):
        """Change operating mode with optional parameters.

        Applies the new mode immediately via execute_once(). Pass dry_run=True
        to calculate and report the command without writing to the device —
        without it, merely selecting a mode engages control.
        """
        self.mode = mode
        
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Set {key} = {value}")
        
        # Get current state for validation
        bat = self.ctrl.read_battery_status()
        current_soc = bat.get('soc', 50)
        target_soc = getattr(self, 'target_soc', 100)
        
        # Print summary line with all SOCs and ETA
        self._print_soc_summary(current_soc)
        
        # Validate target SOC - EXIT if target already reached for charge modes
        if mode == VirtualMode.SELF_CONSUMPTION and current_soc >= target_soc:
            logger.error(f"TARGET ALREADY REACHED: Current SoC {current_soc:.1f}% >= Target {target_soc:.1f}%")
            logger.error("Battery is already at or above target. Cannot charge further.")
            logger.error("Exiting. Lower target SoC or wait for battery to discharge.")
            raise ValueError(f"Target SoC {target_soc}% already reached (current: {current_soc}%)")
        
        if mode == VirtualMode.EMERGENCY_BACKUP and current_soc >= target_soc:
            logger.error(f"TARGET ALREADY REACHED: Current SoC {current_soc:.1f}% >= Target {target_soc:.1f}%")
            logger.error("Battery is already at/above backup target.")
            logger.error("Exiting. Lower target SoC or wait for battery to discharge.")
            raise ValueError(f"Target SoC {target_soc}% already reached (current: {current_soc}%)")
        
        # Check for control conflicts before taking over
        state = self.ctrl.check_state()
        conflicts = state.get('conflicts', [])
        if conflicts:
            for conflict in conflicts:
                logger.warning(f"CONTROL CONFLICT: {conflict}")
            logger.warning("Use --reset-on-start to force takeover, or resolve conflict in vendor app")
        
        logger.info(f"Mode changed to: {self.mode.value}")
        self.execute_once(dry_run=dry_run)
    
    def _print_soc_summary(self, current_soc: float):
        """Print single-line summary of SOC status with ETA."""
        target = getattr(self, 'target_soc', 100)
        min_discharge = getattr(self, 'min_discharge_soc', 20)
        max_charge = getattr(self, 'max_charge_soc', 100)
        
        # Calculate ETA to target based on full charge rate
        if current_soc < target:
            soc_gap = target - current_soc
            # Assume 13.6 kWh battery (from screenshot), 5kW charge = ~2.7 hours for full charge
            # So 1% = ~0.027 hours = ~1.6 minutes at full power
            eta_minutes = soc_gap * 1.6  # Approximate
            eta_str = f"ETA: +{int(eta_minutes)}min"
        elif current_soc == target:
            eta_str = "AT TARGET"
        else:
            eta_str = "ABOVE TARGET"
        
        logger.info(f"SoC: {current_soc:.1f}% | Target: {target:.1f}% | "
                   f"Min: {min_discharge}% | Max: {max_charge}% | {eta_str}")
    
    def is_off_grid(self, status: Optional[Dict] = None) -> bool:
        """Check if the system is currently off-grid."""
        if status is None:
            try:
                grid = self.ctrl.read_grid_status()
            except Exception:
                return False  # Assume on-grid if we can't check
        else:
            grid = status.get('grid', {})
        return grid.get('connection_state', 'Connected') != 'Connected'
    
    def read_status(self) -> Dict[str, Any]:
        """Get current system status from hardware."""
        status = {
            'battery': self.ctrl.read_battery_status(),
            'grid': self.ctrl.read_grid_status(),
            'solar': self.ctrl.read_solar_status(),
            'control': self.ctrl.read_control_status(),
        }
        
        solar_data = status['solar']
        solar = solar_data.get('dc_power_w', 0)
        
        total_solar = solar
        extension_data = solar_data.get('extension', {})
        if extension_data:
            total_solar = extension_data.get('total_solar', solar)
        
        grid = status['grid'].get('grid_power_w', 0)
        
        home_ext = extension_data.get('home_load_ext', 0) if extension_data else 0
        if home_ext > 0:
            # Use extension register home load if available (FranklinWH extension)
            home_est = home_ext
        else:
            # No extension data - estimate home load without feedback loop
            # Simple conservative estimate based on typical home loads
            # When importing: home = solar + grid_import (assuming idle battery)
            # This avoids the feedback loop from using _last_commanded_power
            
            if grid > 0:
                # Importing from grid - home load is at least solar + some grid
                home_est = max(solar + grid * 0.5, 300)
            elif grid < 0:
                # Exporting to grid - home load is less than solar
                home_est = max(solar + grid, 200)  # grid is negative
            else:
                # Grid neutral - home load approximately equals solar
                home_est = max(solar, 300)
            
            # Sanity bounds
            home_est = max(200, min(home_est, 15000))
        
        status['derived'] = {
            'home_load_w': home_est,
            'excess_solar_w': max(total_solar - home_est, 0),
            'grid_import_w': max(grid, 0),
            'grid_export_w': max(-grid, 0),
            'total_solar_w': total_solar,
        }
        
        return status
    
    def calculate_power(self) -> float:
        """Calculate desired battery power based on current mode.
        
        Returns: watts (positive=charge, negative=discharge, 0=idle)
        """
        status = self.read_status()
        
        solar = status['solar'].get('dc_power_w', 0)
        home = status['derived'].get('home_load_w', 0)
        grid = status['grid'].get('grid_power_w', 0)
        soc = status['battery'].get('soc', 50)
        
        calculator = self._get_calculator()
        power = calculator(solar, home, grid, soc)
        
        power = self._apply_safety_limits(power, soc)
        power = self._apply_software_pcs_limits(power, status)
        
        # Inverter safety check only applies when off-grid
        # On-grid: the aGate handles inverter protection natively
        off_grid = self.is_off_grid(status)
        if off_grid:
            is_safe, reason, safe_power = self._check_inverter_safety(status, power)
            if not is_safe:
                # Only log safety violations when the reason changes (dedup)
                if reason != getattr(self, '_last_safety_reason', None):
                    logger.error(f"⚠️  OFF-GRID SAFETY: {reason}. Using safe power: {safe_power:.0f}W")
                    self._last_safety_reason = reason
                power = safe_power
            else:
                self._last_safety_reason = None
        
        return power
    
    def _get_calculator(self) -> Callable:
        """Get the power calculation function for current mode."""
        calculators = {
            VirtualMode.SELF_CONSUMPTION: self._calc_self_consumption,
            VirtualMode.EMERGENCY_BACKUP: self._calc_emergency_backup,
            VirtualMode.TIME_OF_USE: self._calc_time_of_use,
            VirtualMode.GRID_ZERO: self._calc_grid_zero,
            VirtualMode.PEAK_SHAVE: self._calc_peak_shave,
            VirtualMode.MANUAL: self._calc_manual,
        }
        return calculators.get(self.mode, self._calc_self_consumption)
    
    def _calc_self_consumption(self, solar: float, home: float,
                                grid: float, soc: float) -> float:
        """Self-consumption with reserve charging (like vendor app).
        
        - Discharge to cover home load when solar insufficient
        - Charge from excess solar when available  
        - Charge from grid to reach target/reserve SoC (vendor-like behavior)
        """
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        target_soc = getattr(self, 'target_soc', 100)
        excess_solar = solar - home
        
        # ABOVE target: normal self-consumption (discharge to cover load)
        if soc >= target_soc:
            if excess_solar < 0:
                return max(home - solar, -max_discharge)
            elif excess_solar > 0:
                return min(excess_solar, max_charge)  # Charge from excess
            return 0
        
        # BELOW target: FULL POWER CHARGE (matches vendor app screenshot)
        # Vendor charges at maximum power to reach reserve ASAP
        return -max_charge
    
    def _calc_emergency_backup(self, solar: float, home: float,
                                grid: float, soc: float) -> float:
        """Keep battery charged for outages."""
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        target = getattr(self, 'target_soc', self.backup_target_soc)
        
        if soc >= target:
            return 0
        
        charge_needed = (target - soc) / 100 * 5000
        return min(charge_needed * 10, max_charge)
    
    def _calc_grid_zero(self, solar: float, home: float,
                        grid: float, soc: float) -> float:
        """Minimize grid interaction."""
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        target_soc = getattr(self, 'target_soc', 100)
        
        net_load = home - solar
        
        if net_load > 0:
            return max(-min(net_load, max_discharge), -max_discharge)
        else:
            if soc < target_soc:
                return min(-net_load, max_charge)
            return 0
    
    def _calc_peak_shave(self, solar: float, home: float,
                         grid: float, soc: float) -> float:
        """Discharge during peak demand."""
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        
        if home > self.peak_shave_threshold:
            if soc > self.min_discharge_soc + 5:
                return max(min(home - solar, max_discharge), -max_discharge)
        return 0
    
    def _calc_time_of_use(self, solar: float, home: float,
                          grid: float, soc: float) -> float:
        """Time-of-use arbitrage."""
        max_charge = self.ctrl.RATED_MAX_CHARGE_W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W
        target_soc = getattr(self, 'target_soc', 100)
        
        strategy = self.tou.get_strategy()
        min_soc = self.tou.get_min_soc()
        max_soc_limit = self.tou.get_max_soc()
        
        if strategy == "charge":
            if soc < min(max_soc_limit, target_soc) - 5:
                if solar > home:
                    return min(solar - home + max_charge * 0.6, max_charge)
                else:
                    return max_charge
            return 0
        
        elif strategy == "discharge":
            if soc > max(min_soc, self.min_discharge_soc) + 5:
                return max(min(home - solar, max_discharge), -max_discharge)
            return 0
        
        elif strategy == "grid_zero":
            return self._calc_grid_zero(solar, home, grid, soc)
        
        elif strategy == "solar_priority":
            if soc < max_soc_limit - 5 and solar > 0:
                return min(solar, max_charge)
            return self._calc_self_consumption(solar, home, grid, soc)
        
        else:
            return self._calc_self_consumption(solar, home, grid, soc)
    
    def _calc_manual(self, solar: float, home: float,
                     grid: float, soc: float) -> float:
        """Manual power setting."""
        return self.manual_power_w
    
    def _apply_safety_limits(self, power: float, soc: float) -> float:
        """Apply SoC-based safety limits with ramping."""
        if soc >= 99.5 and power > 0:
            logger.warning(f"SoC {soc:.1f}% at absolute maximum - blocking charge")
            return 0
        
        if soc <= 0.5 and power < 0:
            logger.warning(f"SoC {soc:.1f}% at absolute minimum - blocking discharge")
            return 0
        
        max_charge_soc = getattr(self, 'max_charge_soc', 100)
        min_discharge_soc = getattr(self, 'min_discharge_soc', 5)
        ramp_window = getattr(self, 'soc_ramp_window', 10)
        force_override = getattr(self, 'force_soc_limits', False)
        
        if power > 0 and soc >= (max_charge_soc - ramp_window):
            if soc >= max_charge_soc:
                if not force_override:
                    logger.info(f"SoC {soc:.1f}% at max limit ({max_charge_soc}%) - blocking charge")
                    return 0
                else:
                    logger.warning(f"FORCE OVERRIDE: SoC {soc:.1f}% exceeds max")
            else:
                ramp_progress = (soc - (max_charge_soc - ramp_window)) / ramp_window
                ramp_factor = 1.0 - ramp_progress
                ramped_power = power * max(ramp_factor, 0.05)
                power = ramped_power
        
        if power < 0 and soc <= (min_discharge_soc + ramp_window):
            if soc <= min_discharge_soc:
                if not force_override:
                    logger.info(f"SoC {soc:.1f}% at min limit ({min_discharge_soc}%) - blocking discharge")
                    return 0
                else:
                    logger.warning(f"FORCE OVERRIDE: SoC {soc:.1f}% below min")
            else:
                ramp_progress = ((min_discharge_soc + ramp_window) - soc) / ramp_window
                ramp_factor = 1.0 - ramp_progress
                ramped_power = power * max(ramp_factor, 0.05)
                power = ramped_power
        
        return power
        
    def _apply_software_pcs_limits(self, power: float, status: Dict[str, Any]) -> float:
        """Apply software-based PCS (Power Control System) limits on grid and battery flow."""
        # 1. Battery Limits (always positive values, clamp absolute rate)
        if power > 0 and self.battery_charge_limit_w is not None:
            if power > self.battery_charge_limit_w:
                logger.debug(f"PCS: Clamping battery charge {power:.0f}W -> {self.battery_charge_limit_w:.0f}W")
                power = self.battery_charge_limit_w
                
        if power < 0 and self.battery_discharge_limit_w is not None:
            if abs(power) > self.battery_discharge_limit_w:
                logger.debug(f"PCS: Clamping battery discharge {abs(power):.0f}W -> {self.battery_discharge_limit_w:.0f}W")
                power = -self.battery_discharge_limit_w
                
        # 2. Grid Limits (grid power: positive = import, negative = export)
        grid_w = status['grid'].get('grid_power_w', 0.0)
        
        # Grid Import limit: if grid_w > grid_import_limit_w and we are charging,
        # we can reduce charging power to reduce grid import.
        if self.grid_import_limit_w is not None and grid_w > self.grid_import_limit_w:
            excess_import = grid_w - self.grid_import_limit_w
            if power > 0: # battery is charging
                new_power = max(0.0, power - excess_import)
                logger.debug(f"PCS: Grid import {grid_w:.0f}W exceeds limit {self.grid_import_limit_w:.0f}W. Reducing charge {power:.0f}W -> {new_power:.0f}W")
                power = new_power
                
        # Grid Export limit: if grid_w < -grid_export_limit_w (exporting) and we are discharging (power < 0),
        # we can reduce discharging power to reduce grid export.
        if self.grid_export_limit_w is not None and grid_w < -self.grid_export_limit_w:
            export_w = -grid_w
            excess_export = export_w - self.grid_export_limit_w
            if power < 0: # battery is discharging
                new_power = min(0.0, power + excess_export) # make it less negative
                logger.debug(f"PCS: Grid export {export_w:.0f}W exceeds limit {self.grid_export_limit_w:.0f}W. Reducing discharge {abs(power):.0f}W -> {abs(new_power):.0f}W")
                power = new_power
                
        return power
    
    def _check_inverter_safety(self, status: Dict, proposed_power: float) -> Tuple[bool, str, float]:
        """Check if operation is safe for inverter.
        
        Uses the actual charge/discharge nameplate ratings (WChaRteMax/WDisChaRteMax
        from Model 702), NOT the AC continuous rating (WRtg).
        """
        solar = status['solar'].get('dc_power_w', 0)
        home = status['derived'].get('home_load_w', 0)
        max_charge = self.ctrl.RATED_MAX_CHARGE_W      # e.g. 5000W
        max_discharge = self.ctrl.RATED_MAX_DISCHARGE_W  # e.g. 5000W
        
        if proposed_power > 0 and proposed_power > max_charge * 1.05:
            return False, "Charge limit exceeded", max_charge
        
        if proposed_power < 0 and abs(proposed_power) > max_discharge * 1.05:
            return False, "Discharge limit exceeded", -max_discharge
        
        # Off-grid / high-load protection: don't overdraw inverter capacity
        available_solar = max(0, solar)
        total_available = max_discharge + available_solar
        
        if home > total_available * 0.8:
            if not getattr(self, '_warned_high_load', False):
                logger.warning(f"High load: {home:.0f}W at {home/total_available*100:.0f}% of capacity")
                self._warned_high_load = True
            
            if proposed_power < 0 and home > total_available * 0.9:
                max_safe = total_available - home - 500
                if max_safe < 0:
                    max_safe = 0
                if abs(proposed_power) > max_safe:
                    logger.error(f"EMERGENCY: Load exceeds capacity! Limiting discharge")
                    return False, "Load exceeds capacity", -max_safe
        else:
            self._warned_high_load = False
        
        return True, "Safety check passed", proposed_power
    
    def verify_command_execution(self, tolerance_percent: float = 20.0) -> tuple:
        """
        Verify that commanded power matches actual battery DC power.
        
        Returns:
            (ok: bool, commanded: float, actual: float, diff_percent: float)
        """
        try:
            # Get commanded power from control status
            ctl = self.ctrl.read_control_status()
            commanded = ctl.get('wset_watts', 0)
            wset_ena = ctl.get('wset_enabled', 0)
            
            if wset_ena != 1 or commanded == 0:
                # Not actively controlling, skip check
                return True, 0, 0, 0
            
            # Get actual battery DC power from Model 714
            m714 = self.ctrl.get_model(714)
            if not m714:
                return True, commanded, 0, 0  # Can't verify without Model 714
            
            m714.read()
            sf_w = self.ctrl._get_scale_factor(m714, 'DCW_SF')
            blocks = m714.blocks[1:] if hasattr(m714, 'blocks') and len(m714.blocks) > 1 else [m714]
            actual = sum(
                block.DCW.value * (10 ** sf_w)
                for block in blocks
                if hasattr(block, 'DCW') and block.DCW.value is not None
            )
            
            # Calculate difference percentage
            if commanded == 0:
                diff_percent = 0 if actual == 0 else 100
            else:
                diff_percent = abs((actual - commanded) / commanded) * 100
            
            # Check if within tolerance
            ok = diff_percent <= tolerance_percent
            
            return ok, commanded, actual, diff_percent
            
        except Exception as e:
            logger.debug(f"Could not verify command execution: {e}")
            return True, 0, 0, 0  # Fail open (assume OK) on error
    
    def execute_once(self, dry_run: bool = False) -> float:
        """Calculate and send single command. Returns actual power sent.

        With dry_run=True the command is calculated and reported but never
        written, and no commanded-power state is recorded.
        """
        status = self.read_status()
        
        power = self.calculate_power()
        
        cmd = BatteryCommand(power_watts=power, mode=ControlMode.LIMIT_ABS)
        success, msg = self.ctrl.send_command(cmd, dry_run=dry_run)
        
        if dry_run:
            logger.info(f"DRY RUN {self.mode.value}: {power:.0f}W ({msg})")
            return power
        
        if success:
            # Only log when power changes (dedup for loop mode)
            if power != getattr(self, '_last_logged_power', None):
                logger.info(f"{self.mode.value}: {power:.0f}W")
                self._last_logged_power = power
            self._last_commanded_power = power
            return power
        else:
            # Raise exception so tick() can handle reconnection
            err_msg = str(msg).lower()
            if any(x in err_msg for x in ['broken pipe', 'socket', 'timeout', 'connection', 'modbus']):
                raise ConnectionError(f"Modbus error: {msg}")
            else:
                raise RuntimeError(f"Command failed: {msg}")
    
    def tick(self) -> bool:
        """Execute one control cycle. Returns True if successful."""
        try:
            self.execute_once()
            return True
        except Exception as e:
            # Check if it's a connection-related error
            err_str = str(e).lower()
            is_connection_error = (
                isinstance(e, (ConnectionError, BrokenPipeError, OSError)) or
                'broken pipe' in err_str or
                'socket' in err_str or
                'timeout' in err_str or
                'connection' in err_str or
                'modbus' in err_str
            )
            
            if is_connection_error:
                # Connection issues - try to reconnect
                logger.warning(f"Connection lost during tick: {e}")
                if self.ctrl.reconnect():
                    logger.info("Reconnected, retrying tick...")
                    try:
                        self.execute_once()
                        return True
                    except Exception as e2:
                        logger.error(f"Control tick failed after reconnect: {e2}")
                        return False
                else:
                    logger.error("Failed to reconnect")
                    return False
            else:
                logger.error(f"Control tick failed: {e}")
                return False
    
    def run_continuous(self, duration_seconds: Optional[float] = None,
                        enable_safety_checks: bool = False,
                        stop_event: Optional[threading.Event] = None):
        """Run controller continuously.
        
        Args:
            duration_seconds: Run for N seconds, or None for indefinite
            enable_safety_checks: If True, enable alarm/sanity/SoC limit checks
                                  (adds Modbus overhead, use for automation only)
            stop_event: Optional threading.Event to signal shutdown.
                        If None, runs until duration expires or failure limit hit.
                        For CLI usage, use run_with_signal_handling() instead.
        """
        start_time = time.time()
        tick_interval = 5.0
        last_tick = 0
        consecutive_failures = 0
        max_consecutive_failures = 5
        last_progress_soc = None
        off_grid_check_interval = 30.0
        last_off_grid_check = 0
        
        # Safety check intervals (only used if enable_safety_checks=True)
        alarm_interval = 60.0
        sanity_interval = 30.0
        last_alarm_check = 0
        last_sanity_check = 0
        alarm_failures = 0
        
        # Off-grid check at start
        if self.is_off_grid():
            logger.warning("⚠️  SYSTEM IS OFF-GRID — inverter safety limits active")
            logger.warning("   Battery operations limited to prevent overload")
        
        logger.info(f"Running continuous control: safety_checks={enable_safety_checks}")
        
        try:
            while True:
                # Check stop signal
                if stop_event and stop_event.is_set():
                    logger.info("Stop event received, shutting down...")
                    break
                
                now = time.time()
                elapsed = now - start_time
                
                if duration_seconds and elapsed >= duration_seconds:
                    logger.info("Duration expired, stopping...")
                    break
                
                # Periodic off-grid check (every 30s)
                if now - last_off_grid_check >= off_grid_check_interval:
                    last_off_grid_check = now
                    if self.is_off_grid():
                        if not getattr(self, '_off_grid_warned', False):
                            logger.warning("⚠️  SYSTEM IS OFF-GRID — inverter safety limits active")
                            self._off_grid_warned = True
                    else:
                        self._off_grid_warned = False
                
                # Main control tick (every 5s)
                if now - last_tick >= tick_interval:
                    success = self.tick()
                    if success:
                        consecutive_failures = 0
                        
                        # Compact progress output (dedup by SoC change)
                        try:
                            bat = self.ctrl.read_battery_status()
                            soc = bat.get('soc', 0)
                            target = getattr(self, 'target_soc', 100)
                            power = self._last_commanded_power
                            remaining = f" | {int(duration_seconds - elapsed)}s left" if duration_seconds else ""
                            direction = "↑" if power > 0 else "↓" if power < 0 else "—"
                            
                            if soc != last_progress_soc:
                                logger.info(f"SoC: {soc:.0f}% {direction} {abs(power):.0f}W | Target: {target}%{remaining}")
                                last_progress_soc = soc
                        except Exception:
                            pass
                        
                        # SoC limit check (only if safety checks enabled)
                        if enable_safety_checks:
                            try:
                                status = self.ctrl.read_battery_status()
                                soc = status.get('soc', 0)
                                power = self.calculate_power()
                                
                                if power > 0 and soc >= self.max_charge_soc:
                                    logger.info(f"✓ MAX CHARGE SoC REACHED: {soc:.1f}%")
                                    break
                                if power < 0 and soc <= self.min_discharge_soc:
                                    logger.info(f"✓ MIN DISCHARGE SoC REACHED: {soc:.1f}%")
                                    break
                            except Exception as e:
                                logger.debug(f"SoC check failed: {e}")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"Tick failed ({consecutive_failures}/{max_consecutive_failures})")
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error("Too many failures, stopping")
                            break
                    
                    last_tick = now
                
                # Optional safety checks (for automation mode only)
                if enable_safety_checks and consecutive_failures == 0:
                    # Alarm check
                    if now - last_alarm_check >= alarm_interval:
                        last_alarm_check = now
                        try:
                            can_operate, blocking = self.ctrl.check_blocking_alarms()
                            if not can_operate:
                                logger.error(f"🚨 BLOCKING ALARMS: {', '.join(blocking)}")
                                alarm_failures += 1
                                if alarm_failures >= 2:
                                    break
                            else:
                                alarm_failures = 0
                        except Exception as e:
                            logger.debug(f"Alarm check failed: {e}")
                    
                    # Sanity check
                    if now - last_sanity_check >= sanity_interval:
                        last_sanity_check = now
                        try:
                            ok, commanded, actual, diff = self.verify_command_execution()
                            if not ok:
                                logger.warning(f"Command verification: {commanded:.0f}W vs actual {actual:.0f}W")
                        except Exception as e:
                            logger.debug(f"Sanity check failed: {e}")
                
                time.sleep(0.1)
                
        finally:
            # Cleanup - try to reset control state
            cleanup_ok = False
            try:
                # If connection is broken, try to reconnect first
                if not self.ctrl.is_connected():
                    logger.info("Connection lost, reconnecting to reset control...")
                    if self.ctrl.reconnect():
                        logger.info("Reconnected for cleanup")
                    else:
                        logger.error("Could not reconnect for cleanup - control may still be active!")
                
                if self.ctrl.is_connected():
                    self.ctrl.reset_control_state()
                    logger.info("Control released (WSetEna=0)")
                    cleanup_ok = True
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
            
            if not cleanup_ok:
                logger.warning(
                    f"Could not release Modbus control! "
                    f"Manually run: franklinwh_cli.py -i {self.ctrl.ip_address} --stop"
                )


def run_with_signal_handling(
    controller: 'VirtualModeController',
    duration_seconds: Optional[float] = None,
    enable_safety_checks: bool = False,
):
    """Run a VirtualModeController with SIGINT/SIGTERM signal handling.
    
    This is a CLI convenience wrapper around run_continuous(). Library consumers
    should call run_continuous() directly with a stop_event instead.
    
    Args:
        controller: Configured VirtualModeController instance
        duration_seconds: Run for N seconds, or None for indefinite
        enable_safety_checks: If True, enable alarm/sanity/SoC limit checks
    """
    stop = threading.Event()
    
    def signal_handler(signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        stop.set()
    
    old_sigint = signal.getsignal(signal.SIGINT)
    old_sigterm = signal.getsignal(signal.SIGTERM)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        controller.run_continuous(
            duration_seconds=duration_seconds,
            enable_safety_checks=enable_safety_checks,
            stop_event=stop,
        )
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
