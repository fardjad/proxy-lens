# ProxyLens Server

Implementation of the ProxyLens Server spec.

## Running the server

Use the package entry point:

```bash
uv run proxylens-server --bind 127.0.0.1:8000 --log-level info
```

Useful options:

- `--host` / `--port` to set the bind address without `--bind`
- `--reload` for development
- `--workers` to run multiple uvicorn worker processes
- `--data-dir` to choose the server data directory
- `--filter-script` to load an event filter script
- `--no-access-log` to disable access logging
