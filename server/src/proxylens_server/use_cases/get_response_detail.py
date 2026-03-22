from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from proxylens_server.common.http import HeaderPairs
from proxylens_server.domain.errors import ServerNotFoundError
from proxylens_server.infra.persistence.repositories.requests import (
    RequestDetailRecord,
    RequestRepository,
)


class ResponseDetail(BaseModel):
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
    def from_record(cls, request: RequestDetailRecord) -> "ResponseDetail":
        return cls(
            request_id=request.request_id,
            response_status_code=request.response_status_code,
            response_http_version=request.response_http_version,
            response_headers=request.response_headers or [],
            response_trailers=request.response_trailers or [],
            response_body_size=request.response_body_size,
            response_body_blob_id=request.response_body_blob_id,
            response_body_complete=request.response_body_complete,
            response_started=request.response_started,
            response_complete=request.response_complete,
        )


class GetResponseDetailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str


class GetResponseDetailOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: ResponseDetail


class GetResponseDetailUseCase:
    def __init__(self, request_repository: RequestRepository) -> None:
        self._request_repository = request_repository

    def execute(self, data: GetResponseDetailInput) -> GetResponseDetailOutput:
        request = self._request_repository.get_detail(data.request_id)
        if request is None:
            raise ServerNotFoundError(f"request {data.request_id} was not found")
        return GetResponseDetailOutput(response=ResponseDetail.from_record(request))
