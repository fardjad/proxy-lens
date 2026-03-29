# ProxyLens for mitmproxy

The PyPI package is `proxylens-mitmproxy` and the Python import package is `proxylens_mitmproxy`.
It captures HTTP and WebSocket traffic as normalized ProxyLens Server events.

It does three main things:

- propagates `X-ProxyLens-HopChain`
- generates a fresh `X-ProxyLens-RequestId` per observed hop
- synchronizes standard W3C, B3, or Jaeger trace headers, and synthesizes W3C context for fresh 32-hex traces when no standard context arrived inbound
- submits request, response, body, trailer, websocket, and error events to a server client

It can also optionally limit how many requests are allowed through the proxy at
the same time, which is useful when you want more deterministic capture order
from applications that cannot propagate ProxyLens headers themselves.

## Setup

This subproject is self-contained under `mitmproxy_addon/`.

```bash
cd mitmproxy_addon
uv sync --dev
```

Run tests with:

```bash
uv run pytest
```

## Basic Addon Usage

`ProxyLens()` now defaults to a real HTTP client for ProxyLens Server.

Current built-in clients:

- `RecordingProxyLensServerClient`: test/dummy client that records uploads and events in memory
- `ProxyLensServerClient`: real HTTP client for the server write API

Minimal example:

```python
from proxylens_mitmproxy import ProxyLens

addon = ProxyLens(
    node_name="proxy-a",
    max_concurrent_requests_per_host=1,
)

addons = [addon]
```

If you do not pass `node_name`, the addon reads it from `PROXYLENS_NODE_NAME`.

```bash
export PROXYLENS_NODE_NAME=proxy-a
```

If you do not inject a client, the addon uses `ProxyLensServerClient`, which resolves the server base URL from `PROXYLENS_SERVER_BASE_URL` and otherwise defaults to `http://127.0.0.1:8000`.

```bash
export PROXYLENS_SERVER_BASE_URL=http://127.0.0.1:8000
```

You can still inject a custom client explicitly:

```python
from proxylens_mitmproxy import ProxyLens, ProxyLensServerClient

addon = ProxyLens(
    client=ProxyLensServerClient(base_url="http://127.0.0.1:8000"),
    node_name="proxy-a",
)
```

`max_concurrent_requests_per_host=None` keeps the default unlimited behavior.
Set it to `1` to force strict per-host serialization, or to a larger integer to
allow a small bounded number of in-flight requests per host.
WebSocket upgrade requests do not count toward this limit.

If you do not pass `max_concurrent_requests_per_host`, the addon reads it from
`PROXYLENS_MAX_CONCURRENT_REQUESTS_PER_HOST` when set.

```bash
export PROXYLENS_MAX_CONCURRENT_REQUESTS_PER_HOST=1
```

## Running In mitmproxy

Create a small loader script, for example `run_proxylens_mitmproxy.py`:

```python
from proxylens_mitmproxy import ProxyLens

addons = [
    ProxyLens(
        node_name="proxy-a",
    )
]
```

Then run mitmproxy or mitmdump with that script:

```bash
cd mitmproxy_addon
uv run mitmdump -s run_proxylens_mitmproxy.py
```

## Behavior

For each request seen by the current mitmproxy process, the addon:

1. reads any inbound `X-ProxyLens-HopChain`
2. appends the current node name or starts a new trace using a trace id extracted from `traceparent`, B3, or Jaeger headers when available, otherwise generating a new trace id
3. replaces any inbound `X-ProxyLens-RequestId` with a fresh ULID
4. preserves the inbound standard propagation format when W3C, B3, or Jaeger context is already present
5. synthesizes W3C `traceparent` and `tracestate` when no standard trace context arrived inbound and the resolved trace id is 32 hex, so downstream OpenTelemetry instrumentation can join the same trace automatically
6. emits normalized capture events in request-local `event_index` order
7. uploads binary body chunks and binary websocket payloads before emitting referencing events

The addon currently captures:

- request metadata
- request body chunks
- request trailers when exposed by mitmproxy
- request completion
- response metadata
- response body chunks
- response trailers when exposed by mitmproxy
- response completion
- websocket start, message, and end events
- request error events

## Dependency Injection

`ProxyLens` accepts injectable collaborators for deterministic tests and custom runtime behavior:

```python
ProxyLens(
    client=...,
    node_name="proxy-a",
    server_base_url=...,
    trace_id_generator=...,
    request_id_generator=...,
    blob_id_generator=...,
    flow_filter=...,
    max_concurrent_requests_per_host=...,
)
```

`flow_filter(flow)` can be used to skip capture for selected flows.
`server_base_url` is only used when `client` is not injected. If it is unset and
`PROXYLENS_SERVER_BASE_URL` is also unset, the addon disables itself and becomes
an early no-op.
`max_concurrent_requests_per_host` limits how many flows can be active at once
for each destination host; excess flows for that host are queued inside
mitmproxy until a slot becomes available.
WebSocket upgrade flows are excluded from that accounting.

## In-Process Test Harness

The package includes a mitmproxy-native test harness for fast integration tests:

```python
from mitmproxy import http
from proxylens_mitmproxy import (
    ProxyLens,
    RecordingProxyLensServerClient,
    TestMitmProxy,
)


def handler(flow: http.HTTPFlow) -> None:
    flow.response = http.Response.make(200, b"ok")


client = RecordingProxyLensServerClient()
addon = ProxyLens(client=client, node_name="proxy-a")

with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
    flow = proxy.request("GET", "https://example.test/")

assert flow.response is not None
assert client.events[0]["type"] == "http_request_started"
```

`TestMitmProxy` provides:

- `request(...)` / `send(...)` for sync tests
- `arequest(...)` / `asend(...)` for async tests
- real `mitmproxy.http.HTTPFlow` objects
- responder exception surfacing instead of silent logging

## Package Layout

```text
mitmproxy_addon/
├── pyproject.toml
├── README.md
├── src/proxylens_mitmproxy/
└── tests/
```
