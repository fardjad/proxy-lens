from __future__ import annotations

import re

ULID_RE = re.compile(r"^[0-9A-Z]{26,64}$")
TRACE_ID_RE = re.compile(r"^(?:[0-9a-f]{16}|[0-9a-f]{32})$", re.IGNORECASE)


def validate_ulid(value: str) -> str:
    if not ULID_RE.fullmatch(value):
        raise ValueError("must be a ULID")
    return value


def validate_trace_id(value: str) -> str:
    normalized = value.strip().lower()
    if TRACE_ID_RE.fullmatch(normalized) is None or set(normalized) == {"0"}:
        raise ValueError("must be a supported trace id")
    return normalized


def parse_hop_chain(hop_chain: str) -> tuple[str, tuple[str, ...]]:
    trace_id, separator, raw_nodes = hop_chain.partition("@")
    if separator != "@":
        raise ValueError("hop_chain must look like <trace_id>@node-a,node-b")
    trace_id = validate_trace_id(trace_id)
    nodes = tuple(node.strip() for node in raw_nodes.split(",") if node.strip())
    if not nodes:
        raise ValueError("hop_chain must include at least one node name")
    return trace_id, nodes
