from __future__ import annotations

from typing import Any

import networkx as nx

from document_ai.impact.graph import _downstream_sort_key, linked_test_case_ids, xxcs_test_ids
from document_ai.learn.extract_design_items import DesignItemIndex
from document_ai.learn.req_ids import normalize_requirement_id
from document_ai.platform.memory.graph_builder import graph_stats
from document_ai.platform.memory.graph_models import EdgeType, GraphEdge, GraphNode, GraphStats, NodeType


class KnowledgeGraph:
    def __init__(self, graph: nx.DiGraph, metadata: dict[str, Any] | None = None) -> None:
        self.graph = graph
        self.metadata = metadata or {}

    @property
    def case_id(self) -> str:
        return str(self.metadata.get("case_id", ""))

    @property
    def document_set_hint(self) -> str:
        return str(self.metadata.get("document_set_hint", "ec_sw"))

    def stats(self) -> GraphStats:
        return graph_stats(self.graph)

    def _nodes_by_normalized_id(self, node_id: str) -> list[GraphNode]:
        normalized = normalize_requirement_id(node_id) or node_id
        matches: list[GraphNode] = []
        for _, data in self.graph.nodes(data=True):
            node: GraphNode = data["node"]
            if node.normalized_id == normalized:
                matches.append(node)
        return matches

    def find_node(self, node_id: str) -> GraphNode | None:
        matches = self._nodes_by_normalized_id(node_id)
        if not matches:
            return None
        for node in matches:
            if node.type == NodeType.REQUIREMENT:
                return node
        return matches[0]

    def _neighbor_ids(
        self,
        node_id: str,
        *,
        direction: str,
        edge_types: set[EdgeType] | None = None,
        max_depth: int = 2,
    ) -> list[str]:
        start_nodes = self._nodes_by_normalized_id(node_id)
        if not start_nodes:
            return []

        visited: set[str] = set()
        frontier = [node.id for node in start_nodes]
        collected: list[str] = []
        depth = 0

        while frontier and depth < max_depth:
            next_frontier: list[str] = []
            depth += 1
            for current in frontier:
                neighbors = self.graph.successors(current) if direction == "downstream" else self.graph.predecessors(current)
                for neighbor in neighbors:
                    edge_data = self.graph.get_edge_data(
                        current if direction == "downstream" else neighbor,
                        neighbor if direction == "downstream" else current,
                    )
                    if edge_data is None:
                        continue
                    edge: GraphEdge = edge_data["edge"]
                    if edge_types and edge.type not in edge_types:
                        continue
                    neighbor_node: GraphNode = self.graph.nodes[neighbor]["node"]
                    normalized = neighbor_node.normalized_id
                    if normalized not in visited:
                        visited.add(normalized)
                        collected.append(normalized)
                        next_frontier.append(neighbor)
            frontier = next_frontier

        return sorted(collected, key=_downstream_sort_key)

    def _node_ids_for(self, node_id: str) -> list[str]:
        return [node.id for node in self._nodes_by_normalized_id(node_id)]

    def shortest_path(self, source_id: str, target_id: str) -> list[str]:
        source_ids = self._node_ids_for(source_id)
        target_ids = self._node_ids_for(target_id)
        if not source_ids or not target_ids:
            return []

        best: list[str] | None = None
        for source in source_ids:
            for target in target_ids:
                try:
                    path = nx.shortest_path(self.graph, source, target)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                if best is None or len(path) < len(best):
                    best = path
        if best is None:
            return []
        return [self.graph.nodes[node_id]["node"].normalized_id for node_id in best]

    def explain_path(self, source_id: str, target_id: str) -> dict[str, Any]:
        source = normalize_requirement_id(source_id) or source_id
        target = normalize_requirement_id(target_id) or target_id
        node_path = self.shortest_path(source, target)
        if not node_path:
            return {
                "found": False,
                "source": source,
                "target": target,
                "path": [],
                "length": 0,
            }

        steps: list[dict[str, Any]] = []
        for index, normalized in enumerate(node_path):
            node = self.find_node(normalized)
            steps.append(
                {
                    "node": normalized,
                    "type": node.type.value if node else "Unknown",
                }
            )
            if index < len(node_path) - 1:
                current_ids = self._node_ids_for(normalized)
                next_ids = self._node_ids_for(node_path[index + 1])
                edge_info: dict[str, Any] = {"edge": EdgeType.TRACES_TO.value, "evidence": ""}
                for current in current_ids:
                    for nxt in next_ids:
                        data = self.graph.get_edge_data(current, nxt)
                        if data:
                            edge: GraphEdge = data["edge"]
                            edge_info = {"edge": edge.type.value, "evidence": edge.evidence}
                            break
                    if edge_info["evidence"]:
                        break
                steps.append(edge_info)

        return {
            "found": True,
            "source": source,
            "target": target,
            "path": steps,
            "length": len(node_path) - 1,
        }

    def find_impact_radius(self, node_id: str, max_depth: int = 3) -> dict[str, Any]:
        normalized = normalize_requirement_id(node_id) or node_id
        downstream_ids = self.find_downstream(normalized, max_depth=max_depth)
        documents = self.find_related_documents(normalized)
        return {
            "origin": normalized,
            "max_depth": max_depth,
            "downstream_ids": downstream_ids,
            "documents_affected": [doc["template_id"] for doc in documents],
        }

    def find_downstream(
        self,
        node_id: str,
        edge_types: list[EdgeType] | None = None,
        max_depth: int = 2,
    ) -> list[str]:
        allowed = set(edge_types) if edge_types else {EdgeType.TRACES_TO}
        return self._neighbor_ids(node_id, direction="downstream", edge_types=allowed, max_depth=max_depth)

    def find_upstream(
        self,
        node_id: str,
        edge_types: list[EdgeType] | None = None,
        max_depth: int = 2,
    ) -> list[str]:
        allowed = set(edge_types) if edge_types else {EdgeType.TRACES_TO}
        return self._neighbor_ids(node_id, direction="upstream", edge_types=allowed, max_depth=max_depth)

    def find_related_design(self, node_id: str) -> list[str]:
        normalized = normalize_requirement_id(node_id) or node_id
        related: list[str] = []
        for _, data in self.graph.nodes(data=True):
            node: GraphNode = data["node"]
            if node.type != NodeType.DESIGN_ITEM:
                continue
            if node.normalized_id == normalized:
                related.append(node.normalized_id)
        return related

    def find_related_tests(self, node_id: str) -> list[str]:
        downstream = self.find_downstream(node_id, max_depth=1)
        return linked_test_case_ids(downstream)

    def find_related_documents(self, node_id: str) -> list[dict[str, str]]:
        normalized = normalize_requirement_id(node_id) or node_id
        impact = compute_change_impact(self, [normalized])
        documents: list[dict[str, str]] = []
        for template_id, spec in impact.get("documents", {}).items():
            action = spec.get("action", "skip")
            if action in {"patch", "review"}:
                documents.append({"template_id": template_id, "action": action})
        return documents

    def compute_change_impact(
        self,
        req_ids: list[str],
        design_index: DesignItemIndex | None = None,
    ) -> dict[str, Any]:
        return compute_change_impact(self, req_ids, design_index=design_index)


