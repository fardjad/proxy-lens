from __future__ import annotations

import json
import os
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP_BIND = os.environ.get("APP_BIND", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "9443"))
APP_CERT_FILE = os.environ["APP_CERT_FILE"]
APP_KEY_FILE = os.environ["APP_KEY_FILE"]
DOWNSTREAM_URL = os.environ["DOWNSTREAM_URL"]


def _proxylens_headers(headers: BaseHTTPRequestHandler.headers.__class__) -> dict[str, str | None]:
    return {
        "X-ProxyLens-HopChain": headers.get("X-ProxyLens-HopChain"),
        "X-ProxyLens-RequestId": headers.get("X-ProxyLens-RequestId"),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        request = Request(
            DOWNSTREAM_URL,
            headers={"Accept": "application/json"},
            method="GET",
        )
        context = ssl._create_unverified_context()

        try:
            with urlopen(request, timeout=10, context=context) as response:
                downstream = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            self._send_json(
                {
                    "service": "app2",
                    "error": f"downstream returned HTTP {exc.code}",
                    "inbound_headers": _proxylens_headers(self.headers),
                },
                status=502,
            )
            return
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            self._send_json(
                {
                    "service": "app2",
                    "error": f"downstream request failed: {exc}",
                    "inbound_headers": _proxylens_headers(self.headers),
                },
                status=502,
            )
            return

        self._send_json(
            {
                "service": "app2",
                "message": "app2 called app3 through its own proxylens addon",
                "inbound_headers": _proxylens_headers(self.headers),
                "downstream": downstream,
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
