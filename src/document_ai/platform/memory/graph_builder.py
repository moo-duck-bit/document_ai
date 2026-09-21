from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import networkx as nx

from document_ai.learn.extract_design_items import load_design_items
from document_ai.learn.extract_security_tests import load_security_tests
from document_ai.learn.req_ids import normalize_requirement_id, parse_linked_ids
from document_ai.platform.memory.graph_models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphStats,
    NodeType,
    make_node_id,
)

SECURITY_PREFIXES = frozenset({"IA", "UC", "SI", "DC", "RA"})
DOCUMENT_SPECS = (
    ("spec_requirements", "requirements.json"),
    ("spec_design", "design_items.json"),
    ("report_security_verification", "security_tests.json"),
)


def _node_type_for_id(normalized_id: str) -> NodeType:
    prefix = normalized_id.split("-", 1)[0] if "-" in normalized_id else ""
    if prefix in SECURITY_PREFIXES:
        return NodeType.SECURITY_CONTROL
    return NodeType.REQUIREMENT


def _ensure_node(
    graph: nx.DiGraph,
    *,
    case_id: str,
    normalized_id: str,
    source_file: str,
    document_type: str | None,
    metadata: dict[str, Any] | None = None,
    raw_text: str | None = None,
    node_type: NodeType | None = None,
) -> str:
    resolved_type = node_type or _node_type_for_id(normalized_id)
    node_id = make_node_id(case_id, resolved_type, normalized_id)
    if node_id not in graph:
        graph.add_node(
            node_id,
            node=GraphNode(
                id=node_id,
                type=resolved_type,
                label=normalized_id,
                normalized_id=normalized_id,
                case_id=case_id,
                source_file=source_file,
                document_type=document_type,
                metadata=metadata or {},
                raw_text=raw_text,
            ),
        )
    return node_id


