from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from ulid import ULID

PROXYLENS_HOP_CHAIN_HEADER = "X-ProxyLens-HopChain"
PROXYLENS_REQUEST_ID_HEADER = "X-ProxyLens-RequestId"
DEFAULT_NODE_NAME_ENV_VAR = "PROXYLENS_NODE_NAME"


@dataclass(frozen=True, slots=True)
class PropagationState:
    trace_id: str
    hop_nodes: tuple[str, ...]
    hop_chain: str
    request_id: str


def generate_ulid() -> str:
    return str(ULID())


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


def build_propagation_state(
    *,
    existing_hop_chain: str | None,
    node_name: str,
    trace_id_generator: Callable[[], str],
    request_id_generator: Callable[[], str],
) -> PropagationState:
    if existing_hop_chain:
        trace_id, hop_nodes = parse_hop_chain(existing_hop_chain)
        nodes = (*hop_nodes, node_name)
    else:
        trace_id = trace_id_generator()
        nodes = (node_name,)
    return PropagationState(
        trace_id=trace_id,
        hop_nodes=tuple(nodes),
        hop_chain=serialize_hop_chain(trace_id, tuple(nodes)),
        request_id=request_id_generator(),
    )
