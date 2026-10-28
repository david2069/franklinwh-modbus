"""#114 B3/B4: each approved workaround is logged with its tag every time it runs."""
import logging
import struct
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import BatteryCommand, FranklinWHController

TAG = '[approved workaround #114'


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    c.dev = MagicMock()
    return c


def _tagged(caplog, name):
    return [r for r in caplog.records if f'{TAG} {name}' in r.getMessage()]


def test_rating_fallback_logged(ctrl, caplog):
    m702 = MagicMock()
    m702.WMaxRtg.value = 0
    m702.WChaRteMaxRtg.value = 0
    m702.WDisChaRteMaxRtg.value = 0
    ctrl.models = {702: m702}
    ctrl._get_scale_factor = lambda m, n: 0
    with caplog.at_level(logging.WARNING, logger='franklinwh_modbus.controller'):
        ctrl.discover_ratings()
    assert ctrl.RATED_MAX_W == 5000
    assert len(_tagged(caplog, 'B3: rating fallback')) == 3


def test_power_clamp_logged(ctrl, caplog):
    ctrl.RATED_MAX_CHARGE_W = 5000
    with caplog.at_level(logging.WARNING):
        assert ctrl._validate_power(8000) == 5000
        BatteryCommand(power_watts=20000)
    assert len(_tagged(caplog, 'B3: power clamp')) == 2


def test_standby_handshake_logged(ctrl, caplog):
    m704 = MagicMock()
    m704.WSetEna.value = 1
    ctrl.models = {704: m704}
    with patch('franklinwh_modbus.controller.time.sleep'), \
            caplog.at_level(logging.INFO, logger='franklinwh_modbus.controller'):
        ctrl.reset_control_state()
    assert len(_tagged(caplog, 'B3: standby handshake')) == 1


def test_software_timeout_logged(ctrl, caplog):
    m704 = MagicMock()
    ctrl.models = {704: m704}
    ctrl._get_scale_factor = lambda m, n: 0
    with patch('franklinwh_modbus.controller.time.sleep'), \
            caplog.at_level(logging.INFO, logger='franklinwh_modbus.controller'):
        ok, msg = ctrl.send_command(BatteryCommand(power_watts=-500), duration_s=600)
    ctrl.cancel_command_timer()
    assert ok, msg
    assert len(_tagged(caplog, 'B3: software timeout')) == 1


def test_home_load_16000_logged(ctrl, caplog):
    regs = [0] * 14
    regs[6] = 1200  # 15506 quantised
    resp1 = b'\x00' * 9 + struct.pack('>14H', *regs)
    resp2 = b'\x00' * 9 + struct.pack('>H', 1234)
    sock = MagicMock()
    sock.recv.side_effect = [resp1, resp2, resp1, resp2]
    ctrl.dev.client.socket = sock
    with caplog.at_level(logging.DEBUG, logger='franklinwh_modbus.controller'):
        assert ctrl._read_extension_solar()['home_load_ext'] == 1234
        ctrl._read_extension_solar()
    info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO and f'{TAG} B4' in r.getMessage()]
    assert len(info) == 2  # INFO on every read
    assert all('1234W from 16000' in m and '15506 read 1200W' in m for m in info)
