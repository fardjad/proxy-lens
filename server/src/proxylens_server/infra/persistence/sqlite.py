from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import sqlite3
from pathlib import Path
from typing import Iterator

from proxylens_server.config import ServerConfig


class SqliteDatabase:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.data_dir = config.data_dir
        self.db_path = self.data_dir / "proxylens_server.db"
        self.blob_dir = self.data_dir / "blobs"
        self._active_connection: ContextVar[sqlite3.Connection | None] = ContextVar(
            "sqlite_active_connection", default=None
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def close(self) -> None:
        return None

    def blob_path(self, blob_id: str) -> Path:
        return self.blob_dir / blob_id

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        active = self._active_connection.get()
        if active is not None:
            yield active
            return

        connection = self._connect()
        token = self._active_connection.set(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self._active_connection.reset(token)
            connection.close()

    def fetchone(
        self, query: str, params: tuple[object, ...] = ()
    ) -> sqlite3.Row | None:
        return self._with_connection(
            lambda connection: connection.execute(query, params).fetchone()
        )

    def fetchall(
        self, query: str, params: tuple[object, ...] = ()
    ) -> list[sqlite3.Row]:
        return self._with_connection(
            lambda connection: connection.execute(query, params).fetchall()
        )

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        self._with_connection(
            lambda connection: connection.execute(query, params),
            commit_when_unscoped=True,
        )

    def execute_rowcount(self, query: str, params: tuple[object, ...] = ()) -> int:
        return self._with_connection(
            lambda connection: connection.execute(query, params).rowcount,
            commit_when_unscoped=True,
        )

    def executescript(self, script: str) -> None:
        self._with_connection(
            lambda connection: connection.executescript(script),
            commit_when_unscoped=True,
        )

    def _initialize_schema(self) -> None:
        self.executescript(
            """
            CREATE TABLE IF NOT EXISTS blobs (
                blob_id TEXT PRIMARY KEY,
                size_bytes INTEGER NOT NULL,
                content_type TEXT,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL,
                hop_chain TEXT NOT NULL,
                hop_nodes_json TEXT NOT NULL,
                node_name TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                last_event_index INTEGER NOT NULL DEFAULT -1,
                request_method TEXT,
                request_url TEXT,
                request_http_version TEXT,
                request_headers_json TEXT NOT NULL DEFAULT '[]',
                request_trailers_json TEXT NOT NULL DEFAULT '[]',
                request_body_size INTEGER NOT NULL DEFAULT 0,
                request_body_blob_id TEXT,
                request_body_complete INTEGER NOT NULL DEFAULT 0,
                request_started INTEGER NOT NULL DEFAULT 0,
                request_complete INTEGER NOT NULL DEFAULT 0,
                response_status_code INTEGER,
                response_http_version TEXT,
                response_headers_json TEXT NOT NULL DEFAULT '[]',
                response_trailers_json TEXT NOT NULL DEFAULT '[]',
                response_body_size INTEGER NOT NULL DEFAULT 0,
                response_body_blob_id TEXT,
                response_body_complete INTEGER NOT NULL DEFAULT 0,
                response_started INTEGER NOT NULL DEFAULT 0,
                response_complete INTEGER NOT NULL DEFAULT 0,
                websocket_open INTEGER NOT NULL DEFAULT 0,
                websocket_seen INTEGER NOT NULL DEFAULT 0,
                websocket_ended INTEGER NOT NULL DEFAULT 0,
                websocket_url TEXT,
                websocket_http_version TEXT,
                websocket_headers_json TEXT NOT NULL DEFAULT '[]',
                websocket_close_code INTEGER,
                websocket_messages_json TEXT NOT NULL DEFAULT '[]',
                error TEXT,
                complete INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS events (
                request_id TEXT NOT NULL,
                event_index INTEGER NOT NULL,
                type TEXT NOT NULL,
                node_name TEXT NOT NULL,
                hop_chain TEXT NOT NULL,
                blob_id TEXT,
                accepted_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                PRIMARY KEY (request_id, event_index),
                FOREIGN KEY (request_id) REFERENCES requests(request_id) ON DELETE CASCADE,
                FOREIGN KEY (blob_id) REFERENCES blobs(blob_id)
            );

            CREATE TABLE IF NOT EXISTS deferred_events (
                request_id TEXT NOT NULL,
                event_index INTEGER NOT NULL,
                blob_id TEXT,
                deferred_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                PRIMARY KEY (request_id, event_index),
                FOREIGN KEY (blob_id) REFERENCES blobs(blob_id)
            );

            CREATE TABLE IF NOT EXISTS deleted_requests (
                request_id TEXT PRIMARY KEY,
                deleted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        self._configure_connection(connection)
        return connection

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA cache_size = 10000")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA mmap_size = 268435456")

    def _with_connection(self, operation, *, commit_when_unscoped: bool = False):
        active = self._active_connection.get()
        if active is not None:
            return operation(active)

        connection = self._connect()
        try:
            result = operation(connection)
            if commit_when_unscoped:
                connection.commit()
            return result
        except Exception:
            if commit_when_unscoped:
                connection.rollback()
            raise
        finally:
            connection.close()
