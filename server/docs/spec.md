# ProxyLens Server spec

## Goal

Build ProxyLens Server, a server that accepts capture data from one or more producers, stores request-scoped records, applies incremental capture events to those records, relates requests into traces, and provides the foundation for later diagram generation and querying.

This document is the source of truth for:

- the server-owned ingestion contract
- the request record model
- the capture event model
- the rules for applying events to request records
- the relationship between hop-local requests and cross-hop traces

Producer-specific specs should reference this document instead of redefining these contracts.

## Responsibilities

ProxyLens Server is responsible for:

- accepting events from producer clients
- validating event payloads
- creating and updating request records keyed by `request_id`
- relating request records into traces using hop-chain metadata
- preserving event ordering within a request
- persisting metadata in SQLite
- persisting large binary payloads outside SQLite as file-backed blobs
- storing request and response metadata, bodies, trailers, websocket lifecycle, websocket messages, and errors
- exposing lightweight query APIs for histogram and request-summary use cases
- making it easy to clear all captured state or selectively delete completed requests
- deleting all dependent metadata and blob files when data is removed
- providing a stable domain model that later rendering or analysis layers can consume

ProxyLens Server is not responsible for:

- generating request ids or hop-chain metadata inside a producer
- controlling producer runtime behavior
- defining producer-specific capture hooks beyond what producers need to emit valid events

## Intentional scope

V1 should intentionally support:

- events from any producer that conforms to this contract
- ingestion-time filter scripts
- request-scoped record construction and updates
- cross-hop trace reconstruction using hop-chain metadata
- SQLite-backed metadata persistence
- file-backed blob persistence for request/response body chunks or materialized bodies
- HTTP request and response metadata
- HTTP request and response body chunk accumulation
- HTTP request and response trailers when present
- WebSocket lifecycle and message accumulation
- explicit request error handling
- lightweight request histogram queries over time
- lightweight request-summary queries with time-range filters
- on-demand request detail queries for heavier request state

V1 does not need to include:

- user-facing diagram rendering
- server-managed archival or advanced retention-policy features
- authn/authz hardening beyond what is required for local or controlled deployment
- payload-based identity or deduplication across distinct request ids
- alternative metadata backends beyond SQLite

Retention and archival intent for this project:

- the primary use case is local or controlled development-time capture
- archival does not need to be a first-class server feature in v1
- the intended archival operation is to stop the server, zip the configured `data_dir`, and then start fresh
- operational cleanup inside the server is still in scope via explicit deletion, tombstones, tombstone expiry, and vacuum

## Implementation stack

The intended implementation stack for ProxyLens Server is:

- `uv` for project and dependency management
- `justfile` as the only task runner interface for routine developer commands
- CPython `3.14.3` as the current latest stable Python baseline
- FastAPI `0.135.1` for the HTTP server and OpenAPI generation
- `scalar-fastapi` `1.8.1` for API reference UI
- `pytest` for testing
- `black` for code style formatting

Project and test layout rules:

- the server project lives under `server/` in this repository
- unit tests should live next to the source files they cover
- only integration tests should live under `server/tests/`
- integration tests should be kept to the minimum set needed to validate end-to-end behavior
- the default TDD loop should rely primarily on colocated unit tests

Developer task runner rules:

- routine project commands should be exposed through `just`
- the server project should provide `server/justfile`
- `server/justfile` should be the primary documented entry point for server development tasks
- the minimum required recipes are:
- `dev`: run the server in development mode with automatic reload or equivalent watch behavior
- `test`: run the test suite
- `test-watch`: rerun relevant tests in watch mode during development
- `style-check`: check formatting with `black --check`
- `style-fix`: apply formatting with `black`
- if additional tooling is added later, these recipes should remain stable

## Ingestion filters

ProxyLens Server should support optional ingestion-time filter scripts.

Goals:

- allow users to programmatically decide whether an event should be processed
- allow users to modify an incoming event before it is processed
- allow users to inspect the current captured request record, even if it is incomplete

Filter contract:

- a filter is loaded from a user-provided script file
- a filter receives:
- the server's `AppContainer` composition root
- the incoming event
- the current request record for that `request_id`, if one exists
- the filter returns either:
- a possibly modified event to continue processing
- `None` to drop the event

Minimal conceptual shape:

```python
def filter_event(
    app_container: AppContainer,
    event: CaptureEvent,
    request: CapturedRequestRecord | None,
) -> CaptureEvent | None:
    ...
```

The object made available to filters is the application container itself.
It does not need dedicated filter-only helper methods.
Filters may invoke lifecycle behavior through the container's wired use cases, for example:

- `app_container.delete_request_use_case.execute(...)`
- `app_container.delete_requests_use_case.execute(...)`
- `app_container.clear_tombstones_use_case.execute(...)`
- `app_container.vacuum_use_case.execute(...)`
- `app_container.clear_all_use_case.execute(...)`

