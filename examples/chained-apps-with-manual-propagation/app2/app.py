from __future__ import annotations

import os

import requests
import urllib3
from flask import Flask, request

APP_BIND = os.environ.get("APP_BIND", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "9443"))
APP_CERT_FILE = os.environ["APP_CERT_FILE"]
APP_KEY_FILE = os.environ["APP_KEY_FILE"]
APP_NAME = os.environ["APP_NAME"]
DOWNSTREAM_URL = os.environ.get("DOWNSTREAM_URL")
DOWNSTREAM_NAME = os.environ.get("DOWNSTREAM_NAME")

PROXYLENS_HEADERS = ("X-ProxyLens-HopChain", "X-ProxyLens-RequestId")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)


def _headers(names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: request.headers.get(name) for name in names}


@app.get("/")
def index() -> tuple[dict[str, object], int]:
    inbound_headers = _headers(PROXYLENS_HEADERS)
    payload: dict[str, object] = {
        "service": APP_NAME,
        "proxylens": {
            "inbound_headers": inbound_headers,
        },
    }

    if DOWNSTREAM_URL is None:
        payload["message"] = f"hello from {APP_NAME}"
        return payload, 200

    forwarded_headers = {
        "Accept": "application/json",
        **{name: value for name, value in inbound_headers.items() if value is not None},
    }
    payload["proxylens"]["forwarded_headers"] = forwarded_headers

    try:
        response = requests.get(
            DOWNSTREAM_URL,
            headers=forwarded_headers,
            timeout=10,
            verify=False,
        )
        response.raise_for_status()
        payload["message"] = f"{APP_NAME} called {DOWNSTREAM_NAME} with manual ProxyLens header propagation"
        payload["downstream"] = response.json()
        return payload, 200
    except requests.RequestException as exc:
        payload["error"] = f"downstream request failed: {exc}"
        return payload, 502


if __name__ == "__main__":
    app.run(
        host=APP_BIND,
        port=APP_PORT,
        ssl_context=(APP_CERT_FILE, APP_KEY_FILE),
        debug=False,
    )
