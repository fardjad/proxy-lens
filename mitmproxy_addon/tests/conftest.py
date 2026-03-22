from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture
def ulid_factory() -> Iterator[callable]:
    counter = 0

    def make() -> str:
        nonlocal counter
        counter += 1
        return f"01K0TEST{counter:018d}"

    yield make
