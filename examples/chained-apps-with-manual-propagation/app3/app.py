from __future__ import annotations

import os

from flask import Flask, request

APP_BIND = os.environ.get("APP_BIND", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "9443"))
APP_CERT_FILE = os.environ["APP_CERT_FILE"]
APP_KEY_FILE = os.environ["APP_KEY_FILE"]
APP_NAME = os.environ["APP_NAME"]

PROXYLENS_HEADERS = ("X-ProxyLens-HopChain", "X-ProxyLens-RequestId")

app = Flask(__name__)


def _headers(names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: request.headers.get(name) for name in names}


@app.get("/")
def index() -> tuple[dict[str, object], int]:
    return {
        "service": APP_NAME,
        "message": f"hello from {APP_NAME} with manual ProxyLens header propagation",
        "proxylens": {
            "inbound_headers": _headers(PROXYLENS_HEADERS),
        },
    }, 200


if __name__ == "__main__":
    app.run(
        host=APP_BIND,
        port=APP_PORT,
        ssl_context=(APP_CERT_FILE, APP_KEY_FILE),
        debug=False,
    )
