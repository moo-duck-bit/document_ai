from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.platform.memory.graph_builder import build_from_case
from document_ai.platform.memory.graph_export import export_graphml, export_json
from document_ai.platform.memory.graph_query import KnowledgeGraph


class KnowledgeMemory:
    """Platform Knowledge Memory backed by a case-scoped KnowledgeGraph."""

    def __init__(self) -> None:
        self._graph: KnowledgeGraph | None = None
        self._case_dir: Path | None = None

    @property
    def graph(self) -> KnowledgeGraph | None:
        return self._graph

    @property
    def case_dir(self) -> Path | None:
        return self._case_dir

    def load(self, case_dir: str | Path) -> KnowledgeGraph:
        resolved = Path(case_dir)
        nx_graph, metadata = build_from_case(resolved)
        self._graph = KnowledgeGraph(nx_graph, metadata)
        self._case_dir = resolved
        return self._graph

    def ensure_loaded(self, case_dir: str | Path) -> KnowledgeGraph:
        resolved = Path(case_dir)
        if self._graph is None or self._case_dir != resolved:
            return self.load(resolved)
        return self._graph

    def update_after_run(self, result: dict[str, Any], case_dir: str | Path | None = None) -> dict[str, Any]:
        resolved = Path(case_dir) if case_dir else self._case_dir
        if resolved is None:
            case_from_result = result.get("case_dir")
            resolved = Path(case_from_result) if case_from_result else None
        if resolved is None:
            raise ValueError("KnowledgeMemory update requires a case_dir")

        graph = self.ensure_loaded(resolved)
        json_path = export_json(graph, resolved / "knowledge_graph.json")
        graphml_path = export_graphml(graph, resolved / "knowledge_graph.graphml")
        stats = graph.stats()
        return {
            "case_id": graph.case_id,
            "node_count": stats.node_count,
            "edge_count": stats.edge_count,
            "orphan_count": stats.orphan_count,
            "knowledge_graph": str(json_path),
            "graphml": str(graphml_path),
            "change_id": result.get("change_id"),
        }
