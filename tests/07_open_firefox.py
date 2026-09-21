"""POST /open/env/open: open Firefox, verify BiDi handshake, then close on Enter."""

import base64
import hashlib
import os
import socket
from urllib.parse import urlsplit
from _client import call, require_code

CODE = "4b3347cbd4b6bdc585d113e8100868f3"
HEADLESS = False
OPEN_TABS = False
NEED_DEBUG_PORT = True
ARGS = []


def verify_bidi_websocket(endpoint):
    url = urlsplit(endpoint)
    assert url.scheme == "ws" and url.hostname == "127.0.0.1" and url.path == "/session", endpoint
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    request = (f"GET {url.path} HTTP/1.1\r\nHost: {url.hostname}:{url.port}\r\n"
               f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n")
    with socket.create_connection((url.hostname, url.port), timeout=5) as connection:
        connection.sendall(request.encode("ascii"))
        chunks = bytearray()
        while b"\r\n\r\n" not in chunks and len(chunks) < 16_384:
            chunk = connection.recv(4096)
            if not chunk:
                break
            chunks.extend(chunk)
    response = chunks.decode("ascii", errors="replace")
    assert response.startswith("HTTP/1.1 101 "), response
    headers = dict(line.split(":", 1) for line in response.split("\r\n")[1:] if ":" in line)
    assert next((value.strip() for name, value in headers.items() if name.lower() == "sec-websocket-accept"), None) == expected, response


if __name__ == "__main__":
    code = require_code(CODE)
    opened = call("/open/env/open", {"code": code, "headless": HEADLESS,
                                     "openTabs": OPEN_TABS, "needDebugPort": NEED_DEBUG_PORT, "args": ARGS})
    try:
        assert opened["pid"] > 0
        assert opened["browser_kernel"] == "firefox", opened
        assert opened["debug_protocol"] == "webdriver-bidi", opened
        assert opened["debug_port"] > 0
        assert opened["debug_endpoint"] == f"ws://127.0.0.1:{opened['debug_port']}/session"
        verify_bidi_websocket(opened["debug_endpoint"])
        print("WebDriver BiDi WebSocket handshake passed")
        print("Firefox window is open. Press Enter to close it.")
        input()
    finally:
        call("/open/env/close", {"code": code})
