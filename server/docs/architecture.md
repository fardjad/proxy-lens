# Architecture spec

## Goal

This document defines the architectural rules for the server implementation in `server/`.

The target style is:

- simple hexagonal architecture
- light DDD where it helps clarify ownership
- no unnecessary framework-shaped abstraction layers
- no generic shared model buckets

The point is to keep the codebase easy to navigate and hard to muddle.

## Core principles

- Keep the architecture simple. Prefer clear ownership over clever indirection.
- Put code where it naturally belongs instead of introducing shared "utility" files that become dumping grounds.
- The direction of dependency should stay obvious:
- routes depend on use cases
- use cases depend on repository interfaces and other use cases when necessary
- persistence depends on SQLite/filesystem details
- domain stays isolated from infrastructure concerns
- If a concept belongs to one layer, define it in that layer rather than in a cross-cutting shared file.

## Project structure

The intended structure under `server/src/proxylens_server/` is:

- `domain/`
- `use_cases/`
- `infra/routes/`
- `infra/persistence/`
- `infra/filters/`
- `app.py`
- `bootstrap.py`

## Domain rules

The domain layer should stay small and plain.

- Domain entities should represent the real concepts in this server.
- The important entities are:
- `Request`
- `Event`
- The relationship between them is:
- a request is uniquely identified by `request_id`
- an event is uniquely identified by request-local identity plus event identity
- a request can have multiple events
- the request-event relationship includes ordering within that request

Domain code must not contain infrastructure concerns.

- No SQLite details
- No HTTP details
- No Pydantic DTOs
- No JSON serialization helpers
- No generic filtering/query objects
- No external-dependency-heavy helpers unless there is a very strong reason

In practice, the domain should be plain Python objects and small domain errors only.

## Use case rules

Use cases are the application layer.

- Put use cases under `use_cases/`
- Use one file per use case
- Examples:
- `upload_blob.py`
- `ingest_events.py`
- `list_requests.py`
- `get_request.py`
- `delete_request.py`

Each use case file should own:

- its input contract
- its output contract
- its `execute(...)` implementation

Use case contract rules:

- If an input model belongs to one use case, define it in that use case file.
- If an output model belongs to one use case, define it in that use case file.
- Do not move use-case-specific contracts into generic shared files like `models.py`.

Use case dependency rules:

- A use case may depend on repository interfaces.
- A use case may depend on another use case when it is genuinely application orchestration.
- A use case must not depend on route DTOs.
- A use case must not depend on persistence-specific row models unless it is explicitly mapping from repository returns.

Filtering rule:

- Query/filter parsing should not become a domain concept.
- If a route accepts filter parameters, it should pass the relevant values into the use case input contract.

## Route rules

- HTTP endpoints live under `infra/routes/`
- Use one resource directory per resource area
- Each resource directory should contain:
- `router.py`
- `dtos.py`

Route dependency rules:

- `router.py` may depend on use cases
- `dtos.py` should define HTTP request/response DTOs only
- Route DTOs are responsible for HTTP boundary validation and serialization
- Route DTOs should not become generic shared schemas for the rest of the app

## Persistence rules

Persistence code lives under `infra/persistence/`.

- Repository implementations belong under `infra/persistence/repositories/`
- Use one repository per file
- If a repository interface or protocol is needed, define it in the same file as that repository

Persistence ownership rules:

- SQLite row mapping belongs in persistence
- filesystem/blob storage concerns belong in persistence
- persistence-local records belong in persistence
- persistence serialization and deserialization belong in persistence

Persistence code must not push its internal shapes upward as generic app-wide models.

- Repositories may return persistence-local records
- Use cases should map those records into use-case outputs when needed
- Route DTOs should map from use-case outputs, not from persistence models

## Filter rules

Ingestion-time filtering belongs to infrastructure.

- Filter loading and execution belong in `infra/filters/`

The current filter contract shape is conceptually:

```python
def filter_event(app_container, event, request):
    ...
```

## Composition root rules

- `bootstrap.py` is the composition root
- `AppContainer` holds the wired repositories, filter runner, and use cases
- `app.py` creates the container and wires the HTTP app to it

## Shared-model anti-pattern

Do not create a generic shared schema file like `models.py` for unrelated concepts.

A model should live next to the layer that owns it:

- domain entity -> `domain/`
- use-case input/output -> that use case file
- route request/response DTO -> route `dtos.py`
- persistence record -> persistence repository file

The same rule applies to enums.

- If an enum belongs to an ingestion contract, keep it in that ingestion use case module.
- If an enum belongs to histogram behavior, keep it in the histogram use case module.
- Do not put unrelated enums into a generic shared enum bucket.

## Testing rules

Tests should follow ownership.

- Unit tests live next to the source file they cover
- Integration tests live under `server/tests/`

## Simplicity rules

When in doubt:

- prefer directness over indirection
- prefer colocated models over shared buckets
- prefer explicit names over generic names
- prefer one clear abstraction over two overlapping ones

The architecture should make it easy to answer:

- what layer owns this code?
- what data shape owns this model?
- what is the dependency direction?
- where should a new feature be added?

If the answer is fuzzy, the code is probably in the wrong place.