Semantics:

- filters run before normal event processing
- filters may inspect incomplete request state
- filters may call lifecycle use cases through `app_container`
- filters may modify event payloads
- if the filter returns `None`, the event is considered dropped and must not be processed further
- if the filter returns an event, that returned value is what enters normal validation and processing
- filter execution should not bypass tombstone checks, ordering checks, or other server invariants
- if a filter deletes the current `request_id` and still returns an event for that same `request_id`, normal processing should reject it because the tombstone check still applies
- if a filter deletes the current `request_id` and wants to suppress the event entirely, it should return `None`

## Canonical identity model

ProxyLens Server must distinguish traces from requests.

### Trace identity

Cross-hop lineage is carried by hop-chain metadata:

```text
X-ProxyLens-HopChain: <shared_trace_ulid>@<node_name1>,<node_name2>,...
```

Semantics:

- `trace_id` is a ULID shared across multiple related requests that belong to the same end-to-end trace
- node names represent the observed hop path
- the server should parse hop-chain metadata into `trace_id` and an ordered hop list

### Request identity

Per-request identity is carried by request metadata:

```text
X-ProxyLens-RequestId: <request_ulid>
```

Semantics:

- `request_id` is a ULID unique for one concrete request observed at one hop
- request ids are not propagated across hops
- all events for one request record must share the same `request_id`
- the server must treat `request_id` as the primary key for record updates
- payload contents must never be used to decide whether two request ids represent the same request

## HTTP API contract

ProxyLens Server should expose a resource-oriented HTTP API.

Path rules for this spec:

- do not include a version segment in the path
- use plural resource names where practical
- treat requests as the primary readable resource hierarchy
- expose machine-readable OpenAPI at `/openapi.json` and `/openapi.yaml`
- expose Scalar UI at `/scalar`
- `/openapi.yaml` and `/scalar` should be served as utility routes but excluded from the generated OpenAPI schema

Recommended v1 endpoint surface:

- `PUT /blobs/{blob_id}`
- `POST /events`
- `GET /openapi.json`
- `GET /openapi.yaml`
- `GET /scalar`
- `GET /requests`
- `DELETE /requests`
- `GET /requests/histogram`
- `GET /requests/{request_id}`
- `DELETE /requests/{request_id}`
- `GET /requests/{request_id}/events`
- `GET /requests/{request_id}/body`
- `GET /requests/{request_id}/response`
- `GET /requests/{request_id}/response/body`

## Ingestion contract

Producers should send capture data to ProxyLens Server through the write-side HTTP API.

Blob upload contract:

- `blob_id` is generated by the producer and must be a ULID
- the request body is streamed binary content
- the server should store the uploaded content as the blob identified by `blob_id`
- uploading the same `blob_id` with identical content may be treated as idempotent
- uploading the same `blob_id` with different content must be rejected

Recommended blob upload response shape:

```json
{
  "blob_id": "01K0BLOBEXAMPLE000000000000",
  "status": "accepted"
}
```

Request body:

```json
{
  "events": [
    {
      "type": "http_request_started",
      "request_id": "01K0REQUESTEXAMPLE0000000000",
      "event_index": 0,
      "node_name": "proxy-a",
      "hop_chain": "01K0TRACEEXAMPLE000000000000@edge-a,proxy-a",
      "payload": {
        "method": "POST",
        "url": "https://example.test/widgets",
        "http_version": "HTTP/1.1",
        "headers": [["content-type", "application/json"]]
      }
    }
  ]
}
```

Binary-carrying events should reference previously uploaded blobs by `blob_id` instead of embedding large payloads inline.

Server expectations:

- events may arrive one at a time or batched
- batched events may span multiple request ids
- event order is authoritative only within the same `request_id`
- the server must validate that `event_index` is monotonic per `request_id`
- the server should reject malformed events with clear validation errors
- identity is determined by `trace_id`, `request_id`, and `event_index`, not by payload similarity

Timestamp rules:

- the server should assign canonical server-side timestamps when persisting accepted events and request-record updates
- request querying should not depend on producer-specific timestamps
- request histogram and summary filtering should use the request record's `captured_at` timestamp
- timestamp values exposed by the API should use RFC 3339 in UTC

Recommended response shape:

```json
{
  "results": [
    {
      "request_id": "01K0REQUESTEXAMPLE0000000000",
      "event_index": 0,
      "status": "accepted"
    }
  ]
}
```

Per-event statuses:

- `accepted`: the event was valid and applied during this request
- `ignored`: the event was already applied earlier and reapplying it would have no effect
- `deferred`: the event is valid but cannot be applied yet, usually because one or more earlier events for the same `request_id` have not been applied
- `dropped`: the event was intentionally dropped by an ingestion filter and was not processed further
- `rejected`: the event is invalid, conflicts with already-applied state, or cannot be processed safely

Batch-level status rules for v1:

- if any event is `rejected`, the server should return non-2xx for the batch
- if all events are `accepted`, `ignored`, `deferred`, or `dropped`, the server should return 2xx
- if the request body is structurally valid and the batch reaches event processing, the response body should include per-event results so the producer can distinguish applied, duplicate, deferred, and dropped outcomes
- if the request body fails framework-level request validation before event processing begins, the server may return a normal validation error response instead of per-event results

Deleted-request rule:

- if an event targets a `request_id` that was explicitly deleted earlier, that event must be `rejected`
- the server must not silently recreate a deleted request record from later events
- filters still run before normal processing, so a filter may drop such an event before the processing stage reaches the tombstone check

## Query contract

ProxyLens Server should provide lightweight read APIs in addition to ingestion.

### Request histogram endpoint

Purpose:

- return request counts over time for lightweight timeline views
- operate on request records, not raw events
- bucket by the request record's `captured_at` timestamp
- support progressive zooming by querying narrower time windows with finer bucket sizes

HTTP shape:

- `GET /requests/histogram`

Recommended query parameters:

- `captured_after`
- `captured_before`
- `bucket`
- `max_points`

Time-range semantics:

- only `captured_after` means requests with `captured_at > captured_after`
- only `captured_before` means requests with `captured_at < captured_before`
- both means requests with `captured_after < captured_at < captured_before`

Recommended histogram response shape:

```json
{
  "bucket": "minute",
  "captured_after": "2026-03-21T10:00:00Z",
  "captured_before": "2026-03-21T11:00:00Z",
  "points": [
    {"timestamp": "2026-03-21T10:00:00Z", "request_count": 4},
    {"timestamp": "2026-03-21T10:01:00Z", "request_count": 7}
  ]
}
```

Recommended v1 behavior:

- support coarse buckets such as `minute` and `hour`
- support finer buckets such as `second` for narrower windows when the caller is zooming in
- default to a lightweight bucket size if the caller does not specify one
- allow callers to request a finer bucket for a narrower time range without changing the endpoint shape
- the server may choose a coarser effective bucket when the requested range and `max_points` would otherwise produce an excessively dense result
- the response should include the effective bucket that was actually used
- only return counts, not request payloads

Zooming semantics:

- clients should zoom by narrowing `captured_after` and `captured_before`
- clients may request a finer `bucket` for the narrower window
- `max_points` lets the client express an upper bound on result density for timeline rendering
- if the caller omits `bucket`, the server should choose one based on the requested range and `max_points`

### Request summary endpoint

Purpose:

- return lightweight request summaries for list and filter views
- avoid resolving bodies, chunk payloads, or full websocket message payloads

HTTP shape:

- `GET /requests`

Recommended query parameters:

- `captured_after`
- `captured_before`
- `trace_ids`
- `request_ids`
- `node_names`
- `methods`
- `url_contains`
- `status_codes`
- `complete`
- `request_complete`
- `response_complete`
- `limit`
- `offset`

Time-range semantics:

- only `captured_after` means requests with `captured_at > captured_after`
- only `captured_before` means requests with `captured_at < captured_before`
- both means requests with `captured_after < captured_at < captured_before`

Completion filter semantics:

- `complete` filters by the overall terminal request-record state
- `request_complete` filters by whether request capture is complete
- `response_complete` filters by whether response capture is complete
- callers may combine these filters

Multi-value filter semantics:

- `trace_ids`, `request_ids`, `node_names`, `methods`, and `status_codes` should accept arrays
- a request matches one of these filters when its value is contained in the provided array
- when multiple filter fields are provided, the server should combine them with logical `AND`
- within one multi-value filter, the server should combine values with logical `OR`

Recommended summary response shape:

```json
{
  "requests": [
    {
      "request_id": "01K0REQUESTEXAMPLE0000000000",
      "trace_id": "01K0TRACEEXAMPLE000000000000",
      "node_name": "proxy-a",
      "hop_chain": "01K0TRACEEXAMPLE000000000000@edge-a,proxy-a",
      "captured_at": "2026-03-21T10:15:00Z",
      "updated_at": "2026-03-21T10:15:02Z",
      "request_method": "POST",
      "request_url": "https://example.test/widgets",
      "request_http_version": "HTTP/1.1",
      "request_headers": [["content-type", "application/json"]],
      "response_status_code": 201,
      "response_http_version": "HTTP/1.1",
      "response_headers": [["content-type", "application/json"]],
      "request_complete": true,
      "response_complete": true,
      "websocket_open": false,
      "error": null
    }
  ]
}
```

