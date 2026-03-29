#!/bin/sh
set -eu

/proxy-lens/bin/set-ui-api-base-url.sh

mkdir -p "${PROXYLENS_SERVER_DATA_DIR:-/data}"

set -- proxylens-server \
  --host 0.0.0.0 \
  --port "${PROXYLENS_SERVER_PORT:-8000}" \
  --data-dir "${PROXYLENS_SERVER_DATA_DIR:-/data}"

if [ -n "${PROXYLENS_SERVER_FILTER_SCRIPT:-}" ]; then
  set -- "$@" --filter-script "${PROXYLENS_SERVER_FILTER_SCRIPT}"
fi

"$@" &
server_pid=$!

caddy run --config /proxy-lens/Caddyfile --adapter caddyfile &
caddy_pid=$!

cleanup() {
  kill "$server_pid" "$caddy_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  wait "$caddy_pid" 2>/dev/null || true
}

trap cleanup INT TERM

while kill -0 "$server_pid" 2>/dev/null && kill -0 "$caddy_pid" 2>/dev/null; do
  sleep 1
done

server_status=0
caddy_status=0

if ! kill -0 "$server_pid" 2>/dev/null; then
  wait "$server_pid" || server_status=$?
fi

if ! kill -0 "$caddy_pid" 2>/dev/null; then
  wait "$caddy_pid" || caddy_status=$?
fi

cleanup

if [ "$server_status" -ne 0 ]; then
  exit "$server_status"
fi

exit "$caddy_status"
