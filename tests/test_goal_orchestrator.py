from pathlib import Path

from document_ai.platform.orchestration.execution_plan import ExecutionPlan
from document_ai.platform.orchestration.goal_context import analyze_memory_snapshot, build_goal_context
from document_ai.platform.orchestration.goal_orchestrator import GoalOrchestrator
from document_ai.platform.orchestration.workflow_composer import compose_execution_plan, select_templates
from document_ai.platform.planning.goal_parser import parse_goal
from document_ai.platform.planning.intent_classifier import classify_intent, detect_hybrid_intent
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.runtime import PlatformRuntime

SAMPLES = Path("data/ops/samples")


def _memory_snapshot_with_failure() -> dict:
    return {
        "knowledge": {"available": False},
        "events": {
            "available": True,
            "events": [{"event_type": "RuntimeFailed", "event_id": "evt-1"}],
        },
        "reasoning": {"available": True, "traces": []},
        "tasks": {
            "available": True,
            "workflows": [{"workflow_id": "wf-1", "status": "FAILED"}],
        },
        "evaluations": {
            "available": True,
            "evaluations": [{"evaluation_id": "eval-1", "status": "failed"}],
        },
    }


def test_goal_context_creation():
    parsed = parse_goal(
        case_dir="data/cases/mindrium_xa",
        change=Path("data/cases/mindrium_xa/changes/req6_update.json"),
        goal="Req.6 변경 영향 분석",
    )
    snapshot = _memory_snapshot_with_failure()
    goal_context = build_goal_context(
        parsed,
        intent=classify_intent(parsed),
        hybrid=detect_hybrid_intent(parsed),
        memory_snapshot=snapshot,
    )

    assert goal_context.goal
    assert goal_context.intent == "document_change"
    assert goal_context.memory_insights.has_previous_failures is True
    assert goal_context.memory_insights.failed_evaluation_count == 1


def test_memory_snapshot_analysis_interface():
    insights = analyze_memory_snapshot(_memory_snapshot_with_failure())
    assert insights.failed_workflow_count == 1
    assert insights.runtime_failed_event_count == 1
    assert insights.recent_evaluations


def test_workflow_composer_selects_templates():
    parsed = parse_goal(
        case_dir="data/ops",
        change="GPU 서버 Docker 로그 장애 분석",
    )
    goal_context = build_goal_context(
        parsed,
        intent="operation_analysis",
        hybrid=False,
        memory_snapshot={},
    )
    templates = select_templates(goal_context)
    assert [template.template_id for template in templates] == ["operation_workflow"]


def test_execution_plan_creation():
    orchestrator = GoalOrchestrator()
    plan = orchestrator.orchestrate(
        case_dir="data/cases/mindrium_xa",
        change=Path("data/cases/mindrium_xa/changes/req6_update.json"),
        request_id="plan-doc",
    )

    assert isinstance(plan, ExecutionPlan)
    assert plan.plan_id.startswith("plan-")
    assert plan.harness_sequence == ["document"]
    assert plan.execution_strategy == "sequential"
    assert plan.estimated_steps == 1
    assert plan.primary_task_graph.graph_id == "tg-plan-doc"


def test_hybrid_execution_plan():
    orchestrator = GoalOrchestrator()
    plan = orchestrator.orchestrate(
        case_dir="data/cases/mindrium_xa",
        change=Path("data/cases/mindrium_xa/changes/req6_update.json"),
        goal="Req 변경 후 GPU 서버 장애 로그 분석",
        request_id="plan-hybrid",
        metadata={"sample_dir": str(SAMPLES)},
    )

    assert plan.goal_context.hybrid is True
    assert plan.harness_sequence == ["document", "operation"]
    assert plan.estimated_steps == 2
    assert plan.request.metadata["execution_plan"]["plan_id"] == plan.plan_id


def test_planner_integration_returns_execution_plan():
    planner = RuleBasedPlanner()
    planning_result = planner.plan_workflow(
        case_dir="data/cases/mindrium_xa",
        change=Path("data/cases/mindrium_xa/changes/req6_update.json"),
        request_id="planner-plan",
    )

    assert planning_result.execution_plan is not None
    assert planning_result.execution_plan.plan_id.startswith("plan-")
    assert planning_result.request.metadata["memory_insights"] is not None
    assert planning_result.request.metadata["goal_context"]["intent"] == "document_change"


def test_runtime_accepts_execution_plan(tmp_path):
    source_case = Path("data/cases/mindrium_xa")
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (source_case / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    change_path = source_case / "changes" / "req6_update.json"

    planner = RuleBasedPlanner()
    execution_plan = planner.create_execution_plan(
        case_dir=case_copy,
        change=change_path,
        request_id="runtime-plan",
    )

    runtime = PlatformRuntime(planner=planner)
    runtime_result = runtime.run(
        case_dir=case_copy,
        change=change_path,
        execution_plan=execution_plan,
        request_id="runtime-plan",
    )

    assert runtime_result.execution_plan_id == execution_plan.plan_id
    assert runtime_result.task_results["task-document-change-pipeline"]
