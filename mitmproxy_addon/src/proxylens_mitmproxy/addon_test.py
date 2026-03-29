from __future__ import annotations

from mitmproxy import flow, http
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


def test_requestheaders_reuses_traceparent_trace_id_when_hop_chain_is_missing() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
    )
    flow = tflow.tflow(
        req=http.Request.make(
            "GET",
            "https://example.test/widgets",
            headers={
                "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
            },
        ),
        resp=False,
    )

    addon.requestheaders(flow)

    assert (
        flow.request.headers[PROXYLENS_HOP_CHAIN_HEADER]
        == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a"
    )
    assert client.events[0]["hop_chain"] == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a"


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


def test_addon_is_disabled_when_server_base_url_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROXYLENS_SERVER_BASE_URL", raising=False)

    addon = ProxyLens(node_name="proxy-a")

    assert addon._disabled is True
    assert addon._client is None


def test_disabled_addon_logs_enablement_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("PROXYLENS_SERVER_BASE_URL", raising=False)
    addon = ProxyLens(node_name="proxy-a")

    with caplog.at_level("WARNING"):
        addon.load(object())

    assert "ProxyLens addon is disabled because no server base URL is configured" in caplog.text
    assert "PROXYLENS_SERVER_BASE_URL" in caplog.text


def test_enabled_addon_does_not_log_disabled_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("PROXYLENS_SERVER_BASE_URL", "http://server.test:9010")
    addon = ProxyLens(node_name="proxy-a")

    with caplog.at_level("WARNING"):
        addon.load(object())

    assert caplog.records == []


def test_disabled_addon_is_noop_without_touching_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROXYLENS_SERVER_BASE_URL", raising=False)
    addon = ProxyLens(node_name="proxy-a")
    flow = tflow.tflow(
        req=http.Request.make("POST", "https://example.test/widgets", content=b"abc"),
        resp=http.Response.make(200, b"ok"),
    )

    addon.requestheaders(flow)
    addon.request(flow)
    addon.responseheaders(flow)
    addon.response(flow)

    assert flow.metadata == {}
    assert PROXYLENS_HOP_CHAIN_HEADER not in flow.request.headers
    assert PROXYLENS_REQUEST_ID_HEADER not in flow.request.headers


def test_invalid_max_concurrent_requests_per_host_raises() -> None:
    client = RecordingProxyLensServerClient()

    with pytest.raises(
        ValueError, match="max_concurrent_requests_per_host must be at least 1"
    ):
        ProxyLens(
            client=client,
            node_name="proxy-a",
            max_concurrent_requests_per_host=0,
        )


def test_addon_reads_max_concurrent_requests_per_host_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROXYLENS_MAX_CONCURRENT_REQUESTS_PER_HOST", "2")

    addon = ProxyLens(node_name="proxy-a")

    assert addon._max_concurrent_requests_per_host == 2


def test_invalid_max_concurrent_requests_per_host_env_var_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROXYLENS_MAX_CONCURRENT_REQUESTS_PER_HOST", "abc")

    with pytest.raises(
        ValueError,
        match=r"PROXYLENS_MAX_CONCURRENT_REQUESTS_PER_HOST must be an integer",
    ):
        ProxyLens(node_name="proxy-a")


def test_limit_one_queues_second_flow_for_same_host_until_first_flow_completes() -> (
    None
):
    client = RecordingProxyLensServerClient()
    trace_ids = iter(
        [
            "01K0TRACEPROXYAEXAMPLE0000",
            "01K0TRACEPROXYAEXAMPLE0001",
        ]
    )
    request_ids = iter(
        [
            "01K0REQUESTPROXYAEXAMPLE00",
            "01K0REQUESTPROXYAEXAMPLE01",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: next(trace_ids),
        request_id_generator=lambda: next(request_ids),
        max_concurrent_requests_per_host=1,
    )
    first = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/1"), resp=False
    )
    second = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/2"),
        resp=False,
    )

    addon.requestheaders(first)
    addon.requestheaders(second)

    assert first.intercepted is False
    assert second.intercepted is True
    assert [event["type"] for event in client.events] == ["http_request_started"]
    assert client.events[0]["payload"]["url"] == "https://example.test/1"
    assert PROXYLENS_HOP_CHAIN_HEADER not in second.request.headers
    assert PROXYLENS_REQUEST_ID_HEADER not in second.request.headers

    first.response = http.Response.make(204, b"")
    addon.response(first)

    assert second.intercepted is False
    assert (
        second.request.headers[PROXYLENS_HOP_CHAIN_HEADER]
        == "01K0TRACEPROXYAEXAMPLE0001@proxy-a"
    )
    assert (
        second.request.headers[PROXYLENS_REQUEST_ID_HEADER]
        == "01K0REQUESTPROXYAEXAMPLE01"
    )
    assert [event["type"] for event in client.events] == [
        "http_request_started",
        "http_response_completed",
        "http_request_started",
    ]


