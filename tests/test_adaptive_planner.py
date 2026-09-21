from pathlib import Path

from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.planning.goal_parser import parse_goal
from document_ai.platform.planning.intent_classifier import classify_intent
from document_ai.platform.planning.planner import AdaptivePlanner, MemoryQueryContext
from document_ai.platform.planning.workflow_templates import (
    DOCUMENT_WORKFLOW,
    HYBRID_WORKFLOW,
    OPERATION_WORKFLOW,
    select_workflow_template,
)
from document_ai.platform.task_graph import build_task_graph


def test_goal_parsing_extracts_goal_and_metadata():
    parsed = parse_goal(
        case_dir="data/cases/mindrium_xa",
        change="data/cases/mindrium_xa/changes/req6_update.json",
        goal="Req.6 변경 영향 분석",
        intent="document_change",
        metadata={"description": "traceability review"},
    )

    assert parsed.goal == "Req.6 변경 영향 분석"
    assert parsed.explicit_intent == "document_change"
    assert "Req.6" in parsed.combined_text
    assert "traceability" in parsed.combined_text


def test_intent_classification_document_change():
    parsed = parse_goal(
        case_dir="data/cases/mindrium_xa",
        change=Path("data/cases/mindrium_xa/changes/req6_update.json"),
    )
    assert classify_intent(parsed) == "document_change"


def test_intent_classification_operation_analysis():
    parsed = parse_goal(
        case_dir="data/ops",
        change="GPU 서버 Docker 로그 장애 분석",
    )
    assert classify_intent(parsed) == "operation_analysis"


def test_intent_classification_security_review():
    parsed = parse_goal(
        case_dir="data/cases/mindrium_xa",
        change="XXCS 보안 시험 결과 검토",
        intent="security_review",
    )
    assert classify_intent(parsed) == "security_review"


def test_intent_classification_knowledge_query():
    parsed = parse_goal(
        case_dir="data/cases/mindrium_xa",
        change="knowledge graph traceability 영향 분석",
    )
    assert classify_intent(parsed) == "knowledge_query"


def test_workflow_template_selection():
    assert select_workflow_template("operation_analysis").template_id == "operation_workflow"
    assert select_workflow_template("document_change").template_id == "document_workflow"
    assert select_workflow_template("document_change", hybrid=True).template_id == "hybrid_workflow"


def test_hybrid_workflow_task_graph_and_harness_assignment():
    planner = RuleBasedPlanner()
    plan = planner.plan_workflow(
        case_dir="data/cases/mindrium_xa",
        change=Path("data/cases/mindrium_xa/changes/req6_update.json"),
        goal="Req 변경 후 GPU 서버 장애 로그도 분석",
        request_id="hybrid-1",
        metadata={"sample_dir": "data/ops/samples"},
    )

    assert plan.template.template_id == "hybrid_workflow"
    assert plan.intent == "document_change"
    assert plan.request.metadata["hybrid"] is True

    task_graph = plan.task_graph
    ordered = task_graph.ordered_tasks()
    assert len(ordered) == 2
    assert ordered[0].harness == "document"
    assert ordered[1].harness == "operation"
    assert ordered[1].dependencies == ("task-document-change-pipeline",)

    assert plan.harness_assignments == [
        {
            "task_id": "task-document-change-pipeline",
            "harness": "document",
            "action": "run_change_pipeline",
        },
        {
            "task_id": "task-operation-incident-analysis",
            "harness": "operation",
            "action": "analyze_incidents",
        },
    ]


def test_adaptive_planner_memory_query_interface():
    context = MemoryQueryContext()
    snapshot = context.snapshot("data/ops")

    assert "knowledge" in snapshot
    assert "events" in snapshot
    assert "reasoning" in snapshot
    assert "tasks" in snapshot
    assert "evaluations" in snapshot


def test_existing_planner_api_compatibility():
    planner = RuleBasedPlanner()

    request = planner.create_request(
        case_dir="data/cases/mindrium_xa",
        change="data/cases/mindrium_xa/changes/req6_update.json",
        request_id="req-compat",
    )
    task_graph = build_task_graph(request)

    assert request.mode == "change_request"
    assert request.metadata["workflow_template"] == DOCUMENT_WORKFLOW.template_id
    assert request.metadata["planner_intent"] == "document_change"
    assert task_graph.tasks[0].harness == "document"

    op_request = planner.create_request(
        case_dir="data/ops",
        change="연구실 GPU 서버 장애 로그 분석",
        request_id="op-compat",
        metadata={"sample_dir": "data/ops/samples"},
    )
    op_graph = build_task_graph(op_request)

    assert op_request.mode == "operation_request"
    assert op_request.metadata["workflow_template"] == OPERATION_WORKFLOW.template_id
    assert op_graph.tasks[0].harness == "operation"
    assert planner.detect_operation_intent("GPU Docker incident") is True
    assert planner.detect_operation_intent("req6 requirement update") is False


def test_adaptive_planner_backend_protocol_ready():
    planner = AdaptivePlanner()

    assert planner.backend is None
    plan = planner.plan(
        case_dir="data/cases/mindrium_xa",
        change="문서 생성 MDSR render",
        goal="MDSR 문서 생성",
        request_id="gen-1",
    )

    assert plan.intent == "document_generation"
    assert plan.template.template_id == DOCUMENT_WORKFLOW.template_id
    assert plan.workflow.workflow_id == "wf-tg-gen-1"
