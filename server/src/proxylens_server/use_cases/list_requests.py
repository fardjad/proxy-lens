from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from proxylens_server.common.http import HeaderPairs
from proxylens_server.common.time import parse_rfc3339
from proxylens_server.infra.persistence.repositories.requests import (
    RequestRepository,
    RequestSummaryRecord,
)


class RequestSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    trace_id: str
    node_name: str
    hop_chain: str
    hop_nodes: tuple[str, ...]
    captured_at: str
    updated_at: str
    completed_at: str | None = None
    request_method: str | None = None
    request_url: str | None = None
    request_http_version: str | None = None
    request_headers: HeaderPairs = Field(default_factory=list)
    response_status_code: int | None = None
    response_http_version: str | None = None
    response_headers: HeaderPairs = Field(default_factory=list)
    request_complete: bool = False
    response_complete: bool = False
    websocket_open: bool = False
    error: str | None = None
    complete: bool = False

    @classmethod
    def from_record(cls, record: RequestSummaryRecord) -> "RequestSummary":
        return cls(
            request_id=record.request_id,
            trace_id=record.trace_id,
            node_name=record.node_name,
            hop_chain=record.hop_chain,
            hop_nodes=record.hop_nodes,
            captured_at=record.captured_at,
            updated_at=record.updated_at,
            completed_at=record.completed_at,
            request_method=record.request_method,
            request_url=record.request_url,
            request_http_version=record.request_http_version,
            request_headers=record.request_headers or [],
            response_status_code=record.response_status_code,
            response_http_version=record.response_http_version,
            response_headers=record.response_headers or [],
            request_complete=record.request_complete,
            response_complete=record.response_complete,
            websocket_open=record.websocket_open,
            error=record.error,
            complete=record.complete,
        )


class ListRequestsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    captured_after: str | None = None
    captured_before: str | None = None
    trace_ids: list[str] | None = None
    request_ids: list[str] | None = None
    node_names: list[str] | None = None
    methods: list[str] | None = None
    url_contains: str | None = None
    status_codes: list[int] | None = None
    complete: bool | None = None
    request_complete: bool | None = None
    response_complete: bool | None = None
    limit: int = 100
    offset: int = 0


class ListRequestsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: list[RequestSummary]


class ListRequestsUseCase:
    def __init__(self, request_repository: RequestRepository) -> None:
        self._request_repository = request_repository

    def execute(self, data: ListRequestsInput) -> ListRequestsOutput:
        summaries = self._request_repository.list_summaries()
        filtered = [
            summary for summary in summaries if self._matches_query(summary, data)
        ]
        sliced = filtered[data.offset : data.offset + data.limit]
        return ListRequestsOutput(
            requests=[RequestSummary.from_record(summary) for summary in sliced]
        )

    def _matches_query(
        self, summary: RequestSummaryRecord, query: ListRequestsInput
    ) -> bool:
        if not self._time_in_range(
            summary.captured_at,
            captured_after=query.captured_after,
            captured_before=query.captured_before,
        ):
            return False
        if query.trace_ids and summary.trace_id not in query.trace_ids:
            return False
        if query.request_ids and summary.request_id not in query.request_ids:
            return False
        if query.node_names and summary.node_name not in query.node_names:
            return False
        if query.methods and summary.request_method not in query.methods:
            return False
        if query.url_contains and (
            summary.request_url is None or query.url_contains not in summary.request_url
        ):
            return False
        if (
            query.status_codes
            and summary.response_status_code not in query.status_codes
        ):
            return False
        if query.complete is not None and summary.complete != query.complete:
            return False
        if (
            query.request_complete is not None
            and summary.request_complete != query.request_complete
        ):
            return False
        if (
            query.response_complete is not None
            and summary.response_complete != query.response_complete
        ):
            return False
        return True

    def _time_in_range(
        self,
        value: str,
        *,
        captured_after: str | None,
        captured_before: str | None,
    ) -> bool:
        timestamp = parse_rfc3339(value)
        if captured_after is not None and timestamp <= parse_rfc3339(captured_after):
            return False
        if captured_before is not None and timestamp >= parse_rfc3339(captured_before):
            return False
        return True
