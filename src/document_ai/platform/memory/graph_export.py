from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx

from document_ai.platform.memory.graph_models import EdgeType, GraphEdge, GraphNode, NodeType
from document_ai.platform.memory.graph_query import KnowledgeGraph

def export_json(knowledge_graph: KnowledgeGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = knowledge_graph.stats()
    envelope = {
        "schema_version": "1.0",
        "case_id": knowledge_graph.case_id,
        "document_set_hint": knowledge_graph.document_set_hint,
        "built_at": datetime.now(UTC).isoformat(),
        "source_files": knowledge_graph.metadata.get("source_files", []),
        "stats": stats.to_dict(),
        "nodes": [data["node"].to_dict() for _, data in knowledge_graph.graph.nodes(data=True)],
        "edges": [data["edge"].to_dict() for _, _, data in knowledge_graph.graph.edges(data=True)],
    }
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def export_graphml(knowledge_graph: KnowledgeGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    export_graph = nx.DiGraph()
    for node_id, data in knowledge_graph.graph.nodes(data=True):
        node: GraphNode = data["node"]
        export_graph.add_node(
            node_id,
            type=node.type.value,
            label=node.label,
            normalized_id=node.normalized_id,
            case_id=node.case_id,
        )
    for source, target, data in knowledge_graph.graph.edges(data=True):
        edge: GraphEdge = data["edge"]
        export_graph.add_edge(
            source,
            target,
            type=edge.type.value,
            confidence=edge.confidence,
            evidence=edge.evidence[:200],
        )
    nx.write_graphml(export_graph, path)
    return path


def import_json(path: Path) -> KnowledgeGraph:
    payload = json.loads(path.read_text(encoding="utf-8"))
    graph: nx.DiGraph = nx.DiGraph()
    for raw in payload.get("nodes", []):
        node = GraphNode(
            id=raw["id"],
            type=NodeType(raw["type"]),
            label=raw["label"],
            normalized_id=raw["normalized_id"],
            case_id=raw["case_id"],
            source_file=raw.get("source_file", ""),
            document_type=raw.get("document_type"),
            metadata=raw.get("metadata", {}),
            raw_text=raw.get("raw_text"),
        )
        graph.add_node(node.id, node=node)
    for raw in payload.get("edges", []):
        edge = GraphEdge(
            source=raw["source"],
            target=raw["target"],
            type=EdgeType(raw["type"]),
            confidence=raw.get("confidence", 1.0),
            evidence=raw.get("evidence", ""),
            source_file=raw.get("source_file", ""),
            metadata=raw.get("metadata", {}),
        )
        graph.add_edge(edge.source, edge.target, edge=edge)
    metadata = {
        "case_id": payload.get("case_id", ""),
        "document_set_hint": payload.get("document_set_hint", "ec_sw"),
        "source_files": payload.get("source_files", []),
    }
    return KnowledgeGraph(graph, metadata)
