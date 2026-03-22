from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from proxylens_server.bootstrap import AppContainer
from proxylens_server.domain.errors import ServerNotFoundError
from proxylens_server.use_cases.delete_request import (
    DeleteRequestInput,
    DeleteRequestUseCase,
)
from proxylens_server.use_cases.delete_requests import (
    DeleteRequestsInput,
    DeleteRequestsUseCase,
)
from proxylens_server.use_cases.get_request import GetRequestInput, GetRequestUseCase
from proxylens_server.use_cases.get_request_body import (
    GetRequestBodyInput,
    GetRequestBodyUseCase,
)
from proxylens_server.use_cases.get_request_events import (
    GetRequestEventsInput,
    GetRequestEventsUseCase,
)
from proxylens_server.use_cases.get_response_body import (
    GetResponseBodyInput,
    GetResponseBodyUseCase,
)
from proxylens_server.use_cases.get_response_detail import (
    GetResponseDetailInput,
    GetResponseDetailUseCase,
)
from proxylens_server.use_cases.list_requests import (
    ListRequestsInput,
    ListRequestsUseCase,
)
from proxylens_server.use_cases.request_histogram import (
    HistogramBucket,
    RequestHistogramInput,
    RequestHistogramUseCase,
)

from .dtos import (
    HistogramResponseDTO,
    PersistedEventDTO,
    RequestDetailResponseDTO,
    RequestSummaryListResponseDTO,
    ResponseDetailDTO,
)


