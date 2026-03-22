from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

HeaderPairs: TypeAlias = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CaptureContext:
    event_index: int
    request_id: str
    node_name: str
    hop_chain: str


@dataclass(frozen=True, slots=True)
class HttpRequestStartedEvent:
    context: CaptureContext
    method: str
    url: str
    http_version: str
    headers: HeaderPairs
    type: str = "http_request_started"


@dataclass(frozen=True, slots=True)
class HttpRequestBodyEvent:
    context: CaptureContext
    blob_id: str
    size_bytes: int
    complete: bool
    type: str = "http_request_body"


@dataclass(frozen=True, slots=True)
class HttpRequestTrailersEvent:
    context: CaptureContext
    trailers: HeaderPairs
    type: str = "http_request_trailers"


@dataclass(frozen=True, slots=True)
class HttpRequestCompletedEvent:
    context: CaptureContext
    type: str = "http_request_completed"


@dataclass(frozen=True, slots=True)
class HttpResponseStartedEvent:
    context: CaptureContext
    status_code: int
    http_version: str
    headers: HeaderPairs
    type: str = "http_response_started"


@dataclass(frozen=True, slots=True)
class HttpResponseBodyEvent:
    context: CaptureContext
    blob_id: str
    size_bytes: int
    complete: bool
    type: str = "http_response_body"


@dataclass(frozen=True, slots=True)
class HttpResponseTrailersEvent:
    context: CaptureContext
    trailers: HeaderPairs
    type: str = "http_response_trailers"


@dataclass(frozen=True, slots=True)
class HttpResponseCompletedEvent:
    context: CaptureContext
    type: str = "http_response_completed"


@dataclass(frozen=True, slots=True)
class WebSocketStartedEvent:
    context: CaptureContext
    url: str
    http_version: str
    headers: HeaderPairs
    type: str = "websocket_started"


@dataclass(frozen=True, slots=True)
class WebSocketMessageEvent:
    context: CaptureContext
    direction: Literal["client_to_server", "server_to_client"]
    payload_type: Literal["text", "binary"]
    payload_text: str | None = None
    blob_id: str | None = None
    size_bytes: int | None = None
    type: str = "websocket_message"


@dataclass(frozen=True, slots=True)
class WebSocketEndedEvent:
    context: CaptureContext
    close_code: int | None
    type: str = "websocket_ended"


@dataclass(frozen=True, slots=True)
class RequestErrorEvent:
    context: CaptureContext
    message: str
    type: str = "request_error"


CaptureEvent: TypeAlias = (
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
    | RequestErrorEvent
)


def serialize_event(event: CaptureEvent) -> dict[str, object]:
    payload: dict[str, object]
    match event:
        case HttpRequestStartedEvent():
            payload = {
                "method": event.method,
                "url": event.url,
                "http_version": event.http_version,
                "headers": list(event.headers),
            }
        case HttpRequestBodyEvent():
            payload = {
                "blob_id": event.blob_id,
                "size_bytes": event.size_bytes,
                "complete": event.complete,
            }
        case HttpRequestTrailersEvent():
            payload = {"trailers": list(event.trailers)}
        case HttpRequestCompletedEvent():
            payload = {}
        case HttpResponseStartedEvent():
            payload = {
                "status_code": event.status_code,
                "http_version": event.http_version,
                "headers": list(event.headers),
            }
        case HttpResponseBodyEvent():
            payload = {
                "blob_id": event.blob_id,
                "size_bytes": event.size_bytes,
                "complete": event.complete,
            }
        case HttpResponseTrailersEvent():
            payload = {"trailers": list(event.trailers)}
        case HttpResponseCompletedEvent():
            payload = {}
        case WebSocketStartedEvent():
            payload = {
                "url": event.url,
                "http_version": event.http_version,
                "headers": list(event.headers),
            }
        case WebSocketMessageEvent():
            payload = {
                "direction": event.direction,
                "payload_type": event.payload_type,
                "payload_text": event.payload_text,
                "blob_id": event.blob_id,
                "size_bytes": event.size_bytes,
            }
        case WebSocketEndedEvent():
            payload = {"close_code": event.close_code}
        case RequestErrorEvent():
            payload = {"message": event.message}
        case _:
            raise TypeError(f"unsupported event type: {type(event)!r}")
    return {
        "type": event.type,
        "request_id": event.context.request_id,
        "event_index": event.context.event_index,
        "node_name": event.context.node_name,
        "hop_chain": event.context.hop_chain,
        "payload": payload,
    }
