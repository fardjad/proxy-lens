from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.use_cases.ingest_events import CaptureEvent, IngestEventsOutput


class EventBatchRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[CaptureEvent]


class EventIngestResultDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    event_index: int
    status: str
    detail: str | None = None


class EventBatchResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[EventIngestResultDTO]

    @classmethod
    def from_output(cls, output: IngestEventsOutput) -> "EventBatchResponseDTO":
        return cls(
            results=[
                EventIngestResultDTO(**result.model_dump(mode="json"))
                for result in output.results
            ]
        )
