from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    trace_id: str
    node_name: str
    hop_chain: str
    event_indexes: tuple[int, ...] = field(default_factory=tuple)

    def register_event(self, event_index: int) -> "Request":
        if event_index in self.event_indexes:
            return self
        return Request(
            request_id=self.request_id,
            trace_id=self.trace_id,
            node_name=self.node_name,
            hop_chain=self.hop_chain,
            event_indexes=tuple(sorted((*self.event_indexes, event_index))),
        )
