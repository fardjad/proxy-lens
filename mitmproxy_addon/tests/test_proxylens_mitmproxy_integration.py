from __future__ import annotations

from mitmproxy import flow, http, websocket
from wsproto.frame_protocol import Opcode

from proxylens_mitmproxy import (
    ProxyLens,
    RecordingProxyLensServerClient,
    TestMitmProxy,
)
from proxylens_mitmproxy.propagation import (
    PROXYLENS_HOP_CHAIN_HEADER,
    PROXYLENS_REQUEST_ID_HEADER,
)


def test_missing_hop_chain_generates_new_trace_and_request_id() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(204, b"")

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        captured = proxy.request("GET", "https://example.test/widgets")

    assert (
        captured.request.headers[PROXYLENS_HOP_CHAIN_HEADER]
        == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a"
    )
    assert (
        captured.request.headers[PROXYLENS_REQUEST_ID_HEADER]
        == "01K0REQUESTPROXYAEXAMPLE00"
    )
    assert client.events[0]["type"] == "http_request_started"
    assert (
        PROXYLENS_HOP_CHAIN_HEADER,
        "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a",
    ) in client.events[0]["payload"]["headers"]
    assert (PROXYLENS_REQUEST_ID_HEADER, "01K0REQUESTPROXYAEXAMPLE00") in client.events[
        0
    ]["payload"]["headers"]


def test_existing_hop_chain_is_preserved_and_appended_and_upstream_request_id_is_replaced() -> (
    None
):
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-b",
        trace_id_generator=lambda: "unused",
        request_id_generator=lambda: "01K0REQUESTPROXYBEXAMPLE00",
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(204, b"")

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        captured = proxy.request(
            "DELETE",
            "https://example.test/widgets/1",
            headers={
                PROXYLENS_HOP_CHAIN_HEADER: "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a",
                PROXYLENS_REQUEST_ID_HEADER: "01K0REQUESTUPSTREAMEXAMPLE0",
            },
        )

    assert (
        captured.request.headers[PROXYLENS_HOP_CHAIN_HEADER]
        == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a,proxy-b"
    )
    assert (
        captured.request.headers[PROXYLENS_REQUEST_ID_HEADER]
        == "01K0REQUESTPROXYBEXAMPLE00"
    )
    assert (
        client.events[0]["hop_chain"]
        == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a,proxy-b"
    )


def test_request_and_response_bodies_upload_before_body_events_and_capture_versions_and_trailers() -> (
    None
):
    client = RecordingProxyLensServerClient()
    blob_ids = _blob_ids()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=blob_ids,
    )

    def handler(flow: http.HTTPFlow) -> None:
        response = http.Response.make(
            201,
            b'{"status":"created"}',
            {"content-type": "application/json"},
        )
        response.http_version = "HTTP/2"
        response.trailers = http.Headers(((b"x-response-trailer", b"done"),))
        flow.response = response

    request = http.Request.make(
        "POST",
        "https://example.test/widgets",
        content=b'{"name":"demo"}',
        headers={"content-type": "application/json"},
    )
    request.http_version = "HTTP/1.0"
    request.trailers = http.Headers(((b"x-request-trailer", b"done"),))

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        proxy.send(request)

    event_types = [event["type"] for event in client.events]
    assert event_types == [
        "http_request_started",
        "http_request_body",
        "http_request_trailers",
        "http_request_completed",
        "http_response_started",
        "http_response_body",
        "http_response_trailers",
        "http_response_completed",
    ]
    assert client.events[0]["payload"]["http_version"] == "HTTP/1.0"
    assert client.events[4]["payload"]["http_version"] == "HTTP/2"
    assert client.events[2]["payload"]["trailers"] == [("x-request-trailer", "done")]
    assert client.events[6]["payload"]["trailers"] == [("x-response-trailer", "done")]
    request_body_event_index = next(
        index
        for index, operation in enumerate(client.operations)
        if operation["kind"] == "submit_event"
        and operation["event"]["type"] == "http_request_body"
    )
    response_body_event_index = next(
        index
        for index, operation in enumerate(client.operations)
        if operation["kind"] == "submit_event"
        and operation["event"]["type"] == "http_response_body"
    )
    assert client.operations[request_body_event_index - 1]["kind"] == "upload_blob"
    assert client.operations[response_body_event_index - 1]["kind"] == "upload_blob"


def test_streaming_request_and_response_capture_metadata_before_body_events() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        response = http.Response.make(200, b"response-body")
        response.stream = True
        flow.response = response

    request = http.Request.make(
        "POST",
        "https://example.test/stream",
        content=b"request-body",
    )
    request.stream = True

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        proxy.send(request)

    request_events = [
        event for event in client.events if event["type"].startswith("http_request_")
    ]
    response_events = [
        event for event in client.events if event["type"].startswith("http_response_")
    ]
    request_body_events = [
        event for event in request_events if event["type"] == "http_request_body"
    ]
    response_body_events = [
        event for event in response_events if event["type"] == "http_response_body"
    ]
    assert request_events[0]["type"] == "http_request_started"
    assert request_events[-1]["type"] == "http_request_completed"
    assert response_events[0]["type"] == "http_response_started"
    assert response_events[-1]["type"] == "http_response_completed"
    assert len(request_body_events) >= 2
    assert len(response_body_events) >= 2
    assert request_body_events[-1]["payload"]["complete"] is True
    assert response_body_events[-1]["payload"]["complete"] is True
    assert all(
        event["payload"]["complete"] is False for event in request_body_events[:-1]
    )
    assert all(
        event["payload"]["complete"] is False for event in response_body_events[:-1]
    )


def test_websocket_connections_and_messages_are_captured() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(
            101,
            b"",
            {"connection": "upgrade", "upgrade": "websocket"},
        )
        flow.websocket = websocket.WebSocketData(
            messages=[
                websocket.WebSocketMessage(Opcode.TEXT, True, b"hello"),
                websocket.WebSocketMessage(Opcode.BINARY, False, b"\x00\x01"),
            ],
            close_code=1000,
        )

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        proxy.request(
            "GET",
            "https://example.test/ws",
            headers={"connection": "upgrade", "upgrade": "websocket"},
        )

    assert [event["type"] for event in client.events[-4:]] == [
        "websocket_started",
        "websocket_message",
        "websocket_message",
        "websocket_ended",
    ]
    assert client.events[-3]["payload"]["payload_text"] == "hello"
    assert client.events[-2]["payload"]["payload_type"] == "binary"


def test_node_name_can_be_resolved_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("PROXYLENS_NODE_NAME", "proxy-env")
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4739",
        request_id_generator=lambda: "01K0REQUESTPROXYENVEXAMPLE0",
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(204, b"")

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        proxy.request("GET", "https://example.test/env")

    assert client.events[0]["node_name"] == "proxy-env"


def test_error_event_is_submitted_for_failed_flow() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=_blob_ids(),
    )

    def handler(captured_flow: http.HTTPFlow) -> None:
        captured_flow.error = flow.Error("upstream failed")

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        proxy.request("GET", "https://example.test/fail")

    assert client.events[-1]["type"] == "request_error"
    assert client.events[-1]["payload"]["message"] == "upstream failed"


def _blob_ids():
    counter = 0

    def make() -> str:
        nonlocal counter
        counter += 1
        return f"01K0BLOB{counter:018d}"

    return make
