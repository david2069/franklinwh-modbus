"""
Regression tests for #70 and #71.

#70  pysunspec2's close() is a no-op on TCP devices; only disconnect()
     closes the socket. disconnect(), reconnect() and connect() must close
     the previous session, because the aGate serves one Modbus client.
#71  is_connected() probed PDU 40071, which the aGate rejects with
     exception 2 (its SunSpec map starts at PDU 0), so it always returned
     False and virtual-mode cleanup never released control.
"""
import threading
from unittest.mock import MagicMock, patch

import pytest

from franklinwh_modbus import FranklinWHController, VirtualModeController


class AGateLikeDevice:
    """Raw reads behave like the aGate (QUIRKS, Register Addressing):
    "SunS" at PDU 0, exception 2 at PDU 40000 and above."""

    def __init__(self):
        self.disconnect = MagicMock()
        self.close = MagicMock()  # pysunspec2 TCP: a no-op
        self.models = {}

    def read(self, addr, count):
        if addr >= 40000:
            raise Exception('Modbus exception 2: ILLEGAL DATA ADDRESS')
        if addr == 0 and count == 2:
            return b'SunS'
        return b'\x00\x00' * count


def _device_class(instance):
    # Patch the globals the controller methods actually resolve (robust to
    # module reloads by other tests, as in test_connect_no_writes.py).
    return patch.dict(FranklinWHController.connect.__globals__,
                      {'SunSpecModbusClientDeviceTCP': MagicMock(return_value=instance)})


@pytest.fixture
def ctrl():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        c = FranklinWHController(ip_address='127.0.0.1')
    return c


class TestSocketIsClosed:

    def test_disconnect_closes_the_socket(self, ctrl):
        dev = AGateLikeDevice()
        ctrl.dev = dev
        ctrl.disconnect()
        dev.disconnect.assert_called_once()
        assert ctrl.dev is None

    def test_reconnect_closes_the_old_socket(self, ctrl):
        old = AGateLikeDevice()
        ctrl.dev = old
        with _device_class(MagicMock(models={})), \
             patch('time.sleep'):
            assert ctrl.reconnect() is True
        old.disconnect.assert_called_once()

    def test_connect_closes_a_previous_session(self, ctrl):
        old = AGateLikeDevice()
        ctrl.dev = old
        with _device_class(MagicMock(models={})), \
             patch.object(ctrl, 'discover_ratings'), \
             patch.object(ctrl, '_check_orphaned_vpp'):
            ctrl.connect()
        old.disconnect.assert_called_once()

    def test_failed_connect_closes_its_own_session(self, ctrl):
        new = MagicMock()
        new.scan.side_effect = OSError('timed out')
        with _device_class(new):
            assert ctrl.connect() is False
        new.disconnect.assert_called_once()
        assert ctrl.dev is None


class TestIsConnected:

    def test_true_on_an_agate_like_device(self, ctrl):
        ctrl.dev = AGateLikeDevice()
        assert ctrl.is_connected() is True

    def test_true_when_requested_base_differs_from_the_scanned_one(self):
        # The CLI passes base_address=40000; sunspec2's scan finds "SunS" at
        # PDU 0 on the aGate and records it in dev.base_addr.
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            c = FranklinWHController(ip_address='127.0.0.1', base_address=40000)
        dev = AGateLikeDevice()
        dev.base_addr = 0
        c.dev = dev
        assert c.is_connected() is True

    def test_false_when_the_read_fails(self, ctrl):
        dev = AGateLikeDevice()
        dev.read = MagicMock(side_effect=OSError('broken pipe'))
        ctrl.dev = dev
        assert ctrl.is_connected() is False

    def test_false_when_not_a_sunspec_device(self, ctrl):
        dev = AGateLikeDevice()
        dev.read = MagicMock(return_value=b'\x00\x00\x00\x00')
        ctrl.dev = dev
        assert ctrl.is_connected() is False

    def test_false_without_a_device(self, ctrl):
        assert ctrl.is_connected() is False


def _stopped():
    ev = threading.Event()
    ev.set()  # loop exits at once and runs its cleanup
    return ev


class TestModeCleanupReleasesControl:

    def test_cleanup_releases_control_on_an_agate_like_device(self, ctrl):
        ctrl.dev = AGateLikeDevice()
        vmc = VirtualModeController(ctrl)
        with patch.object(ctrl, 'reset_control_state', return_value=True) as reset, \
             patch.object(ctrl, 'reconnect') as reconnect, \
             patch.object(vmc, 'is_off_grid', return_value=False):
            vmc.run_continuous(stop_event=_stopped())
        reset.assert_called_once()
        reconnect.assert_not_called()

    def test_cleanup_attempts_release_even_if_the_probe_fails(self, ctrl):
        dev = AGateLikeDevice()
        dev.read = MagicMock(side_effect=OSError('broken pipe'))
        ctrl.dev = dev
        vmc = VirtualModeController(ctrl)
        with patch.object(ctrl, 'reset_control_state', return_value=True) as reset, \
             patch.object(ctrl, 'reconnect', return_value=False), \
             patch.object(vmc, 'is_off_grid', return_value=False):
            vmc.run_continuous(stop_event=_stopped())
        reset.assert_called_once()
