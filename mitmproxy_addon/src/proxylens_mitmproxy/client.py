from __future__ import annotations

import json
import os
from typing import Any, BinaryIO, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from proxylens_mitmproxy.models import CaptureEvent, serialize_event

DEFAULT_PROXYLENS_SERVER_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PROXYLENS_SERVER_BASE_URL_ENV_VAR = "PROXYLENS_SERVER_BASE_URL"
_SUCCESSFUL_EVENT_STATUSES = {"accepted", "ignored", "deferred", "dropped"}


class ProxyLensServerClientError(RuntimeError):
    pass


class SupportsProxyLensServerClient(Protocol):
    def upload_blob(self, blob_id: str, data: bytes | BinaryIO) -> None: ...

    def submit_event(self, event: CaptureEvent) -> None: ...


class ProxyLensServerClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        base_url_env_var: str = DEFAULT_PROXYLENS_SERVER_BASE_URL_ENV_VAR,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = resolve_server_base_url(
            base_url=base_url,
            env_var=base_url_env_var,
        )
        self.timeout_seconds = timeout_seconds

    def upload_blob(self, blob_id: str, data: bytes | BinaryIO) -> None:
        payload = data if isinstance(data, bytes) else data.read()
        request = Request(
            self._url(f"blobs/{blob_id}"),
            data=payload,
            method="PUT",
            headers={"Content-Type": "application/octet-stream"},
        )
        response = self._json_request(request)
        if response.get("blob_id") != blob_id:
            raise ProxyLensServerClientError(
                f"server blob response did not echo blob_id {blob_id}"
            )

    def submit_event(self, event: CaptureEvent) -> None:
        serialized_event = serialize_event(event)
        request = Request(
            self._url("events"),
            data=json.dumps({"events": [serialized_event]}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        response = self._json_request(request, allow_http_error_json=True)
        results = response.get("results")
        if not isinstance(results, list) or len(results) != 1:
            raise ProxyLensServerClientError(
                "server event response must contain one result"
            )
        result = cast(dict[str, Any], results[0])
        status = result.get("status")
        if status not in _SUCCESSFUL_EVENT_STATUSES:
            raise ProxyLensServerClientError(
                f"server rejected event {serialized_event['request_id']}:{serialized_event['event_index']}: "
                f"{result.get('detail') or status}"
            )

    def _url(self, path: str) -> str:
        return urljoin(f"{self.base_url}/", path)

    def _json_request(
        self,
        request: Request,
        *,
        allow_http_error_json: bool = False,
    ) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read()
        except HTTPError as exc:
            payload = exc.read()
            if allow_http_error_json:
                try:
                    decoded = json.loads(payload.decode("utf-8"))
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, dict):
                    return cast(dict[str, Any], decoded)
            detail = payload.decode("utf-8", errors="replace")
            raise ProxyLensServerClientError(
                f"server request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise ProxyLensServerClientError(
                f"server request failed: {exc.reason}"
            ) from exc

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ProxyLensServerClientError(
                "server response was not valid JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise ProxyLensServerClientError("server response must be a JSON object")
        return cast(dict[str, Any], decoded)


class RecordingProxyLensServerClient:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.uploads: list[dict[str, object]] = []
        self.operations: list[dict[str, object]] = []

    def upload_blob(self, blob_id: str, data: bytes | BinaryIO) -> None:
        blob = data if isinstance(data, bytes) else data.read()
        record = {"blob_id": blob_id, "data": blob}
        self.uploads.append(record)
        self.operations.append({"kind": "upload_blob", **record})

    def submit_event(self, event: CaptureEvent) -> None:
        record = serialize_event(event)
        self.events.append(record)
        self.operations.append({"kind": "submit_event", "event": record})


def resolve_server_base_url(
    *,
    base_url: str | None = None,
    env_var: str = DEFAULT_PROXYLENS_SERVER_BASE_URL_ENV_VAR,
) -> str:
    resolved = (
        base_url or os.environ.get(env_var) or DEFAULT_PROXYLENS_SERVER_BASE_URL
    )
    return resolved.rstrip("/")
