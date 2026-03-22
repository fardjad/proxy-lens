# ProxyLens for mitmproxy spec

Package naming:

- PyPI distribution: `proxylens-mitmproxy`
- Python import package: `proxylens_mitmproxy`

## Goal

Create a Python package with a tight test-driven development loop for a mitmproxy addon that runs inside multiple mitmproxy processes, captures traffic as an ordered stream of events, propagates trace metadata across chained proxies, assigns a fresh request identifier per observed request, and forwards normalized capture events to ProxyLens Server, which will later store data and generate sequence diagrams.

The initial focus is the addon client and its propagation behavior, not diagram rendering. The first milestone is an ergonomic test harness and normalized event-capture client that:

- constructs real `mitmproxy.http.HTTPFlow` objects
- drives them through mitmproxy's addon lifecycle in-process
- lets tests register a `ProxyLens` addon plus a responder addon
- forwards captured events to a fake or mocked ProxyLens Server client
- returns the resulting `HTTPFlow` so tests can assert on emitted events, header propagation, and produced responses

Boundary note:

- addon-owned behavior lives in this document
- server-owned ingestion, request-record, and event-schema contracts live in [server/docs/spec.md](../../server/docs/spec.md)
- this document defines the current mitmproxy producer profile against that server contract

Protocol scope for v1:

- capture plain HTTP traffic as events
- capture decrypted HTTPS traffic as events after mitmproxy interception
- intentionally support mitmproxy Regular mode
- intentionally support HTTP/1.0, HTTP/1.1, HTTP/2, and WebSocket traffic available in Regular mode
- emit request metadata when URL, method, version, and headers are known
- emit request body chunk events when body bytes become known, including streaming situations
- emit request trailer events when trailers become known
- emit response metadata when status, version, and headers are known
- emit response body chunk events when body bytes become known, including streaming situations
- emit response trailer events when trailers become known
- emit WebSocket connection lifecycle events
- emit WebSocket message events when messages are observed
- allow different parts of the same logical flow to be captured at different times
- do not model `CONNECT` tunnel establishment itself as a first-class sequence event
- do not intentionally support HTTP/3 in v1 because Regular mode is the target and HTTP/3 support depends on other mitmproxy modes

## Version baseline

Verified on 2026-03-20:

- Python: `3.14.3`
- mitmproxy: `12.2.1`
- pytest: `9.0.2`

## Design principles

- Use `uv` for interpreter management, locking, and task execution.
- Use mitmproxy's own testing helpers instead of mocking the whole proxy stack.
- Keep the core test path fully in-process. The suite may still include a small number of end-to-end tests that boot the real server over localhost.
- Make the addon a thin client for ProxyLens Server. Diagram generation and persistence live on the server side, not inside mitmproxy.
- Separate capture from rendering. `ProxyLens` should produce and submit normalized capture events; rendering to Mermaid/PlantUML/etc. should be a later server-side layer.
- Keep the initial package focused on capture and propagation. v1 should not expose Mermaid or PlantUML rendering yet.
- Support both ordinary synchronous pytest tests and async pytest tests with parallel sync and async harness APIs.
- Prefer dependency injection for API transport, node-name resolution, trace-id generation, and request-id generation so propagation logic can be tested deterministically.
- Co-locate unit tests with the source modules they cover. Reserve the top-level `tests/` directory for integration tests only.

## Proposed project layout

```text
.
├── .python-version
├── README.md
├── justfile
├── docs/
│   └── spec.md
├── pyproject.toml
├── src/
│   └── proxylens_mitmproxy/
│       ├── __init__.py
│       ├── addon.py
│       ├── addon_test.py
│       ├── client.py
│       ├── client_test.py
│       ├── models.py
│       ├── models_test.py
│       ├── propagation.py
│       ├── propagation_test.py
│       └── testing.py
├── tests/
│   ├── conftest.py
│   ├── test_proxylens_mitmproxy_integration.py
│   ├── test_server_client_integration.py
│   └── test_test_mitm_proxy_integration.py
└── uv.lock
```

Repository note:

- this addon project lives under `mitmproxy_addon/`
- the repository root also contains the sibling `server/` project

