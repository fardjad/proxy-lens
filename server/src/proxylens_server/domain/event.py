from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    HTTP_REQUEST_STARTED = "http_request_started"
    HTTP_REQUEST_BODY = "http_request_body"
    HTTP_REQUEST_TRAILERS = "http_request_trailers"
    HTTP_REQUEST_COMPLETED = "http_request_completed"
    HTTP_RESPONSE_STARTED = "http_response_started"
    HTTP_RESPONSE_BODY = "http_response_body"
    HTTP_RESPONSE_TRAILERS = "http_response_trailers"
    HTTP_RESPONSE_COMPLETED = "http_response_completed"
    WEBSOCKET_STARTED = "websocket_started"
    WEBSOCKET_MESSAGE = "websocket_message"
    WEBSOCKET_ENDED = "websocket_ended"
    REQUEST_ERROR = "request_error"


@dataclass(frozen=True, slots=True)
class Event:
    request_id: str
    event_index: int
    event_type: EventType
    payload: Mapping[str, Any]

    @property
    def event_id(self) -> str:
        return f"{self.request_id}:{self.event_index}"
