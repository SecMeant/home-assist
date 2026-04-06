"""
Integration tests for RemoteMicrophone (server) <-> AudioStream (client).

PyAudio is mocked so no audio hardware is required.  All communication
happens over localhost using an OS-assigned free port.
"""

import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Allow running from repo root or from this directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from audio_stream import AudioStream, RemoteMicrophone


def _free_port() -> int:
    """Ask the OS for a free TCP port."""
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


HOST = "127.0.0.1"
CHUNK = 1024
SAMPLE_RATE = 16000


class TestRemoteMicrophoneAccept(unittest.TestCase):
    """Server-side: accept() binds, listens, and exposes a readable stream."""

    def test_accept_sets_stream(self):
        port = _free_port()
        server = RemoteMicrophone(host=HOST, port=port, chunk_size=CHUNK,
                                  sample_rate=SAMPLE_RATE)

        accept_thread = threading.Thread(target=server.accept, daemon=True)
        accept_thread.start()
        time.sleep(0.05)  # let the server socket bind

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((HOST, port))
        accept_thread.join(timeout=2)

        self.assertIsNotNone(server.stream)

        client.close()
        server.__exit__(None, None, None)

    def test_stream_read_returns_sent_bytes(self):
        port = _free_port()
        payload = bytes(range(256)) * (CHUNK // 256)  # exactly CHUNK bytes
        server = RemoteMicrophone(host=HOST, port=port, chunk_size=CHUNK,
                                  sample_rate=SAMPLE_RATE)

        accept_thread = threading.Thread(target=server.accept, daemon=True)
        accept_thread.start()
        time.sleep(0.05)

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((HOST, port))
        accept_thread.join(timeout=2)

        client.sendall(payload)
        received = server.stream.read(CHUNK)

        self.assertEqual(received, payload)

        client.close()
        server.__exit__(None, None, None)

    def test_attributes_match_constructor_args(self):
        server = RemoteMicrophone(host=HOST, port=0, sample_rate=8000,
                                  chunk_size=512, sample_width=2)
        self.assertEqual(server.SAMPLE_RATE, 8000)
        self.assertEqual(server.CHUNK, 512)
        self.assertEqual(server.SAMPLE_WIDTH, 2)


class TestAudioStreamWithMockedPyAudio(unittest.TestCase):
    """Client-side: AudioStream sends mic data to RemoteMicrophone over TCP."""

    def _make_mock_pa(self, chunk_data: bytes, num_chunks: int):
        """Return a mock PyAudio instance whose stream yields *chunk_data* exactly
        *num_chunks* times before blocking forever (stop_event will fire first)."""
        call_count = {"n": 0}

        def fake_read(size, exception_on_overflow=False):
            call_count["n"] += 1
            return chunk_data

        mock_pa_stream = MagicMock()
        mock_pa_stream.read.side_effect = fake_read
        mock_pa_stream.is_stopped.return_value = False

        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_pa_stream
        return mock_pa, call_count

    def test_connect_and_stream_n_chunks(self):
        port = _free_port()
        NUM_CHUNKS = 4
        chunk_data = b'\xAB\xCD' * (CHUNK // 2)  # realistic 16-bit PCM pattern

        server = RemoteMicrophone(host=HOST, port=port, chunk_size=CHUNK,
                                  sample_rate=SAMPLE_RATE)
        accept_thread = threading.Thread(target=server.accept, daemon=True)
        accept_thread.start()
        time.sleep(0.05)

        mock_pa, call_count = self._make_mock_pa(chunk_data, NUM_CHUNKS)

        with patch("audio_stream.audio_stream.pyaudio.PyAudio", return_value=mock_pa):
            client = AudioStream(host=HOST, port=port, chunk_size=CHUNK,
                                 sample_rate=SAMPLE_RATE)
            client.connect()
            accept_thread.join(timeout=2)

            client.start(block=False)

            received = b"".join(server.stream.read(CHUNK) for _ in range(NUM_CHUNKS))

            client.stop()

        self.assertEqual(received, chunk_data * NUM_CHUNKS)
        server.__exit__(None, None, None)

    def test_stop_terminates_stream_loop(self):
        port = _free_port()
        chunk_data = b'\x00\x01' * (CHUNK // 2)

        server = RemoteMicrophone(host=HOST, port=port, chunk_size=CHUNK,
                                  sample_rate=SAMPLE_RATE)
        accept_thread = threading.Thread(target=server.accept, daemon=True)
        accept_thread.start()
        time.sleep(0.05)

        mock_pa, _ = self._make_mock_pa(chunk_data, num_chunks=999)

        with patch("audio_stream.audio_stream.pyaudio.PyAudio", return_value=mock_pa):
            client = AudioStream(host=HOST, port=port, chunk_size=CHUNK,
                                 sample_rate=SAMPLE_RATE)
            client.connect()
            accept_thread.join(timeout=2)

            client.start(block=False)
            time.sleep(0.1)   # let a few chunks flow
            client.stop()

        # After stop(), all resources must be released
        self.assertIsNone(client._sock)
        self.assertIsNone(client._pa)
        self.assertIsNone(client._pa_stream)
        server.__exit__(None, None, None)

    def test_connect_without_server_raises(self):
        port = _free_port()
        client = AudioStream(host=HOST, port=port)
        with self.assertRaises(ConnectionRefusedError):
            client.connect()

    def test_start_without_connect_raises(self):
        client = AudioStream(host=HOST, port=_free_port())
        with self.assertRaises(RuntimeError):
            client.start()


if __name__ == "__main__":
    unittest.main()