## Environment setup

### `uv` workflow

Use `uv` to pin the interpreter and manage dependencies:

```bash
uv init --package --python 3.14
uv python pin 3.14.3
uv add mitmproxy==12.2.1
uv add python-ulid
uv add typing-extensions
uv add --dev pytest==9.0.2
uv add --dev black
uv add --dev pytest-watch
```

### `pyproject.toml`

Use these package-level constraints:

- `requires-python = ">=3.14"`
- runtime dependencies:
- `mitmproxy==12.2.1`
- `python-ulid`
- `typing-extensions`
- dev dependency group:
- `pytest==9.0.2`
- `black`
- `pytest-watch`

Recommended pytest config:

```toml
[tool.pytest.ini_options]
testpaths = ["src", "tests"]
addopts = "-q"
python_files = ["*_test.py", "test_*_integration.py"]
filterwarnings = [
  "ignore:tagMap is deprecated\\. Please use TAG_MAP instead\\.:DeprecationWarning",
  "ignore:typeMap is deprecated\\. Please use TYPE_MAP instead\\.:DeprecationWarning",
]
```

### Common commands

```bash
uv run pytest
uv run pytest src/proxylens_mitmproxy/propagation_test.py
uv run pytest tests/test_proxylens_mitmproxy_integration.py -q
just test
just style-check
```

## Proposed API

### 1. `ProxyLens`

The addon under test. It is a mitmproxy addon that acts as a client for ProxyLens Server.
Its main responsibilities are:

- read the current node name from configuration or environment
- inspect inbound HTTP and WebSocket traffic
- generate or continue trace and request propagation state
- mutate outbound headers to carry `X-ProxyLens-HopChain` and `X-ProxyLens-RequestId`
- optionally limit how many requests are allowed through concurrently
- emit and submit normalized capture events to a ProxyLens Server client
- emit request-scoped incremental updates as metadata, body chunks, trailers, and lifecycle state become known

It should expose lifecycle hooks such as:

```python
from mitmproxy import http


class ProxyLens:
    def requestheaders(self, flow: http.HTTPFlow) -> None:
        ...

    def request(self, flow: http.HTTPFlow) -> None:
        ...

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        ...

    def response(self, flow: http.HTTPFlow) -> None:
        ...

    def websocket_start(self, flow: http.HTTPFlow) -> None:
        ...

    def websocket_message(self, flow: http.HTTPFlow) -> None:
        ...

    def websocket_end(self, flow: http.HTTPFlow) -> None:
        ...

    def error(self, flow: http.HTTPFlow) -> None:
        ...
```

For testability, its dependencies should be injectable. Likely candidates:

- ProxyLens Server client
- node name provider
- trace id generator
- request id generator
- blob id generator
- filtering predicate
- concurrent request limit

The current implementation also supports constructing a default real HTTP server client when one is not injected directly.

#### Optional concurrency gating

`ProxyLens` may optionally be configured with
`max_concurrent_requests_per_host`.

- `None` means unlimited concurrent flows
- `1` means strict per-host serialization through the addon
- any integer greater than `1` means bounded per-host concurrency
- WebSocket upgrade flows do not count against this limit

When the limit is reached:

- additional flows for that same destination host should be intercepted and queued at `requestheaders`
- queued flows should not mutate ProxyLens headers yet
- queued flows should not emit `http_request_started` yet
- the next queued flow for that host should resume only when an active flow for that host finishes
- WebSocket upgrade flows should always bypass the queue even when the limit is reached

For this feature, a flow is considered finished when:

- an ordinary HTTP flow reaches `response`
- a WebSocket flow reaches `websocket_end`
- a flow reaches `error`

This feature is intentionally heuristic. It can make sequence diagrams more
readable in environments where upstream applications cannot propagate
`X-ProxyLens-*` headers, but it does not create a robust causal relationship on
its own.

Avoid hard-coding file I/O or rendering inside the addon itself. In v1, `ProxyLens` is responsible only for producing normalized capture events and submitting them to the ProxyLens Server client.

#### Node name configuration

Each addon instance should know its node name. The default mechanism should be an environment variable, for example:

