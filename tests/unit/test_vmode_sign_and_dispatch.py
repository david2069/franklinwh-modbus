"""
Regression tests for issues #20, #21 and #22.

#20  Virtual-mode calculators return BatteryCommand convention
     (positive = charge, negative = discharge), so the SoC limiter ramps
     and blocks the right direction. Ramp tests sit inside the ramp
     window (SoC 26% against a 20% floor), where the inversion hid.
#21  verify_dispatch() reads back WSetPct and M714.DCW and reports a
     dispatch the device ignored.
#22  Read failures are recorded and logged at warning level.
"""
import logging
from unittest.mock import Mock, MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController, VirtualModeController
from franklinwh_modbus.schedule import TOUSchedule


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def mock_ctrl():
    ctrl = Mock(spec=FranklinWHController)
    ctrl.RATED_MAX_CHARGE_W = 5000
    ctrl.RATED_MAX_DISCHARGE_W = 5000
    return ctrl


@pytest.fixture
def vmc(mock_ctrl):
    v = VirtualModeController(mock_ctrl, min_discharge_soc=20, soc_ramp_window=10)
    v.self_reserve_pct = 20
    v.target_soc = 100
    return v


@pytest.fixture
def real_ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1')
    ctrl.dev = MagicMock()
    return ctrl


def _models(wset_pct, wset_ena, dcw_per_port):
    """Mock M704/M714 with hardware conventions (+WSetPct / +DCW = discharge)."""
    m704 = MagicMock()
    m704.WSetPct_SF = MagicMock(value=0)
    m704.WSetPct.value = wset_pct
    m704.WSetEna.value = wset_ena
    m714 = MagicMock()
    m714.DCW_SF = MagicMock(value=0)
    blocks = [MagicMock()]
    for w in dcw_per_port:
        b = MagicMock()
        b.DCW.value = w
        blocks.append(b)
    m714.blocks = blocks
    return {704: m704, 714: m714}


# ------------------------------------------------------ #20 calculator signs

class TestCalculatorSigns:

    def test_self_consumption_below_reserve_charges_full_power(self, vmc):
        assert vmc._calc_self_consumption(solar=0, home=1000, grid=1000, soc=15) == 5000

    def test_self_consumption_deficit_discharges(self, vmc):
        assert vmc._calc_self_consumption(solar=500, home=2500, grid=0, soc=60) == -2000

    def test_self_consumption_deficit_capped_at_rating(self, vmc):
        assert vmc._calc_self_consumption(solar=0, home=9000, grid=0, soc=60) == -5000

    def test_self_consumption_excess_solar_charges(self, vmc):
        assert vmc._calc_self_consumption(solar=3000, home=1000, grid=0, soc=60) == 2000

    def test_self_consumption_excess_solar_idle_at_target(self, vmc):
        vmc.target_soc = 90
        assert vmc._calc_self_consumption(solar=3000, home=1000, grid=0, soc=90) == 0

    def test_self_consumption_does_not_grid_charge_above_reserve(self, vmc):
        # Previously: any SoC below target_soc (default 100) returned full charge
        assert vmc._calc_self_consumption(solar=0, home=0, grid=0, soc=50) == 0

    def test_peak_shave_discharges(self, vmc):
        vmc.peak_shave_threshold = 2000
        assert vmc._calc_peak_shave(solar=500, home=3500, grid=3000, soc=60) == -3000

    def test_peak_shave_idle_when_solar_covers_load(self, vmc):
        vmc.peak_shave_threshold = 2000
        assert vmc._calc_peak_shave(solar=4000, home=3500, grid=0, soc=60) == 0

    def test_tou_discharge_strategy_discharges(self, vmc):
        vmc.tou = Mock(spec=TOUSchedule)
        vmc.tou.get_strategy.return_value = "discharge"
        vmc.tou.get_min_soc.return_value = 10
        vmc.tou.get_max_soc.return_value = 100
        assert vmc._calc_time_of_use(solar=0, home=1800, grid=0, soc=60) == -1800

    def test_tou_charge_strategy_charges(self, vmc):
        vmc.tou = Mock(spec=TOUSchedule)
        vmc.tou.get_strategy.return_value = "charge"
        vmc.tou.get_min_soc.return_value = 10
        vmc.tou.get_max_soc.return_value = 100
        assert vmc._calc_time_of_use(solar=0, home=1000, grid=0, soc=60) == 5000


# ------------------------------------------- #20 limiter inside ramp window

class TestRampWindow:
    """Floor 20%, window 10% -> discharge ramp between 20% and 30%."""

    def test_charge_inside_discharge_window_untouched(self, vmc):
        assert vmc._apply_safety_limits(5000, soc=26.0) == 5000

    def test_discharge_inside_window_ramped(self, vmc):
        # ramp_progress = (30 - 26) / 10 = 0.4 -> factor 0.6
        assert vmc._apply_safety_limits(-500, soc=26.0) == pytest.approx(-300)

    def test_self_consumption_reserve_charge_survives_limiter(self, vmc):
        # Old sign: -5000 read as a discharge and ramped to -3000 at 26%
        vmc.self_reserve_pct = 30
        power = vmc._calc_self_consumption(solar=0, home=1000, grid=1000, soc=26.0)
        assert vmc._apply_safety_limits(power, soc=26.0) == 5000

    def test_discharge_below_floor_blocked(self, vmc):
        assert vmc._apply_safety_limits(-500, soc=19.0) == 0

    def test_ramp_is_logged_once(self, vmc, caplog):
        with caplog.at_level(logging.INFO, logger='franklinwh_modbus.modes'):
            vmc._apply_safety_limits(-500, soc=26.0)
            vmc._apply_safety_limits(-500, soc=26.0)
        ramp_logs = [r for r in caplog.records if 'discharge limit' in r.getMessage()]
        assert len(ramp_logs) == 1
        assert '300W of 500W' in ramp_logs[0].getMessage()


