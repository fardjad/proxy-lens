from __future__ import annotations

import os
from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from typing import Any, cast

from mitmproxy import http

from proxylens_mitmproxy.client import (
    DEFAULT_PROXYLENS_SERVER_BASE_URL_ENV_VAR,
    ProxyLensServerClient,
    SupportsProxyLensServerClient,
)
from proxylens_mitmproxy.models import (
    CaptureContext,
    HeaderPairs,
    HttpRequestBodyEvent,
    HttpRequestCompletedEvent,
    HttpRequestStartedEvent,
    HttpRequestTrailersEvent,
    HttpResponseBodyEvent,
    HttpResponseCompletedEvent,
    HttpResponseStartedEvent,
    HttpResponseTrailersEvent,
    RequestErrorEvent,
    WebSocketEndedEvent,
    WebSocketMessageEvent,
    WebSocketStartedEvent,
)
from proxylens_mitmproxy.propagation import (
    DEFAULT_NODE_NAME_ENV_VAR,
    PROXYLENS_HOP_CHAIN_HEADER,
    PROXYLENS_REQUEST_ID_HEADER,
    build_propagation_state,
    generate_span_id,
    generate_trace_id,
    generate_ulid,
    resolve_node_name,
    synchronize_trace_context_headers,
)

_STATE_KEY = "proxylens_state"
_REQUEST = "request"
_RESPONSE = "response"
DEFAULT_MAX_CONCURRENT_REQUESTS_PER_HOST_ENV_VAR = (
    "PROXYLENS_MAX_CONCURRENT_REQUESTS_PER_HOST"
)

type FlowFilter = Callable[[http.HTTPFlow], bool]


