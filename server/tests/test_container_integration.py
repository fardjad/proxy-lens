from __future__ import annotations

from contextlib import closing
from pathlib import Path

import pytest

from proxylens_server.bootstrap import AppContainer, create_container
from proxylens_server.config import ServerConfig
from proxylens_server.use_cases.delete_request import DeleteRequestInput
from proxylens_server.use_cases.get_request import GetRequestInput
from proxylens_server.use_cases.get_request_body import GetRequestBodyInput
from proxylens_server.use_cases.ingest_events import IngestEventsInput
from proxylens_server.use_cases.ingest_events import (
    EventStatus,
    capture_event_adapter,
)
from proxylens_server.use_cases.upload_blob import UploadBlobInput
from proxylens_server.use_cases.vacuum import VacuumInput


def make_container(tmp_path: Path) -> AppContainer:
    return create_container(ServerConfig(data_dir=tmp_path))


def make_event(event_type: str, event_index: int, payload: dict) -> object:
    return capture_event_adapter.validate_python(
        {
            "type": event_type,
            "request_id": "01K0REQUESTEXAMPLE0000000000",
            "event_index": event_index,
            "node_name": "proxy-a",
            "hop_chain": "4bf92f3577b34da6a3ce929d0e0e4736@edge-a,proxy-a",
            "payload": payload,
        }
    )


def test_ingests_ordered_events_and_reconstructs_body(tmp_path: Path) -> None:
    with closing(make_container(tmp_path)) as container:
        container.upload_blob_use_case.execute(
            UploadBlobInput(
                blob_id="01K0BLOBREQUESTBODYCHUNK0000",
                data=b'{"name":"demo"}',
                content_type="application/json",
            )
        )
        container.upload_blob_use_case.execute(
            UploadBlobInput(
                blob_id="01K0BLOBRESPONSEBODYCHUNK00",
                data=b'{"ok":true}',
                content_type="application/json",
            )
        )

        response = container.ingest_events_use_case.execute(
            IngestEventsInput(
                events=[
                    make_event(
                        "http_request_started",
                        0,
                        {
                            "method": "POST",
                            "url": "https://example.test/widgets",
                            "http_version": "HTTP/1.1",
                            "headers": [("content-type", "application/json")],
                        },
                    ),
                    make_event(
                        "http_request_body",
                        1,
                        {
                            "blob_id": "01K0BLOBREQUESTBODYCHUNK0000",
                            "size_bytes": 15,
                            "complete": True,
                        },
                    ),
                    make_event("http_request_completed", 2, {}),
                    make_event(
                        "http_response_started",
                        3,
                        {
                            "status_code": 201,
                            "http_version": "HTTP/1.1",
                            "headers": [("content-type", "application/json")],
                        },
                    ),
                    make_event(
                        "http_response_body",
                        4,
                        {
                            "blob_id": "01K0BLOBRESPONSEBODYCHUNK00",
                            "size_bytes": 11,
                            "complete": True,
                        },
                    ),
                    make_event("http_response_completed", 5, {}),
                ]
            )
        )

        assert [result.status for result in response.results] == [
            EventStatus.ACCEPTED
        ] * 6
        record = container.get_request_use_case.execute(
            GetRequestInput(request_id="01K0REQUESTEXAMPLE0000000000")
        ).request
        assert record.complete is True
        assert record.response_status_code == 201
        body_output = container.get_request_body_use_case.execute(
            GetRequestBodyInput(request_id="01K0REQUESTEXAMPLE0000000000")
        )
        assert body_output.body == b'{"name":"demo"}'
        assert body_output.content_type == "application/json"


def test_defers_out_of_order_events_and_replays_them(tmp_path: Path) -> None:
    with closing(make_container(tmp_path)) as container:
        first = container.ingest_events_use_case.execute(
            IngestEventsInput(events=[make_event("http_request_completed", 1, {})])
        )
        assert first.results[0].status == EventStatus.DEFERRED

        second = container.ingest_events_use_case.execute(
            IngestEventsInput(
                events=[
                    make_event(
                        "http_request_started",
                        0,
                        {
                            "method": "GET",
                            "url": "https://example.test/widgets",
                            "http_version": "HTTP/1.1",
                            "headers": [],
                        },
                    )
                ]
            )
        )
        assert second.results[0].status == EventStatus.ACCEPTED
        record = container.get_request_use_case.execute(
            GetRequestInput(request_id="01K0REQUESTEXAMPLE0000000000")
        ).request
        assert record.request_complete is True