```text
PROXYLENS_NODE_NAME=node-a
```

It should also be possible to inject the value directly in tests.

#### Server base URL configuration

When a client is not injected explicitly, `ProxyLens` should build a default `ProxyLensServerClient`.
That client should resolve its server base URL from configuration or environment, for example:

```text
PROXYLENS_SERVER_BASE_URL=http://127.0.0.1:8000
```

The implementation currently defaults to `http://127.0.0.1:8000` when no explicit base URL is provided.

#### Identity And Propagation

Incoming and outgoing requests should use these headers:

```text
X-ProxyLens-HopChain: <shared_trace_ulid>@<node_name1>,<node_name2>,...
X-ProxyLens-RequestId: <request_ulid>
```

Header semantics for this spec:

- `X-ProxyLens-HopChain` carries a shared `trace_id` plus the ordered node chain
- `X-ProxyLens-RequestId` carries a ULID `request_id` for one concrete request observed by one addon instance
- `trace_id` is propagated unchanged across hops and each proxy appends only its own node name to the trace chain
- `request_id` is not propagated across hops; each proxy generates its own fresh value for the request it observes

Canonical server-owned semantics:

- the request record model is defined in [server/docs/spec.md](../../server/docs/spec.md)
- the capture event schema is defined in [server/docs/spec.md](../../server/docs/spec.md)
- the addon must emit events that conform to the server spec instead of redefining those contracts locally
- the addon should treat `request_id` as the request-scoped correlation key and `hop_chain` as trace-level request metadata
- the addon should assume identity is determined only by `trace_id`, `request_id`, and `event_index`, never by request payload contents
- the addon should assume the server applies events idempotently per `request_id` and `event_index`
- the addon should upload large binary payloads as blobs before emitting events that reference them
- the addon client should be prepared to receive per-event results of `accepted`, `ignored`, `deferred`, `dropped`, or `rejected` from ProxyLens Server
- any mitmproxy-specific limitations or omissions in v1 are producer-profile limitations, not server-contract limitations

Examples:

```text
X-ProxyLens-HopChain: 01K0TRACEEDGEAPROXYB0000000@edge-a,service-b
X-ProxyLens-RequestId: 01K0REQUESTEDGEASVCB000000
```

At the next hop, the request becomes:

```text
X-ProxyLens-HopChain: 01K0TRACEEDGEAPROXYB0000000@edge-a,service-b,proxy-c
X-ProxyLens-RequestId: 01K0REQUESTPROXYCHOP0000000
```

Propagation behavior for HTTP requests:

- if the hop-chain header is missing, generate a new trace id and set `X-ProxyLens-HopChain` to `<trace_id>@<current_node>`
- if the trace header exists, parse it, preserve the shared trace id and existing node names, and append `<current_node>` to the node list
- always generate a fresh request ULID for the request observed at the current hop and set `X-ProxyLens-RequestId`
- do not preserve an inbound `X-ProxyLens-RequestId` value from an upstream hop
- emit request metadata, body-chunk, trailer, and completion events keyed by the current hop's `request_id`
- emit response metadata, body-chunk, trailer, and completion events keyed by the same `request_id`

Propagation behavior for WebSocket connections:

- apply the same header logic during the connection handshake
- emit connection lifecycle events and WebSocket message events as they become known

### 2. `ResponderAddon`

An internal test-only addon that turns a user-provided handler into a mitmproxy addon:

```python
from collections.abc import Callable
from mitmproxy import http

type FlowHandler = Callable[[http.HTTPFlow], None]


class ResponderAddon:
    def __init__(self, handler: FlowHandler) -> None:
        self._handler = handler

    def request(self, flow: http.HTTPFlow) -> None:
        self._handler(flow)
```

This keeps tests concise:

```python
def handler(flow: http.HTTPFlow) -> None:
    flow.response = http.Response.make(200, b"ok")
```

### 3. `TestMitmProxy`

This is the main test harness. It should provide a sync, pytest-friendly facade over mitmproxy's async event handling.
It should also expose an async API for async pytest users so both styles are first-class.

#### Public API

