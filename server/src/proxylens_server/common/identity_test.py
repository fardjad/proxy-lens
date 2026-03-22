from __future__ import annotations

import pytest

from proxylens_server.common.identity import parse_hop_chain, validate_trace_id


def test_parse_hop_chain_extracts_trace_and_nodes() -> None:
    trace_id, nodes = parse_hop_chain(
        "4BF92F3577B34DA6A3CE929D0E0E4736@edge-a,proxy-a"
    )
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert nodes == ("edge-a", "proxy-a")


def test_validate_trace_id_accepts_b3_64_bit_trace_ids() -> None:
    assert validate_trace_id("A3CE929D0E0E4736") == "a3ce929d0e0e4736"


def test_validate_trace_id_rejects_non_hex_values() -> None:
    with pytest.raises(ValueError):
        validate_trace_id("01K0TRACEEDGEAPROXYB0000000")