class ProxyLens:
    def __init__(
        self,
        client: SupportsProxyLensServerClient | None = None,
        *,
        node_name: str | None = None,
        node_name_env_var: str = DEFAULT_NODE_NAME_ENV_VAR,
        server_base_url: str | None = None,
        server_base_url_env_var: str = DEFAULT_PROXYLENS_SERVER_BASE_URL_ENV_VAR,
        trace_id_generator: Callable[[], str] | None = None,
        span_id_generator: Callable[[], str] | None = None,
        request_id_generator: Callable[[], str] | None = None,
        blob_id_generator: Callable[[], str] | None = None,
        flow_filter: FlowFilter | None = None,
        max_concurrent_requests_per_host: int | None = None,
        max_concurrent_requests_per_host_env_var: str = (
            DEFAULT_MAX_CONCURRENT_REQUESTS_PER_HOST_ENV_VAR
        ),
    ) -> None:
        resolved_max_concurrent_requests_per_host = (
            resolve_max_concurrent_requests_per_host(
                max_concurrent_requests_per_host=max_concurrent_requests_per_host,
                env_var=max_concurrent_requests_per_host_env_var,
            )
        )
        self._client = client or ProxyLensServerClient(
            base_url=server_base_url,
            base_url_env_var=server_base_url_env_var,
        )
        self._node_name = resolve_node_name(node_name, env_var=node_name_env_var)
        self._trace_id_generator = trace_id_generator or generate_trace_id
        self._span_id_generator = span_id_generator or generate_span_id
        self._request_id_generator = request_id_generator or generate_ulid
        self._blob_id_generator = blob_id_generator or generate_ulid
        self._flow_filter = flow_filter or (lambda flow: True)
        self._max_concurrent_requests_per_host = (
            resolved_max_concurrent_requests_per_host
        )
        self._active_flow_ids_by_host: dict[str, set[str]] = defaultdict(set)
        self._queued_flows_by_host: dict[str, deque[http.HTTPFlow]] = defaultdict(deque)

    def requestheaders(self, flow: http.HTTPFlow) -> None:
        if not self._flow_filter(flow):
            flow.metadata[_STATE_KEY] = {"enabled": False}
            return

        counts_toward_limit = not _is_websocket_handshake(flow.request)

        if counts_toward_limit and not self._acquire_flow_slot(flow):
            flow.metadata[_STATE_KEY] = {
                "enabled": True,
                "queued": True,
                "slot_acquired": False,
                "concurrency_host": _flow_host(flow),
            }
            self._queued_flows_by_host[_flow_host(flow)].append(flow)
            flow.intercept()
            return

        self._begin_flow_capture(flow, slot_acquired=counts_toward_limit)

    def request(self, flow: http.HTTPFlow) -> None:
        if not self._is_enabled(flow):
            return
        self._emit_body_events(flow, _REQUEST)
        self._emit_trailers(flow, _REQUEST)
        self._submit(flow, HttpRequestCompletedEvent(context=self._next_context(flow)))

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        if not self._is_enabled(flow) or flow.response is None:
            return
        self._wrap_stream(flow, _RESPONSE)
        self._submit(
            flow,
            HttpResponseStartedEvent(
                context=self._next_context(flow),
                status_code=flow.response.status_code,
                http_version=flow.response.http_version,
                headers=_normalize_headers(flow.response.headers),
            ),
        )

    def response(self, flow: http.HTTPFlow) -> None:
        if not self._is_enabled(flow) or flow.response is None:
            return
        self._emit_body_events(flow, _RESPONSE)
        self._emit_trailers(flow, _RESPONSE)
        self._submit(flow, HttpResponseCompletedEvent(context=self._next_context(flow)))
        if flow.websocket is None:
            self._finish_flow(flow)

    def websocket_start(self, flow: http.HTTPFlow) -> None:
        if not self._is_enabled(flow):
            return
        self._submit(
            flow,
            WebSocketStartedEvent(
                context=self._next_context(flow),
                url=flow.request.url,
                http_version=flow.request.http_version,
                headers=_normalize_headers(flow.request.headers),
            ),
        )

    def websocket_message(self, flow: http.HTTPFlow) -> None:
        if (
            not self._is_enabled(flow)
            or flow.websocket is None
            or not flow.websocket.messages
        ):
            return
        message = flow.websocket.messages[-1]
        direction = "client_to_server" if message.from_client else "server_to_client"
        if message.is_text:
            event = WebSocketMessageEvent(
                context=self._next_context(flow),
                direction=direction,
                payload_type="text",
                payload_text=message.text,
            )
        else:
            blob_id = self._upload_blob(message.content)
            event = WebSocketMessageEvent(
                context=self._next_context(flow),
                direction=direction,
                payload_type="binary",
                blob_id=blob_id,
                size_bytes=len(message.content),
            )
        self._submit(flow, event)

    def websocket_end(self, flow: http.HTTPFlow) -> None:
        if not self._is_enabled(flow):
            return
        close_code = flow.websocket.close_code if flow.websocket is not None else None
        self._submit(
            flow,
            WebSocketEndedEvent(
                context=self._next_context(flow),
                close_code=close_code,
            ),
        )
        self._finish_flow(flow)

    def error(self, flow: http.HTTPFlow) -> None:
        if not self._is_enabled(flow) or flow.error is None:
            self._finish_flow(flow)
            return
        self._submit(
            flow,
            RequestErrorEvent(
                context=self._next_context(flow),
                message=flow.error.msg,
            ),
        )
        self._finish_flow(flow)

    def _begin_flow_capture(
        self,
        flow: http.HTTPFlow,
        *,
        slot_acquired: bool,
    ) -> None:
        propagation = build_propagation_state(
            existing_hop_chain=flow.request.headers.get(PROXYLENS_HOP_CHAIN_HEADER),
            headers=flow.request.headers,
            node_name=self._node_name,
            trace_id_generator=self._trace_id_generator,
            request_id_generator=self._request_id_generator,
        )
        flow.request.headers[PROXYLENS_HOP_CHAIN_HEADER] = propagation.hop_chain
        flow.request.headers[PROXYLENS_REQUEST_ID_HEADER] = propagation.request_id
        synchronize_trace_context_headers(
            flow.request.headers,
            trace_id=propagation.trace_id,
            hop_nodes=propagation.hop_nodes,
            propagator=propagation.propagator,
            span_id_generator=self._span_id_generator,
        )
        flow.metadata[_STATE_KEY] = {
            "enabled": True,
            "request_id": propagation.request_id,
            "hop_chain": propagation.hop_chain,
            "node_name": self._node_name,
            "next_event_index": 0,
            "request_streaming_enabled": False,
            "response_streaming_enabled": False,
            "request_pending_stream_chunk": None,
            "response_pending_stream_chunk": None,
            "request_stream_expected_size": None,
            "response_stream_expected_size": None,
            "request_stream_seen_size": 0,
            "response_stream_seen_size": 0,
            "request_stream_passthrough": False,
            "response_stream_passthrough": False,
            "queued": False,
            "slot_acquired": slot_acquired,
            "concurrency_host": _flow_host(flow) if slot_acquired else None,
        }
        self._wrap_stream(flow, _REQUEST)
        self._submit(
            flow,
            HttpRequestStartedEvent(
                context=self._next_context(flow),
                method=flow.request.method,
                url=flow.request.url,
                http_version=flow.request.http_version,
                headers=_normalize_headers(flow.request.headers),
            ),
        )

    def _emit_body_events(self, flow: http.HTTPFlow, side: str) -> None:
        state = self._state(flow)
        if cast(bool, state[f"{side}_streaming_enabled"]):
            return
        message = flow.request if side == _REQUEST else flow.response
        if message is None:
            return

        if message.raw_content:
            self._submit_body_event(
                flow, side, chunk=message.raw_content, complete=True
            )

    def _emit_trailers(self, flow: http.HTTPFlow, side: str) -> None:
        message = flow.request if side == _REQUEST else flow.response
        if message is None or message.trailers is None:
            return
        trailers = _normalize_headers(message.trailers)
        if not trailers:
            return
        if side == _REQUEST:
            event = HttpRequestTrailersEvent(
                context=self._next_context(flow),
                trailers=trailers,
            )
        else:
            event = HttpResponseTrailersEvent(
                context=self._next_context(flow),
                trailers=trailers,
            )
        self._submit(flow, event)

    def _submit_body_event(
        self,
        flow: http.HTTPFlow,
        side: str,
        *,
        chunk: bytes,
        complete: bool,
    ) -> None:
        blob_id = self._upload_blob(chunk)
        if side == _REQUEST:
            event = HttpRequestBodyEvent(
                context=self._next_context(flow),
                blob_id=blob_id,
                size_bytes=len(chunk),
                complete=complete,
            )
        else:
            event = HttpResponseBodyEvent(
                context=self._next_context(flow),
                blob_id=blob_id,
                size_bytes=len(chunk),
                complete=complete,
            )
        self._submit(flow, event)

    def _wrap_stream(self, flow: http.HTTPFlow, side: str) -> None:
        state = self._state(flow)
        message = flow.request if side == _REQUEST else flow.response
        if message is None or not message.stream:
            return

        original_stream = message.stream
        state[f"{side}_streaming_enabled"] = True
        state[f"{side}_stream_expected_size"] = _content_length(message)
        state[f"{side}_stream_seen_size"] = 0
        state[f"{side}_stream_passthrough"] = not callable(original_stream)

        def wrapper(chunk: bytes) -> Iterable[bytes] | bytes:
            result: Iterable[bytes] | bytes
            if callable(original_stream):
                result = original_stream(chunk)
            else:
                result = chunk
            self._emit_streamed_body_events(
                flow,
                side,
                chunks=_streamed_chunks(result),
                final=chunk == b"",
            )
            return result

        message.stream = wrapper

    def _submit(self, flow: http.HTTPFlow, event: object) -> None:
        del flow
        self._client.submit_event(event)

    def _upload_blob(self, data: bytes) -> str:
        blob_id = self._blob_id_generator()
        self._client.upload_blob(blob_id, data)
        return blob_id

    def _emit_streamed_body_events(
        self,
        flow: http.HTTPFlow,
        side: str,
        *,
        chunks: list[bytes],
        final: bool,
    ) -> None:
        state = self._state(flow)
        pending_key = f"{side}_pending_stream_chunk"
        pending_chunk = cast(bytes | None, state[pending_key])
        expected_size = cast(int | None, state[f"{side}_stream_expected_size"])
        seen_size_key = f"{side}_stream_seen_size"
        seen_size = cast(int, state[seen_size_key])
        passthrough = cast(bool, state[f"{side}_stream_passthrough"])
        emitted_chunks = [chunk for chunk in chunks if chunk]

        if passthrough and expected_size is not None and not final:
            for index, chunk in enumerate(emitted_chunks):
                seen_size += len(chunk)
                complete = (
                    seen_size >= expected_size and index == len(emitted_chunks) - 1
                )
                self._submit_body_event(flow, side, chunk=chunk, complete=complete)
            state[seen_size_key] = seen_size
            if seen_size >= expected_size:
                state[pending_key] = None
            return

        if pending_chunk is not None:
            if emitted_chunks:
                self._submit_body_event(flow, side, chunk=pending_chunk, complete=False)
                pending_chunk = None

        if emitted_chunks:
            if final:
                for chunk in emitted_chunks[:-1]:
                    self._submit_body_event(flow, side, chunk=chunk, complete=False)
                self._submit_body_event(
                    flow,
                    side,
                    chunk=emitted_chunks[-1],
                    complete=True,
                )
                state[pending_key] = None
                return

            for chunk in emitted_chunks[:-1]:
                self._submit_body_event(flow, side, chunk=chunk, complete=False)
            state[pending_key] = emitted_chunks[-1]
            return

        if final:
            if pending_chunk is not None:
                self._submit_body_event(flow, side, chunk=pending_chunk, complete=True)
            state[pending_key] = None
            return

        state[pending_key] = pending_chunk

    def _next_context(self, flow: http.HTTPFlow) -> CaptureContext:
        state = self._state(flow)
        event_index = cast(int, state["next_event_index"])
        state["next_event_index"] = event_index + 1
        return CaptureContext(
            event_index=event_index,
            request_id=cast(str, state["request_id"]),
            node_name=cast(str, state["node_name"]),
            hop_chain=cast(str, state["hop_chain"]),
        )

    def _is_enabled(self, flow: http.HTTPFlow) -> bool:
        state = cast(dict[str, Any] | None, flow.metadata.get(_STATE_KEY))
        return bool(state and state.get("enabled") and not state.get("queued"))

    def _state(self, flow: http.HTTPFlow) -> dict[str, Any]:
        state = cast(dict[str, Any] | None, flow.metadata.get(_STATE_KEY))
        if state is None or not state.get("enabled"):
            raise RuntimeError("ProxyLens state was not initialized for this flow")
        return state

    def _acquire_flow_slot(self, flow: http.HTTPFlow) -> bool:
        if self._max_concurrent_requests_per_host is None:
            return True
        host = _flow_host(flow)
        active_flow_ids = self._active_flow_ids_by_host[host]
        if len(active_flow_ids) >= self._max_concurrent_requests_per_host:
            return False
        active_flow_ids.add(flow.id)
        return True

    def _finish_flow(self, flow: http.HTTPFlow) -> None:
        state = cast(dict[str, Any] | None, flow.metadata.get(_STATE_KEY))
        if state is None:
            return
        was_queued = bool(state.get("queued"))
        state["queued"] = False
        concurrency_host = cast(str | None, state.get("concurrency_host"))
        if state.get("slot_acquired"):
            state["slot_acquired"] = False
            if concurrency_host is not None:
                active_flow_ids = self._active_flow_ids_by_host.get(concurrency_host)
                if active_flow_ids is not None:
                    active_flow_ids.discard(flow.id)
                    if not active_flow_ids:
                        self._active_flow_ids_by_host.pop(concurrency_host, None)
        elif not was_queued:
            return
        if concurrency_host is not None:
            self._resume_queued_flows(concurrency_host)

    def _resume_queued_flows(self, host: str) -> None:
        queued_flows = self._queued_flows_by_host.get(host)
        if queued_flows is None:
            return

        while queued_flows:
            if self._max_concurrent_requests_per_host is not None:
                active_flow_ids = self._active_flow_ids_by_host[host]
                if len(active_flow_ids) >= self._max_concurrent_requests_per_host:
                    return

            flow = queued_flows.popleft()
            state = cast(dict[str, Any] | None, flow.metadata.get(_STATE_KEY))
            if state is None or not state.get("queued"):
                continue

            self._active_flow_ids_by_host[host].add(flow.id)
            self._begin_flow_capture(flow, slot_acquired=True)
            flow.resume()

        self._queued_flows_by_host.pop(host, None)