Summary endpoint rules:

- the response should stay lightweight enough for list views and polling
- body blobs, body bytes, chunk lists, and websocket message payloads must not be included
- summary rows may include headers and other small metadata fields needed for filtering or recognition
- large or optional nested state should be reserved for the detail endpoint

### Request detail endpoint

Purpose:

- return the fuller accumulated request record for one `request_id`
- resolve heavier request state only when explicitly requested

HTTP shape:

- `GET /requests/{request_id}`

Recommended detail response contents:

- all summary fields
- request and response trailer fields
- request and response body blob references and sizes
- websocket message metadata and payload references
- any materialized body references maintained by the server
- enough information for the caller to fetch or interpret heavier stored payloads

Detail endpoint rules:

- the detail endpoint may include large metadata fields that the summary endpoint omits
- large binary payloads should still be referenced by `blob_id` rather than forced inline
- if the server later supports inline decoding for small textual bodies, that behavior should remain detail-only

### Request events endpoint

Purpose:

- expose the ordered event stream for one request for debugging, inspection, or replay-oriented tooling

HTTP shape:

- `GET /requests/{request_id}/events`

Endpoint rules:

- events should be returned in `event_index` order
- the endpoint should expose the persisted event facts, not a re-expanded request record
- this endpoint is for one request only and should be keyed by `request_id`

### Request body endpoint

Purpose:

- return the currently resolved request body for one request only when explicitly requested

HTTP shape:

- `GET /requests/{request_id}/body`

Endpoint rules:

- the server may serve a materialized body directly or reconstruct it from stored chunks
- if no request body is known for the request, the endpoint should return `404`
- when the original request `content-type` header is known, the server should use it as the response `Content-Type` for this endpoint
- if the original request `content-type` header is not known, the server may omit `Content-Type` or fall back to a safe generic type such as `application/octet-stream`
- this endpoint exists so list and summary endpoints do not need to inline body data

### Response detail endpoint

Purpose:

- return the response-specific portion of one request record without forcing the caller to fetch the whole request detail shape

HTTP shape:

- `GET /requests/{request_id}/response`

Endpoint rules:

- the response should include status, response headers, response trailers when known, completion state, and body metadata
- the response must stay scoped to the response side of the same `request_id`

### Response body endpoint

Purpose:

- return the currently resolved response body for one request only when explicitly requested

HTTP shape:

- `GET /requests/{request_id}/response/body`

Endpoint rules:

- the server may serve a materialized response body directly or reconstruct it from stored chunks
- if no response body is known for the request, the endpoint should return `404`
- when the original response `content-type` header is known, the server should use it as the response `Content-Type` for this endpoint
- if the original response `content-type` header is not known, the server may omit `Content-Type` or fall back to a safe generic type such as `application/octet-stream`
- this endpoint exists so list and summary endpoints do not need to inline response body data

## Persistence architecture

ProxyLens Server should use:

- a SQLite database for structured metadata
- a filesystem-backed blob store for uploaded request/response chunks, materialized bodies, and binary websocket payloads

The persistence root directory must be configurable.
Call this configured path `data_dir`.

Recommended layout:

```text
<data_dir>/
├── proxylens_server.db
└── blobs/
    ├── <blob-ulid-1>
    ├── <blob-ulid-2>
    └── ...
```

Rules:

- both the SQLite database file and blob store must live under the configured `data_dir`
- each persisted binary blob must have a ULID `blob_id`
- each blob file should be stored at `blobs/<blob_id>` under `data_dir`
- blob file location must be derived by convention from `blob_id`; it should not be stored separately in SQLite
- producers may upload blobs before sending events that reference them
- a blob reference in SQLite should include at least:
- `blob_id`
- `size_bytes`
- `content_type` when known
- chunk blobs and materialized full-body blobs may both exist
- v1 may choose either:
- store chunk blobs only and reconstruct full bodies from events when needed
- store chunk blobs and optionally materialize consolidated request or response body blobs later

Recommended write discipline:

- write blob content to a temporary file first
- atomically rename it to the final blob path
- commit the corresponding SQLite transaction only after the blob file is durable enough for the deployment target

SQLite connection and transaction discipline:

- use short-lived SQLite connections for ordinary repository operations instead of one process-global shared connection
- use explicit transactions for multi-step write operations such as event application, request deletion, and clear-all flows
- the current implementation uses `BEGIN IMMEDIATE` for those explicit write transactions
- every SQLite connection should be configured with:
- `PRAGMA journal_mode = WAL`
- `PRAGMA synchronous = NORMAL`
- `PRAGMA cache_size = 10000`
- `PRAGMA temp_store = MEMORY`
- `PRAGMA foreign_keys = ON`
- `PRAGMA mmap_size = 268435456`

