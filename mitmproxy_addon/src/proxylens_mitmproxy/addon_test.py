from __future__ import annotations

from mitmproxy import http
from mitmproxy.test import tflow
import pytest

from proxylens_mitmproxy.addon import ProxyLens
from proxylens_mitmproxy.client import (
    ProxyLensServerClient,
    RecordingProxyLensServerClient,
)
from proxylens_mitmproxy.propagation import (
    PROXYLENS_HOP_CHAIN_HEADER,
    PROXYLENS_REQUEST_ID_HEADER,
)


def test_requestheaders_mutates_trace_headers_and_submits_request_started() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "01K0TRACEPROXYAEXAMPLE0000",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
    )
    flow = tflow.tflow(
        req=http.Request.make(
            "GET",
            "https://example.test/widgets",
            headers={PROXYLENS_REQUEST_ID_HEADER: "upstream"},
        ),
        resp=False,
    )

    addon.requestheaders(flow)

    assert (
        flow.request.headers[PROXYLENS_HOP_CHAIN_HEADER]
        == "01K0TRACEPROXYAEXAMPLE0000@proxy-a"
    )
    assert (
        flow.request.headers[PROXYLENS_REQUEST_ID_HEADER]
        == "01K0REQUESTPROXYAEXAMPLE00"
    )
    assert client.events[0]["type"] == "http_request_started"


def test_filter_can_exclude_flow() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        flow_filter=lambda flow: flow.request.host != "skip.test",
    )
    flow = tflow.tflow(req=http.Request.make("GET", "https://skip.test/"), resp=False)

    addon.requestheaders(flow)

    assert client.events == []


def test_stream_callback_submits_request_body_incrementally() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "01K0TRACEPROXYAEXAMPLE0000",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
        blob_id_generator=lambda: "01K0BLOBPROXYAEXAMPLE000000",
    )
    flow = tflow.tflow(
        req=http.Request.make(
            "POST",
            "https://example.test/widgets",
            content=b"abcdefgh",
        ),
        resp=False,
    )
    flow.request.stream = True

    addon.requestheaders(flow)
    flow.request.stream(b"abcd")

    assert [event["type"] for event in client.events] == [
        "http_request_started",
        "http_request_body",
    ]
    assert client.events[1]["payload"]["size_bytes"] == 4
    assert client.events[1]["payload"]["complete"] is False


def test_addon_builds_default_http_client_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROXYLENS_SERVER_BASE_URL", "http://server.test:9010")

    addon = ProxyLens(node_name="proxy-a")

    assert isinstance(addon._client, ProxyLensServerClient)
    assert addon._client.base_url == "http://server.test:9010"
