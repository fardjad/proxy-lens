from __future__ import annotations

from proxylens_mitmproxy.models import (
    CaptureContext,
    HttpRequestStartedEvent,
    WebSocketMessageEvent,
    serialize_event,
)


def test_serialize_http_request_started_event() -> None:
    event = HttpRequestStartedEvent(
        context=CaptureContext(
            event_index=0,
            request_id="01K0REQUESTEXAMPLE0000000000",
            node_name="proxy-a",
            hop_chain="4bf92f3577b34da6a3ce929d0e0e4736@proxy-a",
        ),
        method="POST",
        url="https://example.test/widgets",
        http_version="HTTP/1.1",
        headers=(("content-type", "application/json"),),
    )

    assert serialize_event(event) == {
        "type": "http_request_started",
        "request_id": "01K0REQUESTEXAMPLE0000000000",
        "event_index": 0,
        "node_name": "proxy-a",
        "hop_chain": "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a",
        "payload": {
            "method": "POST",
            "url": "https://example.test/widgets",
            "http_version": "HTTP/1.1",
            "headers": [("content-type", "application/json")],
        },
    }


def test_serialize_websocket_binary_message_event() -> None:
    event = WebSocketMessageEvent(
        context=CaptureContext(
            event_index=4,
            request_id="01K0REQUESTEXAMPLE0000000000",
            node_name="proxy-a",
            hop_chain="4bf92f3577b34da6a3ce929d0e0e4736@proxy-a",
        ),
        direction="server_to_client",
        payload_type="binary",
        blob_id="01K0BLOBEXAMPLE0000000000000",
        size_bytes=4,
    )

    assert serialize_event(event)["payload"] == {
        "direction": "server_to_client",
        "payload_type": "binary",
        "payload_text": None,
        "blob_id": "01K0BLOBEXAMPLE0000000000000",
        "size_bytes": 4,
    }
