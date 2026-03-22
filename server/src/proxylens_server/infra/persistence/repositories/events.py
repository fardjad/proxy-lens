from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from proxylens_server.infra.persistence.sqlite import SqliteDatabase


@dataclass(frozen=True)
class BlobChunkRecord:
    blob_id: str
    size_bytes: int
    content_type: str | None = None


@dataclass(frozen=True)
class PersistedEventRecord:
    request_id: str
    event_index: int
    accepted_at: str
    event: dict


class EventRepository(Protocol):
    def get_event_json(self, request_id: str, event_index: int) -> str | None: ...

    def insert_applied_event(
        self,
        *,
        request_id: str,
        event_index: int,
        event_type: str,
        node_name: str,
        hop_chain: str,
        blob_id: str | None,
        accepted_at: str,
        event_json: str,
    ) -> None: ...

    def delete_event(self, request_id: str, event_index: int) -> None: ...

    def list_events(self, request_id: str) -> list[PersistedEventRecord]: ...

    def list_blob_ids_for_request(self, request_id: str) -> set[str]: ...

    def delete_for_request(self, request_id: str) -> None: ...

    def delete_all(self) -> None: ...

    def body_chunks(
        self, request_id: str, event_type: str
    ) -> list[BlobChunkRecord]: ...

    def body_blob_ids(self, request_id: str, event_type: str) -> list[str]: ...


class SqliteEventRepository:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def get_event_json(self, request_id: str, event_index: int) -> str | None:
        row = self._db.fetchone(
            "SELECT event_json FROM events WHERE request_id = ? AND event_index = ?",
            (request_id, event_index),
        )
        return None if row is None else row["event_json"]

    def insert_applied_event(
        self,
        *,
        request_id: str,
        event_index: int,
        event_type: str,
        node_name: str,
        hop_chain: str,
        blob_id: str | None,
        accepted_at: str,
        event_json: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO events (request_id, event_index, type, node_name, hop_chain, blob_id, accepted_at, event_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                event_index,
                event_type,
                node_name,
                hop_chain,
                blob_id,
                accepted_at,
                event_json,
            ),
        )

    def delete_event(self, request_id: str, event_index: int) -> None:
        self._db.execute(
            "DELETE FROM events WHERE request_id = ? AND event_index = ?",
            (request_id, event_index),
        )

    def list_events(self, request_id: str) -> list[PersistedEventRecord]:
        rows = self._db.fetchall(
            """
            SELECT request_id, event_index, accepted_at, event_json
            FROM events
            WHERE request_id = ?
            ORDER BY event_index
            """,
            (request_id,),
        )
        return [
            PersistedEventRecord(
                request_id=row["request_id"],
                event_index=row["event_index"],
                accepted_at=row["accepted_at"],
                event=json.loads(row["event_json"]),
            )
            for row in rows
        ]

    def list_blob_ids_for_request(self, request_id: str) -> set[str]:
        rows = self._db.fetchall(
            "SELECT blob_id FROM events WHERE request_id = ? AND blob_id IS NOT NULL",
            (request_id,),
        )
        return {row["blob_id"] for row in rows}

    def delete_for_request(self, request_id: str) -> None:
        self._db.execute("DELETE FROM events WHERE request_id = ?", (request_id,))

    def delete_all(self) -> None:
        self._db.execute("DELETE FROM events")

    def body_chunks(self, request_id: str, event_type: str) -> list[BlobChunkRecord]:
        rows = self._db.fetchall(
            """
            SELECT e.blob_id, b.size_bytes, b.content_type
            FROM events e
            JOIN blobs b ON b.blob_id = e.blob_id
            WHERE e.request_id = ? AND e.type = ?
            ORDER BY e.event_index
            """,
            (request_id, event_type),
        )
        return [
            BlobChunkRecord(
                blob_id=row["blob_id"],
                size_bytes=row["size_bytes"],
                content_type=row["content_type"],
            )
            for row in rows
            if row["blob_id"] is not None
        ]

    def body_blob_ids(self, request_id: str, event_type: str) -> list[str]:
        rows = self._db.fetchall(
            """
            SELECT blob_id
            FROM events
            WHERE request_id = ? AND type = ?
            ORDER BY event_index
            """,
            (request_id, event_type),
        )
        return [row["blob_id"] for row in rows if row["blob_id"] is not None]
