from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from proxylens_server.common.http import HeaderPairs
from proxylens_server.common.identity import parse_hop_chain, validate_ulid
from proxylens_server.common.json import normalize_json
from proxylens_server.common.time import to_rfc3339, utc_now
from proxylens_server.domain.errors import ServerConflictError
from proxylens_server.infra.filters.script_runner import FilterRunner
from proxylens_server.infra.persistence.repositories.blobs import BlobRepository
from proxylens_server.infra.persistence.repositories.deferred_events import (
    DeferredEventRepository,
)
from proxylens_server.infra.persistence.repositories.events import EventRepository
from proxylens_server.infra.persistence.repositories.requests import RequestRepository
from proxylens_server.infra.persistence.repositories.tombstones import (
    TombstoneRepository,
)
from proxylens_server.infra.persistence.sqlite import SqliteDatabase


class UseCaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebSocketPayloadType(StrEnum):
    TEXT = "text"
    BINARY = "binary"


class WebSocketDirection(StrEnum):
    CLIENT_TO_SERVER = "client_to_server"
    SERVER_TO_CLIENT = "server_to_client"


class EventStatus(StrEnum):
    ACCEPTED = "accepted"
    IGNORED = "ignored"
    DEFERRED = "deferred"
    DROPPED = "dropped"
    REJECTED = "rejected"


class EventBase(UseCaseModel):
    type: str
    request_id: str
    event_index: int = Field(ge=0)
    node_name: str = Field(min_length=1)
    hop_chain: str

    @field_validator("request_id")
    @classmethod
    def _validate_request_id(cls, value: str) -> str:
        return validate_ulid(value)

    @model_validator(mode="after")
    def _validate_hop_chain(self) -> "EventBase":
        _, nodes = parse_hop_chain(self.hop_chain)
        if nodes[-1] != self.node_name:
            raise ValueError("node_name must match the final node in hop_chain")
        return self


class HttpRequestStartedPayload(UseCaseModel):
    method: str = Field(min_length=1)
    url: str = Field(min_length=1)
    http_version: str = Field(min_length=1)
    headers: HeaderPairs = Field(default_factory=list)


class HttpRequestStartedEvent(EventBase):
    type: Literal["http_request_started"]
    payload: HttpRequestStartedPayload


class HttpRequestBodyPayload(UseCaseModel):
    blob_id: str
    size_bytes: int = Field(ge=0)
    complete: bool

    @field_validator("blob_id")
    @classmethod
    def _validate_blob_id(cls, value: str) -> str:
        return validate_ulid(value)


class HttpRequestBodyEvent(EventBase):
    type: Literal["http_request_body"]
    payload: HttpRequestBodyPayload


class HttpRequestTrailersPayload(UseCaseModel):
    trailers: HeaderPairs = Field(default_factory=list)


class HttpRequestTrailersEvent(EventBase):
    type: Literal["http_request_trailers"]
    payload: HttpRequestTrailersPayload


class HttpRequestCompletedEvent(EventBase):
    type: Literal["http_request_completed"]
    payload: dict[str, Any] = Field(default_factory=dict)


class HttpResponseStartedPayload(UseCaseModel):
    status_code: int = Field(ge=100, le=999)
    http_version: str = Field(min_length=1)
    headers: HeaderPairs = Field(default_factory=list)


class HttpResponseStartedEvent(EventBase):
    type: Literal["http_response_started"]
    payload: HttpResponseStartedPayload


class HttpResponseBodyPayload(UseCaseModel):
    blob_id: str
    size_bytes: int = Field(ge=0)
    complete: bool

    @field_validator("blob_id")
    @classmethod
    def _validate_blob_id(cls, value: str) -> str:
        return validate_ulid(value)


class HttpResponseBodyEvent(EventBase):
    type: Literal["http_response_body"]
    payload: HttpResponseBodyPayload


class HttpResponseTrailersPayload(UseCaseModel):
    trailers: HeaderPairs = Field(default_factory=list)


class HttpResponseTrailersEvent(EventBase):
    type: Literal["http_response_trailers"]
    payload: HttpResponseTrailersPayload


class HttpResponseCompletedEvent(EventBase):
    type: Literal["http_response_completed"]
    payload: dict[str, Any] = Field(default_factory=dict)