def test_rejects_events_for_tombstoned_requests(tmp_path: Path) -> None:
    with closing(make_container(tmp_path)) as container:
        container.ingest_events_use_case.execute(
            IngestEventsInput(
                events=[
                    make_event(
                        "http_request_started",
                        0,
                        {
                            "method": "GET",
                            "url": "https://example.test/widgets",
                            "http_version": "HTTP/1.1",
                            "headers": [],
                        },
                    )
                ]
            )
        )
        assert (
            container.delete_request_use_case.execute(
                DeleteRequestInput(request_id="01K0REQUESTEXAMPLE0000000000")
            ).result.deleted
            is True
        )
        result = container.ingest_events_use_case.execute(
            IngestEventsInput(events=[make_event("http_request_completed", 1, {})])
        ).results[0]
        assert result.status == EventStatus.REJECTED


def test_filter_can_drop_event(tmp_path: Path) -> None:
    script = tmp_path / "filter.py"
    script.write_text(
        """
def filter_event(app_container, event, request):
    return None
        """.strip()
    )
    with closing(
        create_container(ServerConfig(data_dir=tmp_path / "data", filter_script=script))
    ) as container:
        result = container.ingest_events_use_case.execute(
            IngestEventsInput(
                events=[
                    make_event(
                        "http_request_started",
                        0,
                        {
                            "method": "GET",
                            "url": "https://example.test/widgets",
                            "http_version": "HTTP/1.1",
                            "headers": [],
                        },
                    )
                ]
            )
        ).results[0]
        assert result.status == EventStatus.DROPPED


def test_delete_cleans_up_unreferenced_blobs(tmp_path: Path) -> None:
    with closing(make_container(tmp_path)) as container:
        blob_id = "01K0BLOBREQUESTBODYCHUNK0000"
        container.upload_blob_use_case.execute(
            UploadBlobInput(blob_id=blob_id, data=b"abc", content_type="text/plain")
        )
        container.ingest_events_use_case.execute(
            IngestEventsInput(
                events=[
                    make_event(
                        "http_request_started",
                        0,
                        {
                            "method": "POST",
                            "url": "https://example.test/widgets",
                            "http_version": "HTTP/1.1",
                            "headers": [],
                        },
                    ),
                    make_event(
                        "http_request_body",
                        1,
                        {"blob_id": blob_id, "size_bytes": 3, "complete": True},
                    ),
                ]
            )
        )
        container.delete_request_use_case.execute(
            DeleteRequestInput(request_id="01K0REQUESTEXAMPLE0000000000")
        )
        assert not container.blob_repository.blob_path(blob_id).exists()


def test_vacuum_deletes_completed_requests(tmp_path: Path) -> None:
    with closing(make_container(tmp_path)) as container:
        container.ingest_events_use_case.execute(
            IngestEventsInput(
                events=[
                    make_event(
                        "http_request_started",
                        0,
                        {
                            "method": "GET",
                            "url": "https://example.test/widgets",
                            "http_version": "HTTP/1.1",
                            "headers": [],
                        },
                    ),
                    make_event("http_request_completed", 1, {}),
                    make_event(
                        "http_response_started",
                        2,
                        {
                            "status_code": 200,
                            "http_version": "HTTP/1.1",
                            "headers": [],
                        },
                    ),
                    make_event("http_response_completed", 3, {}),
                ]
            )
        )
        result = container.vacuum_use_case.execute(VacuumInput()).result
        assert result.deleted_request_count == 1
        with pytest.raises(Exception):
            container.get_request_use_case.execute(
                GetRequestInput(request_id="01K0REQUESTEXAMPLE0000000000")
            )
