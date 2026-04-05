import struct
import socket
import speech_recognition as sr


class RemoteMicrophone(sr.AudioSource):
    """
    An AudioSource that reads PCM audio frames from a connected TCP socket.

    The remote end is expected to be an AudioStreamClient, which sends each
    chunk as a big-endian 4-byte length prefix followed by that many bytes of
    raw 16-bit mono PCM audio sampled at ``sample_rate`` Hz.
    """

    SAMPLE_RATE = 16000
    SAMPLE_WIDTH = 2   # paInt16 -> 2 bytes per sample
    CHUNK = 4096       # frames per buffer, must match the sender

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.stream = None

    def __enter__(self):
        assert self.stream is None, "This audio source is already inside a context manager"
        self.stream = RemoteMicrophone.RemoteStream(self.sock)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stream.close()
        finally:
            self.stream = None

    class RemoteStream:
        """
        Wraps a TCP socket and exposes a read(size) interface expected by
        speech_recognition's Recognizer. Each call receives one length-prefixed
        frame sent by AudioStreamClient.send_audio().
        """

        _HEADER = struct.Struct(">I")  # big-endian unsigned 32-bit length

        def __init__(self, sock: socket.socket):
            self.sock = sock

        def read(self, size: int) -> bytes:
            """
            Receive one audio frame from the socket. The ``size`` argument is
            the number of frames requested by the Recognizer (i.e. CHUNK), but
            the actual byte count is determined by the length prefix in the
            wire protocol.
            """
            header = self._recv_exact(self._HEADER.size)
            if not header:
                return b""
            (frame_len,) = self._HEADER.unpack(header)
            return self._recv_exact(frame_len)

        def _recv_exact(self, n: int) -> bytes:
            """Read exactly n bytes from the socket, blocking until available."""
            buf = bytearray()
            while len(buf) < n:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    break
                buf.extend(chunk)
            return bytes(buf)

        def close(self):
            self.sock.close()
