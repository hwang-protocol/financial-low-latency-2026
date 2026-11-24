#!/usr/bin/env python3
"""One-shot 52-byte TCP echo peer for the F-Stack/X2522 smoke."""

import socket


HOST = "20.1.1.1"
PORT = 43129
BYTES = 52


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((HOST, PORT))
    listener.listen(1)
    listener.settimeout(90)
    connection, peer = listener.accept()
    with connection:
        connection.settimeout(10)
        payload = bytearray()
        while len(payload) < BYTES:
            chunk = connection.recv(BYTES - len(payload))
            if not chunk:
                raise RuntimeError("early EOF")
            payload.extend(chunk)
        connection.sendall(payload)
        print(f"KERNEL_TCP_ECHO_PASS peer={peer[0]} bytes={len(payload)}", flush=True)
