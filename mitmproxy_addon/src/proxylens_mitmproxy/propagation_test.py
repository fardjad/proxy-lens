from __future__ import annotations

import os

import pytest

from proxylens_mitmproxy.propagation import (
    B3_HEADER,
    B3_HOP_NODES_HEADER,
    B3_SAMPLED_HEADER,
    B3_SPAN_ID_HEADER,
    B3_TRACE_ID_HEADER,
    JAEGER_HOP_NODES_HEADER,
    JAEGER_TRACE_CONTEXT_HEADER,
    TRACEPARENT_HEADER,
    TRACESTATE_HEADER,
    build_propagation_state,
    extract_hop_nodes,
    extract_trace_id,
    generate_trace_id,
    generate_ulid,
    parse_hop_chain,
    resolve_node_name,
    synchronize_trace_context_headers,
)


def test_build_proxylens_trace_header_for_new_trace() -> None:
    state = build_propagation_state(
        existing_hop_chain=None,
        headers=None,
        node_name="proxy-a",
        trace_id_generator=lambda: "4bf92f3577b34da6a3ce929d0e0e4736",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
    )

    assert state.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert state.hop_nodes == ("proxy-a",)
    assert state.hop_chain == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a"
    assert state.request_id == "01K0REQUESTPROXYAEXAMPLE00"
    assert state.propagator is None


def test_existing_trace_header_is_appended() -> None:
    state = build_propagation_state(
        existing_hop_chain="4bf92f3577b34da6a3ce929d0e0e4736@proxy-a",
        headers={
            "traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"
        },
        node_name="proxy-b",
        trace_id_generator=lambda: "unused",
        request_id_generator=lambda: "01K0REQUESTPROXYBEXAMPLE00",
    )

    assert state.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert state.hop_nodes == ("proxy-a", "proxy-b")
    assert state.hop_chain == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a,proxy-b"
    assert state.propagator == "w3c"


def test_build_propagation_state_prefers_traceparent_trace_id() -> None:
    state = build_propagation_state(
        existing_hop_chain=None,
        headers={
            "traceparent": "00-4BF92F3577B34DA6A3CE929D0E0E4736-00F067AA0BA902B7-01"
        },
        node_name="proxy-a",
        trace_id_generator=lambda: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
    )

    assert state.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert state.hop_chain == "4bf92f3577b34da6a3ce929d0e0e4736@proxy-a"
    assert state.propagator == "w3c"


def test_build_propagation_state_restores_hop_nodes_from_tracestate() -> None:
    state = build_propagation_state(
        existing_hop_chain=None,
        headers={
            TRACEPARENT_HEADER: "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            TRACESTATE_HEADER: "vendor=keep,proxylens=ZWRnZS1hLHByb3h5LWE",
        },
        node_name="proxy-b",
        trace_id_generator=lambda: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        request_id_generator=lambda: "01K0REQUESTPROXYBEXAMPLE00",
    )

    assert state.hop_nodes == ("edge-a", "proxy-a", "proxy-b")
    assert state.hop_chain == "4bf92f3577b34da6a3ce929d0e0e4736@edge-a,proxy-a,proxy-b"
    assert state.propagator == "w3c"


def test_extract_trace_id_supports_b3_single_multi_and_jaeger() -> None:
    assert extract_trace_id({"b3": "a3ce929d0e0e4736-00f067aa0ba902b7-1"}) == (
        "a3ce929d0e0e4736"
    )
    assert extract_trace_id({"x-b3-traceid": "4BF92F3577B34DA6A3CE929D0E0E4736"}) == (
        "4bf92f3577b34da6a3ce929d0e0e4736"
    )
    assert (
        extract_trace_id(
            {"uber-trace-id": "4BF92F3577B34DA6A3CE929D0E0E4736:00f067aa0ba902b7:0:1"}
        )
        == "4bf92f3577b34da6a3ce929d0e0e4736"
    )


def test_extract_trace_id_ignores_invalid_values() -> None:
    assert (
        extract_trace_id({"traceparent": "00-00000000000000000000000000000000-0-01"})
        is None
    )
    assert extract_trace_id({"b3": "1"}) is None
    assert extract_trace_id({"x-b3-traceid": "not-hex"}) is None
    assert extract_trace_id({"uber-trace-id": "bad"}) is None


def test_extract_hop_nodes_supports_all_state_headers() -> None:
    assert extract_hop_nodes(
        {TRACESTATE_HEADER: "proxylens=ZWRnZS1hLHByb3h5LWE"},
        propagator="w3c",
    ) == (
        "edge-a",
        "proxy-a",
    )
    assert extract_hop_nodes(
        {B3_HOP_NODES_HEADER: "ZWRnZS1hLHByb3h5LWE"},
        propagator="b3",
    ) == (
        "edge-a",
        "proxy-a",
    )
    assert extract_hop_nodes(
        {JAEGER_HOP_NODES_HEADER: "ZWRnZS1hLHByb3h5LWE"},
        propagator="jaeger",
    ) == (
        "edge-a",
        "proxy-a",
    )


