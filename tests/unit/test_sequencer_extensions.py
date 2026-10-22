import pytest
import struct
from unittest.mock import MagicMock, patch
from franklinwh_modbus.sequencer import SunSpecSequencer

class TestSequencerExtensions:
    """Unit tests for upgraded SunSpecSequencer raw datatypes, scaling, and overrides."""

    @pytest.fixture
    def mock_device(self):
        """Create a mocked sunspec2 device with a mocked client and socket."""
        device = MagicMock()
        device.slave_id = 2
        device.base_addr = 0
        device.models = {}
        
        # Mock client and socket
        client = MagicMock()
        socket = MagicMock()
        client.socket = socket
        device.client = client
        
        return device

    def test_raw_read_uint16_default(self, mock_device):
        """Verify reading a raw register address defaults to uint16."""
        seq = SunSpecSequencer(mock_device)
        
        # Mock Modbus TCP response for a single register (value 123)
        # Header (9 bytes: transaction(2), protocol(2), length(2), unit_id(1), func(1), byte_count(1)) + Data (2 bytes) = 11 bytes
        mock_response = struct.pack('>HHHBBB', 0, 0, 5, 2, 3, 2) + struct.pack('>H', 123)
        mock_device.client.socket.recv.return_value = mock_response
        
        val = seq.read_value("15508")  # SelfReserve (uint16 in registry)
        assert val == 123
        
        # Verify socket sent correct Modbus packet (count = 1)
        sent_packet = mock_device.client.socket.sendall.call_args[0][0]
        # transaction(2), protocol(2), length(2), unit_id(1), func(1), addr(2), count(2)
        _, _, _, unit_id, func, addr, count = struct.unpack('>HHHBBHH', sent_packet)
        assert unit_id == 2
        assert func == 3
        assert addr == 15508
        assert count == 1

    def test_raw_read_uint32_registry(self, mock_device):
        """Verify reading a raw register address defined as uint32 in registry reads 2 registers."""
        seq = SunSpecSequencer(mock_device)
        
        # 12959408 in hex is 0x00C5BEB0
        expected_val = 12959408
        # Mock Modbus TCP response for 2 registers (value 12959408)
        # Header (9 bytes) + Data (4 bytes) = 13 bytes
        mock_response = struct.pack('>HHHBBB', 0, 0, 7, 2, 3, 4) + struct.pack('>I', expected_val)
        mock_device.client.socket.recv.return_value = mock_response
        
        val = seq.read_value("15510")  # PVOutputWh (uint32 in registry)
        assert val == expected_val
        
        # Verify socket sent correct Modbus packet (count = 2)
        sent_packet = mock_device.client.socket.sendall.call_args[0][0]
        _, _, _, unit_id, func, addr, count = struct.unpack('>HHHBBHH', sent_packet)
        assert addr == 15510
        assert count == 2

    def test_raw_read_int16_and_scaling_inline(self, mock_device):
        """Verify inline dynamic type and scale overrides for reads."""
        seq = SunSpecSequencer(mock_device)
        
        # Mock -150 formatted as scale factor -1 (so human value is -15.0)
        mock_response = struct.pack('>HHHBBB', 0, 0, 5, 2, 3, 2) + struct.pack('>h', -150)
        mock_device.client.socket.recv.return_value = mock_response
        
        # Query with inline config override
        config = {
            "point": "15025",
            "type": "int16",
            "sf": -1
        }
        val = seq.read_value(config)
        assert val == -15.0  # -150 * 10^-1

    def test_raw_read_address_key_inline(self, mock_device):
        """Verify that dictionary overrides can use "address" instead of "point" or "addr"."""
        seq = SunSpecSequencer(mock_device)
        
        mock_response = struct.pack('>HHHBBB', 0, 0, 5, 2, 3, 2) + struct.pack('>H', 500)
        mock_device.client.socket.recv.return_value = mock_response
        
        # Query using "address" instead of "point" or "addr"
        config = {
            "address": "15508",
            "type": "uint16",
            "sf": 0
        }
        val = seq.read_value(config)
        assert val == 500
        
        # Verify socket sent correct Modbus packet
        sent_packet = mock_device.client.socket.sendall.call_args[0][0]
        _, _, _, unit_id, func, addr, count = struct.unpack('>HHHBBHH', sent_packet)
        assert addr == 15508

    def test_raw_write_uint16_default(self, mock_device):
        """Verify raw uint16 write uses single-register write (Function 6)."""
        seq = SunSpecSequencer(mock_device)
        
        mock_device.client.socket.recv.return_value = struct.pack('>HHHBBHH', 0, 0, 6, 2, 6, 15508, 25)
        assert seq.write_value("15508", 25) == 25
        
        # Verify the FC06 packet sent on the raw socket
        sent = mock_device.client.socket.sendall.call_args[0][0]
        assert struct.unpack('>HHHBBHH', sent)[3:] == (2, 6, 15508, 25)

    def test_raw_write_uint32_registry(self, mock_device):
        """Verify raw uint32 write uses multiple-register write (2 words)."""
        seq = SunSpecSequencer(mock_device)
        
        # Writing 12959408 (0x00C5BEB0) to 15510 should write [197, 48816]
        mock_device.client.socket.recv.return_value = struct.pack('>HHHBBHH', 0, 0, 6, 2, 16, 15510, 2)
        assert seq.write_value("15510", 12959408) == 12959408
        
        sent = mock_device.client.socket.sendall.call_args[0][0]
        assert struct.unpack('>HHHBBHHB', sent[:13])[4:] == (16, 15510, 2, 4)
        assert list(struct.unpack('>2H', sent[13:17])) == [197, 48816]

    def test_execute_writes_uint32_mock_socket(self, mock_device):
        """Verify execute_writes for uint32 maps Function 16 writes correctly over raw socket."""
        seq = SunSpecSequencer(mock_device)
        
        # Mock initial status reads so verification step works
        # Initial read (before): value 0
        before_resp = struct.pack('>HHHBBB', 0, 0, 7, 2, 3, 4) + struct.pack('>I', 0)
        # Target write verification read (after): value 500000
        after_resp = struct.pack('>HHHBBB', 0, 0, 7, 2, 3, 4) + struct.pack('>I', 500000)
        # Write response (Modbus TCP Function 16 response length = 6 bytes after header -> length = 6)
        write_resp = struct.pack('>HHHBBHH', 0, 0, 6, 2, 16, 15510, 2)
        
        mock_device.client.socket.recv.side_effect = [
            before_resp,  # Before write validation check
            write_resp,   # Func 16 write echo response
            after_resp    # Post-write verify read
        ]
        
        # Run sequence write step
        step = {
            "name": "Write PV cumulative energy",
            "writes": {
                "15510": 500000
            },
            "verify": True,
            "verify_timeout_ms": 500
        }
        
        success = seq.run_sequence([step])
        assert success
        
        # Check that Function 16 raw packet was sent
        sent_calls = mock_device.client.socket.sendall.call_args_list
        assert len(sent_calls) >= 3
        
        write_packet = sent_calls[1][0][0]
        # transaction(2), protocol(2), length(2), unit_id(1), func(1), addr(2), count(2), bytes(1)
        _, _, _, unit_id, func, addr, count, byte_count = struct.unpack('>HHHBBHHB', write_packet[:13])
        assert unit_id == 2
        assert func == 16
        assert addr == 15510
        assert count == 2
        assert byte_count == 4
        
        # Verify packed value (500000 in hex is 0x0007A120)
        written_val = struct.unpack('>I', write_packet[13:17])[0]
        assert written_val == 500000

    def test_execute_reads_enum_translation(self, mock_device):
        """Verify execute_reads translates raw register enum descriptions."""
        seq = SunSpecSequencer(mock_device)
        
        # Mock read response: 3 (representing TOU)
        mock_response = struct.pack('>HHHBBB', 0, 0, 5, 2, 3, 2) + struct.pack('>H', 3)
        mock_device.client.socket.recv.return_value = mock_response
        
        # Capture logger print statements
        with patch('franklinwh_modbus.sequencer.logger.info') as mock_log:
            seq.execute_reads(["15507"])
            
            # Assert logger printed symbol description
            mock_log.assert_called_once_with("  Read 15507: 3 (TOU)")


