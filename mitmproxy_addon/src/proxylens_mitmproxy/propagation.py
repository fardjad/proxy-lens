from __future__ import annotations

import base64
import os
import re
import secrets
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Mapping

from ulid import ULID

PROXYLENS_HOP_CHAIN_HEADER = "X-ProxyLens-HopChain"
PROXYLENS_REQUEST_ID_HEADER = "X-ProxyLens-RequestId"
DEFAULT_NODE_NAME_ENV_VAR = "PROXYLENS_NODE_NAME"
TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"
B3_HEADER = "b3"
B3_TRACE_ID_HEADER = "x-b3-traceid"
B3_SPAN_ID_HEADER = "x-b3-spanid"
B3_SAMPLED_HEADER = "x-b3-sampled"
B3_FLAGS_HEADER = "x-b3-flags"
B3_HOP_NODES_HEADER = "x-b3-proxylens-hop-nodes"
JAEGER_TRACE_CONTEXT_HEADER = "uber-trace-id"
JAEGER_HOP_NODES_HEADER = "uberctx-proxylens-hop-nodes"
PROXYLENS_TRACESTATE_KEY = "proxylens"

_TRACE_ID_RE = re.compile(r"^[0-9a-f]{16}([0-9a-f]{16})?$", re.IGNORECASE)
_SPAN_ID_RE = re.compile(r"^[0-9a-f]{16}$", re.IGNORECASE)
_TRACEPARENT_RE = re.compile(
    r"^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PropagationState:
    trace_id: str
    hop_nodes: tuple[str, ...]
    hop_chain: str
    request_id: str
    propagator: str | None


@dataclass(frozen=True, slots=True)
class TraceContext:
    kind: str
    trace_id: str
    span_id: str | None = None
    trace_flags: str = "01"


def generate_ulid() -> str:
    return str(ULID())


def generate_trace_id() -> str:
    return secrets.token_hex(16)


def generate_span_id() -> str:
    return secrets.token_hex(8)


def resolve_node_name(
    node_name: str | None,
    *,
    env_var: str = DEFAULT_NODE_NAME_ENV_VAR,
) -> str:
    resolved = node_name or os.environ.get(env_var)
    if resolved is None or not resolved.strip():
        raise ValueError(f"node name is required via argument or ${env_var}")
    return resolved


def parse_hop_chain(value: str) -> tuple[str, tuple[str, ...]]:
    trace_id, separator, node_chain = value.partition("@")
    if separator == "" or not trace_id:
        raise ValueError(
            "hop chain must have the format '<trace_id>@<node1>,<node2>,...'"
        )
    nodes = tuple(node for node in node_chain.split(",") if node)
    if not nodes:
        raise ValueError("hop chain must include at least one node name")
    return trace_id, nodes


def serialize_hop_chain(trace_id: str, hop_nodes: tuple[str, ...]) -> str:
    if not trace_id:
        raise ValueError("trace_id must not be empty")
    if not hop_nodes:
        raise ValueError("hop_nodes must not be empty")
    return f"{trace_id}@{','.join(hop_nodes)}"


def extract_trace_id(headers: Mapping[str, str] | None) -> str | None:
    trace_context = extract_trace_context(headers)
    return trace_context.trace_id if trace_context else None


def detect_propagator(headers: Mapping[str, str] | None) -> str | None:
    trace_context = extract_trace_context(headers)
    return trace_context.kind if trace_context else None


def extract_trace_context(headers: Mapping[str, str] | None) -> TraceContext | None:
    if headers is None:
        return None
    return (
        _extract_traceparent_trace_context(headers.get(TRACEPARENT_HEADER))
        or _extract_b3_single_trace_context(headers.get(B3_HEADER))
        or _extract_b3_multi_trace_context(headers)
        or _extract_jaeger_trace_context(headers.get(JAEGER_TRACE_CONTEXT_HEADER))
    )


def extract_hop_nodes(
    headers: Mapping[str, str] | None,
    *,
    propagator: str | None = None,
) -> tuple[str, ...] | None:
    if headers is None:
        return None
    resolved_propagator = propagator or detect_propagator(headers)
    if resolved_propagator == "w3c":
        return _extract_hop_nodes_from_tracestate(headers.get(TRACESTATE_HEADER))
    if resolved_propagator == "b3":
        return _decode_hop_nodes(headers.get(B3_HOP_NODES_HEADER))
    if resolved_propagator == "jaeger":
        return _decode_hop_nodes(headers.get(JAEGER_HOP_NODES_HEADER))
    return None


def build_propagation_state(
    *,
    existing_hop_chain: str | None,
    headers: Mapping[str, str] | None,
    node_name: str,
    trace_id_generator: Callable[[], str],
    request_id_generator: Callable[[], str],
) -> PropagationState:
    propagator = detect_propagator(headers)
    if existing_hop_chain:
        trace_id, hop_nodes = parse_hop_chain(existing_hop_chain)
        nodes = (*hop_nodes, node_name)
    else:
        trace_context = extract_trace_context(headers)
        trace_id = (
            trace_context.trace_id
            if trace_context is not None
            else trace_id_generator()
        )
        propagated_hop_nodes = extract_hop_nodes(headers, propagator=propagator)
        nodes = (
            (*propagated_hop_nodes, node_name) if propagated_hop_nodes else (node_name,)
        )
    return PropagationState(
        trace_id=trace_id,
        hop_nodes=tuple(nodes),
        hop_chain=serialize_hop_chain(trace_id, tuple(nodes)),
        request_id=request_id_generator(),
        propagator=propagator,
    )


def synchronize_trace_context_headers(
    headers: MutableMapping[str, str],
    *,
    trace_id: str,
    hop_nodes: tuple[str, ...],
    propagator: str | None,
    span_id_generator: Callable[[], str],
) -> None:
    if propagator is None:
        return
    existing_context = extract_trace_context(headers)
    span_id = (
        existing_context.span_id
        if existing_context and existing_context.span_id
        else span_id_generator()
    )
    trace_flags = existing_context.trace_flags if existing_context is not None else "01"
    encoded_hop_nodes = _encode_hop_nodes(hop_nodes)
    resolved_propagator = (
        propagator if propagator != "w3c" or len(trace_id) == 32 else "b3"
    )
    if resolved_propagator == "w3c" and len(trace_id) == 32:
        headers[TRACEPARENT_HEADER] = f"00-{trace_id}-{span_id}-{trace_flags}"
        headers[TRACESTATE_HEADER] = _upsert_tracestate(
            headers.get(TRACESTATE_HEADER),
            PROXYLENS_TRACESTATE_KEY,
            encoded_hop_nodes,
        )
        _delete_b3_headers(headers)
        _delete_jaeger_headers(headers)
        return

    if resolved_propagator == "jaeger":
        headers[JAEGER_TRACE_CONTEXT_HEADER] = (
            f"{trace_id}:{span_id}:0:{_jaeger_flags_value(trace_flags)}"
        )
        headers[JAEGER_HOP_NODES_HEADER] = encoded_hop_nodes
        _delete_header(headers, TRACEPARENT_HEADER)
        _delete_header(headers, TRACESTATE_HEADER)
        _delete_b3_headers(headers)
        return

    headers[B3_HEADER] = f"{trace_id}-{span_id}-{_b3_sampled_value(trace_flags)}"
    headers[B3_TRACE_ID_HEADER] = trace_id
    headers[B3_SPAN_ID_HEADER] = span_id
    headers[B3_SAMPLED_HEADER] = _b3_sampled_value(trace_flags)
    _delete_header(headers, B3_FLAGS_HEADER)
    headers[B3_HOP_NODES_HEADER] = encoded_hop_nodes
    _delete_header(headers, TRACEPARENT_HEADER)
    _delete_header(headers, TRACESTATE_HEADER)
    _delete_jaeger_headers(headers)


def _extract_traceparent_trace_context(value: str | None) -> TraceContext | None:
    if value is None:
        return None
    match = _TRACEPARENT_RE.fullmatch(value.strip())
    if match is None:
        return None
    trace_id = _normalize_trace_id(match.group(1))
    span_id = _normalize_span_id(match.group(2))
    if trace_id is None or span_id is None:
        return None
    return TraceContext(
        kind="w3c",
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=match.group(3).lower(),
    )


def _extract_b3_single_trace_context(value: str | None) -> TraceContext | None:
    if value is None:
        return None
    parts = value.strip().split("-")
    trace_id = _normalize_trace_id(parts[0] if parts else None)
    if trace_id is None:
        return None
    span_id = _normalize_span_id(parts[1] if len(parts) >= 2 else None)
    trace_flags = _trace_flags_from_b3(parts[2] if len(parts) >= 3 else None)
    return TraceContext(
        kind="b3", trace_id=trace_id, span_id=span_id, trace_flags=trace_flags
    )


def _extract_b3_multi_trace_context(headers: Mapping[str, str]) -> TraceContext | None:
    trace_id = _normalize_trace_id(headers.get(B3_TRACE_ID_HEADER))
    if trace_id is None:
        return None
    span_id = _normalize_span_id(headers.get(B3_SPAN_ID_HEADER))
    trace_flags = _trace_flags_from_b3(
        headers.get(B3_SAMPLED_HEADER) or headers.get(B3_FLAGS_HEADER)
    )
    return TraceContext(
        kind="b3", trace_id=trace_id, span_id=span_id, trace_flags=trace_flags
    )


def _extract_jaeger_trace_context(value: str | None) -> TraceContext | None:
    if value is None:
        return None
    parts = value.strip().split(":")
    trace_id = _normalize_trace_id(parts[0] if parts else None)
    if trace_id is None:
        return None
    span_id = _normalize_span_id(parts[1] if len(parts) >= 2 else None)
    trace_flags = _trace_flags_from_jaeger(parts[3] if len(parts) >= 4 else None)
    return TraceContext(
        kind="jaeger",
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=trace_flags,
    )


def _extract_hop_nodes_from_tracestate(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    for member in value.split(","):
        key, separator, member_value = member.strip().partition("=")
        if separator != "=" or key != PROXYLENS_TRACESTATE_KEY:
            continue
        return _decode_hop_nodes(member_value)
    return None


def _encode_hop_nodes(hop_nodes: tuple[str, ...]) -> str:
    encoded = base64.urlsafe_b64encode(",".join(hop_nodes).encode("utf-8")).decode(
        "ascii"
    )
    return encoded.rstrip("=")


def _decode_hop_nodes(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
    except Exception:
        return None
    nodes = tuple(node for node in decoded.split(",") if node)
    return nodes or None


def _upsert_tracestate(value: str | None, key: str, member_value: str) -> str:
    members = []
    if value:
        for member in value.split(","):
            normalized = member.strip()
            if normalized and not normalized.startswith(f"{key}="):
                members.append(normalized)
    return ",".join([f"{key}={member_value}", *members])


def _normalize_trace_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if _TRACE_ID_RE.fullmatch(normalized) is None:
        return None
    if set(normalized) == {"0"}:
        return None
    return normalized


def _normalize_span_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if _SPAN_ID_RE.fullmatch(normalized) is None:
        return None
    if set(normalized) == {"0"}:
        return None
    return normalized


def _trace_flags_from_b3(value: str | None) -> str:
    if value is None:
        return "01"
    normalized = value.strip().lower()
    return "00" if normalized == "0" else "01"


def _trace_flags_from_jaeger(value: str | None) -> str:
    if value is None:
        return "01"
    try:
        return "01" if int(value, 16) & 1 else "00"
    except ValueError:
        return "01"


def _b3_sampled_value(trace_flags: str) -> str:
    return "1" if int(trace_flags, 16) & 1 else "0"


def _jaeger_flags_value(trace_flags: str) -> str:
    return "1" if int(trace_flags, 16) & 1 else "0"


def _delete_header(headers: MutableMapping[str, str], key: str) -> None:
    if key in headers:
        del headers[key]


def _delete_b3_headers(headers: MutableMapping[str, str]) -> None:
    for key in (
        B3_HEADER,
        B3_TRACE_ID_HEADER,
        B3_SPAN_ID_HEADER,
        B3_SAMPLED_HEADER,
        B3_FLAGS_HEADER,
        B3_HOP_NODES_HEADER,
    ):
        _delete_header(headers, key)


def _delete_jaeger_headers(headers: MutableMapping[str, str]) -> None:
    for key in (JAEGER_TRACE_CONTEXT_HEADER, JAEGER_HOP_NODES_HEADER):
        _delete_header(headers, key)
