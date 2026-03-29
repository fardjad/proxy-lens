#!/bin/sh
set -eu

runtime_config_path="${PROXYLENS_UI_RUNTIME_CONFIG_PATH:-/proxy-lens/ui/runtime-config.js}"

if [ "${1:-}" != "" ]; then
  export PROXYLENS_UI_API_BASE_URL="$1"
fi

python - "$runtime_config_path" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
url = os.environ.get("PROXYLENS_UI_API_BASE_URL", "").strip()
expr = os.environ.get("PROXYLENS_UI_API_BASE_URL_EXPR", "").strip()

if url and expr:
    raise SystemExit(
        "Set either PROXYLENS_UI_API_BASE_URL or PROXYLENS_UI_API_BASE_URL_EXPR, not both."
    )

if expr:
    api_base_url = expr
elif url:
    api_base_url = json.dumps(url)
else:
    api_base_url = 'window.location.origin + "/api"'

path.write_text(
    "window.__PROXYLENS_CONFIG__ = {\n"
    f"  apiBaseUrl: {api_base_url},\n"
    "};\n",
    encoding="utf-8",
)
PY
