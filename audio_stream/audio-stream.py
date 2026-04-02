#!/bin/env python3

import pyaudio
import socket
import struct

class AudioStreamClient:
    """
    Audio stream sender.
    Used for sending audio stream to a server.
    """

    def __init__(self, server_host='10.0.0.1', server_port=9570):
        self.server_host = server_host
        self.server_port = server_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        self.sock.connect((self.server_host, self.server_port))
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4096)

    def read_audio(self):
        return self.stream.read(4096, exception_on_overflow=False)

    def send_audio(self, data):
        self.sock.sendall(struct.pack('>I', len(data)) + data)

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.sock.close()

class AudioStreamServer:
    """
    Audio stream receiver.
    Used for reading remote audio stream from a client.
    """

    def __init__(self, server_host='10.0.0.1', server_port=9570):
        self.server_host = server_host
        self.server_port = server_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.server_host, self.server_port))
        self.sock.listen(1)
        self.client_sock = None
        self.client_addr = None

    def accept(self):
        client_sock, client_addr = self.sock.accept()
        self.client_sock = client_sock
        self.client_addr = client_addr

    def read(self, size=4096):
        return self.client_sock.recv(size)

    def close(self):
        self.client_sock.close()
        self.sock.close()
