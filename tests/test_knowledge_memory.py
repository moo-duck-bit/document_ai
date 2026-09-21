import json
from pathlib import Path

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.impact.graph import TraceabilityGraph
from document_ai.platform.memory import (
    KnowledgeGraph,
    TraceabilityGraphAdapter,
    build_from_case,
    export_graphml,
    export_json,
    import_json,
)
from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.runtime import PlatformRuntime


def test_graph_build_mindrium():
    case_dir = Path("data/cases/mindrium_xa")
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    assert graph.case_id == "mindrium_xa"
    assert graph.stats().node_count > 0
    assert graph.stats().edge_count > 0
    assert graph.find_node("Req. 6") is not None


def test_req6_traces_to_ia04():
    case_dir = Path("data/cases/mindrium_xa")
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    downstream = graph.find_downstream("Req. 6", max_depth=1)
    assert "IA-04" in downstream
    assert "IA-06" in downstream
    assert "SI-06" in downstream


def test_fr02_traces_to_tc02():
    case_dir = Path("data/cases/stt_srs")
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    downstream = graph.find_downstream("FR-02", max_depth=1)
    assert "TC-02" in downstream
    assert graph.find_related_tests("FR-02") == ["TC-02"]


def test_graph_export_roundtrip(tmp_path):
    case_dir = Path("data/cases/mindrium_xa")
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)

    json_path = tmp_path / "knowledge_graph.json"
    graphml_path = tmp_path / "knowledge_graph.graphml"
    export_json(graph, json_path)
    export_graphml(graph, graphml_path)

    assert json_path.exists()
    assert graphml_path.exists()

    loaded = import_json(json_path)
    assert loaded.stats().node_count == graph.stats().node_count
    assert loaded.stats().edge_count == graph.stats().edge_count


def test_adapter_matches_traceability_graph():
    case_dir = Path("data/cases/mindrium_xa")
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)
    adapter = TraceabilityGraphAdapter(graph)
    legacy = TraceabilityGraph(payload["traceability"])

    legacy_impact = legacy.impact(["Req. 6"])
    adapter_impact = adapter.impact(["Req. 6"])
    assert adapter_impact == legacy_impact


def test_adapter_matches_traceability_graph_stt_srs():
    case_dir = Path("data/cases/stt_srs")
    payload = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    nx_graph, metadata = build_from_case(case_dir)
    graph = KnowledgeGraph(nx_graph, metadata)
    adapter = TraceabilityGraphAdapter(graph)
    legacy = TraceabilityGraph(payload["traceability"])

    legacy_impact = legacy.impact(["FR-02"])
    adapter_impact = adapter.impact(["FR-02"])
    assert adapter_impact == legacy_impact


def test_runtime_uses_knowledge_memory(tmp_path):
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
        request_id="kg-runtime",
    )

    knowledge_records = [record for record in runtime_result.memory_records if record.memory_type == "knowledge"]
    assert len(knowledge_records) == 1
    assert knowledge_records[0].action == "update"
    assert (case_copy / "knowledge_graph.json").exists()
    assert (case_copy / "knowledge_graph.graphml").exists()
    assert runtime.memory_manager.knowledge.graph is not None
    assert runtime.memory_manager.knowledge.graph.stats().node_count > 0


def test_memory_manager_load_and_update(tmp_path):
    source_case = Path("data/cases/mindrium_xa")
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (source_case / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    change_path = source_case / "changes" / "req6_update.json"
    result = run_change_pipeline(
        case_copy,
        change_path,
        dry_run=True,
        apply=False,
        change_path=change_path,
    )

    memory = MemoryManager()
    load_record = memory.load_knowledge_memory(case_copy)
    update_record = memory.update_knowledge_memory(result, case_dir=case_copy)

    assert load_record.action == "load"
    assert update_record.action == "update"
    assert update_record.payload["node_count"] > 0
    assert (case_copy / "knowledge_graph.json").exists()
