"""
Regression test: the rating clamp must keep the requested direction.

_validate_power() returned -limit for an over-limit charge, so e.g. a
6000 W charge on a 5000 W unit went out as a 5000 W discharge (and vice
versa). BatteryCommand allows up to +/-10000 W, so any request between the
device rating and 10000 W reached the inverted branch.
"""
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController, BatteryCommand


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    c.RATED_MAX_CHARGE_W = 5000
    c.RATED_MAX_DISCHARGE_W = 5000
    return c


@pytest.mark.parametrize('requested, expected', [
    (6000, 5000),      # over-limit charge stays charge
    (-6000, -5000),    # over-limit discharge stays discharge
    (5000, 5000),
    (-4000, -4000),
    (0, 0),
])
def test_clamp_keeps_direction(ctrl, requested, expected):
    assert ctrl._validate_power(requested) == expected


def test_asymmetric_ratings(ctrl):
    # Bridge sends up to max(charge, discharge); the smaller side must clamp, not flip
    ctrl.RATED_MAX_CHARGE_W = 5000
    ctrl.RATED_MAX_DISCHARGE_W = 10000
    assert ctrl._validate_power(10000) == 5000
    assert ctrl._validate_power(-10000) == -10000


def test_over_limit_charge_writes_charge_setpoint(ctrl):
    # Hardware WSetPct: negative = charge
    m704 = MagicMock()
    m704.WSetPct_SF = MagicMock(value=0)
    with patch.object(ctrl, 'get_model', return_value=m704), \
         patch('franklinwh_modbus.controller.time.sleep'):
        ok, _ = ctrl.send_command(BatteryCommand(power_watts=6000))
    assert ok
    assert m704.WSetPct.value == -100