class WebSocketStartedPayload(UseCaseModel):
    url: str = Field(min_length=1)
    http_version: str = Field(min_length=1)
    headers: HeaderPairs = Field(default_factory=list)


class WebSocketStartedEvent(EventBase):
    type: Literal["websocket_started"]
    payload: WebSocketStartedPayload


class WebSocketMessagePayload(UseCaseModel):
    direction: WebSocketDirection
    payload_type: WebSocketPayloadType
    payload_text: str | None = None
    blob_id: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)

    @field_validator("blob_id")
    @classmethod
    def _validate_blob_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_ulid(value)

    @model_validator(mode="after")
    def _validate_payload(self) -> "WebSocketMessagePayload":
        if self.payload_type == WebSocketPayloadType.TEXT:
            if self.payload_text is None:
                raise ValueError("text websocket messages require payload_text")
            if self.blob_id is not None or self.size_bytes is not None:
                raise ValueError("text websocket messages must not set blob metadata")
        else:
            if self.blob_id is None or self.size_bytes is None:
                raise ValueError(
                    "binary websocket messages require blob_id and size_bytes"
                )
            if self.payload_text is not None:
                raise ValueError("binary websocket messages must not set payload_text")
        return self


class WebSocketMessageEvent(EventBase):
    type: Literal["websocket_message"]
    payload: WebSocketMessagePayload


class WebSocketEndedPayload(UseCaseModel):
    close_code: int | None = None


class WebSocketEndedEvent(EventBase):
    type: Literal["websocket_ended"]
    payload: WebSocketEndedPayload


class RequestErrorPayload(UseCaseModel):
    message: str = Field(min_length=1)


class RequestErrorEvent(EventBase):
    type: Literal["request_error"]
    payload: RequestErrorPayload


CaptureEvent = Annotated[
    HttpRequestStartedEvent
    | HttpRequestBodyEvent
    | HttpRequestTrailersEvent
    | HttpRequestCompletedEvent
    | HttpResponseStartedEvent
    | HttpResponseBodyEvent
    | HttpResponseTrailersEvent
    | HttpResponseCompletedEvent
    | WebSocketStartedEvent
    | WebSocketMessageEvent
    | WebSocketEndedEvent
    | RequestErrorEvent,
    Field(discriminator="type"),
]

capture_event_adapter = TypeAdapter(CaptureEvent)


class EventIngestResult(UseCaseModel):
    request_id: str
    event_index: int
    status: EventStatus
    detail: str | None = None


def canonical_event_json(event: CaptureEvent) -> str:
    return normalize_json(event.model_dump(mode="json"))


def event_blob_id(event: CaptureEvent) -> str | None:
    blob_id = getattr(event.payload, "blob_id", None)
    return blob_id if isinstance(blob_id, str) else None


class IngestEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[CaptureEvent]


class IngestEventsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[EventIngestResult]


