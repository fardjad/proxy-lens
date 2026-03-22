from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from proxylens_server.common.http import HeaderPairs
from proxylens_server.use_cases.get_request import RequestDetail
from proxylens_server.use_cases.get_request_events import PersistedEvent
from proxylens_server.use_cases.get_response_detail import ResponseDetail
from proxylens_server.use_cases.ingest_events import (
    WebSocketDirection,
    WebSocketPayloadType,
)
from proxylens_server.use_cases.list_requests import RequestSummary
from proxylens_server.use_cases.request_histogram import (
    HistogramBucket,
    RequestHistogram,
)


class BlobRefDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blob_id: str
    size_bytes: int
    content_type: str | None = None


class WebSocketMessageDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_index: int
    captured_at: str
    direction: WebSocketDirection
    payload_type: WebSocketPayloadType
    payload_text: str | None = None
    blob_id: str | None = None
    size_bytes: int | None = None


class RequestSummaryDTO(BaseModel):
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


class RequestSummaryListResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requests: list[RequestSummaryDTO]

    @classmethod
    def from_output(
        cls, requests: list[RequestSummary]
    ) -> "RequestSummaryListResponseDTO":
        return cls(
            requests=[
                RequestSummaryDTO(**request.model_dump(mode="json"))
                for request in requests
            ]
        )


class RequestDetailResponseDTO(RequestSummaryDTO):
    request_trailers: HeaderPairs = Field(default_factory=list)
    request_body_size: int = 0
    request_body_blob_id: str | None = None
    request_body_complete: bool = False
    response_trailers: HeaderPairs = Field(default_factory=list)
    response_body_size: int = 0
    response_body_blob_id: str | None = None
    response_body_complete: bool = False
    response_started: bool = False
    request_started: bool = False
    websocket_url: str | None = None
    websocket_http_version: str | None = None
    websocket_headers: HeaderPairs = Field(default_factory=list)
    websocket_close_code: int | None = None
    websocket_messages: list[WebSocketMessageDTO] = Field(default_factory=list)
    request_body_chunks: list[BlobRefDTO] = Field(default_factory=list)
    response_body_chunks: list[BlobRefDTO] = Field(default_factory=list)

    @classmethod
    def from_output(cls, output: RequestDetail) -> "RequestDetailResponseDTO":
        return cls(**output.model_dump(mode="json"))


class HistogramPointDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    request_count: int


class HistogramResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: HistogramBucket
    captured_after: str | None = None
    captured_before: str | None = None
    points: list[HistogramPointDTO]

    @classmethod
    def from_output(cls, output: RequestHistogram) -> "HistogramResponseDTO":
        return cls(**output.model_dump(mode="json"))


class PersistedEventDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    event_index: int
    accepted_at: str
    event: dict

    @classmethod
    def from_output(cls, output: PersistedEvent) -> "PersistedEventDTO":
        return cls(**output.model_dump(mode="json"))


class ResponseDetailDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    response_status_code: int | None = None
    response_http_version: str | None = None
    response_headers: HeaderPairs = Field(default_factory=list)
    response_trailers: HeaderPairs = Field(default_factory=list)
    response_body_size: int = 0
    response_body_blob_id: str | None = None
    response_body_complete: bool = False
    response_started: bool = False
    response_complete: bool = False

    @classmethod
    def from_output(cls, output: ResponseDetail) -> "ResponseDetailDTO":
        return cls(**output.model_dump(mode="json"))