# ------------------------------------------------------ #21 verify_dispatch

class TestVerifyDispatch:

    def _verify(self, ctrl, models, expected, **kw):
        with patch.object(ctrl, 'get_model', side_effect=models.get):
            return ctrl.verify_dispatch(expected, **kw)

    def test_charge_verified(self, real_ctrl):
        # hardware -30% = charge 1500W; DCW negative = into battery
        r = self._verify(real_ctrl, _models(-30, 1, [-1480]), 1500)
        assert r['ok'] and r['dispatched']
        assert r['commanded_w'] == 1500 and r['actual_w'] == 1480

    def test_ignored_dispatch_detected(self, real_ctrl):
        # Bridge #26: WSetEna=1, setpoint 100%, battery stays at 0W
        r = self._verify(real_ctrl, _models(100, 1, [0]), -5000)
        assert not r['ok'] and not r['dispatched']
        assert 'not responding' in r['reason']

    def test_wrong_direction_detected(self, real_ctrl):
        r = self._verify(real_ctrl, _models(-30, 1, [-1500]), -1500)
        assert not r['ok']
        assert 'setpoint mismatch' in r['reason']

    def test_not_enabled_detected(self, real_ctrl):
        r = self._verify(real_ctrl, _models(-30, 0, [0]), 1500)
        assert not r['ok']
        assert 'not enabled' in r['reason']

    def test_moving_but_outside_tolerance(self, real_ctrl):
        r = self._verify(real_ctrl, _models(-60, 1, [-1000]), 3000)
        assert r['dispatched'] and not r['ok']
        assert 'outside' in r['reason']

    def test_release_verified(self, real_ctrl):
        r = self._verify(real_ctrl, _models(0, 0, [0]), 0)
        assert r['ok']

    def test_readback_failure_does_not_fail_open(self, real_ctrl):
        with patch.object(real_ctrl, '_read_dispatch_state', side_effect=OSError('EPIPE')):
            r = real_ctrl.verify_dispatch(1500)
        assert not r['ok']
        assert 'readback failed' in r['reason']

    def test_polls_until_battery_responds(self, real_ctrl):
        states = iter([
            {'enabled': True, 'wset_pct': -30, 'commanded_w': 1500, 'actual_w': 0},
            {'enabled': True, 'wset_pct': -30, 'commanded_w': 1500, 'actual_w': 1500},
        ])
        with patch.object(real_ctrl, '_read_dispatch_state', side_effect=lambda: next(states)), \
             patch('franklinwh_modbus.controller.time.sleep'):
            r = real_ctrl.verify_dispatch(1500, timeout_s=10, poll_interval_s=1)
        assert r['ok']

    def _verify_state(self, ctrl, state, expected):
        with patch.object(ctrl, '_read_dispatch_state', return_value=state):
            return ctrl.verify_dispatch(expected)

    def test_small_command_verified_on_setpoint(self, real_ctrl):
        # 80W self-consumption trim: DCW reads in 100W steps, so 0W is expected
        r = self._verify_state(real_ctrl, {'enabled': True, 'wset_pct': -1.6,
                                           'commanded_w': 80, 'actual_w': 0}, 80)
        assert r['ok'] and 'below battery power resolution' in r['reason']

    def test_small_command_wrong_direction_still_detected(self, real_ctrl):
        r = self._verify_state(real_ctrl, {'enabled': True, 'wset_pct': 1.6,
                                           'commanded_w': -80, 'actual_w': 0}, 80)
        assert not r['ok'] and 'setpoint mismatch' in r['reason']

    def test_quantised_readback_within_floor(self, real_ctrl):
        # 300W reads back as 200W: 33% off, but within the 100W DCW step
        r = self._verify_state(real_ctrl, {'enabled': True, 'wset_pct': -6,
                                           'commanded_w': 300, 'actual_w': 200}, 300)
        assert r['ok']

    def test_ignored_small_but_verifiable_command_detected(self, real_ctrl):
        r = self._verify_state(real_ctrl, {'enabled': True, 'wset_pct': -6,
                                           'commanded_w': 300, 'actual_w': 0}, 300)
        assert not r['ok'] and 'not responding' in r['reason']


# ------------------------------------------------- #22 read-failure surfacing

class TestReadFailureTracking:

    def test_failure_recorded_and_warned_once(self, real_ctrl, caplog):
        with patch.object(real_ctrl, 'get_model', side_effect=BrokenPipeError(32, 'Broken pipe')), \
             patch.object(real_ctrl, 'reconnect', return_value=False), \
             caplog.at_level(logging.DEBUG, logger='franklinwh_modbus.controller'):
            assert real_ctrl.read_battery_status() == {}
            assert real_ctrl.read_grid_status() == {}
        assert real_ctrl.consecutive_failures == 2
        assert 'Broken pipe' in real_ctrl.last_error
        warnings = [r for r in caplog.records
                    if r.levelno == logging.WARNING and 'Failed to read' in r.getMessage()]
        assert len(warnings) == 1

    def test_success_resets_failures(self, real_ctrl):
        real_ctrl._record_read_failure('battery status', OSError('x'))
        assert real_ctrl._with_retry(lambda: {'soc': 50}) == {'soc': 50}
        assert real_ctrl.consecutive_failures == 0
        assert real_ctrl.data_age_s is not None and real_ctrl.data_age_s < 5
