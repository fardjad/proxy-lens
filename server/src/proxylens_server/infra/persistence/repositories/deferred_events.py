from __future__ import annotations

from typing import Protocol

from proxylens_server.infra.persistence.sqlite import SqliteDatabase


class DeferredEventRepository(Protocol):
    def get_event_json(self, request_id: str, event_index: int) -> str | None: ...

    def upsert(
        self,
        *,
        request_id: str,
        event_index: int,
        blob_id: str | None,
        deferred_at: str,
        event_json: str,
    ) -> None: ...

    def delete(self, request_id: str, event_index: int) -> None: ...

    def delete_for_request(self, request_id: str) -> None: ...

    def list_blob_ids_for_request(self, request_id: str) -> set[str]: ...

    def delete_all(self) -> None: ...


class SqliteDeferredEventRepository:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def get_event_json(self, request_id: str, event_index: int) -> str | None:
        row = self._db.fetchone(
            """
            SELECT event_json
            FROM deferred_events
            WHERE request_id = ? AND event_index = ?
            """,
            (request_id, event_index),
        )
        return None if row is None else row["event_json"]

    def upsert(
        self,
        *,
        request_id: str,
        event_index: int,
        blob_id: str | None,
        deferred_at: str,
        event_json: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO deferred_events (request_id, event_index, blob_id, deferred_at, event_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(request_id, event_index) DO UPDATE SET
                blob_id = excluded.blob_id,
                deferred_at = excluded.deferred_at,
                event_json = excluded.event_json
            """,
            (request_id, event_index, blob_id, deferred_at, event_json),
        )

    def delete(self, request_id: str, event_index: int) -> None:
        self._db.execute(
            "DELETE FROM deferred_events WHERE request_id = ? AND event_index = ?",
            (request_id, event_index),
        )

    def delete_for_request(self, request_id: str) -> None:
        self._db.execute(
            "DELETE FROM deferred_events WHERE request_id = ?", (request_id,)
        )

    def list_blob_ids_for_request(self, request_id: str) -> set[str]:
        rows = self._db.fetchall(
            """
            SELECT blob_id
            FROM deferred_events
            WHERE request_id = ? AND blob_id IS NOT NULL
            """,
            (request_id,),
        )
        return {row["blob_id"] for row in rows}

    def delete_all(self) -> None:
        self._db.execute("DELETE FROM deferred_events")
