#!/usr/bin/env python3
from __future__ import annotations  # Postpone type hint evaluation (allows import without rich)
"""
FranklinWH CLI Dashboard Monitor

A terminal-based dashboard that mirrors the web dashboard functionality
with real-time updates and interactive control.

Usage:
    python franklinwh_cli.py -i YOUR_AGATE_IP --monitor
    python franklinwh_monitor.py -i YOUR_AGATE_IP --refresh 2

Keyboard Shortcuts:
    c       Enter charge mode (prompts for watts)
    d       Enter discharge mode (prompts for watts)
    s       Standby (0W)
    m       Max charge
    M       Max discharge
    +       Increase power by 100W
    -       Decrease power by 100W
    r       Reset control (release to idle)
    R       Toggle auto-refresh
    1-9     Set refresh rate (1-9 seconds)
    q       Quit
    Ctrl+C  Quit
"""

import time
import sys
import signal
import threading
import select
import tty
import termios
import os
import logging
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .controller import FranklinWHController
from .types import BatteryCommand, ControlMode


@dataclass
class ThemeConfig:
    """Color theme configuration."""
    name: str
    bg_color: str = "default"
    text_color: str = "white"
    accent_color: str = "cyan"
    success_color: str = "green"
    warning_color: str = "yellow"
    error_color: str = "red"
    solar_color: str = "yellow"
    battery_color: str = "magenta"
    grid_color: str = "blue"
    home_color: str = "green"
    header_style: str = "bold cyan"
    border_style: str = "blue"
    
    @classmethod
    def get_theme(cls, name: str) -> "ThemeConfig":
        """Get theme by name."""
        themes = {
            "dark": cls(
                name="dark",
                text_color="white",
                accent_color="cyan",
                success_color="green",
                warning_color="yellow",
                error_color="red",
                solar_color="yellow",
                battery_color="magenta",
                grid_color="blue",
                home_color="green",
                header_style="bold cyan",
                border_style="blue",
            ),
            "green": cls(
                name="green",
                text_color="#00ff00",
                accent_color="#00ff00",
                success_color="#00ff00",
                warning_color="#80ff00",
                error_color="#ff0000",
                solar_color="#00ff00",
                battery_color="#00ff00",
                grid_color="#00ff00",
                home_color="#00ff00",
                header_style="bold #00ff00",
                border_style="#00ff00",
            ),
            "amber": cls(
                name="amber",
                text_color="#ffb000",
                accent_color="#ffb000",
                success_color="#ffb000",
                warning_color="#ff8000",
                error_color="#ff0000",
                solar_color="#ffb000",
                battery_color="#ffb000",
                grid_color="#ffb000",
                home_color="#ffb000",
                header_style="bold #ffb000",
                border_style="#ffb000",
            ),
            "white": cls(
                name="white",
                text_color="white",
                accent_color="white",
                success_color="white",
                warning_color="white",
                error_color="white",
                solar_color="white",
                battery_color="white",
                grid_color="white",
                home_color="white",
                header_style="bold white",
                border_style="white",
            ),
            "paper": cls(
                name="paper",
                text_color="white",
                accent_color="white",
                success_color="white",
                warning_color="white",
                error_color="red",
                solar_color="white",
                battery_color="white",
                grid_color="white",
                home_color="white",
                header_style="bold white",
                border_style="white",
            ),
        }
        return themes.get(name, themes["dark"])


@dataclass
class MonitorConfig:
    """Configuration for the monitor."""
    ip_address: str
    port: int = 502
    unit_id: int = 2
    timeout: float = 10.0
    refresh_rate: float = 5.0
    use_rich: bool = True
    theme: str = "dark"  # dark, green, amber, white, paper
    max_history: int = 720  # 60 minutes at 5s intervals
    quiet: bool = False  # Suppress non-error output


@dataclass
class PowerFlowData:
    """Power flow snapshot."""
    solar_w: float = 0.0
    home_w: float = 0.0
    battery_w: float = 0.0
    grid_w: float = 0.0
    battery_state: str = "Idle"  # Charging, Discharging, Idle
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SolarData:
    """Solar input breakdown (AC-coupled)."""
    total_w: float = 0.0
    proximal_w: float = 0.0
    remote1_w: float = 0.0
    remote2_w: float = 0.0
    

