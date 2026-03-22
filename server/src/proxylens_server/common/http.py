from __future__ import annotations

from typing import TypeAlias

HeaderPairs: TypeAlias = list[tuple[str, str]]


def header_value(headers: HeaderPairs, name: str) -> str | None:
    expected = name.lower()
    for header_name, header_value_text in headers:
        if header_name.lower() == expected:
            return header_value_text
    return None
