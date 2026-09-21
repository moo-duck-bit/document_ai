from __future__ import annotations

from typing import Any

from document_ai.impact.graph import TraceabilityGraph


class LegacyTraceabilityAdapter:
    """Legacy impact engine backed by TraceabilityGraph."""

    def __init__(self, traceability: list[dict[str, Any]]) -> None:
        self._graph = TraceabilityGraph(traceability)
        self.engine = "legacy"

    def downstream_for_req(self, req_id: str) -> list[str]:
        return self._graph.downstream_for_req(req_id)

    def downstream_for_reqs(self, req_ids: list[str]) -> list[str]:
        return self._graph.downstream_for_reqs(req_ids)

    def security_for_req(self, req_id: str) -> list[str]:
        return self._graph.security_for_req(req_id)

    def security_for_reqs(self, req_ids: list[str]) -> list[str]:
        return self._graph.security_for_reqs(req_ids)

    def impact(self, req_ids: list[str], design_index: Any | None = None) -> dict[str, Any]:
        return self._graph.impact(req_ids, design_index=design_index)
