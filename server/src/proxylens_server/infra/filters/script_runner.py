from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


class FilterError(RuntimeError):
    pass


class FilterRunner:
    def __init__(self, script_path: Path | None) -> None:
        self._script_path = script_path
        self._module: ModuleType | None = None

    def load(self) -> None:
        if self._script_path is None:
            return
        spec = importlib.util.spec_from_file_location(
            "proxylens_server_filter", self._script_path
        )
        if spec is None or spec.loader is None:
            raise FilterError(f"failed to load filter script at {self._script_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "filter_event"):
            raise FilterError(
                "filter script must define filter_event(app_container, event, request)"
            )
        self._module = module

    def apply(
        self,
        app_container: object,
        event: Any,
        request: Any | None,
    ) -> Any | None:
        if self._module is None:
            return event
        return self._module.filter_event(app_container, event, request)
