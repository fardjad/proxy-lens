from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from proxylens_server.common.http import HeaderPairs
from proxylens_server.infra.persistence.repositories.events import (
    BlobChunkRecord,
    EventRepository,
)
from proxylens_server.infra.persistence.sqlite import SqliteDatabase


@dataclass(frozen=True)
class RequestSummaryRecord:
    request_id: str
    trace_id: str
    node_name: str
    hop_chain: str
    hop_nodes: tuple[str, ...]
    captured_at: str
    updated_at: str
    completed_at: str | None = None
    request_method: str | None = None
    request_url: str | None = None
    request_http_version: str | None = None
    request_headers: HeaderPairs | None = None
    response_status_code: int | None = None
    response_http_version: str | None = None
    response_headers: HeaderPairs | None = None
    request_complete: bool = False
    response_complete: bool = False
    websocket_open: bool = False
    error: str | None = None
    complete: bool = False


@dataclass(frozen=True)
class RequestDetailRecord(RequestSummaryRecord):
    request_trailers: HeaderPairs | None = None
    request_body_size: int = 0
    request_body_blob_id: str | None = None
    request_body_complete: bool = False
    response_trailers: HeaderPairs | None = None
    response_body_size: int = 0
    response_body_blob_id: str | None = None
    response_body_complete: bool = False
    response_started: bool = False
    request_started: bool = False
    websocket_url: str | None = None
    websocket_http_version: str | None = None
    websocket_headers: HeaderPairs | None = None
    websocket_close_code: int | None = None
    websocket_messages: list[dict[str, Any]] | None = None
    request_body_chunks: list[BlobChunkRecord] | None = None
    response_body_chunks: list[BlobChunkRecord] | None = None


class RequestRepository(Protocol):
    def get_state(self, request_id: str) -> dict[str, Any] | None: ...

    def save_state(self, record: dict[str, Any]) -> None: ...

    def get_detail(self, request_id: str) -> RequestDetailRecord | None: ...

    def list_summaries(self) -> list[RequestSummaryRecord]: ...

    def delete(self, request_id: str) -> bool: ...

    def list_completed_ids(self) -> list[str]: ...

    def delete_all(self) -> None: ...


