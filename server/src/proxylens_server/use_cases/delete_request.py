from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, ConfigDict

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


class DeleteRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    deleted: bool


class DeleteRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str


class DeleteRequestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: DeleteRequestResult


class DeleteRequestUseCase:
    def __init__(
        self,
        db: SqliteDatabase,
        request_repository: RequestRepository,
        event_repository: EventRepository,
        deferred_event_repository: DeferredEventRepository,
        blob_repository: BlobRepository,
        tombstone_repository: TombstoneRepository,
        tombstone_ttl: timedelta,
    ) -> None:
        self._db = db
        self._requests = request_repository
        self._events = event_repository
        self._deferred = deferred_event_repository
        self._blobs = blob_repository
        self._tombstones = tombstone_repository
        self._tombstone_ttl = tombstone_ttl

    def execute(self, data: DeleteRequestInput) -> DeleteRequestOutput:
        with self._db.transaction():
            state = self._requests.get_state(data.request_id)
            if state is None:
                return DeleteRequestOutput(
                    result=DeleteRequestResult(
                        request_id=data.request_id, deleted=False
                    )
                )

            candidate_blob_ids = self._events.list_blob_ids_for_request(
                data.request_id
            ) | self._deferred.list_blob_ids_for_request(data.request_id)
            for blob_id in (
                state["request_body_blob_id"],
                state["response_body_blob_id"],
            ):
                if blob_id is not None:
                    candidate_blob_ids.add(blob_id)

            self._events.delete_for_request(data.request_id)
            self._deferred.delete_for_request(data.request_id)
            self._requests.delete(data.request_id)
            self._tombstones.upsert(data.request_id, self._tombstone_ttl)

        for blob_id in candidate_blob_ids:
            if self._blobs.count_references(blob_id) == 0:
                self._blobs.delete_blob(blob_id)

        return DeleteRequestOutput(
            result=DeleteRequestResult(request_id=data.request_id, deleted=True)
        )
