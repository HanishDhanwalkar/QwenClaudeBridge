"""
Very small Chromium DevTools Protocol WebSocket client.

This intentionally avoids Selenium/Playwright. It implements only the pieces
needed by this project.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import urllib.parse


class CDPClient:
    def __init__(self, websocket_url):
        self.url = websocket_url
        self.sock = None
        self.lock = threading.Lock()
        self.counter = 0

    def connect(self):
        u = urllib.parse.urlparse(self.url)
        host = u.hostname
        port = u.port or 80
        path = u.path or "/"
        if u.query:
            path += "?" + u.query

        sock = socket.create_connection((host, port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = self._read_http_headers(sock)
        if " 101 " not in response.split("\r\n", 1)[0]:
            sock.close()
            raise RuntimeError("CDP WebSocket handshake failed:\n" + response)

        self.sock = sock
        self.sock.settimeout(30)

    def _read_http_headers(self, sock):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode("latin-1")

    def is_alive(self):
        return self.sock is not None

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _send_frame(self, payload, opcode=1):
        if not self.sock:
            raise RuntimeError("CDP is not connected")

        data = payload.encode("utf-8")
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))

        first = 0x80 | opcode
        length = len(masked)
        if length < 126:
            header = struct.pack("!BB", first, 0x80 | length)
        elif length < 65536:
            header = struct.pack("!BBH", first, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", first, 0x80 | 127, length)

        self.sock.sendall(header + mask_key + masked)

    def _recv_exact(self, n):
        chunks = []
        remaining = n
        while remaining:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise ConnectionError("CDP socket closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _recv_frame(self):
        h = self._recv_exact(2)
        b1, b2 = h
        opcode = b1 & 0x0F
        length = b2 & 0x7F

        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]

        if b2 & 0x80:
            mask = self._recv_exact(4)
        else:
            mask = None

        payload = self._recv_exact(length)
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

        return opcode, payload

    def _recv_message(self):
        chunks = []
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise ConnectionError("CDP WebSocket closed by peer")
            if opcode == 0x9:  # ping
                self._send_frame(payload.decode("utf-8", errors="ignore"), opcode=0xA)
                continue
            if opcode in (0x1, 0x0):
                chunks.append(payload)
                if opcode == 0x1 or chunks:
                    # CDP normally sends a complete text message in one frame.
                    # Handle continuation frames conservatively.
                    if opcode == 0x1:
                        try:
                            return b"".join(chunks).decode("utf-8")
                        except UnicodeDecodeError:
                            pass
            elif opcode == 0xA:
                continue

    def call(self, method, params=None, timeout=30):
        with self.lock:
            self.counter += 1
            msg_id = self.counter
            msg = {"id": msg_id, "method": method}
            if params is not None:
                msg["params"] = params
            self._send_frame(json.dumps(msg))

            old_timeout = self.sock.gettimeout()
            self.sock.settimeout(timeout)
            try:
                while True:
                    text = self._recv_message()
                    event = json.loads(text)
                    if event.get("id") == msg_id:
                        return event
            finally:
                self.sock.settimeout(old_timeout)

    def evaluate(self, expression, await_promise=True, return_by_value=True):
        return self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": return_by_value,
            },
        )
