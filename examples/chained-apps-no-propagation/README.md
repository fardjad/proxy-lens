# Chained Apps Without Header Propagation

This example demonstrates chained HTTPS calls where the applications are not
aware of `X-ProxyLens-*` headers and do not propagate them themselves.

Topology:

```text
browser
  -> caddy["app1"]
  -> proxylens-addon["app1"]
  -> app1
  -> proxylens-addon["app1"]
  -> caddy["app2"]
  -> proxylens-addon["app2"]
  -> app2
  -> proxylens-addon["app2"]
  -> caddy["app3"]
  -> proxylens-addon["app3"]
  -> app3
```

`app1` calls `caddy["app2"]` through its own ProxyLens addon sidecar.
`app2` then calls `caddy["app3"]` through its own ProxyLens addon sidecar.
None of the apps read, write, or forward `X-ProxyLens-*` headers directly.
All three addon instances run with
`max_concurrent_requests_per_host=1`.
This works for `app1` and `app2` because each inbound hop and downstream hop
target different hosts, so they do not share the same per-host concurrency
bucket.

## What This Shows

Because the applications do not propagate ProxyLens headers, the full
`app1 -> app2 -> app3` chain does not appear as one connected trace.

What you get instead:

- one trace for the browser request entering `app1`
- one separate trace for `app1 -> app2`
- one separate trace for `app2 -> app3`

The addon-side per-host concurrency limit makes the sequence diagrams easier to
read, but it does not reconstruct causal linkage across unaware applications.

## Start

From `examples/chained-apps-no-propagation/`:

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
   nested `app3` response inside that.
4. In ProxyLens Server, expect separate traces rather than one fully connected
   end-to-end trace.

Useful server URLs:

- `http://localhost:8000/scalar`
- `http://localhost:8000/requests?limit=100`
- `http://localhost:8000/requests?limit=100&node_names=app1&node_names=app2&node_names=app3`

## Stop And Clean

```bash
just stop
just clean
```