def test_extract_hop_nodes_requires_detected_propagator() -> None:
    assert (
        extract_hop_nodes({TRACESTATE_HEADER: "proxylens=ZWRnZS1hLHByb3h5LWE"}) is None
    )
    assert extract_hop_nodes({B3_HOP_NODES_HEADER: "ZWRnZS1hLHByb3h5LWE"}) is None
    assert extract_hop_nodes({JAEGER_HOP_NODES_HEADER: "ZWRnZS1hLHByb3h5LWE"}) is None


def test_synchronize_trace_context_headers_only_updates_w3c_headers_for_w3c_requests() -> (
    None
):
    headers: dict[str, str] = {
        TRACEPARENT_HEADER: "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        TRACESTATE_HEADER: "vendor=keep",
    }

    synchronize_trace_context_headers(
        headers,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        hop_nodes=("edge-a", "proxy-a"),
        propagator="w3c",
        span_id_generator=lambda: "aaaaaaaaaaaaaaaa",
    )

    assert (
        headers[TRACEPARENT_HEADER]
        == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    )
    assert headers[TRACESTATE_HEADER] == "proxylens=ZWRnZS1hLHByb3h5LWE,vendor=keep"
    assert B3_HEADER not in headers
    assert B3_TRACE_ID_HEADER not in headers
    assert JAEGER_TRACE_CONTEXT_HEADER not in headers


def test_synchronize_trace_context_headers_only_updates_b3_headers_for_b3_requests() -> (
    None
):
    headers: dict[str, str] = {
        B3_HEADER: "a3ce929d0e0e4736-00f067aa0ba902b7-1",
        B3_HOP_NODES_HEADER: "ZWRnZS1h",
    }

    synchronize_trace_context_headers(
        headers,
        trace_id="a3ce929d0e0e4736",
        hop_nodes=("edge-a", "proxy-a"),
        propagator="b3",
        span_id_generator=lambda: "00f067aa0ba902b7",
    )

    assert headers[B3_HEADER] == "a3ce929d0e0e4736-00f067aa0ba902b7-1"
    assert headers[B3_TRACE_ID_HEADER] == "a3ce929d0e0e4736"
    assert headers[B3_SPAN_ID_HEADER] == "00f067aa0ba902b7"
    assert headers[B3_SAMPLED_HEADER] == "1"
    assert headers[B3_HOP_NODES_HEADER] == "ZWRnZS1hLHByb3h5LWE"
    assert TRACEPARENT_HEADER not in headers
    assert JAEGER_TRACE_CONTEXT_HEADER not in headers


def test_synchronize_trace_context_headers_only_updates_jaeger_headers_for_jaeger_requests() -> (
    None
):
    headers: dict[str, str] = {
        JAEGER_TRACE_CONTEXT_HEADER: "4bf92f3577b34da6a3ce929d0e0e4736:00f067aa0ba902b7:0:1",
        JAEGER_HOP_NODES_HEADER: "ZWRnZS1h",
    }

    synchronize_trace_context_headers(
        headers,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        hop_nodes=("edge-a", "proxy-a"),
        propagator="jaeger",
        span_id_generator=lambda: "aaaaaaaaaaaaaaaa",
    )

    assert (
        headers[JAEGER_TRACE_CONTEXT_HEADER]
        == "4bf92f3577b34da6a3ce929d0e0e4736:00f067aa0ba902b7:0:1"
    )
    assert headers[JAEGER_HOP_NODES_HEADER] == "ZWRnZS1hLHByb3h5LWE"
    assert TRACEPARENT_HEADER not in headers
    assert B3_HEADER not in headers


def test_synchronize_trace_context_headers_is_noop_without_detected_propagator() -> (
    None
):
    headers: dict[str, str] = {}

    synchronize_trace_context_headers(
        headers,
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        hop_nodes=("proxy-a",),
        propagator=None,
        span_id_generator=lambda: "aaaaaaaaaaaaaaaa",
    )

    assert headers == {}


def test_parse_hop_chain_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        parse_hop_chain("broken")


def test_node_name_can_be_resolved_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROXYLENS_NODE_NAME", "proxy-env")

    assert resolve_node_name(None) == "proxy-env"


def test_missing_node_name_raises() -> None:
    existing = os.environ.pop("PROXYLENS_NODE_NAME", None)
    try:
        with pytest.raises(ValueError):
            resolve_node_name(None)
    finally:
        if existing is not None:
            os.environ["PROXYLENS_NODE_NAME"] = existing


def test_generate_ulid_returns_canonical_length() -> None:
    assert len(generate_ulid()) == 26


def test_generate_trace_id_returns_32_hex_chars() -> None:
    trace_id = generate_trace_id()

    assert len(trace_id) == 32
    assert all(character in "0123456789abcdef" for character in trace_id)
