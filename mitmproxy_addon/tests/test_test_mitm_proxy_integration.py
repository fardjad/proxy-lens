from __future__ import annotations

import asyncio

import pytest
from mitmproxy import http

from proxylens_mitmproxy import (
    ProxyLens,
    RecordingProxyLensServerClient,
    TestMitmProxy,
)


def test_repeated_calls_in_one_session_preserve_order() -> None:
    client = RecordingProxyLensServerClient()
    request_ids = iter(
        [
            "01K0REQUESTFIRSTEXAMPLE0000",
            "01K0REQUESTSECONDEXAMPLE000",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: next(request_ids),
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(200, b"ok")

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        first = proxy.request("GET", "https://example.test/first")
        second = proxy.request("GET", "https://example.test/second")

    request_started_events = [
        event for event in client.events if event["type"] == "http_request_started"
    ]
    assert (
        first.request.headers["X-ProxyLens-RequestId"]
        == "01K0REQUESTFIRSTEXAMPLE0000"
    )
    assert (
        second.request.headers["X-ProxyLens-RequestId"]
        == "01K0REQUESTSECONDEXAMPLE000"
    )
    assert [event["request_id"] for event in request_started_events] == [
        "01K0REQUESTFIRSTEXAMPLE0000",
        "01K0REQUESTSECONDEXAMPLE000",
    ]


def test_handler_exceptions_surface() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=_blob_ids(),
    )

    def handler(flow: http.HTTPFlow) -> None:
        raise RuntimeError("boom")

    proxy = TestMitmProxy(proxy_lens=addon, handler=handler)
    with pytest.raises(RuntimeError, match="boom"):
        proxy.request("GET", "https://example.test/fail-fast")
    proxy.close()


def test_async_entry_points_behave_like_sync() -> None:
    async def run() -> tuple[int, list[dict[str, object]]]:
        client = RecordingProxyLensServerClient()
        addon = ProxyLens(
            client=client,
            node_name="proxy-a",
            trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
            request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
            blob_id_generator=_blob_ids(),
        )

        def handler(flow: http.HTTPFlow) -> None:
            flow.response = http.Response.make(202, b"accepted")

        async with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
            captured = await proxy.arequest(
                "POST", "https://example.test/async", content=b"ok"
            )
        return captured.response.status_code, client.events

    status_code, events = asyncio.run(run())

    assert status_code == 202
    assert [event["type"] for event in events] == [
        "http_request_started",
        "http_request_body",
        "http_request_completed",
        "http_response_started",
        "http_response_body",
        "http_response_completed",
    ]


def _blob_ids():
    counter = 0

    def make() -> str:
        nonlocal counter
        counter += 1
        return f"01K0BLOB{counter:018d}"

    return make
