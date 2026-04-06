#!/bin/env python3

import signal
import socket
import sys
import threading

import pyaudio


class AudioStream:
    """
    Captures audio from the local microphone and streams raw PCM data to a
    RemoteMicrophone server over TCP.

    Usage (blocking)::

        stream = AudioStream(host='172.16.0.5', port=9560)
        stream.connect()   # blocks until the server accepts
        stream.start()     # blocks until stopped (Ctrl-C or stream.stop())

    Usage (background thread)::

        stream = AudioStream(host='172.16.0.5', port=9560)
        stream.connect()
        stream.start(block=False)
        …
        stream.stop()

    Audio parameters must match those used by the RemoteMicrophone instance on
    the server (defaults: 16 kHz, 16-bit mono, 1024-frame chunks).
    """

    def __init__(self, host: str, port: int, sample_rate: int = 16000,
                 chunk_size: int = 1024, sample_width_bytes: int = 2):
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        # pyaudio format derived from sample width (2 bytes → paInt16)
        self._pa_format = {1: pyaudio.paInt8, 2: pyaudio.paInt16,
                           4: pyaudio.paInt32}.get(sample_width_bytes, pyaudio.paInt16)

        self._sock: socket.socket | None = None
        self._pa: pyaudio.PyAudio | None = None
        self._pa_stream: pyaudio.Stream | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def connect(self) -> None:
        """Open a TCP connection to the RemoteMicrophone server."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Connecting to {self.host}:{self.port} …")
        self._sock.connect((self.host, self.port))
        print(f"Connected to {self.host}:{self.port}")

    def start(self, block: bool = True) -> None:
        """
        Begin capturing from the local microphone and streaming to the server.

        If *block* is True (default) this call blocks until stop() is called or
        the connection drops.  If *block* is False the streaming runs in a
        background daemon thread.
        """
        if self._sock is None:
            raise RuntimeError("Not connected — call connect() first")

        self._stop_event.clear()
        self._pa = pyaudio.PyAudio()
        self._pa_stream = self._pa.open(
            format=self._pa_format,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        if block:
            self._stream_loop()
        else:
            self._thread = threading.Thread(target=self._stream_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Signal the streaming loop to stop and clean up resources."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._cleanup()

    def _stream_loop(self) -> None:
        print("Streaming microphone audio… (Ctrl-C to stop)")
        try:
            while not self._stop_event.is_set():
                data = self._pa_stream.read(self.chunk_size, exception_on_overflow=False)
                try:
                    self._sock.sendall(data)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    print("Connection to server lost.")
                    break
        except KeyboardInterrupt:
            print("\nStopping audio stream…")
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        if self._pa_stream is not None:
            try:
                if not self._pa_stream.is_stopped():
                    self._pa_stream.stop_stream()
                self._pa_stream.close()
            except Exception:
                pass
            self._pa_stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    stream = AudioStream(host=host, port=port)
    stream.connect()

    def _handle_signal(sig, frame):
        stream.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    stream.start(block=True)


if __name__ == "__main__":
    main()