def create_router(get_container: Callable[[], AppContainer]) -> APIRouter:
    router = APIRouter()

    def list_requests_uc(
        container: AppContainer = Depends(get_container),
    ) -> ListRequestsUseCase:
        return container.list_requests_use_case

    def delete_requests_uc(
        container: AppContainer = Depends(get_container),
    ) -> DeleteRequestsUseCase:
        return container.delete_requests_use_case

    def histogram_uc(
        container: AppContainer = Depends(get_container),
    ) -> RequestHistogramUseCase:
        return container.request_histogram_use_case

    def get_request_uc(
        container: AppContainer = Depends(get_container),
    ) -> GetRequestUseCase:
        return container.get_request_use_case

    def delete_request_uc(
        container: AppContainer = Depends(get_container),
    ) -> DeleteRequestUseCase:
        return container.delete_request_use_case

    def get_events_uc(
        container: AppContainer = Depends(get_container),
    ) -> GetRequestEventsUseCase:
        return container.get_request_events_use_case

    def get_request_body_uc(
        container: AppContainer = Depends(get_container),
    ) -> GetRequestBodyUseCase:
        return container.get_request_body_use_case

    def get_response_uc(
        container: AppContainer = Depends(get_container),
    ) -> GetResponseDetailUseCase:
        return container.get_response_detail_use_case

    def get_response_body_uc(
        container: AppContainer = Depends(get_container),
    ) -> GetResponseBodyUseCase:
        return container.get_response_body_use_case

    @router.get("/requests", response_model=RequestSummaryListResponseDTO)
    def get_requests(
        use_case: ListRequestsUseCase = Depends(list_requests_uc),
        captured_after: str | None = None,
        captured_before: str | None = None,
        trace_ids: Annotated[list[str] | None, Query()] = None,
        request_ids: Annotated[list[str] | None, Query()] = None,
        node_names: Annotated[list[str] | None, Query()] = None,
        methods: Annotated[list[str] | None, Query()] = None,
        url_contains: str | None = None,
        status_codes: Annotated[list[int] | None, Query()] = None,
        complete: bool | None = None,
        request_complete: bool | None = None,
        response_complete: bool | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> RequestSummaryListResponseDTO:
        output = use_case.execute(
            ListRequestsInput(
                captured_after=captured_after,
                captured_before=captured_before,
                trace_ids=trace_ids,
                request_ids=request_ids,
                node_names=node_names,
                methods=methods,
                url_contains=url_contains,
                status_codes=status_codes,
                complete=complete,
                request_complete=request_complete,
                response_complete=response_complete,
                limit=limit,
                offset=offset,
            )
        )
        return RequestSummaryListResponseDTO.from_output(output.requests)

    @router.delete("/requests", status_code=202)
    def delete_requests(
        use_case: DeleteRequestsUseCase = Depends(delete_requests_uc),
        captured_after: str | None = None,
        captured_before: str | None = None,
        trace_ids: Annotated[list[str] | None, Query()] = None,
        request_ids: Annotated[list[str] | None, Query()] = None,
        node_names: Annotated[list[str] | None, Query()] = None,
        methods: Annotated[list[str] | None, Query()] = None,
        url_contains: str | None = None,
        status_codes: Annotated[list[int] | None, Query()] = None,
        complete: bool | None = None,
        request_complete: bool | None = None,
        response_complete: bool | None = None,
        limit: int = Query(default=1000, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
    ) -> Response:
        try:
            use_case.execute(
                DeleteRequestsInput(
                    captured_after=captured_after,
                    captured_before=captured_before,
                    trace_ids=trace_ids,
                    request_ids=request_ids,
                    node_names=node_names,
                    methods=methods,
                    url_contains=url_contains,
                    status_codes=status_codes,
                    complete=complete,
                    request_complete=request_complete,
                    response_complete=response_complete,
                    limit=limit,
                    offset=offset,
                )
            )
        except ServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=202)

    @router.get("/requests/histogram", response_model=HistogramResponseDTO)
    def get_histogram(
        use_case: RequestHistogramUseCase = Depends(histogram_uc),
        captured_after: str | None = None,
        captured_before: str | None = None,
        bucket: HistogramBucket | None = None,
        max_points: int = Query(default=200, ge=1, le=10000),
    ) -> HistogramResponseDTO:
        return HistogramResponseDTO.from_output(
            use_case.execute(
                RequestHistogramInput(
                    captured_after=captured_after,
                    captured_before=captured_before,
                    bucket=bucket,
                    max_points=max_points,
                )
            ).histogram
        )

    @router.get("/requests/{request_id}", response_model=RequestDetailResponseDTO)
    def get_request_detail(
        request_id: str,
        use_case: GetRequestUseCase = Depends(get_request_uc),
    ) -> RequestDetailResponseDTO:
        try:
            output = use_case.execute(GetRequestInput(request_id=request_id))
        except ServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RequestDetailResponseDTO.from_output(output.request)

    @router.delete("/requests/{request_id}", status_code=202)
    def delete_request(
        request_id: str,
        use_case: DeleteRequestUseCase = Depends(delete_request_uc),
    ) -> Response:
        result = use_case.execute(DeleteRequestInput(request_id=request_id)).result
        if not result.deleted:
            raise HTTPException(
                status_code=404, detail=f"request {request_id} was not found"
            )
        return Response(status_code=202)

    @router.get("/requests/{request_id}/events", response_model=list[PersistedEventDTO])
    def get_request_events(
        request_id: str,
        use_case: GetRequestEventsUseCase = Depends(get_events_uc),
    ) -> list[PersistedEventDTO]:
        try:
            output = use_case.execute(GetRequestEventsInput(request_id=request_id))
        except ServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [PersistedEventDTO.from_output(event) for event in output.events]

    @router.get("/requests/{request_id}/body")
    def get_request_body(
        request_id: str,
        use_case: GetRequestBodyUseCase = Depends(get_request_body_uc),
    ) -> Response:
        try:
            output = use_case.execute(GetRequestBodyInput(request_id=request_id))
        except ServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=output.body,
            media_type=output.content_type or "application/octet-stream",
        )

    @router.get("/requests/{request_id}/response", response_model=ResponseDetailDTO)
    def get_response(
        request_id: str,
        use_case: GetResponseDetailUseCase = Depends(get_response_uc),
    ) -> ResponseDetailDTO:
        try:
            output = use_case.execute(GetResponseDetailInput(request_id=request_id))
        except ServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ResponseDetailDTO.from_output(output.response)

    @router.get("/requests/{request_id}/response/body")
    def get_response_body(
        request_id: str,
        use_case: GetResponseBodyUseCase = Depends(get_response_body_uc),
    ) -> Response:
        try:
            output = use_case.execute(GetResponseBodyInput(request_id=request_id))
        except ServerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=output.body,
            media_type=output.content_type or "application/octet-stream",
        )

    return router
