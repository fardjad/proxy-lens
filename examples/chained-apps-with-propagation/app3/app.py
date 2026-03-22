from __future__ import annotations

import json
import os
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_BIND = os.environ.get("APP_BIND", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "9443"))
APP_CERT_FILE = os.environ["APP_CERT_FILE"]
APP_KEY_FILE = os.environ["APP_KEY_FILE"]


def _proxylens_headers(
    headers: BaseHTTPRequestHandler.headers.__class__,
) -> dict[str, str | None]:
    return {
        "X-ProxyLens-HopChain": headers.get("X-ProxyLens-HopChain"),
        "X-ProxyLens-RequestId": headers.get("X-ProxyLens-RequestId"),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._send_json(
            {
                "service": "app3",
                "message": "hello from app3 with propagated proxylens headers",
                "inbound_headers": _proxylens_headers(self.headers),
            }
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((APP_BIND, APP_PORT), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=APP_CERT_FILE, keyfile=APP_KEY_FILE)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
