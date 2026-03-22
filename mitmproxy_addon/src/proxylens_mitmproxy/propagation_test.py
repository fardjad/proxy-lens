from __future__ import annotations

import os

import pytest

from proxylens_mitmproxy.propagation import (
    build_propagation_state,
    generate_ulid,
    parse_hop_chain,
    resolve_node_name,
)


def test_build_proxylens_trace_header_for_new_trace() -> None:
    state = build_propagation_state(
        existing_hop_chain=None,
        node_name="proxy-a",
        trace_id_generator=lambda: "01K0TRACEPROXYAEXAMPLE0000",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
    )

    assert state.trace_id == "01K0TRACEPROXYAEXAMPLE0000"
    assert state.hop_nodes == ("proxy-a",)
    assert state.hop_chain == "01K0TRACEPROXYAEXAMPLE0000@proxy-a"
    assert state.request_id == "01K0REQUESTPROXYAEXAMPLE00"


def test_existing_trace_header_is_appended() -> None:
    state = build_propagation_state(
        existing_hop_chain="01K0TRACEPROXYAEXAMPLE0000@proxy-a",
        node_name="proxy-b",
        trace_id_generator=lambda: "unused",
        request_id_generator=lambda: "01K0REQUESTPROXYBEXAMPLE00",
    )

    assert state.trace_id == "01K0TRACEPROXYAEXAMPLE0000"
    assert state.hop_nodes == ("proxy-a", "proxy-b")
    assert state.hop_chain == "01K0TRACEPROXYAEXAMPLE0000@proxy-a,proxy-b"


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
