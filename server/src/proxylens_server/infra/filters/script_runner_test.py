from __future__ import annotations

from pathlib import Path

from proxylens_server.infra.filters.script_runner import FilterRunner
from proxylens_server.use_cases.ingest_events import capture_event_adapter


def test_filter_runner_loads_and_applies_filter(tmp_path: Path) -> None:
    script = tmp_path / "filter.py"
    script.write_text(
        """
def filter_event(app_container, event, request):
    payload = event.payload.model_copy(update={"method": "PATCH"})
    return event.model_copy(update={"payload": payload})
        """.strip()
    )
    runner = FilterRunner(script)
    runner.load()
    event = capture_event_adapter.validate_python(
        {
            "type": "http_request_started",
            "request_id": "01K0REQUESTEXAMPLE0000000000",
            "event_index": 0,
            "node_name": "proxy-a",
            "hop_chain": "4bf92f3577b34da6a3ce929d0e0e4736@edge-a,proxy-a",
            "payload": {
                "method": "POST",
                "url": "https://example.test",
                "http_version": "HTTP/1.1",
                "headers": [],
            },
        }
    )
    updated = runner.apply(object(), event, None)
    assert updated is not None
    assert updated.payload.method == "PATCH"
