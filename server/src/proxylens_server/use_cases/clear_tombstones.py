from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from proxylens_server.infra.persistence.repositories.tombstones import (
    TombstoneRepository,
)


class ClearTombstonesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cleared_count: int


class ClearTombstonesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expired_only: bool = False


class ClearTombstonesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: ClearTombstonesResult


class ClearTombstonesUseCase:
    def __init__(self, tombstone_repository: TombstoneRepository) -> None:
        self._tombstone_repository = tombstone_repository

    def execute(self, data: ClearTombstonesInput) -> ClearTombstonesOutput:
        cleared_count = (
            self._tombstone_repository.clear_expired()
            if data.expired_only
            else self._tombstone_repository.clear()
        )
        return ClearTombstonesOutput(
            result=ClearTombstonesResult(cleared_count=cleared_count)
        )
