from __future__ import annotations

from proxylens_server.common.identity import parse_hop_chain


def test_parse_hop_chain_extracts_trace_and_nodes() -> None:
    trace_id, nodes = parse_hop_chain("01K0TRACEEDGEAPROXYB0000000@edge-a,proxy-a")
    assert trace_id == "01K0TRACEEDGEAPROXYB0000000"
    assert nodes == ("edge-a", "proxy-a")
