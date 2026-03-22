from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from proxylens_server.bootstrap import AppContainer
from proxylens_server.use_cases.ingest_events import (
    EventStatus,
    IngestEventsInput,
    IngestEventsUseCase,
)

from .dtos import EventBatchRequestDTO, EventBatchResponseDTO


def create_router(get_container: Callable[[], AppContainer]) -> APIRouter:
    router = APIRouter()

    def get_use_case(
        container: AppContainer = Depends(get_container),
    ) -> IngestEventsUseCase:
        return container.ingest_events_use_case

    @router.post("/events", response_model=EventBatchResponseDTO)
    def post_events(
        payload: EventBatchRequestDTO,
        use_case: IngestEventsUseCase = Depends(get_use_case),
    ) -> JSONResponse:
        response = EventBatchResponseDTO.from_output(
            use_case.execute(IngestEventsInput(events=payload.events))
        )
        status_code = (
            409
            if any(result.status == EventStatus.REJECTED for result in response.results)
            else 200
        )
        return JSONResponse(
            status_code=status_code, content=response.model_dump(mode="json")
        )

    return router
