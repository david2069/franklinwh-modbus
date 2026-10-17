"""
The library reports alarms; deciding what to do about them is the client's job
(owner direction 2026-10-15, #40, #46).

- active_alarms() lists every active alarm by name.
- healthcheck() lists alarms but its verdict doesn't depend on them.
- check_blocking_alarms() still works but is deprecated.
- VirtualModeController.run_continuous() no longer stops on alarms.
"""
import threading
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.modes import VirtualModeController


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    return c


def _alarms(system=(), dc_port=(), solar=(), battery='OK'):
    return {'system_alrm': 1 if system else 0, 'dc_port_alrm': 0, 'battery_sta': 0,
            'solar_evt': 0, 'vendor_info': '',
            'decoded': {'system': list(system), 'dc_port': list(dc_port),
                        'solar': list(solar), 'battery_status': battery,
                        'vendor_info': ''}}


def test_active_alarms_lists_everything(ctrl):
    a = _alarms(system=['GROUND_FAULT'], dc_port=['Port 0: OVER_TEMP'],
                solar=['DC_DISCONNECT'], battery='ERROR')
    assert ctrl.active_alarms(a) == ['GROUND_FAULT', 'Port 0: OVER_TEMP',
                                     'Solar: DC_DISCONNECT', 'Battery: ERROR']


def test_active_alarms_empty_when_ok(ctrl):
    assert ctrl.active_alarms(_alarms()) == []


def test_check_blocking_alarms_is_deprecated(ctrl):
    with patch.object(ctrl, 'read_alarms', return_value=_alarms()), \
         pytest.warns(DeprecationWarning):
        ctrl.check_blocking_alarms()


def _health_ctrl(ctrl, alarms):
    ctrl.models = {701: MagicMock(), 704: MagicMock(), 713: MagicMock()}
    patches = [
        patch.object(ctrl, 'read_alarms', return_value=alarms),
        patch.object(ctrl, 'read_battery_status', return_value={'soc': 50.0}),
        patch.object(ctrl, 'read_control_status', return_value={'wset_enabled': 0, 'wset_pct': 0}),
        patch.object(ctrl, 'read_native_mode', return_value={'mode_name': 'Self-Consumption'}),
        patch.object(ctrl, 'read_nameplate', return_value={}),
        patch.object(ctrl, 'check_blocking_alarms', side_effect=AssertionError('policy call')),
    ]
    return patches


def test_healthcheck_lists_alarms_without_changing_the_verdict(ctrl):
    a = _alarms(system=['GROUND_FAULT'])
    patches = _health_ctrl(ctrl, a)
    for p in patches:
        p.start()
    try:
        with_alarm = ctrl.healthcheck()
        for p in patches:
            p.stop()
        patches = _health_ctrl(ctrl, _alarms())
        for p in patches:
            p.start()
        without = ctrl.healthcheck()
    finally:
        for p in patches:
            p.stop()
    assert with_alarm.details['alarms'] == ['GROUND_FAULT']
    assert without.details['alarms'] == []
    assert with_alarm.healthy == without.healthy
    assert with_alarm.message == without.message
    assert any('GROUND_FAULT' in r for r in with_alarm.recommendations)


def test_run_continuous_does_not_stop_on_alarms():
    c = MagicMock()
    c.check_blocking_alarms.return_value = (False, ['GROUND_FAULT'])
    c.read_alarms.return_value = _alarms(system=['GROUND_FAULT'])
    c.is_connected.return_value = True
    vmc = VirtualModeController.__new__(VirtualModeController)
    vmc.ctrl = c
    stop = threading.Event()
    with patch.object(VirtualModeController, 'is_off_grid', return_value=False), \
         patch.object(VirtualModeController, 'tick', return_value=True), \
         patch.object(VirtualModeController, 'verify_command_execution', return_value=None), \
         patch.object(VirtualModeController, 'calculate_power', return_value=0), \
         patch('franklinwh_modbus.modes.time.sleep'):
        threading.Timer(0.3, stop.set).start()
        vmc.max_charge_soc, vmc.min_discharge_soc = 100, 0
        c.read_battery_status.return_value = {'soc': 50}
        vmc.run_continuous(enable_safety_checks=True, stop_event=stop)
    c.check_blocking_alarms.assert_not_called()


def test_active_alarms_reports_a_failed_read(ctrl):
    # A failed read must not come back as [] ("no alarms").
    a = _alarms()
    a['error'] = 'timed out'
    assert ctrl.active_alarms(a) == ['Alarm read failed: timed out']


def test_deprecated_check_blocks_on_a_failed_read(ctrl):
    a = _alarms()
    a['error'] = 'timed out'
    with patch.object(ctrl, 'read_alarms', return_value=a), \
         warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        ok, reasons = ctrl.check_blocking_alarms()
    assert ok is False
    assert reasons == ['ALARM_READ_FAILED: timed out']
