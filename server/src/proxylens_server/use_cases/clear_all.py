from __future__ import annotations

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


class ClearAllResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared: bool


class ClearAllInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClearAllOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: ClearAllResult


class ClearAllUseCase:
    def __init__(
        self,
        db: SqliteDatabase,
        request_repository: RequestRepository,
        event_repository: EventRepository,
        deferred_event_repository: DeferredEventRepository,
        tombstone_repository: TombstoneRepository,
        blob_repository: BlobRepository,
    ) -> None:
        self._db = db
        self._requests = request_repository
        self._events = event_repository
        self._deferred = deferred_event_repository
        self._tombstones = tombstone_repository
        self._blobs = blob_repository

    def execute(self, _: ClearAllInput) -> ClearAllOutput:
        with self._db.transaction():
            self._events.delete_all()
            self._deferred.delete_all()
            self._requests.delete_all()
            self._tombstones.delete_all()
            self._blobs.delete_all()
        return ClearAllOutput(result=ClearAllResult(cleared=True))
