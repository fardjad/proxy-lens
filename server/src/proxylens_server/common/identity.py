from __future__ import annotations

import re

ULID_RE = re.compile(r"^[0-9A-Z]{26,64}$")


def validate_ulid(value: str) -> str:
    if not ULID_RE.fullmatch(value):
        raise ValueError("must be a ULID")
    return value


def parse_hop_chain(hop_chain: str) -> tuple[str, tuple[str, ...]]:
    trace_id, separator, raw_nodes = hop_chain.partition("@")
    if separator != "@":
        raise ValueError("hop_chain must look like <trace_id>@node-a,node-b")
    validate_ulid(trace_id)
    nodes = tuple(node.strip() for node in raw_nodes.split(",") if node.strip())
    if not nodes:
        raise ValueError("hop_chain must include at least one node name")
    return trace_id, nodes