def _normalize_headers(headers: http.Headers) -> HeaderPairs:
    return tuple((name, value) for name, value in headers.items(multi=True))


def _streamed_chunks(result: Iterable[bytes] | bytes) -> list[bytes]:
    if isinstance(result, bytes):
        return [result] if result else []
    return [chunk for chunk in result if chunk]


def _content_length(message: http.Message) -> int | None:
    content_length = message.headers.get("content-length")
    if content_length is None:
        return None
    try:
        return int(content_length)
    except ValueError:
        return None


def _is_websocket_handshake(request: http.Request) -> bool:
    connection = request.headers.get("connection", "")
    upgrade = request.headers.get("upgrade", "")
    connection_tokens = {token.strip().lower() for token in connection.split(",")}
    return "upgrade" in connection_tokens and upgrade.lower() == "websocket"


def _flow_host(flow: http.HTTPFlow) -> str:
    return flow.request.host.lower()


def resolve_max_concurrent_requests_per_host(
    *,
    max_concurrent_requests_per_host: int | None = None,
    env_var: str = DEFAULT_MAX_CONCURRENT_REQUESTS_PER_HOST_ENV_VAR,
) -> int | None:
    if max_concurrent_requests_per_host is not None:
        resolved = max_concurrent_requests_per_host
    else:
        resolved = _resolve_max_concurrent_requests_per_host_from_env(env_var=env_var)

    if resolved is not None and resolved < 1:
        raise ValueError("max_concurrent_requests_per_host must be at least 1")
    return resolved


def _resolve_max_concurrent_requests_per_host_from_env(*, env_var: str) -> int | None:
    configured_value = os.environ.get(env_var)
    if configured_value is None or configured_value == "":
        return None

    try:
        return int(configured_value)
    except ValueError as exc:
        raise ValueError(
            f"max_concurrent_requests_per_host environment variable ${env_var} must be an integer"
        ) from exc
