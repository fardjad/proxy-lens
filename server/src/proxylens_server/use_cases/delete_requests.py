from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.domain.errors import ServerNotFoundError
from proxylens_server.use_cases.delete_request import (
    DeleteRequestResult,
    DeleteRequestInput,
    DeleteRequestUseCase,
)
from proxylens_server.use_cases.list_requests import (
    ListRequestsInput,
    ListRequestsUseCase,
)


class DeleteRequestsInput(BaseModel):
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


class DeleteRequestsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[DeleteRequestResult]


class DeleteRequestsUseCase:
    def __init__(
        self,
        list_requests_use_case: ListRequestsUseCase,
        delete_request_use_case: DeleteRequestUseCase,
    ) -> None:
        self._list_requests_use_case = list_requests_use_case
        self._delete_request_use_case = delete_request_use_case

    def execute(self, data: DeleteRequestsInput) -> DeleteRequestsOutput:
        requests = self._list_requests_use_case.execute(
            ListRequestsInput(**data.model_dump())
        ).requests
        if not requests:
            raise ServerNotFoundError("no matching requests were found")
        return DeleteRequestsOutput(
            results=[
                self._delete_request_use_case.execute(
                    DeleteRequestInput(request_id=request.request_id)
                ).result
                for request in requests
            ]
        )
