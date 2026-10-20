"""
Regression test for #42: --status --detail must label AC Type with the
source it is actually derived from (the M701.LNV voltage band), not
M701.ACType, which the library does not read.
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.franklinwh_cli import print_status


def test_ac_type_label_names_its_real_source(capsys):
    ctrl = MagicMock()
    for name in ('read_nameplate', 'read_battery_status', 'read_solar_status',
                 'read_control_status', 'read_native_mode', 'read_alarms',
                 'get_command_timer_status'):
        getattr(ctrl, name).return_value = {}
    ctrl.read_grid_status.return_value = {'ac_type': 'Single-Phase (230V Nominal)',
                                          'voltage_v': 240.0}
    ctrl.active_alarms.return_value = []
    print_status(ctrl)
    line = next(l for l in capsys.readouterr().out.splitlines() if 'AC Type:' in l)
    assert '(derived from M701.LNV)' in line
    assert 'M701.ACType' not in line