class TestSequencerRawReconnect:
    """Raw-address access must reconnect: pysunspec2 leaves client.socket = None after a scan."""

    @pytest.fixture
    def closed_device(self):
        device = MagicMock()
        device.slave_id = 1
        device.models = {}
        client = MagicMock()
        client.socket = None
        sock = MagicMock()

        def connect():
            client.socket = sock
        client.connect.side_effect = connect
        device.client = client
        return device, sock

    def test_raw_read_connects_first(self, closed_device):
        device, sock = closed_device
        sock.recv.return_value = struct.pack('>HHHBBB', 0, 0, 5, 1, 3, 2) + struct.pack('>H', 6)
        assert SunSpecSequencer(device).read_value("15016") == 6
        device.client.connect.assert_called()

    def test_raw_step_write_connects_and_sends(self, closed_device):
        device, sock = closed_device
        # before-read 0, FC06 echo, verify-read 1
        sock.recv.side_effect = [
            struct.pack('>HHHBBB', 0, 0, 5, 1, 3, 2) + struct.pack('>H', 0),
            struct.pack('>HHHBBHH', 0, 0, 6, 1, 6, 15600, 1),
            struct.pack('>HHHBBB', 0, 0, 5, 1, 3, 2) + struct.pack('>H', 1),
        ]
        ok = SunSpecSequencer(device).execute_writes({"15600": 1}, {}, dry_run=False)
        assert ok
        writes = [c[0][0] for c in sock.sendall.call_args_list if c[0][0][7] == 6]
        assert len(writes) == 1
        assert struct.unpack('>HHHBBHH', writes[0])[5:] == (15600, 1)

    def test_write_value_uses_raw_socket(self, closed_device):
        device, sock = closed_device
        sock.recv.return_value = struct.pack('>HHHBBHHB', 0, 0, 6, 1, 16, 15600, 2, 4)
        val = SunSpecSequencer(device).write_value({"addr": 15600, "type": "uint32"}, 300)
        assert val == 300
        sent = sock.sendall.call_args[0][0]
        assert sent[7] == 16 and struct.unpack('>I', sent[13:17])[0] == 300

    def test_raw_write_exception_response_is_failure(self, closed_device):
        device, sock = closed_device
        sock.recv.return_value = struct.pack('>HHHBBB', 0, 0, 3, 1, 0x86, 3)
        assert SunSpecSequencer(device).write_value("15600", 1) is None
