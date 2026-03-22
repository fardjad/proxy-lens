from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.domain.errors import ServerNotFoundError
from proxylens_server.infra.persistence.repositories.events import (
    EventRepository,
    PersistedEventRecord,
)


class PersistedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    event_index: int
    accepted_at: str
    event: dict

    @classmethod
    def from_record(cls, record: PersistedEventRecord) -> "PersistedEvent":
        return cls(
            request_id=record.request_id,
            event_index=record.event_index,
            accepted_at=record.accepted_at,
            event=record.event,
        )


class GetRequestEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str


class GetRequestEventsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[PersistedEvent]


class GetRequestEventsUseCase:
    def __init__(self, event_repository: EventRepository) -> None:
        self._event_repository = event_repository

    def execute(self, data: GetRequestEventsInput) -> GetRequestEventsOutput:
        events = self._event_repository.list_events(data.request_id)
        if not events:
            raise ServerNotFoundError(f"request {data.request_id} was not found")
        return GetRequestEventsOutput(
            events=[PersistedEvent.from_record(event) for event in events]
        )