```python
from collections.abc import Mapping
from mitmproxy import http
from mitmproxy.options import Options


class TestMitmProxy:
    def __init__(
        self,
        proxy_lens: ProxyLens,
        handler: FlowHandler,
        *,
        options: Options | None = None,
    ) -> None:
        ...

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | str = b"",
        headers: Mapping[str, str | bytes] | None = None,
    ) -> http.HTTPFlow:
        ...

    def send(self, request: http.Request) -> http.HTTPFlow:
        ...

    async def arequest(
        self,
        method: str,
        url: str,
        *,
        content: bytes | str = b"",
        headers: Mapping[str, str | bytes] | None = None,
    ) -> http.HTTPFlow:
        ...

    async def asend(self, request: http.Request) -> http.HTTPFlow:
        ...

    def close(self) -> None:
        ...

    async def aclose(self) -> None:
        ...

    def __enter__(self) -> "TestMitmProxy":
        ...

    def __exit__(self, exc_type, exc, tb) -> None:
        ...

    async def __aenter__(self) -> "TestMitmProxy":
        ...

    async def __aexit__(self, exc_type, exc, tb) -> None:
        ...
```

#### Usage example

```python
from mitmproxy import http
from proxylens_mitmproxy.addon import ProxyLens
from proxylens_mitmproxy.testing import TestMitmProxy


def handler(flow: http.HTTPFlow) -> None:
    flow.response = http.Response.make(
        201,
        b'{"status":"created"}',
        {"content-type": "application/json"},
    )


def test_records_request_capture_events() -> None:
    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-a",
        trace_id_generator=lambda: "01K0TRACEPROXYAEXAMPLE0000",
        request_id_generator=lambda: "01K0REQUESTPROXYAEXAMPLE00",
    )

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        flow = proxy.request(
            "POST",
            "https://example.test/widgets",
            content=b'{"name":"demo"}',
            headers={"content-type": "application/json"},
        )

    assert flow.response is not None
    assert flow.response.status_code == 201
    trace_header = flow.request.headers["X-ProxyLens-HopChain"]
    request_id_header = flow.request.headers["X-ProxyLens-RequestId"]
    assert trace_header == "01K0TRACEPROXYAEXAMPLE0000@proxy-a"
    assert request_id_header == "01K0REQUESTPROXYAEXAMPLE00"
    assert [event["type"] for event in client.events] == [
        "http_request_started",
        "http_request_body",
        "http_request_completed",
        "http_response_started",
        "http_response_body",
        "http_response_completed",
    ]
    assert client.events[0]["event_index"] == 0
    assert client.events[0]["hop_chain"] == "01K0TRACEPROXYAEXAMPLE0000@proxy-a"
    assert client.events[0]["payload"]["method"] == "POST"
    assert client.events[0]["payload"]["url"] == "https://example.test/widgets"
    assert (
        "X-ProxyLens-HopChain",
        trace_header,
    ) in client.events[0]["payload"]["headers"]
    assert (
        "X-ProxyLens-RequestId",
        request_id_header,
    ) in client.events[0]["payload"]["headers"]
```

### 4. `ProxyLensServerClient`

This is the transport client used by the addon to talk to ProxyLens Server.
The canonical event schema and request-record semantics live in [server/docs/spec.md](../../server/docs/spec.md).

```python
from typing import BinaryIO


class ProxyLensServerClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        base_url_env_var: str = "PROXYLENS_SERVER_BASE_URL",
        timeout_seconds: float = 10.0,
    ) -> None:
        ...

    def upload_blob(self, blob_id: str, data: bytes | BinaryIO) -> None:
        ...

    def submit_event(self, event: CaptureEvent) -> None:
        ...
```

Implementation notes:

- the default client talks to the real server write API over HTTP
- blob uploads target `PUT /blobs/{blob_id}`
- event submission targets `POST /events`
- the client should treat `accepted`, `ignored`, `deferred`, and `dropped` as non-fatal results
- the client should raise on malformed responses or `rejected` per-event results
- tests should still use a fake in-memory implementation for the in-process path

## Harness behavior

### Construction

`TestMitmProxy` should:

- create a mitmproxy testing context
- register addons in this order: `ProxyLens`, then `ResponderAddon`

That ordering matters:

- on the `request` hook, `ProxyLens` sees the inbound request before the responder sets `flow.response`
- this lets tests verify header mutation and central-client submission before or regardless of the synthetic response

### Request creation

`request(...)` should:

- build a real mitmproxy request via `mitmproxy.http.Request.make(...)`
- wrap it in a real `HTTPFlow`
- drive that flow through mitmproxy lifecycle events
- return the mutated `HTTPFlow`

`send(...)` should accept a prebuilt `http.Request` for tests that need unusual request shaping.

`arequest(...)` and `asend(...)` should provide the same behavior for async tests without forcing users through sync wrappers.

### Lifecycle driving

Implementation should reuse mitmproxy internals instead of reimplementing the state machine:

- `mitmproxy.test.taddons.context`
- `mitmproxy.test.tflow.tflow`
- `mitmproxy.eventsequence.iterate(flow)`
- `context.master.addons.handle_lifecycle(event)`

This gives us real hook ordering without booting a real proxy server.

### Scope of v1

`TestMitmProxy` v1 should support:

- Regular mode as the intentional target mode
- HTTP request hook
- HTTP response hook
- HTTP request and response header hooks
- decrypted HTTPS requests after interception
- HTTP/1.0, HTTP/1.1, and HTTP/2 request/response metadata capture
- streaming request and response bodies
- request and response trailers when exposed by the underlying protocol stack
- WebSocket connection lifecycle hooks
- WebSocket messages
- custom headers
- custom body content
- repeated calls in the same test session
- both synchronous and asynchronous test APIs
- fake or mocked ProxyLens Server clients
- fake or mocked blob upload handling
- assertions over propagated `X-ProxyLens-HopChain` and `X-ProxyLens-RequestId` headers

Out of scope for v1:

- true socket-level proxying
- TLS handshake behavior
- `CONNECT` tunnel establishment as a sequence event
- intentional HTTP/3 support
- upstream server timing or retry semantics
- ProxyLens Server persistence or diagram rendering implementation

## Why this approach

### Fast feedback loop

This design keeps the core hot path cheap:

- no subprocess startup
- no port allocation
- no HTTP client dependency required for the core tests
- direct assertions on mitmproxy-native objects

The current test suite also includes a single end-to-end server integration test that boots the real server over localhost.

### TDD-friendly failure modes

Tests can fail at the correct layer:

- pure normalization and header propagation errors fail in unit tests
- addon lifecycle and client-submission mistakes fail in integration tests
- protocol-specific and streaming edge cases can be isolated in focused integration tests
- future real-proxy edge cases can be isolated in slower smoke tests

## Test strategy

### Unit tests

Target pure code with no mitmproxy lifecycle. These tests should live next to the source modules under `src/proxylens_mitmproxy/`:

- event model normalization
- URL/path extraction
- node-name resolution
- `X-ProxyLens-HopChain` parsing and serialization
- trace-id generation rules
- request-id generation rules
- event ordering and event kind transitions
- trailer normalization
- filtering behavior

Example:

```python
def test_build_proxylens_trace_header_for_new_trace() -> None:
    trace_header = build_proxylens_trace_header(
        existing_header=None,
        node_name="proxy-a",
        trace_id="01K0TRACEPROXYAEXAMPLE0000",
    )

    assert trace_header == "01K0TRACEPROXYAEXAMPLE0000@proxy-a"
```

### Integration tests

Target real addon hook interaction through `TestMitmProxy`:

- missing trace header causes a new trace id to be generated and injected
- existing trace header is preserved and appended to
- a fresh request id is generated and injected at each hop
- an inbound request-id header from an upstream hop is replaced at the current hop
- HTTP request metadata events are submitted as soon as URL, method, and headers are known
- request blobs are uploaded before request body events reference them
- HTTP request body events are submitted incrementally as body bytes become known
- HTTP response metadata events are submitted as soon as status and headers are known
- response blobs are uploaded before response body events reference them
- HTTP response body events are submitted incrementally as body bytes become known
- request and response trailers are captured when available
- request and response `http_version` values are captured
- WebSocket start and message events are submitted as they are observed
- buffered and streamed bodies produce a coherent event sequence for the same request record
- multiple requests preserve event ordering
- filters exclude non-matching flows
- handler exceptions are surfaced clearly
- sync and async harness entry points behave equivalently
- the default HTTP server client can be exercised against the real `server/` project over localhost