Recommended SQLite tables:

- `requests`
- `events`
- `deferred_events`
- `blobs`
- `deleted_requests`

Suggested table responsibilities:

- `requests` stores one row per `request_id` with consolidated request-level state
- `events` stores one row per accepted event with `request_id`, `event_index`, event type, structured metadata, and optional `blob_id`
- `deferred_events` stores out-of-order but otherwise valid events that are waiting for earlier indices for the same `request_id`
- `blobs` stores one row per uploaded or materialized blob with ULID-keyed blob metadata
- `deleted_requests` stores tombstones for explicitly deleted `request_id` values

Possible blob row shape:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class BlobRef:
    blob_id: str
    size_bytes: int
    content_type: str | None = None
```

Dataclass note:

- `@dataclass` is used here as a compact way to describe structured server state
- `slots=True` means only the declared fields may exist on the object; that keeps memory use lower and prevents accidental typo-fields
- these dataclasses are illustrative schema shapes, not a requirement that the implementation store data in Python objects exactly this way

## Data lifecycle and deletion

ProxyLens Server should make destructive cleanup easy and explicit.

Required capabilities:

- delete one or more specific requests by `request_id`
- clear all captured state and start fresh
- clear tombstones explicitly
- run routine vacuum that cleans up completed requests, expired tombstones, and unreferenced known blobs
- cascade deletion to event rows, blob references, and blob files that are no longer referenced

HTTP lifecycle shape:

- `DELETE /requests`
- `DELETE /requests/{request_id}`

Delete endpoint intent:

- `DELETE /requests/{request_id}` deletes one request idempotently
- `DELETE /requests` deletes a matching set of requests, typically selected by query filters
- the bulk delete endpoint should support the same lightweight filtering dimensions as `GET /requests` where practical
- both delete endpoints must apply the same tombstone and blob-cleanup rules
- delete endpoints do not need to return a response body
- delete endpoints should return `202 Accepted` when deletion was accepted
- delete endpoints should return `404 Not Found` when the targeted request or filtered request set does not exist

Programmatic lifecycle exposure:

- the current implementation wires lifecycle behavior as use cases on the application container
- code that needs programmatic lifecycle access should call those use cases directly rather than depending on a separate facade layer

Behavior:

- deleting a request must be idempotent
- deleting a request must remove request metadata, event rows, pending deferred state, and unreferenced blob files for that request
- deleting a request must leave behind a tombstone for its `request_id`
- `clear_all` should remove all request records, events, blob metadata, pending deferred state, and blob files
- `clear_all` should also remove tombstones so the system can truly start fresh
- request deletion must be transactional with respect to SQLite metadata
- blob-file cleanup should leave no unreferenced files behind once deletion completes successfully

Deleted-request tombstones:

- when a request is explicitly deleted, the server should persist a tombstone for its `request_id`
- tombstones are used to reject later events for request ids that were intentionally deleted
- tombstones should survive normal request-data deletion
- tombstones should have an adjustable timeout, for example 10 minutes
- completed requests deleted by vacuum should also produce tombstones
- tombstones may be cleared explicitly through the lifecycle API
- expired tombstones should be removed by vacuum
- `clear_all` should clear tombstones as well, because the user explicitly asked to start fresh

Possible tombstone row shape:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class DeletedRequestTombstone:
    request_id: str
    deleted_at: str
    expires_at: str
```

Vacuum semantics:

- vacuum should be safe to run routinely
- vacuum may delete completed requests according to retention policy
- when vacuum deletes a completed request, it must delete all dependent rows and unreferenced blob files and create a tombstone for that `request_id`
- vacuum should remove expired tombstones
- vacuum should remove unreferenced blobs that are still known in blob metadata after metadata cleanup

## Request record model

ProxyLens Server should maintain a request record keyed by `request_id`.

Meaning of the main request-record fields:

- `request_id`: ULID for the concrete observed request at one hop
- `trace_id`: ULID shared across related requests in the same trace
- `hop_chain`: raw propagated hop-chain value used to relate the request to a trace
- `hop_nodes`: parsed node names extracted from `hop_chain`
- `node_name`: the local node that observed and emitted events for this request
- `captured_at`: server-assigned timestamp when the request record was first created
- `updated_at`: server-assigned timestamp of the latest accepted event that changed the request record
- `completed_at`: server-assigned timestamp when the record became terminal, if known
- `request_*`: accumulated request-side state
- `response_*`: accumulated response-side state
- `websocket_*`: accumulated websocket lifecycle and message state when the request upgrades
- `error`: error information associated with the request, if any
- `complete`: overall terminal status for the request record

Dataclass note:

- `slots=True` is used for the same reason as above: explicit fields only, lower overhead, and typo resistance
- `CapturedRequestRecord` is intentionally not `frozen=True` in this example because the server conceptually updates it as events are applied
- an implementation may still choose immutable internal state and replace whole records instead of mutating them in place

Possible shape:

```python
from dataclasses import dataclass


@dataclass(slots=True)
class CapturedRequestRecord:
    request_id: str
    trace_id: str
    hop_chain: str
    hop_nodes: tuple[str, ...]
    node_name: str
    captured_at: str
    updated_at: str
    completed_at: str | None = None
    request_method: str | None = None
    request_url: str | None = None
    request_http_version: str | None = None
    request_headers: tuple[tuple[str, str], ...] = ()
    request_body_size: int = 0
    request_body_blob_id: str | None = None
    request_trailers: tuple[tuple[str, str], ...] = ()
    request_started: bool = False
    request_complete: bool = False
    response_status_code: int | None = None
    response_http_version: str | None = None
    response_headers: tuple[tuple[str, str], ...] = ()
    response_body_size: int = 0
    response_body_blob_id: str | None = None
    response_trailers: tuple[tuple[str, str], ...] = ()
    response_started: bool = False
    response_complete: bool = False
    websocket_open: bool = False
    websocket_messages: tuple["WebSocketMessageEvent", ...] = ()
    error: str | None = None
    complete: bool = False
```

Normalization rules:

- `trace_id`, `hop_chain`, `hop_nodes`, `node_name`, and `request_id` belong to the request record
- `captured_at` is the canonical server-assigned timestamp when the request record was first created
- `updated_at` is the canonical server-assigned timestamp of the latest accepted event that changed the request record
- `completed_at` should be set when the server determines the request record is terminal
- the ingestion event schema may repeat `node_name` and `hop_chain` for self-contained validation and storage, but the canonical accumulated state lives on the request record
- request and response bodies should be accumulated logically by applying chunk events in order
- the request record should reference persisted body blobs by `blob_id` instead of embedding large binary payloads inline
- trailers should be stored separately from headers
- `complete` should reflect whether the request record is terminal for the server's purposes
- consolidation must be deterministic and idempotent with respect to duplicate delivery of the same event

The query APIs should project this canonical request record into two shapes:

- a lightweight request summary shape for `GET /requests`
- a fuller request detail shape for `GET /requests/{request_id}`

## Capture event model

The server owns the canonical event schema.

Meaning of the shared event-context fields:

- `event_index`: request-local ordering key used to apply events deterministically
- `request_id`: ULID of the request record this event belongs to
- `node_name`: node that observed this event
- `hop_chain`: trace lineage metadata carried alongside the request

Dataclass note:

- event dataclasses use `slots=True, frozen=True`
- `slots=True` keeps the event shape explicit and compact
- `frozen=True` means events are immutable after creation, which matches the intent that events are append-only facts rather than mutable state
- this distinction is intentional: events are immutable facts, while the accumulated request record is mutable or replaceable derived state

Possible shape:

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True, frozen=True)
class CaptureContext:
    event_index: int
    request_id: str
    node_name: str
    hop_chain: str


@dataclass(slots=True, frozen=True)
class HttpRequestStartedEvent:
    context: CaptureContext
    method: str
    url: str
    http_version: str
    headers: tuple[tuple[str, str], ...]


@dataclass(slots=True, frozen=True)
class HttpRequestBodyEvent:
    context: CaptureContext
    blob_id: str
    size_bytes: int
    complete: bool


@dataclass(slots=True, frozen=True)
class HttpRequestTrailersEvent:
    context: CaptureContext
    trailers: tuple[tuple[str, str], ...]


@dataclass(slots=True, frozen=True)
class HttpRequestCompletedEvent:
    context: CaptureContext


@dataclass(slots=True, frozen=True)
class HttpResponseStartedEvent:
    context: CaptureContext
    status_code: int
    http_version: str
    headers: tuple[tuple[str, str], ...]


@dataclass(slots=True, frozen=True)
class HttpResponseBodyEvent:
    context: CaptureContext
    blob_id: str
    size_bytes: int
    complete: bool


@dataclass(slots=True, frozen=True)
class HttpResponseTrailersEvent:
    context: CaptureContext
    trailers: tuple[tuple[str, str], ...]


@dataclass(slots=True, frozen=True)
class HttpResponseCompletedEvent:
    context: CaptureContext


@dataclass(slots=True, frozen=True)
class WebSocketStartedEvent:
    context: CaptureContext
    url: str
    http_version: str
    headers: tuple[tuple[str, str], ...]


@dataclass(slots=True, frozen=True)
class WebSocketMessageEvent:
    context: CaptureContext
    direction: Literal["client_to_server", "server_to_client"]
    payload_type: Literal["text", "binary"]
    payload_text: str | None = None
    blob_id: str | None = None
    size_bytes: int | None = None


