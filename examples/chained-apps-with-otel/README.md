# Chain Apps With OpenTelemetry

This example demonstrates chained HTTPS calls across three services written in
different languages and instrumented with OpenTelemetry:

- `app1`: Node.js with Fastify and OpenTelemetry
- `app2`: C# with .NET 10 minimal APIs and OpenTelemetry
- `app3`: Python with Flask and OpenTelemetry

Topology:

```text
browser
  -> caddy["app1"]
  -> proxylens-addon["app1"]
  -> app1 (Fastify + OpenTelemetry)
  -> proxylens-addon["app1"]
  -> caddy["app2"]
  -> proxylens-addon["app2"]
  -> app2 (.NET 10 + OpenTelemetry)
  -> proxylens-addon["app2"]
  -> caddy["app3"]
  -> proxylens-addon["app3"]
  -> app3 (Flask + OpenTelemetry)
```

`app1` calls `app2` with Node's built-in `fetch()`, `app2` calls `app3` with
`.NET HttpClient`, and `app3` terminates the chain. The applications are kept
intentionally simple: they do not manually inspect or return trace headers, and
they rely on standard runtime proxy configuration through environment
variables.

- `app1` uses `HTTP_PROXY` and `HTTPS_PROXY` together with `NODE_USE_ENV_PROXY=1`
  and trusts both the local service certificate and the proxy MITM CA at
  container startup
- `app2` uses the default `.NET HttpClient` proxy behavior from
  `HTTP_PROXY` and `HTTPS_PROXY`, and its container trusts both the mounted
  localhost certificate and the proxy MITM CA before the app starts
- `app3` is just the terminal Flask service and does not make a downstream call

OpenTelemetry instrumentation still propagates `traceparent` through the chain
when standard trace headers already exist. When a request reaches the first
ProxyLens addon without `traceparent`, B3, or Jaeger headers, the addon now
creates a new shared ProxyLens trace id and synthesizes W3C `traceparent` and
`tracestate` before forwarding, so downstream OpenTelemetry instrumentation can
join the same trace automatically.

Because the ProxyLens addon now derives its shared trace id from standard trace
propagation headers, the full `app1 -> app2 -> app3` request chain should be
captured as one connected trace.

## What This Shows

- one request chain spanning Node.js, .NET, and Python services
- standard proxy configuration with `HTTP_PROXY` and `HTTPS_PROXY`
- automatic OpenTelemetry propagation without custom trace/header handling in
  application code
- idiomatic OpenTelemetry instrumentation for inbound Fastify, ASP.NET Core,
  and Flask requests
- idiomatic OpenTelemetry instrumentation for outbound Node `fetch()` via
  `undici` and `.NET HttpClient` calls
- ProxyLens stitching the full chain together from OpenTelemetry trace context

Each app response is intentionally small: it only reports the service name, a
simple message, and the nested downstream response when there is one.

## Start

From `examples/chained-apps-with-otel/`:

```bash
just start
```

`just start` generates a local self-signed `localhost` certificate in
`.data/tls/` if it does not already exist.

This starts:

- ProxyLens Server on `http://localhost:8000`
- the browser entrypoint on `https://localhost:8443`

## Use

1. Open `https://localhost:8443/` in your browser.
2. Accept the certificate warning.
3. The JSON response should show `app1`, the nested `app2` response, and the
   nested `app3` response.
4. In ProxyLens Server, expect one end-to-end trace covering the whole chain.

Useful server URLs:

- `http://localhost:8000/scalar`
- `http://localhost:8000/requests?limit=100`
- `http://localhost:8000/requests?limit=100&node_names=app1&node_names=app2&node_names=app3`

## Stop And Clean

```bash
just stop
just clean
```
