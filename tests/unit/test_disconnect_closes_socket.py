"""disconnect() must close the TCP socket (#138).

pysunspec2's SunSpecModbusClientDeviceTCP.close() is a no-op; only
disconnect() closes the socket. The aGate allows one Modbus client, so a
socket left open after a raw-socket read blocks the next client.
"""
import socket
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController


@pytest.fixture
def listener():
    srv = socket.socket()
    srv.bind(('127.0.0.1', 0))
    srv.listen(4)
    yield srv.getsockname()[1]
    srv.close()


@pytest.mark.parametrize('run', [1, 2, 3])
def test_disconnect_closes_an_open_socket(listener, run):
    from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
    dev = SunSpecModbusClientDeviceTCP(slave_id=1, ipaddr='127.0.0.1', ipport=listener, timeout=2)
    dev.client.connect()                       # as the raw-socket read paths do
    sock = dev.client.socket
    assert sock.fileno() != -1                 # control: the socket is open
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1', port=listener)
    ctrl.dev = dev
    ctrl.disconnect()
    assert sock.fileno() == -1
    assert ctrl.dev is None


def test_disconnect_survives_a_failing_close():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController(ip_address='127.0.0.1')
    ctrl.dev = MagicMock()
    dev = ctrl.dev
    dev.disconnect.side_effect = OSError('reset')
    ctrl.disconnect()
    dev.close.assert_called_once()
    assert ctrl.dev is None
