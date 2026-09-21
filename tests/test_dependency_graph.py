"""Tests for C1 dependency closure graph."""

from __future__ import annotations

import json
from pathlib import Path

from document_ai.document_set.dependency_graph import (
    DependencyGraph,
    build_ec_sw_dependency_graph,
    expand_patch_candidates_with_closure,
)


def test_dependency_graph_closure():
    graph = DependencyGraph(
        nodes={"Req. 2", "IA-01", "Req. 3"},
        edges=[("Req. 2", "IA-01"), ("Req. 3", "IA-01")],
    )
    closed = graph.closure({"Req. 2"})
    assert "IA-01" in closed
    assert "Req. 3" not in closed


def test_expand_patch_candidates_with_closure(tmp_path: Path):
    case = tmp_path / "closure_case"
    case.mkdir()
    (case / "requirements.json").write_text(
        json.dumps(
            {
                "requirements": [
                    {"req_id": "Req. 2", "description": "A"},
                    {"req_id": "Req. 3", "description": "B"},
                ],
                "traceability": [
                    {
                        "requirement": "IA-01",
                        "linked_reqs": "Req. 2, Req. 3",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    req_payload = json.loads((case / "requirements.json").read_text(encoding="utf-8"))
    dep = build_ec_sw_dependency_graph(req_payload)
    assert "Req. 2" in dep.nodes
    assert any(edge[0] == "Req. 2" for edge in dep.edges)

    expanded = expand_patch_candidates_with_closure(
        {"Req. 2"},
        req_payload,
        apply_closure=True,
    )
    assert "Req. 2" in expanded["original"]
    assert "IA-01" in expanded["expanded"]
    assert len(expanded["expanded"]) >= len(expanded["original"])

    no_closure = expand_patch_candidates_with_closure(
        {"Req. 2"},
        req_payload,
        apply_closure=False,
    )
    assert no_closure["expanded"] == ["Req. 2"]
