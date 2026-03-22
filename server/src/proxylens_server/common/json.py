from __future__ import annotations

import json
from typing import Any


def normalize_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