class SqliteRequestRepository:
    def __init__(self, db: SqliteDatabase, event_repository: EventRepository) -> None:
        self._db = db
        self._events = event_repository

    def get_state(self, request_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            "SELECT * FROM requests WHERE request_id = ?",
            (request_id,),
        )
        return None if row is None else self._row_to_record_dict(row)

    def save_state(self, record: dict[str, Any]) -> None:
        self._db.execute(
            """
            INSERT INTO requests (
                request_id, trace_id, hop_chain, hop_nodes_json, node_name, captured_at, updated_at,
                completed_at, last_event_index, request_method, request_url, request_http_version,
                request_headers_json, request_trailers_json, request_body_size, request_body_blob_id,
                request_body_complete, request_started, request_complete, response_status_code,
                response_http_version, response_headers_json, response_trailers_json, response_body_size,
                response_body_blob_id, response_body_complete, response_started, response_complete,
                websocket_open, websocket_seen, websocket_ended, websocket_url, websocket_http_version,
                websocket_headers_json, websocket_close_code, websocket_messages_json, error, complete
            ) VALUES (
                :request_id, :trace_id, :hop_chain, :hop_nodes_json, :node_name, :captured_at, :updated_at,
                :completed_at, :last_event_index, :request_method, :request_url, :request_http_version,
                :request_headers_json, :request_trailers_json, :request_body_size, :request_body_blob_id,
                :request_body_complete, :request_started, :request_complete, :response_status_code,
                :response_http_version, :response_headers_json, :response_trailers_json, :response_body_size,
                :response_body_blob_id, :response_body_complete, :response_started, :response_complete,
                :websocket_open, :websocket_seen, :websocket_ended, :websocket_url, :websocket_http_version,
                :websocket_headers_json, :websocket_close_code, :websocket_messages_json, :error, :complete
            )
            ON CONFLICT(request_id) DO UPDATE SET
                trace_id = excluded.trace_id,
                hop_chain = excluded.hop_chain,
                hop_nodes_json = excluded.hop_nodes_json,
                node_name = excluded.node_name,
                captured_at = excluded.captured_at,
                updated_at = excluded.updated_at,
                completed_at = excluded.completed_at,
                last_event_index = excluded.last_event_index,
                request_method = excluded.request_method,
                request_url = excluded.request_url,
                request_http_version = excluded.request_http_version,
                request_headers_json = excluded.request_headers_json,
                request_trailers_json = excluded.request_trailers_json,
                request_body_size = excluded.request_body_size,
                request_body_blob_id = excluded.request_body_blob_id,
                request_body_complete = excluded.request_body_complete,
                request_started = excluded.request_started,
                request_complete = excluded.request_complete,
                response_status_code = excluded.response_status_code,
                response_http_version = excluded.response_http_version,
                response_headers_json = excluded.response_headers_json,
                response_trailers_json = excluded.response_trailers_json,
                response_body_size = excluded.response_body_size,
                response_body_blob_id = excluded.response_body_blob_id,
                response_body_complete = excluded.response_body_complete,
                response_started = excluded.response_started,
                response_complete = excluded.response_complete,
                websocket_open = excluded.websocket_open,
                websocket_seen = excluded.websocket_seen,
                websocket_ended = excluded.websocket_ended,
                websocket_url = excluded.websocket_url,
                websocket_http_version = excluded.websocket_http_version,
                websocket_headers_json = excluded.websocket_headers_json,
                websocket_close_code = excluded.websocket_close_code,
                websocket_messages_json = excluded.websocket_messages_json,
                error = excluded.error,
                complete = excluded.complete
            """,
            {
                "request_id": record["request_id"],
                "trace_id": record["trace_id"],
                "hop_chain": record["hop_chain"],
                "hop_nodes_json": json.dumps(record["hop_nodes"]),
                "node_name": record["node_name"],
                "captured_at": record["captured_at"],
                "updated_at": record["updated_at"],
                "completed_at": record["completed_at"],
                "last_event_index": record["last_event_index"],
                "request_method": record["request_method"],
                "request_url": record["request_url"],
                "request_http_version": record["request_http_version"],
                "request_headers_json": json.dumps(record["request_headers"]),
                "request_trailers_json": json.dumps(record["request_trailers"]),
                "request_body_size": record["request_body_size"],
                "request_body_blob_id": record["request_body_blob_id"],
                "request_body_complete": int(record["request_body_complete"]),
                "request_started": int(record["request_started"]),
                "request_complete": int(record["request_complete"]),
                "response_status_code": record["response_status_code"],
                "response_http_version": record["response_http_version"],
                "response_headers_json": json.dumps(record["response_headers"]),
                "response_trailers_json": json.dumps(record["response_trailers"]),
                "response_body_size": record["response_body_size"],
                "response_body_blob_id": record["response_body_blob_id"],
                "response_body_complete": int(record["response_body_complete"]),
                "response_started": int(record["response_started"]),
                "response_complete": int(record["response_complete"]),
                "websocket_open": int(record["websocket_open"]),
                "websocket_seen": int(record["websocket_seen"]),
                "websocket_ended": int(record["websocket_ended"]),
                "websocket_url": record["websocket_url"],
                "websocket_http_version": record["websocket_http_version"],
                "websocket_headers_json": json.dumps(record["websocket_headers"]),
                "websocket_close_code": record["websocket_close_code"],
                "websocket_messages_json": json.dumps(record["websocket_messages"]),
                "error": record["error"],
                "complete": int(record["complete"]),
            },
        )

    def get_detail(self, request_id: str) -> RequestDetailRecord | None:
        row = self._db.fetchone(
            "SELECT * FROM requests WHERE request_id = ?",
            (request_id,),
        )
        return None if row is None else self._row_to_detail(row)

    def list_summaries(self) -> list[RequestSummaryRecord]:
        rows = self._db.fetchall("SELECT * FROM requests ORDER BY captured_at DESC")
        return [self._row_to_summary(row) for row in rows]

    def delete(self, request_id: str) -> bool:
        rowcount = self._db.execute_rowcount(
            "DELETE FROM requests WHERE request_id = ?",
            (request_id,),
        )
        return rowcount > 0

    def list_completed_ids(self) -> list[str]:
        rows = self._db.fetchall("SELECT request_id FROM requests WHERE complete = 1")
        return [row["request_id"] for row in rows]

    def delete_all(self) -> None:
        self._db.execute("DELETE FROM requests")

    def _row_to_record_dict(self, row: Any) -> dict[str, Any]:
        return {
            "request_id": row["request_id"],
            "trace_id": row["trace_id"],
            "hop_chain": row["hop_chain"],
            "hop_nodes": json.loads(row["hop_nodes_json"]),
            "node_name": row["node_name"],
            "captured_at": row["captured_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
            "last_event_index": row["last_event_index"],
            "request_method": row["request_method"],
            "request_url": row["request_url"],
            "request_http_version": row["request_http_version"],
            "request_headers": json.loads(row["request_headers_json"]),
            "request_trailers": json.loads(row["request_trailers_json"]),
            "request_body_size": row["request_body_size"],
            "request_body_blob_id": row["request_body_blob_id"],
            "request_body_complete": bool(row["request_body_complete"]),
            "request_started": bool(row["request_started"]),
            "request_complete": bool(row["request_complete"]),
            "response_status_code": row["response_status_code"],
            "response_http_version": row["response_http_version"],
            "response_headers": json.loads(row["response_headers_json"]),
            "response_trailers": json.loads(row["response_trailers_json"]),
            "response_body_size": row["response_body_size"],
            "response_body_blob_id": row["response_body_blob_id"],
            "response_body_complete": bool(row["response_body_complete"]),
            "response_started": bool(row["response_started"]),
            "response_complete": bool(row["response_complete"]),
            "websocket_open": bool(row["websocket_open"]),
            "websocket_seen": bool(row["websocket_seen"]),
            "websocket_ended": bool(row["websocket_ended"]),
            "websocket_url": row["websocket_url"],
            "websocket_http_version": row["websocket_http_version"],
            "websocket_headers": json.loads(row["websocket_headers_json"]),
            "websocket_close_code": row["websocket_close_code"],
            "websocket_messages": json.loads(row["websocket_messages_json"]),
            "error": row["error"],
            "complete": bool(row["complete"]),
        }

    def _row_to_summary(self, row: Any) -> RequestSummaryRecord:
        return RequestSummaryRecord(
            request_id=row["request_id"],
            trace_id=row["trace_id"],
            node_name=row["node_name"],
            hop_chain=row["hop_chain"],
            hop_nodes=tuple(json.loads(row["hop_nodes_json"])),
            captured_at=row["captured_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            request_method=row["request_method"],
            request_url=row["request_url"],
            request_http_version=row["request_http_version"],
            request_headers=json.loads(row["request_headers_json"]),
            response_status_code=row["response_status_code"],
            response_http_version=row["response_http_version"],
            response_headers=json.loads(row["response_headers_json"]),
            request_complete=bool(row["request_complete"]),
            response_complete=bool(row["response_complete"]),
            websocket_open=bool(row["websocket_open"]),
            error=row["error"],
            complete=bool(row["complete"]),
        )

    def _row_to_detail(self, row: Any) -> RequestDetailRecord:
        request_id = row["request_id"]
        summary = self._row_to_summary(row)
        return RequestDetailRecord(
            **summary.__dict__,
            request_trailers=json.loads(row["request_trailers_json"]),
            request_body_size=row["request_body_size"],
            request_body_blob_id=row["request_body_blob_id"],
            request_body_complete=bool(row["request_body_complete"]),
            response_trailers=json.loads(row["response_trailers_json"]),
            response_body_size=row["response_body_size"],
            response_body_blob_id=row["response_body_blob_id"],
            response_body_complete=bool(row["response_body_complete"]),
            response_started=bool(row["response_started"]),
            request_started=bool(row["request_started"]),
            websocket_url=row["websocket_url"],
            websocket_http_version=row["websocket_http_version"],
            websocket_headers=json.loads(row["websocket_headers_json"]),
            websocket_close_code=row["websocket_close_code"],
            websocket_messages=json.loads(row["websocket_messages_json"]),
            request_body_chunks=self._events.body_chunks(
                request_id, "http_request_body"
            ),
            response_body_chunks=self._events.body_chunks(
                request_id, "http_response_body"
            ),
        )
