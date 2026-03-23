from __future__ import annotations

from datetime import UTC, datetime

from proxylens_server.common.time import parse_rfc3339, to_rfc3339
from proxylens_server.use_cases.list_requests import ListRequestsUseCase


def test_to_rfc3339_preserves_milliseconds() -> None:
    timestamp = datetime(2026, 3, 23, 12, 0, 0, 123456, tzinfo=UTC)

    assert to_rfc3339(timestamp) == "2026-03-23T12:00:00.123Z"


def test_request_time_filter_compares_milliseconds() -> None:
    use_case = ListRequestsUseCase(None)  # type: ignore[arg-type]

    assert (
        use_case._time_in_range(
            "2026-03-23T12:00:00.123Z",
            captured_after="2026-03-23T12:00:00.122Z",
            captured_before="2026-03-23T12:00:00.124Z",
        )
        is True
    )
    assert (
        use_case._time_in_range(
            "2026-03-23T12:00:00.123Z",
            captured_after="2026-03-23T12:00:00.123Z",
            captured_before=None,
        )
        is False
    )
    assert parse_rfc3339("2026-03-23T12:00:00.123Z") == datetime(
        2026,
        3,
        23,
        12,
        0,
        0,
        123000,
        tzinfo=UTC,
    )