Example:

```python
def test_existing_propagation_header_is_appended() -> None:
    def handler(flow: http.HTTPFlow) -> None:
        flow.response = http.Response.make(204, b"")

    client = RecordingProxyLensServerClient()
    addon = ProxyLens(
        client=client,
        node_name="proxy-b",
        trace_id_generator=lambda: "01K0TRACEPROXYBEXAMPLE0000",
        request_id_generator=lambda: "01K0REQUESTPROXYBEXAMPLE00",
    )

    with TestMitmProxy(proxy_lens=addon, handler=handler) as proxy:
        flow = proxy.request(
            "DELETE",
            "https://example.test/widgets/1",
            headers={
                "X-ProxyLens-HopChain": "01K0TRACEPROXYAEXAMPLE0000@proxy-a",
                "X-ProxyLens-RequestId": "01K0REQUESTUPSTREAMEXAMPLE0",
            },
        )

    assert flow.request.headers["X-ProxyLens-HopChain"] == "01K0TRACEPROXYAEXAMPLE0000@proxy-a,proxy-b"
    assert flow.request.headers["X-ProxyLens-RequestId"] == "01K0REQUESTPROXYBEXAMPLE00"
    assert client.events[0]["headers"]["X-ProxyLens-HopChain"] == "01K0TRACEPROXYAEXAMPLE0000@proxy-a,proxy-b"
    assert client.events[0]["headers"]["X-ProxyLens-RequestId"] == "01K0REQUESTPROXYBEXAMPLE00"
```

### Additional end-to-end tests

The current implementation also keeps one end-to-end server integration test in the default suite.
It boots the real `server/` project over localhost and verifies that addon-emitted events are accepted and queryable through the server API.
Slower real-proxy smoke tests can still be added later as a separate layer if needed.

## Implementation notes

### Recommended internal data model

The canonical request-record and capture-event schemas live in [server/docs/spec.md](../../server/docs/spec.md).

For addon implementation purposes:

- the addon should avoid storing raw `HTTPFlow` objects as its main long-lived model
- the addon should emit discrete events that conform to the server-owned event schema
- the addon should treat ProxyLens Server as the owner of request-record merge rules and accumulated state
- the addon should treat SQLite persistence, blob-file persistence, and relative blob-path management as ProxyLens Server concerns
- the addon should treat blob storage as an explicit upload-then-reference contract with ProxyLens Server
- the addon may define local helper types or DTOs, but they must stay compatible with the server spec

### Implementation mapping

Keep the public spec request-centric, but the implementation should explicitly account for mitmproxy's hook model:

- request metadata maps naturally to `requestheaders(...)`
- buffered request bodies are available in `request(...)`
- response metadata maps naturally to `responseheaders(...)`
- buffered response bodies are available in `response(...)`
- streamed request and response chunk capture requires configuring body streaming callbacks before the full body is buffered
- streamed request and response body events should be uploaded and submitted from the streaming callback path as chunks become known
- WebSocket lifecycle and message capture maps naturally to `websocket_start(...)`, `websocket_message(...)`, and `websocket_end(...)`
- request and response trailers should be captured when the underlying protocol stack exposes them on the request or response object

Compatibility notes:

- Regular mode is the intentional support target for v1
- HTTP/3 should not be claimed as supported in v1 because Regular mode is the supported mode
- HTTP/1.x trailers are not supported by mitmproxy today, so trailer capture should only be claimed where the underlying protocol stack exposes trailers
- cleartext HTTP/2 (h2c) should not be claimed as supported in v1 because mitmproxy does not support it
- WebSocket ping and pong frames should not be modeled as message events in v1 because mitmproxy forwards them but does not store them as WebSocket messages

### Dependency injection

