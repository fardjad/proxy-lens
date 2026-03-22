# Chained Apps With Header Propagation

This example demonstrates chained HTTPS calls where the applications are aware
of `X-ProxyLens-*` headers and forward them on their downstream requests.

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
`app1` and `app2` both read the incoming `X-ProxyLens-*` headers and forward
them directly to their downstream requests.
All three addon instances run with
`max_concurrent_requests_per_host=1`.

## What This Shows

Because the applications propagate ProxyLens headers, the full
`browser -> app1 -> app2 -> app3` chain should appear as one connected trace.

What you get:

- one end-to-end trace spanning all three applications
- the same propagated `trace_id` visible across the chained requests
- forwarded `X-ProxyLens-HopChain` values visible in each app's JSON response

## Start

From `examples/chained-apps-with-propagation/`:

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
4. In ProxyLens Server, expect one fully connected end-to-end trace rather than
   separate traces for each hop.

Useful server URLs:

- `http://localhost:8000/scalar`
- `http://localhost:8000/requests?limit=100`
- `http://localhost:8000/requests?limit=100&node_names=app1&node_names=app2&node_names=app3`

## Stop And Clean

```bash
just stop
just clean
```
