from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from proxylens_server.common.time import parse_rfc3339, to_rfc3339, utc_now
from proxylens_server.infra.persistence.sqlite import SqliteDatabase


class TombstoneRepository(Protocol):
    def has_active(self, request_id: str) -> bool: ...

    def upsert(self, request_id: str, ttl: timedelta) -> None: ...

    def clear(self) -> int: ...

    def clear_expired(self) -> int: ...

    def delete_all(self) -> None: ...


class SqliteTombstoneRepository:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def has_active(self, request_id: str) -> bool:
        row = self._db.fetchone(
            "SELECT expires_at FROM deleted_requests WHERE request_id = ?",
            (request_id,),
        )
        if row is None:
            return False
        if parse_rfc3339(row["expires_at"]) <= utc_now():
            self._db.execute(
                "DELETE FROM deleted_requests WHERE request_id = ?",
                (request_id,),
            )
            return False
        return True

    def upsert(self, request_id: str, ttl: timedelta) -> None:
        now = utc_now()
        self._db.execute(
            """
            INSERT INTO deleted_requests (request_id, deleted_at, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(request_id) DO UPDATE SET
                deleted_at = excluded.deleted_at,
                expires_at = excluded.expires_at
            """,
            (request_id, to_rfc3339(now), to_rfc3339(now + ttl)),
        )

    def clear(self) -> int:
        return self._db.execute_rowcount("DELETE FROM deleted_requests")

    def clear_expired(self) -> int:
        return self._db.execute_rowcount(
            "DELETE FROM deleted_requests WHERE expires_at <= ?",
            (to_rfc3339(utc_now()),),
        )

    def delete_all(self) -> None:
        self._db.execute("DELETE FROM deleted_requests")