class IngestEventsUseCase:
    def __init__(
        self,
        db: SqliteDatabase,
        request_repository: RequestRepository,
        event_repository: EventRepository,
        deferred_event_repository: DeferredEventRepository,
        blob_repository: BlobRepository,
        tombstone_repository: TombstoneRepository,
        filter_runner: FilterRunner,
        app_container: object,
    ) -> None:
        self._db = db
        self._requests = request_repository
        self._events = event_repository
        self._deferred = deferred_event_repository
        self._blobs = blob_repository
        self._tombstones = tombstone_repository
        self._filters = filter_runner
        self._app_container = app_container

    def execute(self, data: IngestEventsInput) -> IngestEventsOutput:
        results: list[EventIngestResult] = []
        for raw_event in data.events:
            current_request = self._requests.get_detail(raw_event.request_id)
            try:
                filtered = self._filters.apply(
                    self._app_container, raw_event, current_request
                )
            except Exception as exc:
                results.append(
                    EventIngestResult(
                        request_id=raw_event.request_id,
                        event_index=raw_event.event_index,
                        status=EventStatus.REJECTED,
                        detail=f"filter execution failed: {exc}",
                    )
                )
                continue

            if filtered is None:
                results.append(
                    EventIngestResult(
                        request_id=raw_event.request_id,
                        event_index=raw_event.event_index,
                        status=EventStatus.DROPPED,
                    )
                )
                continue

            try:
                event = capture_event_adapter.validate_python(
                    filtered.model_dump(mode="python")
                )
                results.append(self._ingest_event(event))
            except Exception as exc:
                results.append(
                    EventIngestResult(
                        request_id=filtered.request_id,
                        event_index=filtered.event_index,
                        status=EventStatus.REJECTED,
                        detail=str(exc),
                    )
                )
        return IngestEventsOutput(results=results)

    def _ingest_event(self, event: CaptureEvent) -> EventIngestResult:
        if self._tombstones.has_active(event.request_id):
            raise ServerConflictError(
                f"request {event.request_id} was explicitly deleted"
            )

        blob_id = event_blob_id(event)
        if blob_id is not None and not self._blobs.exists(blob_id):
            raise ServerConflictError(f"blob {blob_id} does not exist")

        event_json = canonical_event_json(event)
        existing_event_json = self._events.get_event_json(
            event.request_id, event.event_index
        )
        if existing_event_json is not None:
            if existing_event_json == event_json:
                return EventIngestResult(
                    request_id=event.request_id,
                    event_index=event.event_index,
                    status=EventStatus.IGNORED,
                )
            raise ServerConflictError(
                f"conflicting duplicate event for {event.request_id} at index {event.event_index}"
            )

        state = self._requests.get_state(event.request_id)
        trace_id, hop_nodes = parse_hop_chain(event.hop_chain)
        if state is not None:
            if (
                state["trace_id"] != trace_id
                or state["hop_chain"] != event.hop_chain
                or state["node_name"] != event.node_name
            ):
                raise ServerConflictError(
                    "event context conflicts with the existing request record"
                )

        next_expected = 0 if state is None else state["last_event_index"] + 1
        if event.event_index > next_expected:
            return self._defer_event(event, event_json, blob_id)
        if event.event_index < next_expected:
            raise ServerConflictError(
                f"event_index {event.event_index} is older than next expected index {next_expected}"
            )

        now = to_rfc3339(utc_now())
        record = (
            self._default_record(event, trace_id=trace_id, hop_nodes=hop_nodes, now=now)
            if state is None
            else state
        )
        self._apply_event(record, event, now)

        with self._db.transaction():
            self._requests.save_state(record)
            self._events.insert_applied_event(
                request_id=event.request_id,
                event_index=event.event_index,
                event_type=event.type,
                node_name=event.node_name,
                hop_chain=event.hop_chain,
                blob_id=blob_id,
                accepted_at=now,
                event_json=event_json,
            )
            self._deferred.delete(event.request_id, event.event_index)

        self._drain_deferred(event.request_id)
        return EventIngestResult(
            request_id=event.request_id,
            event_index=event.event_index,
            status=EventStatus.ACCEPTED,
        )

    def _defer_event(
        self, event: CaptureEvent, event_json: str, blob_id: str | None
    ) -> EventIngestResult:
        existing = self._deferred.get_event_json(event.request_id, event.event_index)
        if existing is not None and existing != event_json:
            raise ServerConflictError(
                f"conflicting deferred event for {event.request_id} at index {event.event_index}"
            )
        self._deferred.upsert(
            request_id=event.request_id,
            event_index=event.event_index,
            blob_id=blob_id,
            deferred_at=to_rfc3339(utc_now()),
            event_json=event_json,
        )
        return EventIngestResult(
            request_id=event.request_id,
            event_index=event.event_index,
            status=EventStatus.DEFERRED,
        )

    def _drain_deferred(self, request_id: str) -> None:
        while True:
            state = self._requests.get_state(request_id)
            if state is None:
                return
            next_index = state["last_event_index"] + 1
            event_json = self._deferred.get_event_json(request_id, next_index)
            if event_json is None:
                return
            event = capture_event_adapter.validate_python(json.loads(event_json))
            try:
                result = self._ingest_event(event)
            except ServerConflictError:
                with self._db.transaction():
                    self._deferred.delete(request_id, next_index)
                return
            if result.status != EventStatus.ACCEPTED:
                return

    def _apply_event(
        self, record: dict[str, Any], event: CaptureEvent, now: str
    ) -> None:
        if record["complete"]:
            raise ServerConflictError(f"request {event.request_id} is already terminal")

        payload = (
            event.payload.model_dump(mode="python")
            if hasattr(event.payload, "model_dump")
            else {}
        )
        record["updated_at"] = now
        record["last_event_index"] = event.event_index

        if event.type == "http_request_started":
            self._set_once_or_same(record, "request_method", payload["method"])
            self._set_once_or_same(record, "request_url", payload["url"])
            self._set_once_or_same(
                record, "request_http_version", payload["http_version"]
            )
            self._set_once_or_same(record, "request_headers", payload["headers"])
            record["request_started"] = True
        elif event.type == "http_request_body":
            if record["request_body_complete"]:
                raise ServerConflictError("request body is already complete")
            record["request_body_size"] += payload["size_bytes"]
            record["request_body_complete"] = bool(payload["complete"])
        elif event.type == "http_request_trailers":
            self._set_once_or_same(record, "request_trailers", payload["trailers"])
        elif event.type == "http_request_completed":
            record["request_complete"] = True
        elif event.type == "http_response_started":
            self._set_once_or_same(
                record, "response_status_code", payload["status_code"]
            )
            self._set_once_or_same(
                record, "response_http_version", payload["http_version"]
            )
            self._set_once_or_same(record, "response_headers", payload["headers"])
            record["response_started"] = True
        elif event.type == "http_response_body":
            if record["response_body_complete"]:
                raise ServerConflictError("response body is already complete")
            record["response_body_size"] += payload["size_bytes"]
            record["response_body_complete"] = bool(payload["complete"])
        elif event.type == "http_response_trailers":
            self._set_once_or_same(record, "response_trailers", payload["trailers"])
        elif event.type == "http_response_completed":
            record["response_complete"] = True
        elif event.type == "websocket_started":
            self._set_once_or_same(record, "websocket_url", payload["url"])
            self._set_once_or_same(
                record, "websocket_http_version", payload["http_version"]
            )
            self._set_once_or_same(record, "websocket_headers", payload["headers"])
            record["websocket_seen"] = True
            record["websocket_open"] = True
        elif event.type == "websocket_message":
            message = {
                "event_index": event.event_index,
                "captured_at": now,
                "direction": payload["direction"],
                "payload_type": payload["payload_type"],
                "blob_id": payload.get("blob_id"),
                "size_bytes": payload.get("size_bytes"),
                "payload_text": payload.get("payload_text"),
            }
            record["websocket_seen"] = True
            record["websocket_open"] = True
            record["websocket_messages"].append(message)
        elif event.type == "websocket_ended":
            record["websocket_seen"] = True
            record["websocket_open"] = False
            record["websocket_ended"] = True
            record["websocket_close_code"] = payload["close_code"]
        elif event.type == "request_error":
            record["error"] = payload["message"]
        else:
            raise ServerConflictError(f"unsupported event type {event.type}")

        if record["error"] is not None:
            record["complete"] = True
        elif record["websocket_ended"]:
            record["complete"] = True
        elif record["request_complete"] and record["response_complete"]:
            record["complete"] = True

        if record["complete"] and record["completed_at"] is None:
            record["completed_at"] = now

    def _default_record(
        self,
        event: CaptureEvent,
        *,
        trace_id: str,
        hop_nodes: tuple[str, ...],
        now: str,
    ) -> dict[str, Any]:
        return {
            "request_id": event.request_id,
            "trace_id": trace_id,
            "hop_chain": event.hop_chain,
            "hop_nodes": list(hop_nodes),
            "node_name": event.node_name,
            "captured_at": now,
            "updated_at": now,
            "completed_at": None,
            "last_event_index": -1,
            "request_method": None,
            "request_url": None,
            "request_http_version": None,
            "request_headers": [],
            "request_trailers": [],
            "request_body_size": 0,
            "request_body_blob_id": None,
            "request_body_complete": False,
            "request_started": False,
            "request_complete": False,
            "response_status_code": None,
            "response_http_version": None,
            "response_headers": [],
            "response_trailers": [],
            "response_body_size": 0,
            "response_body_blob_id": None,
            "response_body_complete": False,
            "response_started": False,
            "response_complete": False,
            "websocket_open": False,
            "websocket_seen": False,
            "websocket_ended": False,
            "websocket_url": None,
            "websocket_http_version": None,
            "websocket_headers": [],
            "websocket_close_code": None,
            "websocket_messages": [],
            "error": None,
            "complete": False,
        }

    def _set_once_or_same(self, record: dict[str, Any], key: str, value: Any) -> None:
        current = record[key]
        if current in (None, [], ()):
            record[key] = value
            return
        if current != value:
            raise ServerConflictError(
                f"{key} conflicts with the existing request state"
            )