`ProxyLens` should accept collaborators instead of hard-coding them internally, while still allowing a default HTTP server client to be created when desired:

```python
class ProxyLens:
    def __init__(
        self,
        client: SupportsProxyLensServerClient | None = None,
        *,
        node_name: str | None = None,
        node_name_env_var: str = "PROXYLENS_NODE_NAME",
        server_base_url: str | None = None,
        server_base_url_env_var: str = "PROXYLENS_SERVER_BASE_URL",
        trace_id_generator: Callable[[], str] | None = None,
        request_id_generator: Callable[[], str] | None = None,
        blob_id_generator: Callable[[], str] | None = None,
        flow_filter: Callable[[http.HTTPFlow], bool] | None = None,
    ) -> None:
        ...
```

This keeps tests deterministic while still supporting a default server client in normal runtime use.
When provided, the generators should return canonical ULID strings.

### Error behavior

For v1:

- let handler exceptions fail the test directly
- do not swallow addon exceptions
- do not silently suppress propagation or client submission failures
- fail fast if no node name can be resolved

If no response is set, the returned flow should still reflect that state so tests can assert on it.

## Definition of done for the first implementation

The first implementation is complete when all of the following are true:

- project is bootstrapped with `uv`
- interpreter is pinned to Python `3.14.3`
- mitmproxy `12.2.1` and pytest `9.0.2` are installed
- `ProxyLens` exists as a normal addon object and ProxyLens Server client wrapper
- `TestMitmProxy` exists and can drive flows in-process
- the addon spec references [server/docs/spec.md](../../server/docs/spec.md) as the source of truth for event and request-record contracts
- the spec and implementation intentionally target mitmproxy Regular mode
- the default server client can resolve its base URL from `PROXYLENS_SERVER_BASE_URL`
- at least one integration test proves that a missing `X-ProxyLens-HopChain` header creates a new hop-chain header value
- at least one integration test proves that an existing `X-ProxyLens-HopChain` header is preserved and appended to
- at least one integration test proves that a fresh `X-ProxyLens-RequestId` value is generated at the current hop
- at least one integration test proves that an inbound `X-ProxyLens-RequestId` value is replaced at the current hop
- at least one integration test proves that HTTP request metadata events are submitted before body events for buffered and streamed bodies
- at least one integration test proves that request blobs are uploaded before request body events reference them
- at least one integration test proves that HTTP request body events are submitted incrementally when body bytes become available
- at least one integration test proves that HTTP response metadata, body, and completion events are captured
- at least one integration test proves that response blobs are uploaded before response body events reference them
- at least one integration test proves that request and response trailers are captured when available
- at least one integration test proves that request and response `http_version` values are captured
- at least one integration test proves that WebSocket connections and messages are captured as separate events
- at least one integration test proves that node name resolution works from injected config and environment
- at least one integration test proves that the default HTTP server client works against the real `server/` project
- tests run with `uv run pytest`

## Current decisions

1. `CONNECT` does not need to appear as a first-class event; capture begins at decrypted HTTPS traffic after interception.
2. `ProxyLens` should store a normalized intermediate representation only. Rendering is out of scope for v1.
3. The test harness should expose both synchronous and asynchronous APIs.
4. The addon is a client for ProxyLens Server. Multiple mitmproxy processes may be chained, and the addon must propagate `X-ProxyLens-HopChain` across hops while generating a fresh `X-ProxyLens-RequestId` at each hop.
5. V1 captures HTTP/HTTPS and WebSocket traffic as an event stream instead of single request snapshots, and those events update a request record keyed by `request_id`.
6. `X-ProxyLens-HopChain` uses the format `<shared_trace_id>@<node_name1>,<node_name2>,...`, where the trace id is propagated unchanged and each hop appends only its node name.
7. `X-ProxyLens-RequestId` is a ULID generated fresh at each hop and used as the primary key for correlating capture events for one concrete request observed at that hop.
8. mitmproxy Regular mode is the intentional support target for v1.
9. V1 intentionally covers request and response metadata, body chunks, completion, trailers when exposed, WebSocket lifecycle, and WebSocket messages.
