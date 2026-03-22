from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import threading

import pytest

from proxylens_mitmproxy.client import (
    ProxyLensServerClient,
    ProxyLensServerClientError,
    RecordingProxyLensServerClient,
    resolve_server_base_url,
)
from proxylens_mitmproxy.models import CaptureContext, HttpRequestCompletedEvent


def test_recording_client_records_uploads_and_events() -> None:
    client = RecordingProxyLensServerClient()

    client.upload_blob("01K0BLOBEXAMPLE0000000000000", BytesIO(b"payload"))
    client.submit_event(
        HttpRequestCompletedEvent(
            context=CaptureContext(
                event_index=1,
                request_id="01K0REQUESTEXAMPLE0000000000",
                node_name="proxy-a",
                hop_chain="01K0TRACEEXAMPLE000000000000@proxy-a",
            )
        )
    )

    assert client.uploads == [
        {
            "blob_id": "01K0BLOBEXAMPLE0000000000000",
            "data": b"payload",
        }
    ]
    assert client.events[0]["type"] == "http_request_completed"
    assert client.operations[0]["kind"] == "upload_blob"
    assert client.operations[1]["kind"] == "submit_event"


def test_resolve_server_base_url_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROXYLENS_SERVER_BASE_URL", "http://server.test:9999/")

    assert resolve_server_base_url() == "http://server.test:9999"


def test_http_client_uploads_blobs_and_submits_events() -> None:
    with _recording_server() as server:
        client = ProxyLensServerClient(base_url=server["base_url"])

        client.upload_blob("01K0BLOBEXAMPLE0000000000000", b"payload")
        client.submit_event(
            HttpRequestCompletedEvent(
                context=CaptureContext(
                    event_index=1,
                    request_id="01K0REQUESTEXAMPLE0000000000",
                    node_name="proxy-a",
                    hop_chain="01K0TRACEEXAMPLE000000000000@proxy-a",
                )
            )
        )

    assert server["requests"][0]["method"] == "PUT"
    assert server["requests"][0]["path"] == "/blobs/01K0BLOBEXAMPLE0000000000000"
    assert server["requests"][0]["body"] == b"payload"
    assert server["requests"][1]["method"] == "POST"
    assert server["requests"][1]["path"] == "/events"
    assert json.loads(server["requests"][1]["body"]) == {
        "events": [
            {
                "type": "http_request_completed",
                "request_id": "01K0REQUESTEXAMPLE0000000000",
                "event_index": 1,
                "node_name": "proxy-a",
                "hop_chain": "01K0TRACEEXAMPLE000000000000@proxy-a",
                "payload": {},
            }
        ]
    }


def test_http_client_raises_on_rejected_event_result() -> None:
    with _recording_server(reject_events=True) as server:
        client = ProxyLensServerClient(base_url=server["base_url"])

        with pytest.raises(ProxyLensServerClientError, match="server rejected event"):
            client.submit_event(
                HttpRequestCompletedEvent(
                    context=CaptureContext(
                        event_index=1,
                        request_id="01K0REQUESTEXAMPLE0000000000",
                        node_name="proxy-a",
                        hop_chain="01K0TRACEEXAMPLE000000000000@proxy-a",
                    )
                )
            )


@contextmanager
def _recording_server(*, reject_events: bool = False):
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self) -> None:
            body = self._read_body()
            requests.append(
                {
                    "method": "PUT",
                    "path": self.path,
                    "headers": dict(self.headers.items()),
                    "body": body,
                }
            )
            blob_id = self.path.rsplit("/", 1)[-1]
            self._write_json({"blob_id": blob_id, "status": "accepted"})

        def do_POST(self) -> None:
            body = self._read_body()
            payload = json.loads(body.decode("utf-8"))
            requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "headers": dict(self.headers.items()),
                    "body": body,
                }
            )
            event = payload["events"][0]
            status = "rejected" if reject_events else "accepted"
            self._write_json(
                {
                    "results": [
                        {
                            "request_id": event["request_id"],
                            "event_index": event["event_index"],
                            "status": status,
                            "detail": "forced rejection" if reject_events else None,
                        }
                    ]
                },
                status_code=409 if reject_events else 200,
            )

        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def _read_body(self) -> bytes:
            content_length = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(content_length)

        def _write_json(
            self, payload: dict[str, object], *, status_code: int = 200
        ) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "base_url": f"http://127.0.0.1:{server.server_address[1]}",
            "requests": requests,
        }
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