@dataclass(slots=True, frozen=True)
class WebSocketEndedEvent:
    context: CaptureContext
    close_code: int | None


@dataclass(slots=True, frozen=True)
class RequestErrorEvent:
    context: CaptureContext
    message: str
```

```python
type CaptureEvent = (
    HttpRequestStartedEvent
    | HttpRequestBodyEvent
    | HttpRequestTrailersEvent
    | HttpRequestCompletedEvent
    | HttpResponseStartedEvent
    | HttpResponseBodyEvent
    | HttpResponseTrailersEvent
    | HttpResponseCompletedEvent
    | WebSocketStartedEvent
    | WebSocketMessageEvent
    | WebSocketEndedEvent
    | RequestErrorEvent
)
```

Event rules:

- each event must include `request_id`, `event_index`, `node_name`, and `hop_chain`
- events must be append-only facts
- events should never require the client to resend the full accumulated request record
- event payloads should only contain the new information learned at that step
- two events with different `request_id`s must always be treated as belonging to different requests, regardless of payload equality
- events for tombstoned `request_id` values must be rejected
- events that reference `blob_id` values must only reference blobs that already exist in ProxyLens Server

Persistence mapping rules:

- producers upload binary payloads separately through the blob upload API
- events should reference uploaded blobs by `blob_id` instead of carrying large binary payloads inline
- chunk events in SQLite should reference `blob_id` values instead of embedding large binary payloads inline
- blob lookup should resolve on-disk content by joining `data_dir / "blobs" / blob_id`
- textual metadata such as methods, URLs, status codes, headers, trailers, and error messages should remain in SQLite
- binary websocket messages should be represented by blob references
- text websocket messages should remain inline in SQLite in v1

## Event application rules

The server should apply events to the request record deterministically.

### Ordering

- `event_index` must be strictly increasing per `request_id`
- the server may reject out-of-order events
- alternatively, the server may mark an out-of-order but otherwise valid event as `deferred` and hold it until missing earlier events arrive
- the server should apply events idempotently per `request_id` and `event_index`
- if the same event is delivered twice for the same `request_id` and `event_index`, reapplying it must not change the final request record
- if the server later supports retries, it may accept duplicate already-applied events only when they are byte-for-byte identical

Status interpretation:

- identical duplicate event: `ignored`
- conflicting duplicate event: `rejected`
- valid but out-of-order event that the server chooses to buffer: `deferred`
- filter-returned `None`: `dropped`
- valid and newly applied event: `accepted`
- any event for an explicitly deleted `request_id`: `rejected`

Deferred-event handling:

- a deferred event must not mutate the request record yet
- the server should persist enough pending state to retry applying deferred events later
- when missing earlier events arrive, the server should retry deferred events for that `request_id` in `event_index` order
- if a deferred event later becomes contradictory or invalid, the server may mark it rejected during retry processing

### Request-side merge rules

- `HttpRequestStartedEvent` initializes request metadata
- `HttpRequestBodyEvent` records the referenced blob in event storage and updates request-body aggregate metadata only if that event has not already been applied
- `HttpRequestBodyEvent.complete=True` marks the request body stream complete, but does not by itself imply the entire request record is complete
- `HttpRequestTrailersEvent` sets `request_trailers`
- `HttpRequestCompletedEvent` marks request transmission complete

### Response-side merge rules

- `HttpResponseStartedEvent` initializes response metadata
- `HttpResponseBodyEvent` records the referenced blob in event storage and updates response-body aggregate metadata only if that event has not already been applied
- `HttpResponseBodyEvent.complete=True` marks the response body stream complete
- `HttpResponseTrailersEvent` sets `response_trailers`
- `HttpResponseCompletedEvent` marks response transmission complete

### WebSocket merge rules

- `WebSocketStartedEvent` marks `websocket_open=True`
- `WebSocketMessageEvent` appends to the ordered message list only if that event has not already been applied, using inline text payloads or referenced binary blobs depending on `payload_type`
- `WebSocketEndedEvent` marks `websocket_open=False`

### Error rules

- `RequestErrorEvent` sets `error`
- an error may coexist with partial request or response data already accumulated
- the server may mark the request record terminal when an error event arrives

## Trace reconstruction

The server must reconstruct traces from request records, not directly from events.

Suggested approach:

- parse `trace_id` and hop nodes from `hop_chain`
- group request records by `trace_id`
- sort or organize records using hop order plus request start time once timestamps are added later

This keeps events request-scoped and avoids mixing trace-level and request-level abstractions.

## Compatibility constraints

The server contract should remain producer-independent.

- the server may accept any valid capture event payload that conforms to this contract
- individual producers may implement only a subset of the contract initially
- producer-specific limitations should be documented in producer-specific specs, not in this document
- the current mitmproxy producer profile is defined in [mitmproxy_addon/docs/spec.md](../../mitmproxy_addon/docs/spec.md)

## Test strategy

### Unit tests

Focus on pure server logic:

- payload validation
- hop-chain parsing
- trace-id extraction
- request-record merge rules
- filter-script decision behavior
- filter-script lifecycle API usage
- blob path generation and relative-path validation
- out-of-order event rejection
- duplicate-event handling policy
- deferred-event buffering and replay policy
- tombstone timeout and vacuum policy

### Integration tests

Focus on end-to-end ingestion and storage behavior:

- expose OpenAPI JSON at `/openapi.json`
- expose OpenAPI YAML at `/openapi.yaml`
- serve Scalar UI at `/scalar`
- upload a blob through `/blobs/{blob_id}` and then reference it from an event
- post events through `/events`
- ingest one event and create a request record
- ingest ordered request and response events and produce the expected final record
- persist chunk payloads as blob files under the data directory and store `blob_id` references in SQLite
- ingest websocket lifecycle and message events
- reject malformed events
- reject out-of-order events for the same request
- optionally defer out-of-order but otherwise valid events and apply them later when missing earlier events arrive
- drop events through filters before processing
- mutate events through filters before processing
- invoke deletion or vacuum through the `app_container` object exposed to filters
- group multiple request records under the same trace id via hop chain
- list lightweight request summaries through `GET /requests`
- query a request histogram through `GET /requests/histogram`
- fetch a request's ordered event stream through `GET /requests/{request_id}/events`
- query request histograms over `captured_at` with supported bucket sizes
- query lightweight request summaries with `captured_after`, `captured_before`, and combined between-style filtering
- fetch request details and verify heavier state is excluded from summaries but available in detail responses
- fetch request and response bodies only through their dedicated body endpoints
- delete requests idempotently and verify dependent rows and blob files are removed
- clear all state and verify the database and blob directory are empty of captured data
- clear tombstones explicitly
- vacuum completed requests, expired tombstones, and unreferenced known blobs
- reject later events for tombstoned request ids

## Definition of done

ProxyLens Server is realized when all of the following are true:

- the project is managed with `uv`
- the server project lives under `server/`
- `server/justfile` is present and is the primary task-runner interface
- the runtime baseline is CPython `3.14.3`
- FastAPI `0.135.1` is used for the HTTP API
- `scalar-fastapi` `1.8.1` is used to serve the API reference UI
- `black` is used for code formatting
- unit tests live next to the source files they cover
- only integration tests live under `server/tests/`
- integration tests are kept minimal and focused on end-to-end behavior
- `just dev` runs the server in development mode with reload or equivalent watch behavior
- `just test` runs the tests
- `just test-watch` reruns tests in watch mode
- `just style-check` checks formatting with `black --check`
- `just style-fix` applies formatting with `black`
- the blob upload API accepts streamed binary uploads keyed by client-generated `blob_id`
- events that reference missing blobs are rejected
- the ingestion API accepts valid capture events
- the OpenAPI spec is exposed at `/openapi.json`
- the OpenAPI spec is also exposed at `/openapi.yaml`
- Scalar UI is exposed at `/scalar`
- `/openapi.yaml` and `/scalar` are not included as paths in the generated OpenAPI schema
- the query API exposes lightweight request histograms over time
- the query API exposes lightweight filtered request summaries
- the detail API exposes heavier request state on demand
- invalid event payloads are rejected with clear errors
- SQLite is used for metadata persistence
- the persistence root `data_dir` is configurable
- request/response chunks or materialized bodies are stored as file-backed blobs under the configured `data_dir`
- SQLite stores blob references by `blob_id`, and blob file paths are derived by convention from that id
- request records are created and updated by applying events in order
- request and response bodies are accumulated logically from chunk events
- request and response trailers are stored when available
- websocket lifecycle and messages are stored correctly
- request summaries omit bodies, chunk payloads, and websocket message payloads
- request details include body/blob references and other heavier request state without forcing binary data inline
- per-event ingestion results distinguish `accepted`, `ignored`, `deferred`, `dropped`, and `rejected`
- deferred events can be retried and later applied in order
- filter scripts can inspect the current request record, mutate events, or drop them by returning `None`
- filter scripts can invoke lifecycle use cases through the `AppContainer` passed to them during filtering
- requests can be deleted idempotently with full metadata and blob cleanup
- tombstones can be cleared explicitly
- vacuum can remove completed requests, create tombstones, and clean up expired tombstones
- all captured state can be cleared to start fresh
- events for explicitly deleted request ids are rejected
- request records can be grouped into traces using hop-chain metadata
- producer-specific specs reference this document as the source of truth for event and request-record contracts