def _add_edge(
    graph: nx.DiGraph,
    *,
    source: str,
    target: str,
    edge_type: EdgeType,
    source_file: str,
    evidence: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    key = (source, target, edge_type.value)
    if key in {(u, v, data["edge"].type.value) for u, v, data in graph.edges(data=True)}:
        return
    graph.add_edge(
        source,
        target,
        edge=GraphEdge(
            source=source,
            target=target,
            type=edge_type,
            evidence=evidence,
            source_file=source_file,
            metadata=metadata or {},
        ),
    )


def build_from_case(case_path: Path) -> tuple[nx.DiGraph, dict[str, Any]]:
    case_dir = Path(case_path)
    case_id = case_dir.name
    graph: nx.DiGraph = nx.DiGraph()
    source_files: list[str] = []
    document_set_hint = "ec_sw"

    req_path = case_dir / "requirements.json"
    if req_path.exists():
        rel_req = str(req_path.as_posix())
        source_files.append(rel_req)
        payload = json.loads(req_path.read_text(encoding="utf-8"))
        document_set_hint = payload.get("document_set", document_set_hint)

        for row in payload.get("requirements", []):
            req_id = normalize_requirement_id(row.get("req_id", ""))
            if not req_id:
                continue
            _ensure_node(
                graph,
                case_id=case_id,
                normalized_id=req_id,
                source_file=rel_req,
                document_type="spec_requirements",
                metadata={"description": row.get("description", "")},
            )

        for row in payload.get("traceability", []):
            upstream = normalize_requirement_id(row.get("requirement", "")) or row.get("requirement", "").strip()
            if not upstream:
                continue
            upstream_id = _ensure_node(
                graph,
                case_id=case_id,
                normalized_id=upstream,
                source_file=rel_req,
                document_type="spec_requirements",
                raw_text=row.get("linked_reqs"),
                node_type=_node_type_for_id(upstream),
            )
            linked = parse_linked_ids(row.get("linked_reqs", ""))
            for linked_id in linked:
                linked_node = _ensure_node(
                    graph,
                    case_id=case_id,
                    normalized_id=linked_id,
                    source_file=rel_req,
                    document_type="spec_requirements",
                    node_type=_node_type_for_id(linked_id),
                )
                evidence = f"traceability {upstream} -> {linked_id}"
                _add_edge(
                    graph,
                    source=upstream_id,
                    target=linked_node,
                    edge_type=EdgeType.TRACES_TO,
                    source_file=rel_req,
                    evidence=evidence,
                )
                _add_edge(
                    graph,
                    source=linked_node,
                    target=upstream_id,
                    edge_type=EdgeType.TRACES_TO,
                    source_file=rel_req,
                    evidence=evidence,
                    metadata={"bidirectional": True},
                )

    design_path = case_dir / "design_items.json"
    if design_path.exists():
        rel_design = str(design_path.as_posix())
        source_files.append(rel_design)
        payload = load_design_items(design_path)
        for item in payload.get("items", []):
            req_id = normalize_requirement_id(item.get("req_id", ""))
            if not req_id:
                continue
            design_node = _ensure_node(
                graph,
                case_id=case_id,
                normalized_id=req_id,
                source_file=rel_design,
                document_type="spec_design",
                metadata={
                    "block_kind": item.get("block_kind"),
                    "design_description": item.get("design_description"),
                },
                node_type=NodeType.DESIGN_ITEM,
            )
            req_node = _ensure_node(
                graph,
                case_id=case_id,
                normalized_id=req_id,
                source_file=rel_design,
                document_type="spec_requirements",
                node_type=NodeType.REQUIREMENT,
            )
            _add_edge(
                graph,
                source=design_node,
                target=req_node,
                edge_type=EdgeType.IMPLEMENTS,
                source_file=rel_design,
                evidence=f"design_items implements {req_id}",
            )

    security_path = case_dir / "security_tests.json"
    if security_path.exists():
        rel_security = str(security_path.as_posix())
        source_files.append(rel_security)
        payload = load_security_tests(security_path)
        for row in payload.get("tests", []):
            control_id = normalize_requirement_id(row.get("req_id", ""))
            if not control_id:
                continue
            test_node = _ensure_node(
                graph,
                case_id=case_id,
                normalized_id=control_id,
                source_file=rel_security,
                document_type="report_security_verification",
                metadata={
                    "test_result": row.get("test_result"),
                    "applied": row.get("applied"),
                },
                node_type=NodeType.SECURITY_TEST,
            )
            control_node = _ensure_node(
                graph,
                case_id=case_id,
                normalized_id=control_id,
                source_file=rel_security,
                document_type="report_security_verification",
                node_type=NodeType.SECURITY_CONTROL,
            )
            _add_edge(
                graph,
                source=test_node,
                target=control_node,
                edge_type=EdgeType.VERIFIES,
                source_file=rel_security,
                evidence=f"security test verifies {control_id}",
            )

    for template_id, filename in DOCUMENT_SPECS:
        artifact = case_dir / filename
        if not artifact.exists():
            continue
        doc_node_id = make_node_id(case_id, NodeType.DOCUMENT, template_id)
        if doc_node_id not in graph:
            graph.add_node(
                doc_node_id,
                node=GraphNode(
                    id=doc_node_id,
                    type=NodeType.DOCUMENT,
                    label=template_id,
                    normalized_id=template_id,
                    case_id=case_id,
                    source_file=str(artifact.as_posix()),
                    document_type=template_id,
                ),
            )

    if any(req_id.startswith(("FR-", "NFR-")) for _, data in graph.nodes(data=True) for req_id in [data["node"].normalized_id]):
        document_set_hint = "ieee_srs"

    meta = {
        "case_id": case_id,
        "document_set_hint": document_set_hint,
        "source_files": source_files,
    }
    return graph, meta


def graph_stats(graph: nx.DiGraph) -> GraphStats:
    orphan_count = sum(1 for node_id in graph.nodes if graph.in_degree(node_id) == 0 and graph.out_degree(node_id) == 0)
    return GraphStats(node_count=graph.number_of_nodes(), edge_count=graph.number_of_edges(), orphan_count=orphan_count)
