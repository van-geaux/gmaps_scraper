"""Small authenticated HTTP CONNECT gateway for the Selenium network."""

from __future__ import annotations

import base64
import os
import select
import socket
import socketserver
from typing import BinaryIO


UPSTREAM_HOST = os.environ["UPSTREAM_PROXY_HOST"]
UPSTREAM_PORT = int(os.environ["UPSTREAM_PROXY_PORT"])
UPSTREAM_USER = os.environ.get("UPSTREAM_PROXY_USER", "")
UPSTREAM_PASSWORD = os.environ.get("UPSTREAM_PROXY_PASSWORD", "")
UPSTREAM_AUTH = ""
if UPSTREAM_USER or UPSTREAM_PASSWORD:
    UPSTREAM_AUTH = base64.b64encode(
        f"{UPSTREAM_USER}:{UPSTREAM_PASSWORD}".encode()
    ).decode()


class ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(30)
        header = self._read_headers(self.request)
        if not header:
            return

        first_line = header.split(b"\r\n", 1)[0].decode("latin1")
        method, target, _ = first_line.split(" ", 2)
        upstream = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=30)
        try:
            if method.upper() == "CONNECT":
                self._connect_tunnel(upstream, target)
            else:
                self._forward_http(upstream, header)
        finally:
            upstream.close()

    @staticmethod
    def _read_headers(sock: socket.socket) -> bytes:
        data = bytearray()
        while b"\r\n\r\n" not in data and len(data) <= 65536:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    def _upstream_headers(self, target: str) -> bytes:
        auth = (
            f"Proxy-Authorization: Basic {UPSTREAM_AUTH}\r\n"
            if UPSTREAM_AUTH
            else ""
        )
        return (
            f"CONNECT {target} HTTP/1.1\r\n"
            f"Host: {target}\r\n"
            f"{auth}\r\n"
        ).encode("latin1")

    def _connect_tunnel(self, upstream: socket.socket, target: str) -> None:
        upstream.sendall(self._upstream_headers(target))
        response = self._read_headers(upstream)
        self.request.sendall(response)
        if not response.startswith(b"HTTP/") or b" 2" not in response.split(b"\r\n", 1)[0]:
            return
        self._relay(upstream, self.request)

    def _forward_http(self, upstream: socket.socket, header: bytes) -> None:
        lines = header.split(b"\r\n")
        auth = (
            f"Proxy-Authorization: Basic {UPSTREAM_AUTH}".encode("ascii")
            if UPSTREAM_AUTH
            else b""
        )
        lines = [line for line in lines if not line.lower().startswith(b"proxy-authorization:")]
        if auth:
            lines.insert(-2, auth)
        upstream.sendall(b"\r\n".join(lines))
        self._relay(upstream, self.request, bidirectional=False)

    @staticmethod
    def _relay(left: socket.socket, right: socket.socket, bidirectional: bool = True) -> None:
        sockets = [left, right] if bidirectional else [left]
        while sockets:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                return
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                destination = right if source is left else left
                destination.sendall(data)


class ThreadedServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedServer(("0.0.0.0", 3128), ProxyHandler) as server:
        server.serve_forever()
