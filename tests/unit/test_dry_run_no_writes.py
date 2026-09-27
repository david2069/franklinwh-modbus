"""Regression tests: a dry run must not engage control.

`set_mode()` applies the new mode immediately via `execute_once()`. Before the
fix it took no `dry_run` parameter, so `franklinwh_cli.py --vmode ... --dry-run`
wrote `WSetEna=1 / WSetPct=100.0` to the device and then reported
"no commands sent". Observed on an aGate X (V10R01B04D00) on 2026-09-23 and
witnessed independently by the Local Bridge orphaned-dispatch alert.
"""

import pytest
from unittest.mock import MagicMock, patch

from franklinwh_modbus import FranklinWHController, VirtualModeController, VirtualMode


@pytest.fixture
def vmc():
    """A VirtualModeController over a controller whose device layer is mocked."""
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1')
        ctrl.dev = MagicMock()
        ctrl.send_command = MagicMock(return_value=(True, "Dry Run: WSetPct=-1000 (-5000W)"))
        ctrl.read_battery_status = MagicMock(return_value={'soc': 19.0})
        ctrl.check_state = MagicMock(return_value={'conflicts': []})

        controller = VirtualModeController(ctrl, min_discharge_soc=5)
        controller.read_status = MagicMock(return_value={
            'solar': {'dc_power_w': 0},
            'derived': {'home_load_w': 260},
            'grid': {'grid_power_w': 0, 'connection_state': 'Connected'},
            'battery': {'soc': 19.0},
        })
        return controller


def test_execute_once_dry_run_does_not_write(vmc):
    """execute_once(dry_run=True) must pass dry_run through to send_command."""
    vmc.execute_once(dry_run=True)

    vmc.ctrl.send_command.assert_called_once()
    assert vmc.ctrl.send_command.call_args.kwargs.get('dry_run') is True


def test_execute_once_default_still_writes(vmc):
    """The default path is unchanged: a real run still commands the device."""
    vmc.execute_once()

    vmc.ctrl.send_command.assert_called_once()
    assert vmc.ctrl.send_command.call_args.kwargs.get('dry_run') is False


def test_set_mode_dry_run_does_not_engage_control(vmc):
    """set_mode(dry_run=True) must not write — the original defect."""
    vmc.set_mode(VirtualMode.SELF_CONSUMPTION, dry_run=True, target_soc=90)

    assert vmc.ctrl.send_command.call_args.kwargs.get('dry_run') is True, (
        "set_mode(dry_run=True) reached send_command without dry_run — "
        "this is the bug that engaged WSetEna=1/WSetPct=100.0 on live hardware"
    )


def test_set_mode_dry_run_records_no_commanded_power(vmc):
    """A dry run must not record a commanded power.

    The attribute is initialised to 0.0 in __init__, so the assertion is that
    a dry run leaves it untouched rather than that it is absent.
    """
    vmc._last_commanded_power = -1234.0   # sentinel
    vmc.set_mode(VirtualMode.SELF_CONSUMPTION, dry_run=True, target_soc=90)

    assert vmc._last_commanded_power == -1234.0, (
        "dry run overwrote _last_commanded_power — it recorded a command it never sent"
    )


def test_set_mode_still_applies_kwargs_with_dry_run(vmc):
    """dry_run must not be swallowed into the attribute-setting kwargs loop."""
    vmc.set_mode(VirtualMode.SELF_CONSUMPTION, dry_run=True, target_soc=90)

    assert vmc.target_soc == 90
    assert not hasattr(vmc, 'dry_run'), "dry_run leaked into instance attributes"
