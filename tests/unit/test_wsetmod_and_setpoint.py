"""#114 A2/A6 and A3.

A2/A6: ControlMode had four values (LIMIT_ABS 0 ... SET_IMPORT 3); SunSpec 704
WSetMod has two (0 W_MAX_PCT, 1 WATTS). send_command ignored the mode.
A3: check_state()['actual_power'] was the setpoint, not measured power, and
battery_activity under Modbus control was taken from the setpoint.
"""
import json
import logging
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sunspec2

from franklinwh_modbus import BatteryCommand, ControlMode, FranklinWHController

ROOT = Path(__file__).resolve().parents[2]


def test_controlmode_matches_sunspec():
    with open(os.path.join(os.path.dirname(sunspec2.__file__), 'models', 'json', 'model_704.json')) as f:
        points = {p['name']: p for p in json.load(f)['group']['points']}
    spec = {s['value']: s['name'] for s in points['WSetMod']['symbols']}
    assert {m.value: m.name for m in ControlMode} == spec


def test_default_mode_is_watts():
    assert BatteryCommand(power_watts=500).mode == ControlMode.WATTS


def test_no_invalid_wsetmod_writes():
    pattern = re.compile(r'WSetMod\.value\s*=\s*(\d+)')
    for path in list((ROOT / 'src').rglob('*.py')) + list((ROOT / 'tools').glob('*.py')):
        for value in pattern.findall(path.read_text()):
            assert int(value) in (0, 1), f"{path.name} writes WSetMod={value}"


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    return c


def test_percent_mode_refused_without_writes(ctrl, caplog):
    m704 = MagicMock()
    ctrl.models = {704: m704}
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ok, msg = ctrl.send_command(BatteryCommand(power_watts=500, mode=ControlMode.W_MAX_PCT))
    assert not ok and 'W_MAX_PCT' in msg
    assert any('Command not sent' in r.getMessage() for r in caplog.records)
    m704.write.assert_not_called()


def _state(ctrl, wset_ena=1, wset_watts=1000, dcw=400):
    ctrl.read_battery_status = lambda: {'soc': 50, 'battery_power_w': dcw}
    ctrl.read_grid_status = lambda: {'grid_power_w': 0, 'voltage_v': 230, 'connection_state': 'Connected'}
    ctrl.read_control_status = lambda: {'wset_enabled': wset_ena, 'wset_mode': 1,
                                        'wset_watts': wset_watts, 'wset_pct': 0}
    ctrl.read_native_mode = lambda: {}
    ctrl.read_alarms = lambda: {}
    ctrl.active_alarms = lambda a=None: []
    ctrl._read_extension_solar = lambda: {}
    ctrl.models = {}
    return ctrl.check_state()


def test_setpoint_and_measured_reported_separately(ctrl):
    st = _state(ctrl)
    assert st['setpoint_w'] == 1000
    assert st['measured_dc_w'] == 400
    assert st['battery_activity'] == 'Discharging (400W, setpoint 1000W)'


def test_activity_follows_measured_power(ctrl):
    st = _state(ctrl, wset_watts=1000, dcw=0)
    assert st['battery_activity'] == 'Idle (setpoint 1000W)'


def test_actual_power_deprecated_alias(ctrl):
    st = _state(ctrl)
    with pytest.warns(DeprecationWarning, match='setpoint_w'):
        assert st['actual_power'] == 1000
    with pytest.warns(DeprecationWarning):
        assert st.get('actual_power') == 1000