class KeyboardInput:
    """Non-blocking keyboard input handler for terminal."""
    
    def __init__(self):
        self.key_queue = []
        self.running = False
        self.thread = None
        self.old_settings = None
        
    def _setup_terminal(self):
        """Set terminal to cbreak mode for single key input."""
        if sys.stdin.isatty():
            self.old_settings = termios.tcgetattr(sys.stdin)
            # Use cbreak mode - immediate keys but preserves some terminal handling
            tty.setcbreak(sys.stdin.fileno())
            
    def _restore_terminal(self):
        """Restore terminal to original settings."""
        if self.old_settings and sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            
    def _read_input(self):
        """Background thread to read keyboard input."""
        self._setup_terminal()
        try:
            while self.running:
                # Non-blocking with 50ms timeout - responsive but not aggressive
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    key = sys.stdin.read(1)
                    if key:
                        self.key_queue.append(key)
                # Don't sleep here - let select do the waiting
        finally:
            self._restore_terminal()
            
    def start(self):
        """Start the input thread."""
        self.running = True
        self.thread = threading.Thread(target=self._read_input, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the input thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
            
    def get_key(self) -> Optional[str]:
        """Get next key from queue (non-blocking)."""
        if self.key_queue:
            return self.key_queue.pop(0)
        return None
        
    def clear(self):
        """Clear key queue."""
        self.key_queue.clear()


@dataclass
class SystemData:
    """Complete system state for display."""
    # Power flow
    power_flow: PowerFlowData = field(default_factory=PowerFlowData)
    
    # Battery DC
    soc: float = 0.0
    soh: float = 0.0
    reserve_soc: float = 20.0
    self_reserve_soc: float = 20.0
    tou_reserve_soc: float = 20.0
    target_soc: float = 100.0
    dc_power: float = 0.0
    dc_current: float = 0.0
    battery_temp: float = 0.0
    available_wh: float = 0.0
    rated_wh: float = 0.0
    
    # AC Power
    ac_voltage: float = 0.0
    ac_current: float = 0.0
    ac_frequency: float = 0.0
    ac_pf: float = 0.0
    ac_va: float = 0.0
    ac_var: float = 0.0
    ac_type: str = "Single-Phase"
    
    # Solar (AC-coupled)
    solar: SolarData = field(default_factory=SolarData)
    
    # Temperatures
    cabinet_temp: float = 0.0
    ambient_temp: float = 0.0
    
    # Lifetime energy (Wh)
    lifetime_injected: float = 0.0
    lifetime_absorbed: float = 0.0
    lifetime_discharged: float = 0.0
    lifetime_charged: float = 0.0
    lifetime_generated: float = 0.0
    lifetime_grid_export: float = 0.0
    lifetime_grid_import: float = 0.0
    
    # System info
    serial: str = ""
    model: str = ""
    firmware: str = ""
    grid_connected: bool = False
    grid_mode: str = "Unknown"  # Grid Following, Grid Forming
    operating_mode: str = "Self-Consumption"
    wset_ena: int = 0
    wset_pct: float = 0.0
    control_source: str = "aGate"  # aGate native or Modbus remote
    loc_rem_ctl: str = "N/A"  # SunSpec LocRemCtl (Local/Remote)
    derived_control: str = "Local"  # Our interpretation: Local or Remote
    
    # Alarms
    active_alarms: List[str] = field(default_factory=list)
    extension_writable: bool = False
    
    # History for sparkline
    history: deque = field(default_factory=lambda: deque(maxlen=720))


class CLIMonitor:
    """Terminal-based dashboard monitor for FranklinWH battery."""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.theme = ThemeConfig.get_theme(config.theme)
        self.console = Console(theme=self._get_rich_theme()) if HAS_RICH else None
        self.controller: Optional[FranklinWHController] = None
        self.data = SystemData()
        self.running = False
        self.paused = False
        self.current_power = 0  # Current commanded power
        self.input_handler = KeyboardInput()
        self.command_prompt = ""  # Current command being entered
        self.show_prompt = False  # Whether to show command input
        self.prompt_buffer = ""   # Buffer for numeric input
        self.prompt_mode = None   # 'charge' or 'discharge'
        self.command_log = []     # Recent commands/messages
        self.max_log_lines = 8    # Number of lines to show
        self.last_key = None      # Last key pressed (for feedback)
        self.last_key_time = 0    # Timestamp of last key
        self.show_help = False    # Show help overlay
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _get_rich_theme(self):
        """Get Rich theme based on config."""
        from rich.theme import Theme
        if self.config.theme in ("green", "amber", "white"):
            # Monochrome themes use the accent color for everything
            accent = self.theme.accent_color
            return Theme({
                "info": accent,
                "success": self.theme.success_color,
                "warning": self.theme.warning_color,
                "error": self.theme.error_color,
            })
        return None  # Default dark theme
        
    def _get_border_style(self, functional_color: str = "blue") -> str:
        """Get border color based on theme.
        
        For monochrome themes (green, amber, white, paper), use the theme accent color.
        For dark theme, use functional colors to distinguish panel types.
        """
        if self.config.theme in ("green", "amber", "white", "paper"):
            return self.theme.accent_color
        return functional_color
        
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self.running = False
        # Restore terminal settings immediately
        if hasattr(self, 'input_handler') and self.input_handler:
            self.input_handler.stop()
        raise KeyboardInterrupt()
        
    def connect(self) -> bool:
        """Connect to the FranklinWH device."""
        # Suppress logging if quiet mode
        if self.config.quiet:
            logging.getLogger().setLevel(logging.WARNING)
        try:
            self.controller = FranklinWHController(
                ip_address=self.config.ip_address,
                port=self.config.port,
                unit_id=self.config.unit_id,
                timeout=self.config.timeout
            )
            self.controller.connect()
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Connection failed: {e}[/red]")
            else:
                print(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect and cleanup."""
        if self.controller:
            try:
                self.controller.disconnect()
            except:
                pass
            self.controller = None
            
    def _read_lifetime_energy(self) -> dict:
        """Read lifetime energy accumulators from Model 715 (if available)."""
        try:
            m715 = self.controller.get_model(715)
            if not m715:
                return {}
            m715.read()
            
            # Check if this is actually an accumulator model or control model
            # Some firmware versions have M715 as DER control, not accumulators
            if hasattr(m715, 'TotWhExp'):
                sf_wh = self.controller._get_scale_factor(m715, 'TotWhExp_SF')
                
                def get_wh(point_name):
                    pt = getattr(m715, point_name, None)
                    if pt and hasattr(pt, 'value') and pt.value is not None:
                        return pt.value * (10 ** sf_wh)
                    return 0
                
                return {
                    'injected_wh': get_wh('TotWhExp'),
                    'absorbed_wh': get_wh('TotWhImp'),
                    'discharged_wh': get_wh('TotWhOut'),
                    'charged_wh': get_wh('TotWhIn'),
                    'generated_wh': get_wh('TotWhExp'),
                }
            else:
                # M715 is DER control model, not accumulators
                return {}
        except Exception as e:
            return {}
        
    def fetch_data(self) -> bool:
        """Fetch all data from the device."""
        if not self.controller:
            return False
            
        try:
            # Read all status methods (enriched — includes M714, M701 extras, extensions)
            battery = self.controller.read_battery_status()
            grid = self.controller.read_grid_status()
            solar = self.controller.read_solar_status()
            control = self.controller.read_control_status()
            native = self.controller.read_native_mode()
            nameplate = self.controller.read_nameplate()  # Now returns strings
            
            # Get extension solar data if available
            ext_solar = solar.get('extension', {})
            solar_total = ext_solar.get('total_solar', abs(solar.get('ac_power_w', 0)))
            
            # Battery DC power from enriched read_battery_status()
            battery_dc = battery.get('battery_power_w', 0)
            
            # Grid power from controller
            grid_raw = grid.get('grid_power_w', 0)
            
            # Store power flow
            self.data.power_flow.solar_w = solar_total
            self.data.power_flow.battery_w = battery_dc
            self.data.power_flow.grid_w = grid_raw
            
            # Sourced home load from high-res ext register 16000 or fallback to balance calculation
            home_load_ext = ext_solar.get('home_load_ext', 0)
            if home_load_ext > 0:
                self.data.power_flow.home_w = home_load_ext
            else:
                self.data.power_flow.home_w = solar_total + battery_dc + grid_raw
            
            # Battery state from enriched read_battery_status()
            # (derived from M714 DCW — M713.Sta is always 0 on FranklinWH)
            self.data.power_flow.battery_state = battery.get('battery_state', 'IDLE')
                 
            # Update Battery DC — all from enriched read_battery_status()
            self.data.soc = battery.get('soc', self.data.soc)
            self.data.soh = battery.get('soh', self.data.soh)
            self.data.dc_power = battery_dc
            self.data.dc_current = battery.get('battery_current_a', 0)
            self.data.battery_temp = battery.get('battery_temp_c', 0)
            self.data.available_wh = battery.get('wh_available', 0)
            self.data.rated_wh = battery.get('wh_rating', 0)
            
            # Store native reserve settings
            self.data.self_reserve_soc = native.get('self_reserve_pct', 20.0)
            self.data.tou_reserve_soc = native.get('tou_reserve_pct', 20.0)
            
            # Active effective reserve SoC based on current native operating mode
            active_reserve, _ = self.controller.get_effective_reserve_level()
            self.data.reserve_soc = active_reserve if active_reserve is not None else self.data.self_reserve_soc
            
            # Update AC Power — enriched grid status now includes current, PF, temps
            self.data.ac_voltage = grid.get('voltage_v', 0)
            self.data.ac_current = grid.get('current_a', 0)
            self.data.ac_frequency = grid.get('frequency_hz', 0)
            self.data.ac_pf = grid.get('power_factor', 0)
            self.data.ac_va = grid.get('grid_va', 0)
            self.data.ac_var = grid.get('grid_var', 0)
            self.data.ac_type = grid.get('ac_type', 'Single-Phase')
            self.data.grid_connected = grid.get('connection_state') == 'Connected'
            self.data.grid_mode = grid.get('grid_mode', 'Unknown')
            
            # Update Solar (AC-coupled)
            self.data.solar.total_w = solar_total
            self.data.solar.proximal_w = ext_solar.get('pv_proximal', solar_total)
            self.data.solar.remote1_w = ext_solar.get('pv_remote1', 0)
            self.data.solar.remote2_w = ext_solar.get('pv_remote2', 0)
            
            # Update Temperatures — enriched grid status now includes temps
            self.data.cabinet_temp = grid.get('cabinet_temp_c', 0)
            self.data.ambient_temp = grid.get('ambient_temp_c', 0)
            
            # Update System Info — read_nameplate() now returns strings directly
            self.data.serial = nameplate.get('serial', '')
            self.data.model = nameplate.get('model', 'aGate X')
            self.data.firmware = nameplate.get('version', '')
            self.data.operating_mode = native.get('mode_name', 'Self-Consumption')
            self.data.wset_ena = control.get('wset_enabled', 0)
            self.data.control_source = 'Modbus' if control.get('wset_enabled') else 'aGate'
            self.data.loc_rem_ctl = control.get('loc_rem_ctl_name', 'N/A')
            wset_pct = control.get('wset_pct', 0)
            self.data.wset_pct = wset_pct
            if control.get('wset_enabled'):
                self.data.derived_control = f"Remote (Modbus WSetPct={wset_pct}%)"
            else:
                self.data.derived_control = f"Local (aGate, {self.data.operating_mode})"
                
            # Set extension writable from connection writability check
            write_status = self.controller.get_extension_write_status()
            self.data.extension_writable = write_status.get('ongrid_mode', {}).get('writable', False)
            
            # Update Lifetime Energy (from M502 solar and M714 battery)
            m502 = self.controller.get_model(502)
            m714_energy = self.controller.get_model(714)
            
            if m502 and hasattr(m502, 'OutWh') and m502.OutWh.value is not None:
                self.data.lifetime_generated = m502.OutWh.value
            
            if m714_energy:
                try:
                    m714_energy.read()
                    sf_wh = self.controller._get_scale_factor(m714_energy, 'DCWH_SF')
                    if sf_wh is None:
                        sf_wh = self.controller._get_scale_factor(m714_energy, 'DCWh_SF')
                    if sf_wh is None:
                        sf_wh = 0
                    
                    blocks = m714_energy.blocks[1:] if hasattr(m714_energy, 'blocks') and len(m714_energy.blocks) > 1 else [m714_energy]
                    
                    self.data.lifetime_discharged = sum(
                        block.DCWhInj.value * (10 ** sf_wh)
                        for block in blocks
                        if hasattr(block, 'DCWhInj') and block.DCWhInj.value is not None
                    )
                    
                    self.data.lifetime_charged = sum(
                        block.DCWhAbs.value * (10 ** sf_wh)
                        for block in blocks
                        if hasattr(block, 'DCWhAbs') and block.DCWhAbs.value is not None
                    )
                except Exception as e:
                    logger.debug(f"Could not read Model 714 lifetime energy in monitor: {e}")
            
            # Grid lifetime energy (from M701 already read above)
            grid_export_wh = grid.get('grid_export_wh', 0)
            grid_import_wh = grid.get('grid_import_wh', 0)
            if grid_export_wh:
                self.data.lifetime_grid_export = grid_export_wh
            if grid_import_wh:
                self.data.lifetime_grid_import = grid_import_wh
            
            # Add to history for sparkline
            self.data.history.append({
                'timestamp': datetime.now(),
                'battery_w': self.data.power_flow.battery_w,
                'solar_w': self.data.power_flow.solar_w,
                'grid_w': self.data.power_flow.grid_w
            })
            return True
        except Exception as e:
            return False
            
    def create_layout(self) -> Layout:
        """Create the Rich layout structure."""
        # Main layout with header and body
        layout = Layout(name="root")
        
        # Header
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=4)
        )
        
        # Body splits
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Left column
        layout["left"].split_column(
            Layout(name="power_flow", size=9),
            Layout(name="soc_bar", size=5),
            Layout(name="dc_power", size=13)
        )
        
        # Right column
        layout["right"].split_column(
            Layout(name="ac_power", size=8),
            Layout(name="solar", size=7),
            Layout(name="lifetime", size=7),
            Layout(name="command_console", size=5)
        )
        
        return layout
        
    def render_header(self) -> Panel:
        """Render the header panel."""
        # Format: DD-Mmm-YY HH:MM
        now = datetime.now()
        timestamp = now.strftime("%d-%b-%y %H:%M")
        
        # Use serial if available, otherwise IP
        device_id = self.data.serial if self.data.serial else f"{self.config.ip_address}:{self.config.port}"
        title = f"FranklinWH Monitor - {device_id}"
        refresh = f"Refresh: {self.config.refresh_rate:.0f}s"
        status = "PAUSED" if self.paused else "LIVE"
        
        # Keystroke feedback (show for 0.3 seconds - visible but not lingering)
        key_feedback = ""
        if self.last_key and (time.time() - self.last_key_time) < 0.3:
            key_display = self.last_key
            if key_display == ' ':
                key_display = 'SPACE'
            elif key_display == '\x03':
                key_display = 'CTRL+C'
            elif key_display == '\r':
                key_display = 'ENTER'
            elif key_display == '\x7f':
                key_display = 'BKSP'
            key_feedback = f" [Key: {key_display}]"
        
        left_content = Text()
        left_content.append(timestamp, style="dim")
        left_content.append(" | ", style="dim")
        left_content.append(title, style=self.theme.header_style)
        left_content.append(f" | {refresh}", style="dim")
        status_color = self.theme.success_color if not self.paused else self.theme.warning_color
        left_content.append(f" | [{status}]", style=status_color)
        if key_feedback:
            left_content.append(key_feedback, style=f"bold {self.theme.warning_color}")
            
        right_content = Text()
        right_content.append("Control: ", style="dim")
        if self.data.wset_ena == 1:
            right_content.append("Remote (r=release)", style="bold red")
        else:
            right_content.append("Local", style="bold green")
            
        table = Table(show_header=False, box=None, padding=0, expand=True)
        table.add_column("Left", justify="left")
        table.add_column("Right", justify="right")
        table.add_row(left_content, right_content)
        
        return Panel(table, box=box.SIMPLE, padding=(0, 1))
        
    def render_power_flow(self) -> Panel:
        """Render Power Flow Summary panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Source", style="cyan", justify="left")
        table.add_column("Power", style="white", justify="right")
        table.add_column("State", style="green", justify="left")
        table.add_column("Flow", style="dim", justify="center")
        
        pf = self.data.power_flow
        
        # Solar
        solar_active = pf.solar_w > 50  # Threshold for "Producing"
        solar_icon = "→" if solar_active else " "
        solar_state = "Producing" if solar_active else "Idle"
        table.add_row("Solar", f"{pf.solar_w:>6.0f}W", solar_state, solar_icon)
        
        # Home
        home_icon = "←" if pf.home_w > 0 else " "
        table.add_row("Home", f"{pf.home_w:>6.0f}W", "Consuming", home_icon)
        
        # Battery (Standard SunSpec: Negative=Charge, Positive=Discharge)
        battery_state = pf.battery_state
        if self.config.theme in ("green", "amber", "white", "paper"):
            battery_style = self.theme.accent_color
        else:
            battery_style = "green" if battery_state == "Charging" else "yellow" if battery_state == "Discharging" else "dim"
        
        # Icon mapping: ↓ for charging (negative), ↑ for discharging (positive)
        battery_icon = "↓" if battery_state == "Charging" else "↑" if battery_state == "Discharging" else "○"
        table.add_row("Battery", f"{abs(pf.battery_w):>6.0f}W", f"[{battery_style}]{battery_state}[/{battery_style}]", battery_icon)
        
        # Grid (Standard SunSpec: Positive=Import, Negative=Export)
        grid_state = "Importing" if pf.grid_w > 0 else "Exporting" if pf.grid_w < 0 else "Idle"
        grid_icon = "←" if pf.grid_w > 0 else "→" if pf.grid_w < 0 else "○"
        table.add_row("Grid", f"{abs(pf.grid_w):>6.0f}W", grid_state, grid_icon)
        
        # Inverter Utilization Bar (if controller available)
        if self.controller:
            max_w = self.controller.RATED_MAX_W
            battery_abs = abs(pf.battery_w)
            util_pct = min(100, (battery_abs / max_w) * 100) if max_w > 0 else 0
            bar_width = 15
            filled = int((util_pct / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            # Utilization bar always uses functional colors for readability
            bar_color = "green" if util_pct < 70 else "yellow" if util_pct < 90 else "red"
            table.add_row(
                "Inverter", 
                f"{util_pct:>5.0f}%", 
                f"[{bar_color}]{bar}[/{bar_color}]",
                ""
            )
        
        return Panel(table, title="[bold]Power Flow Summary[/bold]", border_style=self._get_border_style("blue"), box=box.ROUNDED)
        
    def render_soc_bar(self) -> Panel:
        """Render SoC bar with reserve indicator."""
        soc = self.data.soc
        reserve = self.data.reserve_soc
        target = self.data.target_soc
        
        # Create text representation of bar
        bar_width = 30
        filled = int((soc / 100) * bar_width)
        reserve_pos = int((reserve / 100) * bar_width)
        
        bar_text = Text()
        is_mono = self.config.theme in ("green", "amber", "white", "paper")
        for i in range(bar_width):
            if i < reserve_pos:
                char = "█" if i < filled else "░"
                if is_mono:
                    style = self.theme.accent_color if i < filled else "dim"
                else:
                    style = "red" if i < filled else "dim red"
            elif i < filled:
                char = "█"
                style = self.theme.accent_color if is_mono else "green"
            else:
                char = "░"
                style = "dim"
            bar_text.append(char, style=style)
            
        # Info line
        info = Text()
        info.append(f"SoC: {soc:.1f}%", style=self.theme.header_style)
        info.append(f" | Reserve: {reserve:.0f}%", style="dim")
        info.append(f" | Target: {target:.0f}%", style="dim")
        mode_color = self.theme.accent_color if is_mono else "yellow"
        info.append(f" | Mode: {self.data.operating_mode}", style=mode_color)
        
        if self.data.wset_ena == 1:
            vpp_info = Text()
            vpp_info.append("\n⚠️ REMOTE VPP CONTROL ACTIVE | ", style="bold red")
            vpp_info.append("WSetEna: ", style="dim")
            vpp_info.append("1", style="bold green")
            vpp_info.append(" | WSetPct: ", style="dim")
            vpp_info.append(f"{self.data.wset_pct:.1f}%", style="bold yellow")
            content = Text.assemble(bar_text, "\n", info, vpp_info)
        else:
            content = Text.assemble(bar_text, "\n", info)
            
        return Panel(content, title="[bold]Battery State of Charge[/bold]", border_style=self._get_border_style("green"), box=box.ROUNDED)
        
    def render_dc_power(self) -> Panel:
        """Render DC Power (Battery) panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="white", justify="right")
        table.add_column("Unit", style="dim")
        
        table.add_row("Power", f"{self.data.dc_power:,.0f}", "W")
        table.add_row("Current", f"{self.data.dc_current:.1f}", "A")
        table.add_row("SoC", f"{self.data.soc:.1f}", "%")
        table.add_row("SoH", f"{self.data.soh:.1f}", "%")
        table.add_row("Ambient Temp", f"{self.data.ambient_temp:.1f}", "°C")
        table.add_row("Cabinet Temp", f"{self.data.cabinet_temp:.1f}", "°C")
        table.add_row("Available", f"{self.data.available_wh/1000:.1f}", "kWh")
        table.add_row("Rated", f"{self.data.rated_wh/1000:.1f}", "kWh")
        
        return Panel(table, title="[bold]DC Power (Battery)[/bold]", border_style=self._get_border_style("magenta"), box=box.ROUNDED)
        
    def render_ac_power(self) -> Panel:
        """Render AC Power panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="white", justify="right")
        table.add_column("Unit", style="dim")
        
        table.add_row("Voltage", f"{self.data.ac_voltage:.1f}", "V")
        table.add_row("Current", f"{self.data.ac_current:.1f}", "A")
        table.add_row("Frequency", f"{self.data.ac_frequency:.2f}", "Hz")
        table.add_row("Power Factor", f"{self.data.ac_pf:.3f}", "")
        table.add_row("Apparent Power", f"{self.data.ac_va:.0f}", "VA")
        table.add_row("Reactive Power", f"{self.data.ac_var:.0f}", "VAR")
        table.add_row("Type", self.data.ac_type, "")
        
        return Panel(table, title=f"[bold]AC Power ({self.data.ac_type})[/bold]", border_style=self._get_border_style("yellow"), box=box.ROUNDED)
        
    def render_solar(self) -> Panel:
        """Render Solar AC Inputs panel."""
        solar = self.data.solar
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Source", style="cyan")
        table.add_column("Power", style="white", justify="right")
        
        table.add_row("Total Solar", f"{solar.total_w:,.0f}W")
        table.add_row("├─ Proximal", f"{solar.proximal_w:,.0f}W")
        table.add_row("├─ Remote 1 (APbox)", f"{solar.remote1_w:,.0f}W")
        table.add_row("└─ Remote 2", f"{solar.remote2_w:,.0f}W")
        
        return Panel(table, title="[bold]Solar AC Inputs[/bold]", border_style=self._get_border_style("bright_yellow"), box=box.ROUNDED)
        
    def render_lifetime(self) -> Panel:
        """Render Lifetime Energy panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Type", style="cyan")
        table.add_column("Energy", style="white", justify="right")
        
        # Check if lifetime data is available
        has_data = (self.data.lifetime_generated > 0 or 
                   self.data.lifetime_discharged > 0 or 
                   self.data.lifetime_charged > 0)
        
        if has_data:
            # Solar first (most important for PV owners)
            table.add_row("☀ Solar PV Total", f"{self.data.lifetime_generated/1e6:.2f} MWh")
            # Battery activity (compact, no spacer)
            table.add_row("🔋 Discharged", f"{self.data.lifetime_discharged/1e6:.2f} MWh")
            table.add_row("🔌 Charged", f"{self.data.lifetime_charged/1e6:.2f} MWh")
            # Grid lifetime (M701 accumulators)
            table.add_row("⚡ Grid Export", f"{self.data.lifetime_grid_export/1e6:.2f} MWh")
            table.add_row("📥 Grid Import", f"{self.data.lifetime_grid_import/1e6:.2f} MWh")
        else:
            table.add_row("Lifetime data not available", "", style="dim italic")
        
        return Panel(table, title="[bold]Lifetime Energy[/bold]", border_style=self._get_border_style("cyan"), box=box.ROUNDED)
        
    def render_timeline(self) -> Optional[Panel]:
        """Render timeline sparkline (placeholder for Stage 6)."""
        # Will be implemented in Stage 6
        content = Text("Timeline chart coming in Stage 6", style="dim")
        return Panel(content, title="[bold]Power Timeline (60 min)[/bold]", border_style=self._get_border_style("blue"), box=box.ROUNDED)
        
    def render_system_info(self) -> Panel:
        """Render System Info panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Model", self.data.model or "aGate X")
        table.add_row("Serial", self.data.serial or "Unknown")
        table.add_row("Firmware", self.data.firmware or "Unknown")
        table.add_row("Grid Connection", "Connected" if self.data.grid_connected else "Disconnected")
        table.add_row("Grid Mode", self.data.grid_mode)
        table.add_row("LocRemCtl", self.data.loc_rem_ctl)
        table.add_row("Derived Control", self.data.derived_control)
        table.add_row("Cabinet Temp", f"{self.data.cabinet_temp:.1f}°C")
        table.add_row("Ambient Temp", f"{self.data.ambient_temp:.1f}°C")
        
        return Panel(table, title="[bold]Device Info[/bold]", border_style=self._get_border_style("white"), box=box.ROUNDED)
        
    def render_alarms(self) -> Panel:
        """Render Alarms panel."""
        if self.data.active_alarms:
            content = Text("\n".join(f"⚠️  {alarm}" for alarm in self.data.active_alarms), style="red")
        else:
            content = Text("✓ No active alarms", style="green")
            
        if not self.data.extension_writable:
            content.append("\n⚠️  Extension: READ-ONLY (writes not applied)", style="yellow")
            
        return Panel(content, title="[bold]Alarms & Status[/bold]", 
                    border_style=self.theme.error_color if self.data.active_alarms else self._get_border_style("green"), 
                    box=box.ROUNDED)
        
    def render_command_console(self) -> Panel:
        """Render command console with recent log messages."""
        if not self.command_log:
            content = Text("No commands yet. Press c/d/s/m/M to send commands.", style="dim italic")
        else:
            content = Text()
            for i, line in enumerate(self.command_log):
                if i > 0:
                    content.append("\n")
                # Color based on message type
                if "Error" in line:
                    content.append(line, style="red")
                elif "Charge" in line:
                    content.append(line, style="green")
                elif "Discharge" in line:
                    content.append(line, style="yellow")
                elif "Standby" in line:
                    content.append(line, style="cyan")
                else:
                    content.append(line, style="white")
                    
        return Panel(content, title="[bold]Command Console[/bold]", border_style=self._get_border_style("blue"), box=box.ROUNDED)
        
    def render_footer(self) -> Panel:
        """Render footer with keyboard shortcuts or prompt."""
        if self.show_prompt and self.prompt_mode:
            # Show input prompt with context
            if self.prompt_mode == 'mode':
                prompt_text = f"Set native mode (1=Backup, 2=Self, 3=TOU, 4=Manual): {self.prompt_buffer}_"
            elif self.prompt_mode == 'self_reserve':
                prompt_text = f"Set Self-Consumption Reserve % (0-100): {self.prompt_buffer}_"
            elif self.prompt_mode == 'tou_reserve':
                prompt_text = f"Set TOU Reserve % (0-100): {self.prompt_buffer}_"
            else:
                prompt_text = f"{self.prompt_mode.capitalize()} watts: {self.prompt_buffer}_"
            content = Text(prompt_text, style="bold yellow")
            content.append(" [Enter=send Esc=cancel]", style="dim")
            return Panel(content, box=box.SIMPLE, padding=(0, 1), border_style=self._get_border_style("yellow"))
        else:
            # Show normal shortcuts - organized by function
            line1 = Text()
            line1.append("[c]", style="bold cyan")
            line1.append("=charge ", style="dim")
            line1.append("[d]", style="bold cyan")
            line1.append("=discharge ", style="dim")
            line1.append("[s]", style="bold cyan")
            line1.append("=standby(0W) ", style="dim")
            line1.append("[r]", style="bold cyan")
            line1.append("=release ", style="dim")
            line1.append("[q]", style="bold cyan")
            line1.append("=quit", style="dim")
            
            if self.data.extension_writable:
                line1.append(" [o]", style="bold cyan")
                line1.append("=mode", style="dim")
                line1.append(" [v]", style="bold cyan")
                line1.append("=self_res", style="dim")
                line1.append(" [t]", style="bold cyan")
                line1.append("=tou_res", style="dim")
            
            line2 = Text()
            line2.append("[m]", style="bold cyan")
            line2.append("=max▲ ", style="dim")
            line2.append("[M]", style="bold cyan")
            line2.append("=max▼ ", style="dim")
            line2.append("[+]", style="bold cyan")
            line2.append("=+100W ", style="dim")
            line2.append("[-]", style="bold cyan")
            line2.append("=-100W ", style="dim")
            line2.append("[R]", style="bold cyan")
            line2.append("=pause ", style="dim")
            line2.append("[1-9]", style="bold cyan")
            line2.append("=rate ", style="dim")
            line2.append("[h]", style="bold cyan")
            line2.append("=help", style="dim")
            
            from rich.console import Group
            content = Group(line1, line2)
            
            return Panel(content, box=box.SIMPLE, padding=(0, 1))
        
    def render_help(self) -> Panel:
        """Render help overlay panel."""
        help_text = """
[c] Charge mode      - Enter watts to charge battery
[d] Discharge mode   - Enter watts to discharge battery
[s] Standby          - Set to 0W (keep control)
[r] Release          - Give control back to cloud/app
[m] Max charge       - Charge at maximum rate
[M] Max discharge    - Discharge at maximum rate
[+] Increase power   - Add 100W to current setting
[-] Decrease power   - Subtract 100W from current setting
[R] Toggle refresh   - Pause/resume display updates
[1-9] Set rate       - Change refresh interval (seconds)
[h] Toggle help      - Show/hide this help
[q] Quit             - Exit monitor
        """.strip()
        
        if self.data.extension_writable:
            help_text += "\n[o] Native Mode      - Set native mode (1=Backup, 2=Self, 3=TOU, 4=Manual)\n[v] Self Reserve     - Set Self-Consumption Reserve %\n[t] TOU Reserve      - Set TOU Reserve %"
            
        content = Text(help_text)
        return Panel(content, title="[bold]Keyboard Help[/bold] (press h to close)", 
                    border_style=self._get_border_style("cyan"), box=box.DOUBLE)
        
    def update_display(self) -> Layout:
        """Update all panels and return the layout."""
        layout = self.create_layout()
        
        layout["header"].update(self.render_header())
        layout["footer"].update(self.render_footer())
        
        # If help is shown, unsplit body and show help full-screen
        if self.show_help:
            layout["body"].unsplit()
            layout["body"].update(self.render_help())
        else:
            layout["power_flow"].update(self.render_power_flow())
            layout["soc_bar"].update(self.render_soc_bar())
            layout["dc_power"].update(self.render_dc_power())
            layout["ac_power"].update(self.render_ac_power())
            layout["solar"].update(self.render_solar())
            layout["lifetime"].update(self.render_lifetime())
            layout["command_console"].update(self.render_command_console())
        
        return layout
        
    def run_simple_mode(self):
        """Run in simple ANSI mode (no Rich)."""
        print("FranklinWH CLI Monitor - Simple Mode")
        print(f"Device: {self.config.ip_address}:{self.config.port}")
        print("-" * 60)
        print("Rich library not available. Install with: pip install rich")
        print("Or use: python -m pip install rich")
        print("-" * 60)
        print()
        print("Press Ctrl+C to exit")
        
        self.running = True
        try:
            while self.running:
                if not self.paused:
                    # Simple data fetch and display
                    self.fetch_data()
                    print(f"\rSoC: {self.data.soc:.1f}% | Power: {self.data.dc_power:.0f}W | "
                          f"Grid: {self.data.power_flow.grid_w:.0f}W | "
                          f"Solar: {self.data.solar.total_w:.0f}W", end="", flush=True)
                time.sleep(self.config.refresh_rate)
        except KeyboardInterrupt:
            pass
        finally:
            print("\n\nExiting...")
            self.disconnect()
            
    def _handle_key(self, key: str) -> bool:
        """Handle a single keypress. Returns False if should quit."""
        # Handle prompt mode (accumulating input)
        if self.show_prompt:
            return self._handle_prompt_key(key)
        
        # Normal mode - command shortcuts
        # Track keystroke for feedback (only printable keys)
        if key.isprintable() and len(key) == 1:
            self.last_key = key
            self.last_key_time = time.time()
        
        # Help toggle
        if key in 'hH?':
            self.show_help = not self.show_help
            return True
        
        # Number keys 1-9 set refresh rate
        if key in '123456789':
            self.config.refresh_rate = int(key)
            self._log_command(f"Refresh: {key}s")
            return True
            
        # Quit keys - q, Q, Ctrl+C (0x03), or Escape (0x1b)
        if key in 'qQ' or ord(key) == 3:  # 3 = Ctrl+C
            return False
            
        # Toggle refresh
        if key in 'R':
            self.paused = not self.paused
            self._log_command("Paused" if self.paused else "Resumed")
            return True
            
        # Standby
        if key == 's':
            self._send_command(0)
            return True
            
        # Reset control
        if key == 'r':
            if self.controller:
                self.controller.reset_control_state()
                self._log_command("Released control (aGate native mode)")
            return True
            
        # Max charge
        if key == 'm':
            if self.controller:
                self._send_command(self.controller.RATED_MAX_CHARGE_W)
            return True
            
        # Max discharge
        if key == 'M':
            if self.controller:
                self._send_command(-self.controller.RATED_MAX_DISCHARGE_W)
            return True
            
        # Increase/decrease power
        if key == '+':
            self._adjust_power(100)
            return True
        if key == '-':
            self._adjust_power(-100)
            return True
            
        # Charge mode - enter prompt mode
        if key == 'c':
            self.show_prompt = True
            self.prompt_mode = 'charge'
            self.prompt_buffer = ""
            return True
            
        # Discharge mode - enter prompt mode
        if key == 'd':
            self.show_prompt = True
            self.prompt_mode = 'discharge'
            self.prompt_buffer = ""
            return True
            
        # Native Mode - enter prompt mode if extension writable
        if key == 'o':
            if self.data.extension_writable:
                self.show_prompt = True
                self.prompt_mode = 'mode'
                self.prompt_buffer = ""
            return True

        # Self-Consumption Reserve - enter prompt mode if extension writable
        if key == 'v':
            if self.data.extension_writable:
                self.show_prompt = True
                self.prompt_mode = 'self_reserve'
                self.prompt_buffer = ""
            return True

        # TOU Reserve - enter prompt mode if extension writable
        if key == 't':
            if self.data.extension_writable:
                self.show_prompt = True
                self.prompt_mode = 'tou_reserve'
                self.prompt_buffer = ""
            return True
            
        return True
        
    def _handle_prompt_key(self, key: str) -> bool:
        """Handle key when in prompt mode."""
        # Enter - submit command (\r=13 or \n=10)
        if ord(key) in (10, 13):
            try:
                val = int(self.prompt_buffer) if self.prompt_buffer else 0
                if self.prompt_mode == 'charge':
                    self._send_command(abs(val))  # Positive = charge
                elif self.prompt_mode == 'discharge':
                    self._send_command(-abs(val))  # Negative = discharge
                elif self.prompt_mode == 'mode':
                    if self.controller:
                        success, msg = self.controller.set_native_mode(val)
                        self._log_command(f"Mode set {val}: {'Success' if success else 'Error: ' + msg}")
                elif self.prompt_mode == 'self_reserve':
                    if self.controller:
                        success, msg = self.controller.set_self_consumption_reserve(val)
                        self._log_command(f"Self reserve set {val}%: {'Success' if success else 'Error: ' + msg}")
                elif self.prompt_mode == 'tou_reserve':
                    if self.controller:
                        success, msg = self.controller.set_tou_reserve(val)
                        self._log_command(f"TOU reserve set {val}%: {'Success' if success else 'Error: ' + msg}")
            except ValueError:
                self._log_command("Error: Invalid number")
            # Exit prompt mode
            self.show_prompt = False
            self.prompt_buffer = ""
            self.prompt_mode = None
            return True
            
        # Escape (0x1b) or Ctrl+C (0x03) - cancel prompt
        if ord(key) == 27 or ord(key) == 3:  # Escape or Ctrl+C
            self.show_prompt = False
            self.prompt_buffer = ""
            self.prompt_mode = None
            self._log_command("Cancelled")
            return True
            
        # Backspace (0x7f or 0x08)
        if ord(key) == 127 or ord(key) == 8:
            self.prompt_buffer = self.prompt_buffer[:-1]
            return True
            
        # Digits
        if key.isdigit():
            self.prompt_buffer += key
            return True
            
        return True
        
    def _log_command(self, message: str):
        """Add a message to the command log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.command_log.append(f"[{timestamp}] {message}")
        # Keep only recent lines
        if len(self.command_log) > self.max_log_lines:
            self.command_log.pop(0)
            
    def _send_command(self, power_w: int):
        """Send power command to battery."""
        if not self.controller:
            self._log_command("Error: No controller connected")
            return
        if not self.controller.is_connected():
            self._log_command("Error: Modbus disconnected — reconnecting...")
            if not self.controller.reconnect():
                self._log_command("Error: Reconnect failed")
                return
        try:
            from .types import BatteryCommand
            cmd = BatteryCommand(power_watts=power_w)
            success, msg = self.controller.send_command(cmd)
            self.current_power = power_w
            
            # Log the command with result
            if power_w > 0:
                action = f"Charge: {power_w}W"
            elif power_w < 0:
                action = f"Discharge: {abs(power_w)}W"
            else:
                action = "Standby (0W)"
            
            if success:
                self._log_command(f"{action} — OK")
            else:
                self._log_command(f"{action} — FAILED: {msg}")
                
        except Exception as e:
            self._log_command(f"Error: {str(e)[:50]}")
            
    def _adjust_power(self, delta: int):
        """Adjust current power by delta."""
        new_power = self.current_power + delta
        self._send_command(new_power)
        
    def run(self):
        """Run the monitor with Rich."""
        if not HAS_RICH or not self.config.use_rich:
            return self.run_simple_mode()
            
        if not self.connect():
            return 1
            
        self.running = True
        self.input_handler.start()
        last_data_fetch = 0
        last_display_update = 0
        
        # Suppress all stream handlers while Rich Live owns the screen.
        # Logger messages to stderr disrupt the alternate screen buffer.
        root_logger = logging.getLogger()
        saved_handlers = []
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                saved_handlers.append(handler)
                root_logger.removeHandler(handler)
        
        try:
            with Live(
                self.update_display(),
                console=self.console,
                screen=True,
                refresh_per_second=10  # 100ms updates - smooth but not flickering
            ) as live:
                while self.running:
                    # Check for keyboard input
                    key = self.input_handler.get_key()
                    if key is not None:
                        if not self._handle_key(key):
                            break
                    
                    # Data fetch at configured rate
                    now = time.time()
                    data_changed = False
                    if not self.paused and (now - last_data_fetch) >= self.config.refresh_rate:
                        self.fetch_data()
                        last_data_fetch = now
                        data_changed = True
                    
                    # Update display if data changed or enough time passed
                    if data_changed or (now - last_display_update) >= 0.5:
                        live.update(self.update_display())
                        last_display_update = now
                    
                    # Sleep to prevent CPU spinning
                    time.sleep(0.05)  # 50ms - 20 FPS check rate
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.input_handler.stop()
            self.disconnect()
            # Restore logger handlers
            for handler in saved_handlers:
                root_logger.addHandler(handler)
            
        return 0


def main():
    """Main entry point for standalone monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FranklinWH CLI Monitor")
    parser.add_argument("-i", "--ip", required=True, help="aGate IP address")
    parser.add_argument("-p", "--port", type=int, default=502, help="Modbus port")
    parser.add_argument("-u", "--unit", type=int, default=2, help="Modbus unit ID")
    parser.add_argument("-r", "--refresh", type=float, default=5.0, help="Refresh rate (seconds)")
    parser.add_argument("--no-rich", action="store_true", help="Use simple ANSI mode")
    parser.add_argument("--theme", default="dark", choices=["dark", "light"], help="Color theme")
    
    args = parser.parse_args()
    
    config = MonitorConfig(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit,
        refresh_rate=args.refresh,
        use_rich=not args.no_rich,
        theme=args.theme
    )
    
    monitor = CLIMonitor(config)
    return monitor.run()


if __name__ == "__main__":
    sys.exit(main())
