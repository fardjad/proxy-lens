from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from proxylens_server.common.http import HeaderPairs
from proxylens_server.domain.errors import ServerNotFoundError
from proxylens_server.infra.persistence.repositories.events import BlobChunkRecord
from proxylens_server.infra.persistence.repositories.requests import (
    RequestDetailRecord,
    RequestRepository,
)
from proxylens_server.use_cases.ingest_events import (
    WebSocketDirection,
    WebSocketPayloadType,
)


class BlobRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blob_id: str
    size_bytes: int
    content_type: str | None = None

    @classmethod
    def from_record(cls, record: BlobChunkRecord) -> "BlobRef":
        return cls(
            blob_id=record.blob_id,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
        )


class WebSocketMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_index: int
    captured_at: str
    direction: WebSocketDirection
    payload_type: WebSocketPayloadType
    payload_text: str | None = None
    blob_id: str | None = None
    size_bytes: int | None = None


class RequestDetail(BaseModel):
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
    websocket_messages: list[WebSocketMessage] = Field(default_factory=list)
    request_body_chunks: list[BlobRef] = Field(default_factory=list)
    response_body_chunks: list[BlobRef] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: RequestDetailRecord) -> "RequestDetail":
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
            request_trailers=record.request_trailers or [],
            request_body_size=record.request_body_size,
            request_body_blob_id=record.request_body_blob_id,
            request_body_complete=record.request_body_complete,
            response_trailers=record.response_trailers or [],
            response_body_size=record.response_body_size,
            response_body_blob_id=record.response_body_blob_id,
            response_body_complete=record.response_body_complete,
            response_started=record.response_started,
            request_started=record.request_started,
            websocket_url=record.websocket_url,
            websocket_http_version=record.websocket_http_version,
            websocket_headers=record.websocket_headers or [],
            websocket_close_code=record.websocket_close_code,
            websocket_messages=[
                WebSocketMessage(**message)
                for message in (record.websocket_messages or [])
            ],
            request_body_chunks=[
                BlobRef.from_record(chunk)
                for chunk in (record.request_body_chunks or [])
            ],
            response_body_chunks=[
                BlobRef.from_record(chunk)
                for chunk in (record.response_body_chunks or [])
            ],
        )


class GetRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str


class GetRequestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: RequestDetail


class GetRequestUseCase:
    def __init__(self, request_repository: RequestRepository) -> None:
        self._request_repository = request_repository

    def execute(self, data: GetRequestInput) -> GetRequestOutput:
        request = self._request_repository.get_detail(data.request_id)
        if request is None:
            raise ServerNotFoundError(f"request {data.request_id} was not found")
        return GetRequestOutput(request=RequestDetail.from_record(request))
