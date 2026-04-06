#!/bin/env python3

import socket
import speech_recognition as sr


class RemoteMicrophone(sr.AudioSource):
    """
    An AudioSource that receives a raw PCM audio stream over TCP.

    Acts as a TCP server: binds to the given host/port and waits for a
    single client (the remote microphone) to connect via accept().
    Once connected the incoming byte stream is exposed as self.stream,
    making it compatible with speech_recognition's Recognizer methods
    (adjust_for_ambient_noise, listen, record, …).
    """

    def __init__(self, host: str, port: int, sample_rate: int = 16000,
                 chunk_size: int = 1024, sample_width: int = 2):
        self.host = host
        self.port = port
        self.SAMPLE_RATE = sample_rate
        self.CHUNK = chunk_size
        self.SAMPLE_WIDTH = sample_width

        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self.stream: RemoteMicrophone.RemoteStream | None = None

    def accept(self) -> None:
        """
        Binds to host:port and blocks until a remote audio client connects.
        Sets self.stream so that the source is ready for use with Recognizer.
        """
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(1)
        print(f"Waiting for audio stream on {self.host}:{self.port} …")
        self._client_socket, addr = self._server_socket.accept()
        print(f"Audio stream connected from {addr}")
        self.stream = RemoteMicrophone.RemoteStream(self._client_socket)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        if self._client_socket is not None:
            self._client_socket.close()
            self._client_socket = None
        if self._server_socket is not None:
            self._server_socket.close()
            self._server_socket = None

    class RemoteStream:
        """
        Wraps a connected client socket and exposes the read(size) interface
        expected by speech_recognition's Recognizer.
        """

        def __init__(self, sock: socket.socket):
            self._socket = sock

        def read(self, size: int) -> bytes:
            """Read exactly *size* bytes from the socket, blocking until available."""
            buf = bytearray()
            while len(buf) < size:
                chunk = self._socket.recv(size - len(buf))
                if not chunk:
                    break
                buf += chunk
            return bytes(buf)

        def close(self) -> None:
            self._socket.close()
