from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.infra.persistence.repositories.blobs import BlobRepository
from proxylens_server.infra.persistence.repositories.requests import RequestRepository
from proxylens_server.use_cases.clear_tombstones import (
    ClearTombstonesInput,
    ClearTombstonesUseCase,
)
from proxylens_server.use_cases.delete_request import (
    DeleteRequestInput,
    DeleteRequestUseCase,
)


class VacuumResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_request_count: int
    cleared_tombstone_count: int
    removed_blob_count: int


class VacuumInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VacuumOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: VacuumResult


class VacuumUseCase:
    def __init__(
        self,
        request_repository: RequestRepository,
        delete_request_use_case: DeleteRequestUseCase,
        clear_tombstones_use_case: ClearTombstonesUseCase,
        blob_repository: BlobRepository,
    ) -> None:
        self._requests = request_repository
        self._delete_request_use_case = delete_request_use_case
        self._clear_tombstones_use_case = clear_tombstones_use_case
        self._blobs = blob_repository

    def execute(self, _: VacuumInput) -> VacuumOutput:
        completed_ids = self._requests.list_completed_ids()
        deleted_results = [
            self._delete_request_use_case.execute(
                DeleteRequestInput(request_id=request_id)
            ).result
            for request_id in completed_ids
        ]
        cleared = self._clear_tombstones_use_case.execute(
            ClearTombstonesInput(expired_only=True)
        ).result
        removed_blob_count = 0
        for blob_id in self._blobs.list_blob_ids():
            if self._blobs.count_references(blob_id) == 0 and self._blobs.delete_blob(
                blob_id
            ):
                removed_blob_count += 1
        return VacuumOutput(
            result=VacuumResult(
                deleted_request_count=sum(
                    1 for result in deleted_results if result.deleted
                ),
                cleared_tombstone_count=cleared.cleared_count,
                removed_blob_count=removed_blob_count,
            )
        )
