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
