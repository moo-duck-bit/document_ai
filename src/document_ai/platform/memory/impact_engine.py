from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol

from document_ai.learn.extract_design_items import DesignItemIndex
from document_ai.platform.memory.graph_query import TraceabilityGraphAdapter
from document_ai.platform.memory.knowledge_memory import KnowledgeMemory
from document_ai.platform.memory.legacy_adapter import LegacyTraceabilityAdapter


class ImpactEngine(Protocol):
    engine: str

    def impact(self, req_ids: list[str], design_index: Any | None = None) -> dict[str, Any]:
        ...


def use_legacy_graph() -> bool:
    return os.environ.get("DOCUMENT_AI_USE_LEGACY_GRAPH", "").lower() in {"1", "true", "yes"}


def resolve_impact_engine(
    case_dir: Path,
    traceability: list[dict[str, Any]],
    *,
    design_index: DesignItemIndex | None = None,
    knowledge_graph: Any | None = None,
) -> ImpactEngine:
    if use_legacy_graph():
        return LegacyTraceabilityAdapter(traceability)

    try:
        if knowledge_graph is not None:
            adapter = TraceabilityGraphAdapter(knowledge_graph, design_index=design_index)
            adapter.engine = "knowledge_graph"
            return adapter

        memory = KnowledgeMemory()
        graph = memory.ensure_loaded(case_dir)
        adapter = TraceabilityGraphAdapter(graph, design_index=design_index)
        adapter.engine = "knowledge_graph"
        return adapter
    except Exception:
        return LegacyTraceabilityAdapter(traceability)
