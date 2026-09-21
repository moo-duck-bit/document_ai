"""C1 dependency closure for document-set patch/rollback candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from document_ai.impact.graph import TraceabilityGraph
from document_ai.learn.req_ids import normalize_requirement_id


@dataclass
class DependencyGraph:
    """Directed graph: edge A→B means B depends on A (undo A requires undo B)."""

    nodes: set[str] = field(default_factory=set)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def to_networkx(self) -> nx.DiGraph:
        g = nx.DiGraph()
        g.add_nodes_from(self.nodes)
        g.add_edges_from(self.edges)
        return g

    def closure(self, targets: set[str]) -> set[str]:
        """C1: include all nodes that transitively depend on any target."""
        if not targets:
            return set()
        g = self.to_networkx()
        result = set(targets)
        for node in list(targets):
            if node not in g:
                continue
            # dependents: nodes reachable from node (node was prerequisite)
            for dep in nx.descendants(g, node):
                result.add(dep)
        return result

    def salvage_ratio(self, kept: set[str], total: set[str]) -> float:
        if not total:
            return 1.0
        return round(len(kept & total) / len(total), 4)


def build_ec_sw_dependency_graph(
    requirements_payload: dict[str, Any],
    design_payload: dict[str, Any] | None = None,
) -> DependencyGraph:
    """Build Req → traceability/design dependency edges from case payloads."""
    graph = DependencyGraph()
    trace = requirements_payload.get("traceability") or []
    tg = TraceabilityGraph(trace)

    req_ids = {
        normalize_requirement_id(r.get("req_id", "")) or r.get("req_id", "")
        for r in requirements_payload.get("requirements", [])
    }
    req_ids = {r for r in req_ids if r}
    graph.nodes.update(req_ids)

    for req_id in req_ids:
        for downstream in tg.downstream_for_req(req_id):
            dn = normalize_requirement_id(downstream) or downstream
            graph.nodes.add(dn)
            # downstream depends on req_id
            graph.edges.append((req_id, dn))

    if design_payload:
        for item in design_payload.get("items") or []:
            rid = normalize_requirement_id(item.get("req_id", "")) or item.get("req_id", "")
            if rid:
                graph.nodes.add(rid)
                graph.edges.append((rid, f"design:{rid}"))

    return graph


def expand_patch_candidates_with_closure(
    candidate_ids: set[str],
    requirements_payload: dict[str, Any],
    design_payload: dict[str, Any] | None = None,
    *,
    apply_closure: bool = True,
) -> dict[str, Any]:
    """Return original vs C1-expanded candidate sets."""
    dep = build_ec_sw_dependency_graph(requirements_payload, design_payload)
    normalized = {
        normalize_requirement_id(c) or c for c in candidate_ids if c
    }
    expanded = dep.closure(normalized) if apply_closure else set(normalized)
    return {
        "original": sorted(normalized),
        "expanded": sorted(expanded),
        "added_by_closure": sorted(expanded - normalized),
        "salvage_ratio_if_keep": dep.salvage_ratio(expanded, dep.nodes),
        "apply_closure": apply_closure,
    }
