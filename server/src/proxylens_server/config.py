from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass(slots=True)
class ServerConfig:
    data_dir: Path
    tombstone_ttl: timedelta = timedelta(minutes=10)
    filter_script: Path | None = None
