from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.domain.errors import ServerNotFoundError
from proxylens_server.common.http import header_value
from proxylens_server.infra.persistence.repositories.blobs import BlobRepository
from proxylens_server.infra.persistence.repositories.events import EventRepository
from proxylens_server.infra.persistence.repositories.requests import RequestRepository


class GetResponseBodyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str


class GetResponseBodyOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: bytes
    content_type: str | None = None


class GetResponseBodyUseCase:
    def __init__(
        self,
        request_repository: RequestRepository,
        event_repository: EventRepository,
        blob_repository: BlobRepository,
    ) -> None:
        self._request_repository = request_repository
        self._event_repository = event_repository
        self._blob_repository = blob_repository

    def execute(self, data: GetResponseBodyInput) -> GetResponseBodyOutput:
        request = self._request_repository.get_detail(data.request_id)
        if request is None:
            raise ServerNotFoundError(f"request {data.request_id} was not found")
        blob_ids = self._event_repository.body_blob_ids(
            data.request_id, "http_response_body"
        )
        if not blob_ids:
            raise ServerNotFoundError(
                f"response body for {data.request_id} was not found"
            )
        body = b"".join(
            self._blob_repository.read_bytes(blob_id) for blob_id in blob_ids
        )
        return GetResponseBodyOutput(
            body=body,
            content_type=header_value(request.response_headers, "content-type"),
        )
