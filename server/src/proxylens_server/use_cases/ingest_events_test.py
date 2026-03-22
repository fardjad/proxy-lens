from __future__ import annotations

import pytest

from proxylens_server.use_cases.ingest_events import capture_event_adapter


def test_capture_event_requires_final_hop_to_match_node() -> None:
    with pytest.raises(ValueError):
        capture_event_adapter.validate_python(
            {
                "type": "http_request_completed",
                "request_id": "01K0REQUESTEXAMPLE0000000000",
                "event_index": 0,
                "node_name": "proxy-b",
                "hop_chain": "4bf92f3577b34da6a3ce929d0e0e4736@edge-a,proxy-a",
                "payload": {},
            }
        )
