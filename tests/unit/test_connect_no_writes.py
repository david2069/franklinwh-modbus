"""connect() must never write to the device (S1: it used to write 15507-15509)."""
from unittest.mock import MagicMock, patch

from franklinwh_modbus import FranklinWHController


def _fake_device():
    dev = MagicMock()
    models = {}
    for mid in (1, 701, 702, 704, 713, 714, 715):
        m = MagicMock(name=f'm{mid}')
        models[str(mid)] = [m]
    dev.models = models
    return dev


def test_connect_issues_no_writes():
    dev = _fake_device()
    # Patch the globals connect() actually resolves (robust to module reloads
    # by other tests)
    g = FranklinWHController.connect.__globals__
    with patch.dict(g, {'SUNSPEC_AVAILABLE': True,
                        'SunSpecModbusClientDeviceTCP': MagicMock(return_value=dev)}):
        ctrl = FranklinWHController('127.0.0.1')
        with patch.object(ctrl, 'test_extension_writability',
                          side_effect=AssertionError('connect() ran the write test')):
            assert ctrl.connect()

    # No raw-socket Modbus requests (the old test used client.socket.sendall)
    dev.client.socket.sendall.assert_not_called()
    # No SunSpec model writes
    for models in dev.models.values():
        for m in models:
            m.write.assert_not_called()
    assert ctrl.get_extension_write_status()['tested'] is False


def test_write_test_still_available_explicitly():
    with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
        ctrl = FranklinWHController('127.0.0.1')
    assert ctrl._test_extension_writability == ctrl.test_extension_writability
