# ProxyLens for mitmproxy

The PyPI package is `proxylens-mitmproxy` and the Python import package is `proxylens_mitmproxy`.
It captures HTTP and WebSocket traffic as normalized ProxyLens Server events.

It does three main things:

- propagates `X-ProxyLens-HopChain`
- generates a fresh `X-ProxyLens-RequestId` per observed hop
- submits request, response, body, trailer, websocket, and error events to a server client

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
2. appends the current node name or starts a new trace
3. replaces any inbound `X-ProxyLens-RequestId` with a fresh ULID
4. emits normalized capture events in request-local `event_index` order
5. uploads binary body chunks and binary websocket payloads before emitting referencing events

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
)
```

`flow_filter(flow)` can be used to skip capture for selected flows.
`server_base_url` is only used when `client` is not injected.

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
