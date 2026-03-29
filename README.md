# ProxyLens

> Proxy based traffic capture and visualization tool for development

ProxyLens is a traffic-capture toolkit for following requests across multiple
hops.

At a high level:

- producers capture HTTP and WebSocket traffic as ordered events
- the server stores those events as request-scoped records
- related requests are stitched into traces across hops
- the UI lets you inspect captured requests and view sequence-style flows

The repository is split by responsibility rather than by one monolithic app.

## Projects

- [`server/`](server/): FastAPI ingestion and
  query server. This is the system of record for the capture model and storage
  behavior.
- [`mitmproxy_addon/`](mitmproxy_addon/): Python
  mitmproxy addon that captures traffic, propagates ProxyLens headers, and
  forwards normalized events to the server.
- [`ui/`](ui/): Preact UI for browsing requests,
  inspecting details, and viewing sequence diagrams from server data.
- [`examples/`](examples/): end-to-end example
  stacks showing chained services with either manual `X-ProxyLens-*`
  propagation or OpenTelemetry propagation.

## Read Next

- Start with the server contract:
  [`server/docs/spec.md`](server/docs/spec.md)
- Then read the server overview:
  [`server/README.md`](server/README.md)
- For the mitmproxy producer behavior:
  [`mitmproxy_addon/docs/spec.md`](mitmproxy_addon/docs/spec.md)
- For addon setup and usage:
  [`mitmproxy_addon/README.md`](mitmproxy_addon/README.md)
- For runnable demos:
  [`examples/chained-apps-with-manual-propagation/README.md`](examples/chained-apps-with-manual-propagation/README.md)
  and
  [`examples/chained-apps-with-otel/README.md`](examples/chained-apps-with-otel/README.md)

## Repository Notes

- The top-level [`justfile`](justfile) wraps the PyPI release workflow for
  [`mitmproxy_addon/`](mitmproxy_addon/) only.
- [`server/`](server/) remains an in-repo project with its own local build and
  test commands, but it is not part of the PyPI release flow.
- Setup, run, and test commands live with each subproject and should be treated
  as the source of truth for that subproject.

## Docker

The repository now includes a root [`Dockerfile`](Dockerfile) with two useful
targets:

- `runtime`: builds the UI, packages the server source, installs the server,
  runs the API on port `8000`, and serves the UI on port `8080` through Caddy.
- `bundle`: produces a reusable `/proxy-lens` directory containing:
  - `ui/`: production-built static assets
  - `server/`: installable server source
  - `bin/set-ui-api-base-url.sh`: rewrites `ui/runtime-config.js` at runtime
  - `Caddyfile`: a minimal static-file + `/api` reverse-proxy config

Example:

```bash
docker build -t proxylens .
docker run --rm -p 8080:8080 -p 8000:8000 proxylens
```

Or with Docker Compose:

```bash
docker compose up --build
```

To publish the runtime image using the version from [`VERSION.txt`](VERSION.txt):

```bash
just publish pypi "<username>/proxylens"
```

That pushes both `<username>/proxylens:<version>` and
`<username>/proxylens:latest`.

### Reusing `/proxy-lens` From A Published Image

Every published runtime image also contains the reusable `/proxy-lens` bundle.
A downstream image can copy that directory directly instead of rebuilding this
repository.

Example downstream Dockerfile using `uv sync`, `gunicorn`, and Caddy:

```dockerfile
FROM python:3-slim

COPY --from=docker.io/fardjad/proxylens:0.0.0 /proxy-lens /proxy-lens
COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy

RUN pip install --no-cache-dir uv
WORKDIR /proxy-lens/server
RUN uv sync --no-dev
RUN uv add --frozen --no-sync gunicorn

ENV PROXYLENS_SERVER_PORT=8000
ENV PROXYLENS_SERVER_DATA_DIR=/data
ENV PROXYLENS_UI_PORT=8080

RUN mkdir -p /data

CMD ["/bin/sh", "-lc", "\
  /proxy-lens/bin/set-ui-api-base-url.sh && \
  uv run gunicorn 'proxylens_server.app:create_app()' \
    --bind 0.0.0.0:${PROXYLENS_SERVER_PORT} \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 & \
  caddy run --config /proxy-lens/Caddyfile --adapter caddyfile \
"]
```

What the bundle contains:

- `/proxy-lens/ui`: built static UI assets
- `/proxy-lens/server`: installable server source plus `uv.lock`
- `/proxy-lens/bin/set-ui-api-base-url.sh`: rewrites
  `/proxy-lens/ui/runtime-config.js`
- `/proxy-lens/Caddyfile`: serves the UI and proxies `/api/*` to the server

How it should be started:

- Run `uv sync --no-dev` in `/proxy-lens/server` to create the runtime
  environment from the bundled lockfile.
- Add any extra runtime-only packages you need, such as `gunicorn`.
- Start the Python server on `0.0.0.0:${PROXYLENS_SERVER_PORT}` with
  `uv run ...`.
- Serve `/proxy-lens/ui` through Caddy using `/proxy-lens/Caddyfile`.
- Run `/proxy-lens/bin/set-ui-api-base-url.sh` before starting Caddy if you
  want the browser to target a different API base URL.
- By default the script writes `window.location.origin + "/api"` into
  `runtime-config.js`, which matches the bundled Caddy config.