def compute_change_impact(
    knowledge_graph: KnowledgeGraph,
    req_ids: list[str],
    design_index: DesignItemIndex | None = None,
) -> dict[str, Any]:
    normalized = [normalize_requirement_id(req_id) for req_id in req_ids]
    normalized = [req_id for req_id in normalized if req_id]

    linked_ids: list[str] = []
    seen: set[str] = set()
    for req_id in normalized:
        for downstream_id in knowledge_graph.find_downstream(req_id, max_depth=1):
            if downstream_id not in seen:
                seen.add(downstream_id)
                linked_ids.append(downstream_id)

    linked_ids = sorted(linked_ids, key=_downstream_sort_key)
    xxcs_ids = xxcs_test_ids(linked_ids)
    test_ids = linked_test_case_ids(linked_ids)

    mddr_req_ids: list[str] = []
    mddr_reason = "MDDR / design blocks not indexed"
    if design_index is not None:
        mddr_req_ids = design_index.req_ids_for(normalized)
        if mddr_req_ids:
            mddr_reason = ""

    is_srs = any(req_id.startswith(("FR-", "NFR-")) for req_id in normalized)

    return {
        "changed_req_ids": normalized,
        "linked_downstream_ids": linked_ids,
        "linked_security_ids": linked_ids,
        "linked_test_ids": test_ids,
        "document_set_hint": "ieee_srs" if is_srs else knowledge_graph.document_set_hint,
        "documents": {
            "spec_requirements": {
                "action": "patch",
                "req_ids": normalized,
            },
            "spec_design": {
                "action": "patch" if mddr_req_ids else "skip",
                "req_ids": mddr_req_ids,
                "reason": mddr_reason,
            },
            "report_security_verification": {
                "action": "patch" if xxcs_ids else "skip",
                "security_req_ids": xxcs_ids,
            },
            "test_cases": {
                "action": "review" if test_ids else "skip",
                "test_ids": test_ids,
                "reason": "SRS RTM — update linked test cases (TC-xx) manually or via test spec DOCX when available",
            },
        },
    }


class TraceabilityGraphAdapter:
    """Adapter that mirrors legacy TraceabilityGraph using KnowledgeGraph."""

    engine = "knowledge_graph"

    def __init__(self, knowledge_graph: KnowledgeGraph, design_index: DesignItemIndex | None = None) -> None:
        self._knowledge_graph = knowledge_graph
        self._design_index = design_index

    def downstream_for_req(self, req_id: str) -> list[str]:
        return self._knowledge_graph.find_downstream(req_id, max_depth=1)

    def downstream_for_reqs(self, req_ids: list[str]) -> list[str]:
        combined: set[str] = set()
        for req_id in req_ids:
            combined.update(self.downstream_for_req(req_id))
        from document_ai.impact.graph import _downstream_sort_key

        return sorted(combined, key=_downstream_sort_key)

    def security_for_req(self, req_id: str) -> list[str]:
        return self.downstream_for_req(req_id)

    def security_for_reqs(self, req_ids: list[str]) -> list[str]:
        return self.downstream_for_reqs(req_ids)

    def impact(self, req_ids: list[str], design_index: Any | None = None) -> dict[str, Any]:
        index = design_index if design_index is not None else self._design_index
        return compute_change_impact(self._knowledge_graph, req_ids, design_index=index)
