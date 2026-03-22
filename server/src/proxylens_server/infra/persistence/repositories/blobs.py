from __future__ import annotations

import hashlib
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from proxylens_server.domain.errors import ServerConflictError
from proxylens_server.common.identity import validate_ulid
from proxylens_server.common.time import to_rfc3339, utc_now
from proxylens_server.infra.persistence.sqlite import SqliteDatabase


@dataclass(frozen=True)
class BlobUploadRecord:
    blob_id: str
    status: str


class BlobRepository(Protocol):
    def save_uploaded_blob(
        self, blob_id: str, data: bytes, content_type: str | None = None
    ) -> BlobUploadRecord: ...

    def exists(self, blob_id: str) -> bool: ...

    def blob_path(self, blob_id: str) -> Path: ...

    def read_bytes(self, blob_id: str) -> bytes: ...

    def list_blob_ids(self) -> list[str]: ...

    def count_references(self, blob_id: str) -> int: ...

    def delete_blob(self, blob_id: str) -> bool: ...

    def delete_all(self) -> None: ...


class SqliteBlobRepository:
    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db

    def save_uploaded_blob(
        self, blob_id: str, data: bytes, content_type: str | None = None
    ) -> BlobUploadRecord:
        validate_ulid(blob_id)
        digest = hashlib.sha256(data).hexdigest()
        now = to_rfc3339(utc_now())
        target = self.blob_path(blob_id)
        temp_path = self._db.blob_dir / f".{blob_id}.{uuid4().hex}.tmp"
        row = self._db.fetchone(
            "SELECT blob_id, size_bytes, sha256 FROM blobs WHERE blob_id = ?",
            (blob_id,),
        )
        if row is not None:
            if row["size_bytes"] == len(data) and row["sha256"] == digest:
                return BlobUploadRecord(blob_id=blob_id, status="accepted")
            raise ServerConflictError(
                f"blob {blob_id} already exists with different content"
            )

        temp_path.write_bytes(data)
        os.replace(temp_path, target)
        self._db.execute(
            """
            INSERT INTO blobs (blob_id, size_bytes, content_type, sha256, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (blob_id, len(data), content_type, digest, now),
        )
        return BlobUploadRecord(blob_id=blob_id, status="accepted")

    def exists(self, blob_id: str) -> bool:
        row = self._db.fetchone("SELECT 1 FROM blobs WHERE blob_id = ?", (blob_id,))
        return row is not None

    def blob_path(self, blob_id: str) -> Path:
        return self._db.blob_path(blob_id)

    def read_bytes(self, blob_id: str) -> bytes:
        return self.blob_path(blob_id).read_bytes()

    def list_blob_ids(self) -> list[str]:
        rows = self._db.fetchall("SELECT blob_id FROM blobs")
        return [row["blob_id"] for row in rows]

    def count_references(self, blob_id: str) -> int:
        row = self._db.fetchone(
            """
            SELECT
                (SELECT COUNT(*) FROM events WHERE blob_id = ?) +
                (SELECT COUNT(*) FROM deferred_events WHERE blob_id = ?) +
                (SELECT COUNT(*) FROM requests WHERE request_body_blob_id = ? OR response_body_blob_id = ?) AS ref_count
            """,
            (blob_id, blob_id, blob_id, blob_id),
        )
        return 0 if row is None else row["ref_count"]

    def delete_blob(self, blob_id: str) -> bool:
        rowcount = self._db.execute_rowcount(
            "DELETE FROM blobs WHERE blob_id = ?", (blob_id,)
        )
        with suppress(FileNotFoundError):
            self.blob_path(blob_id).unlink()
        return rowcount > 0

    def delete_all(self) -> None:
        self._db.execute("DELETE FROM blobs")
        for path in self._db.blob_dir.iterdir():
            if path.is_file():
                path.unlink()
