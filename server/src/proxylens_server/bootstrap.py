from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from proxylens_server.config import ServerConfig
from proxylens_server.infra.filters.script_runner import FilterRunner
from proxylens_server.infra.persistence.repositories.blobs import SqliteBlobRepository
from proxylens_server.infra.persistence.repositories.deferred_events import (
    SqliteDeferredEventRepository,
)
from proxylens_server.infra.persistence.repositories.events import (
    SqliteEventRepository,
)
from proxylens_server.infra.persistence.repositories.requests import (
    SqliteRequestRepository,
)
from proxylens_server.infra.persistence.repositories.tombstones import (
    SqliteTombstoneRepository,
)
from proxylens_server.infra.persistence.sqlite import SqliteDatabase
from proxylens_server.use_cases.clear_all import ClearAllUseCase
from proxylens_server.use_cases.clear_tombstones import ClearTombstonesUseCase
from proxylens_server.use_cases.delete_request import (
    DeleteRequestUseCase,
)
from proxylens_server.use_cases.delete_requests import DeleteRequestsUseCase
from proxylens_server.use_cases.get_request import GetRequestUseCase
from proxylens_server.use_cases.get_request_body import GetRequestBodyUseCase
from proxylens_server.use_cases.get_request_events import GetRequestEventsUseCase
from proxylens_server.use_cases.get_response_body import GetResponseBodyUseCase
from proxylens_server.use_cases.get_response_detail import GetResponseDetailUseCase
from proxylens_server.use_cases.ingest_events import IngestEventsUseCase
from proxylens_server.use_cases.list_requests import ListRequestsUseCase
from proxylens_server.use_cases.request_histogram import RequestHistogramUseCase
from proxylens_server.use_cases.upload_blob import UploadBlobUseCase
from proxylens_server.use_cases.vacuum import VacuumUseCase


@dataclass
class AppContainer:
    config: ServerConfig
    db: SqliteDatabase
    filter_runner: FilterRunner
    blob_repository: SqliteBlobRepository
    event_repository: SqliteEventRepository
    deferred_event_repository: SqliteDeferredEventRepository
    tombstone_repository: SqliteTombstoneRepository
    request_repository: SqliteRequestRepository
    upload_blob_use_case: UploadBlobUseCase
    list_requests_use_case: ListRequestsUseCase
    request_histogram_use_case: RequestHistogramUseCase
    get_request_use_case: GetRequestUseCase
    get_request_events_use_case: GetRequestEventsUseCase
    get_request_body_use_case: GetRequestBodyUseCase
    get_response_detail_use_case: GetResponseDetailUseCase
    get_response_body_use_case: GetResponseBodyUseCase
    clear_tombstones_use_case: ClearTombstonesUseCase
    delete_request_use_case: DeleteRequestUseCase
    delete_requests_use_case: DeleteRequestsUseCase
    clear_all_use_case: ClearAllUseCase
    vacuum_use_case: VacuumUseCase
    ingest_events_use_case: IngestEventsUseCase

    @property
    def data_dir(self) -> Path:
        return self.db.data_dir

    @property
    def db_path(self) -> Path:
        return self.db.db_path

    @property
    def blob_dir(self) -> Path:
        return self.db.blob_dir

    def close(self) -> None:
        self.db.close()


def create_container(config: ServerConfig) -> AppContainer:
    db = SqliteDatabase(config)

    filter_runner = FilterRunner(config.filter_script)
    filter_runner.load()

    blob_repository = SqliteBlobRepository(db)
    event_repository = SqliteEventRepository(db)
    deferred_event_repository = SqliteDeferredEventRepository(db)
    tombstone_repository = SqliteTombstoneRepository(db)
    request_repository = SqliteRequestRepository(db, event_repository)

    upload_blob_use_case = UploadBlobUseCase(blob_repository)
    list_requests_use_case = ListRequestsUseCase(request_repository)
    request_histogram_use_case = RequestHistogramUseCase(request_repository)
    get_request_use_case = GetRequestUseCase(request_repository)
    get_request_events_use_case = GetRequestEventsUseCase(event_repository)
    get_request_body_use_case = GetRequestBodyUseCase(
        request_repository,
        event_repository,
        blob_repository,
    )
    get_response_detail_use_case = GetResponseDetailUseCase(request_repository)
    get_response_body_use_case = GetResponseBodyUseCase(
        request_repository,
        event_repository,
        blob_repository,
    )
    clear_tombstones_use_case = ClearTombstonesUseCase(tombstone_repository)
    delete_request_use_case = DeleteRequestUseCase(
        db,
        request_repository,
        event_repository,
        deferred_event_repository,
        blob_repository,
        tombstone_repository,
        config.tombstone_ttl,
    )
    delete_requests_use_case = DeleteRequestsUseCase(
        list_requests_use_case,
        delete_request_use_case,
    )
    clear_all_use_case = ClearAllUseCase(
        db,
        request_repository,
        event_repository,
        deferred_event_repository,
        tombstone_repository,
        blob_repository,
    )
    vacuum_use_case = VacuumUseCase(
        request_repository,
        delete_request_use_case,
        clear_tombstones_use_case,
        blob_repository,
    )
    container = AppContainer(
        config=config,
        db=db,
        filter_runner=filter_runner,
        blob_repository=blob_repository,
        event_repository=event_repository,
        deferred_event_repository=deferred_event_repository,
        tombstone_repository=tombstone_repository,
        request_repository=request_repository,
        upload_blob_use_case=upload_blob_use_case,
        list_requests_use_case=list_requests_use_case,
        request_histogram_use_case=request_histogram_use_case,
        get_request_use_case=get_request_use_case,
        get_request_events_use_case=get_request_events_use_case,
        get_request_body_use_case=get_request_body_use_case,
        get_response_detail_use_case=get_response_detail_use_case,
        get_response_body_use_case=get_response_body_use_case,
        clear_tombstones_use_case=clear_tombstones_use_case,
        delete_request_use_case=delete_request_use_case,
        delete_requests_use_case=delete_requests_use_case,
        clear_all_use_case=clear_all_use_case,
        vacuum_use_case=vacuum_use_case,
        ingest_events_use_case=cast(IngestEventsUseCase, None),
    )
    container.ingest_events_use_case = IngestEventsUseCase(
        db,
        request_repository,
        event_repository,
        deferred_event_repository,
        blob_repository,
        tombstone_repository,
        filter_runner,
        container,
    )
    return container
