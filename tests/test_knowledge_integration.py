import json
import os
from pathlib import Path

from document_ai.impact.graph import TraceabilityGraph
from document_ai.impact.orchestrator import compute_impact
from document_ai.platform.memory import (
    KnowledgeGraph,
    LegacyTraceabilityAdapter,
    build_from_case,
    resolve_impact_engine,
)
from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.runtime import PlatformRuntime


def _mindrium_change() -> dict:
    return json.loads(
        (Path("data/cases/mindrium_xa") / "changes" / "req6_update.json").read_text(encoding="utf-8")
    )


def test_compute_impact_uses_knowledge_graph_by_default():
    case_dir = Path("data/cases/mindrium_xa")
    change = _mindrium_change()
    result = compute_impact(case_dir, change)

    assert "IA-04" in result["impact"]["linked_security_ids"]
    assert result["impact"]["changed_req_ids"] == ["Req. 6"]


def test_compute_impact_kg_matches_legacy_mindrium():
    case_dir = Path("data/cases/mindrium_xa")
    change = _mindrium_change()
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))

    kg_result = compute_impact(case_dir, change)
    legacy = LegacyTraceabilityAdapter(payload["traceability"])
    legacy_impact = legacy.impact(["Req. 6"])

    assert kg_result["impact"] == legacy_impact


def test_compute_impact_kg_matches_legacy_stt_srs():
    case_dir = Path("data/cases/stt_srs")
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    change = {
        "change_id": "eval-fr02",
        "requirement_changes": [{"req_id": "FR-02", "description": "STT update"}],
    }

    kg_result = compute_impact(case_dir, change)
    legacy = LegacyTraceabilityAdapter(payload["traceability"])
    legacy_impact = legacy.impact(["FR-02"])

    assert kg_result["impact"] == legacy_impact
    assert kg_result["impact"]["linked_test_ids"] == ["TC-02"]


def test_req6_explain_path_ia04():
    case_dir = Path("data/cases/mindrium_xa")
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    path = graph.explain_path("Req. 6", "IA-04")
    assert path["found"] is True
    assert path["source"] == "Req. 6"
    assert path["target"] == "IA-04"
    assert path["length"] >= 1


def test_fr02_shortest_path_tc02():
    case_dir = Path("data/cases/stt_srs")
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    path = graph.shortest_path("FR-02", "TC-02")
    assert path == ["FR-02", "TC-02"]


def test_legacy_fallback_env(monkeypatch):
    case_dir = Path("data/cases/mindrium_xa")
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    monkeypatch.setenv("DOCUMENT_AI_USE_LEGACY_GRAPH", "1")

    engine = resolve_impact_engine(case_dir, payload["traceability"])
    assert isinstance(engine, LegacyTraceabilityAdapter)
    assert engine.engine == "legacy"


def test_platform_runtime_uses_knowledge_graph_queries(tmp_path):
    source_case = Path("data/cases/mindrium_xa")
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (source_case / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    changes_dir = case_copy / "changes"
    changes_dir.mkdir()
    change_path = changes_dir / "req6_update.json"
    change_path.write_text(
        (source_case / "changes" / "req6_update.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    runtime = PlatformRuntime()
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        dry_run=True,
        apply=False,
        request_id="kg-integration",
    )

    assert runtime_result.knowledge_context["engine"] == "knowledge_graph"
    assert runtime_result.knowledge_context["queries"]
    downstream = runtime_result.knowledge_context["queries"][0]["downstream"]
    assert "IA-04" in downstream
    assert runtime_result.planner_request.metadata.get("knowledge_graph") is not None


def test_planner_lookup_requirement_context():
    case_dir = Path("data/cases/mindrium_xa")
    memory = MemoryManager()
    memory.load_knowledge_memory(case_dir)
    planner = RuleBasedPlanner()

    context = planner.lookup_requirement_context(memory, ["Req. 6"])

    assert context["available"] is True
    assert context["requirements"][0]["req_id"] == "Req. 6"
    assert "IA-04" in context["requirements"][0]["downstream"]


def test_traceability_graph_still_available_for_regression():
    case_dir = Path("data/cases/mindrium_xa")
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    legacy = TraceabilityGraph(payload["traceability"])
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    legacy_impact = legacy.impact(["Req. 6"])
    kg_impact = graph.compute_change_impact(["Req. 6"])
    assert legacy_impact == kg_impact
