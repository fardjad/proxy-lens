from __future__ import annotations

import os

from flask import Flask
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

APP_BIND = os.environ.get("APP_BIND", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "9443"))
APP_CERT_FILE = os.environ["APP_CERT_FILE"]
APP_KEY_FILE = os.environ["APP_KEY_FILE"]
APP_NAME = os.environ["APP_NAME"]

app = Flask(__name__)
trace.set_tracer_provider(
    TracerProvider(resource=Resource.create({"service.name": APP_NAME}))
)
FlaskInstrumentor().instrument_app(app)


@app.get("/")
def index() -> tuple[dict[str, object], int]:
    return {
        "service": APP_NAME,
        "message": f"hello from {APP_NAME}",
    }, 200


if __name__ == "__main__":
    app.run(
        host=APP_BIND,
        port=APP_PORT,
        ssl_context=(APP_CERT_FILE, APP_KEY_FILE),
        debug=False,
    )