def test_limit_two_allows_two_active_flows_per_host_and_queues_third() -> None:
    client = RecordingProxyLensServerClient()
    trace_ids = iter(
        [
            "01K0TRACEPROXYAEXAMPLE0000",
            "01K0TRACEPROXYAEXAMPLE0001",
            "01K0TRACEPROXYAEXAMPLE0002",
        ]
    )
    request_ids = iter(
        [
            "01K0REQUESTPROXYAEXAMPLE00",
            "01K0REQUESTPROXYAEXAMPLE01",
            "01K0REQUESTPROXYAEXAMPLE02",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: next(trace_ids),
        request_id_generator=lambda: next(request_ids),
        max_concurrent_requests_per_host=2,
    )
    first = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/1"), resp=False
    )
    second = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/2"),
        resp=False,
    )
    third = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/3"), resp=False
    )

    addon.requestheaders(first)
    addon.requestheaders(second)
    addon.requestheaders(third)

    assert first.intercepted is False
    assert second.intercepted is False
    assert third.intercepted is True
    assert [event["payload"]["url"] for event in client.events] == [
        "https://example.test/1",
        "https://example.test/2",
    ]

    first.response = http.Response.make(204, b"")
    addon.response(first)

    assert third.intercepted is False
    assert [
        event["payload"]["url"]
        for event in client.events
        if event["type"] == "http_request_started"
    ] == [
        "https://example.test/1",
        "https://example.test/2",
        "https://example.test/3",
    ]


def test_error_releases_slot_and_resumes_next_queued_flow() -> None:
    client = RecordingProxyLensServerClient()
    trace_ids = iter(
        [
            "01K0TRACEPROXYAEXAMPLE0000",
            "01K0TRACEPROXYAEXAMPLE0001",
        ]
    )
    request_ids = iter(
        [
            "01K0REQUESTPROXYAEXAMPLE00",
            "01K0REQUESTPROXYAEXAMPLE01",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: next(trace_ids),
        request_id_generator=lambda: next(request_ids),
        max_concurrent_requests_per_host=1,
    )
    first = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/1"), resp=False
    )
    second = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/2"),
        resp=False,
    )

    addon.requestheaders(first)
    addon.requestheaders(second)
    first.error = flow.Error("upstream failure")

    addon.error(first)

    assert second.intercepted is False
    assert [event["type"] for event in client.events] == [
        "http_request_started",
        "request_error",
        "http_request_started",
    ]


def test_limit_one_allows_one_active_flow_per_host() -> None:
    client = RecordingProxyLensServerClient()
    trace_ids = iter(
        [
            "01K0TRACEPROXYAEXAMPLE0000",
            "01K0TRACEPROXYAEXAMPLE0001",
        ]
    )
    request_ids = iter(
        [
            "01K0REQUESTPROXYAEXAMPLE00",
            "01K0REQUESTPROXYAEXAMPLE01",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: next(trace_ids),
        request_id_generator=lambda: next(request_ids),
        max_concurrent_requests_per_host=1,
    )
    first = tflow.tflow(
        req=http.Request.make("GET", "https://alpha.test/1"), resp=False
    )
    second = tflow.tflow(
        req=http.Request.make("GET", "https://beta.test/2"),
        resp=False,
    )

    addon.requestheaders(first)
    addon.requestheaders(second)

    assert first.intercepted is False
    assert second.intercepted is False
    assert [
        event["payload"]["url"]
        for event in client.events
        if event["type"] == "http_request_started"
    ] == [
        "https://alpha.test/1",
        "https://beta.test/2",
    ]


def test_active_http_request_does_not_queue_websocket_handshake() -> None:
    client = RecordingProxyLensServerClient()
    trace_ids = iter(
        [
            "01K0TRACEPROXYAEXAMPLE0000",
            "01K0TRACEPROXYAEXAMPLE0001",
        ]
    )
    request_ids = iter(
        [
            "01K0REQUESTPROXYAEXAMPLE00",
            "01K0REQUESTPROXYAEXAMPLE01",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: next(trace_ids),
        request_id_generator=lambda: next(request_ids),
        max_concurrent_requests_per_host=1,
    )
    active_http = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/http"),
        resp=False,
    )
    websocket = tflow.tflow(
        req=http.Request.make(
            "GET",
            "https://example.test/ws",
            headers={"connection": "upgrade", "upgrade": "websocket"},
        ),
        resp=False,
    )

    addon.requestheaders(active_http)
    addon.requestheaders(websocket)

    assert active_http.intercepted is False
    assert websocket.intercepted is False
    assert [event["payload"]["url"] for event in client.events] == [
        "https://example.test/http",
        "https://example.test/ws",
    ]


def test_active_websocket_does_not_block_http_request() -> None:
    client = RecordingProxyLensServerClient()
    trace_ids = iter(
        [
            "01K0TRACEPROXYAEXAMPLE0000",
            "01K0TRACEPROXYAEXAMPLE0001",
        ]
    )
    request_ids = iter(
        [
            "01K0REQUESTPROXYAEXAMPLE00",
            "01K0REQUESTPROXYAEXAMPLE01",
        ]
    )
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: next(trace_ids),
        request_id_generator=lambda: next(request_ids),
        max_concurrent_requests_per_host=1,
    )
    websocket = tflow.tflow(
        req=http.Request.make(
            "GET",
            "https://example.test/ws",
            headers={"connection": "upgrade", "upgrade": "websocket"},
        ),
        resp=False,
    )
    http_flow = tflow.tflow(
        req=http.Request.make("GET", "https://example.test/http"),
        resp=False,
    )

    addon.requestheaders(websocket)
    addon.requestheaders(http_flow)

    assert websocket.intercepted is False
    assert http_flow.intercepted is False
    assert [event["payload"]["url"] for event in client.events] == [
        "https://example.test/ws",
        "https://example.test/http",
    ]
