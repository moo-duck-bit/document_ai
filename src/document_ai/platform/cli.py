from __future__ import annotations

import json
import sys
import traceback
from argparse import Namespace
from pathlib import Path
from typing import Any

from document_ai.platform.evaluation.benchmark_runner import PlatformBenchmarkRunner
from document_ai.platform.improvement.improvement_engine import ImprovementEngine
from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.models import RuntimeResult, TaskSpec
from document_ai.platform.operation.operation_harness import OperationHarness
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.runtime import PlatformRuntime
from document_ai.platform.task_graph import TaskGraph


def serialize_task_graph(task_graph: TaskGraph) -> dict[str, Any]:
    return {
        "graph_id": task_graph.graph_id,
        "tasks": [
            {
                "task_id": task.task_id,
                "name": task.name,
                "harness": task.harness,
                "action": task.action,
                "state": task.state,
                "dependencies": list(task.dependencies),
                "agent_assignment": task.agent_assignment,
                "metadata": dict(task.metadata),
            }
            for task in task_graph.ordered_tasks()
        ],
        "metadata": dict(task_graph.metadata),
    }


def serialize_runtime_result(result: RuntimeResult) -> dict[str, Any]:
    return {
        "correlation_id": result.correlation_id,
        "workflow_id": result.workflow_id,
        "task_graph_id": result.task_graph_id,
        "reasoning_id": result.reasoning_id,
        "evaluation_id": result.evaluation_id,
        "execution_plan_id": result.execution_plan_id,
        "harness": result.harness,
        "task_results": result.task_results,
        "knowledge_context": result.knowledge_context,
        "event_refs": result.event_refs,
        "result": result.result,
    }


def emit_json(payload: dict[str, Any], out_path: str | Path | None = None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    print(text)


def emit_error(
    exc: BaseException,
    *,
    out_path: str | Path | None = None,
    context: dict[str, Any] | None = None,
) -> int:
    payload: dict[str, Any] = {
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    }
    if context:
        payload["error"]["context"] = context
    emit_json(payload, out_path)
    traceback.print_exc(file=sys.stderr)
    return 1


def _build_metadata(args: Namespace) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if getattr(args, "sample_dir", None):
        metadata["sample_dir"] = str(args.sample_dir)
    return metadata


def _resolve_change(args: Namespace) -> Any:
    if getattr(args, "change", None):
        return args.change
    if getattr(args, "goal", None):
        return args.goal
    return ""


def cmd_platform_plan(args: Namespace) -> int:
    try:
        planner = RuleBasedPlanner()
        metadata = _build_metadata(args)
        case_dir = getattr(args, "case", None) or "."
        change = _resolve_change(args)
        goal = getattr(args, "goal", None)

        plan = planner.create_execution_plan(
            case_dir=case_dir,
            change=change,
            goal=goal,
            dry_run=not getattr(args, "apply", False),
            apply=getattr(args, "apply", False),
            request_id=getattr(args, "request_id", None) or "platform-plan",
            metadata=metadata or None,
        )
        task_graph = plan.primary_task_graph
        payload = {
            "plan_id": plan.plan_id,
            "intent": plan.goal_context.intent,
            "hybrid": plan.goal_context.hybrid,
            "workflow_template": plan.request.metadata.get("workflow_template"),
            "harness_sequence": list(plan.harness_sequence),
            "task_graph": serialize_task_graph(task_graph),
            "execution_strategy": plan.execution_strategy,
            "estimated_steps": plan.estimated_steps,
        }
        emit_json(payload, getattr(args, "out", None))
        return 0
    except Exception as exc:
        return emit_error(exc, out_path=getattr(args, "out", None))


def cmd_platform_run(args: Namespace) -> int:
    try:
        case_dir = Path(args.case)
        change = args.change
        if not case_dir.exists():
            raise FileNotFoundError(f"Missing case directory: {case_dir}")
        change_path = Path(change) if isinstance(change, str) and change.endswith(".json") else None
        if change_path is not None and not change_path.exists():
            raise FileNotFoundError(f"Missing change file: {change_path}")

        metadata = _build_metadata(args)
        planner = RuleBasedPlanner()
        execution_plan = planner.create_execution_plan(
            case_dir=case_dir,
            change=change,
            goal=getattr(args, "goal", None),
            dry_run=not getattr(args, "apply", False),
            apply=getattr(args, "apply", False),
            change_path=change_path,
            request_id=getattr(args, "request_id", None) or "platform-run",
            metadata=metadata or None,
        )

        runtime = PlatformRuntime(planner=planner)
        runtime_result = runtime.run(
            case_dir=case_dir,
            change=change,
            dry_run=not getattr(args, "apply", False),
            apply=getattr(args, "apply", False),
            change_path=change_path,
            request_id=getattr(args, "request_id", None) or "platform-run",
            goal=getattr(args, "goal", None),
            metadata=metadata or None,
            execution_plan=execution_plan,
        )

        payload = serialize_runtime_result(runtime_result)
        out_path = getattr(args, "out", None)
        emit_json(payload, out_path)
        return 0
    except Exception as exc:
        return emit_error(exc, out_path=getattr(args, "out", None))


def cmd_platform_ops_analyze(args: Namespace) -> int:
    try:
        samples = Path(args.samples)
        if not samples.exists():
            raise FileNotFoundError(f"Missing samples directory: {samples}")

        planner = RuleBasedPlanner()
        request = planner.create_request(
            case_dir="data/ops",
            change="GPU 서버 장애 로그 분석",
            request_id="platform-ops-analyze",
            metadata={"sample_dir": str(samples)},
        )
        task = TaskSpec(
            task_id="task-operation-incident-analysis",
            name="Analyze GPU server incident samples",
            harness="operation",
            action="analyze_incidents",
            agent_assignment="operation_harness",
            metadata={"sample_dir": str(samples)},
        )
        result = OperationHarness().run(request, task)
        payload = result["incident_report"]
        emit_json(payload, getattr(args, "out", None))
        return 0
    except Exception as exc:
        return emit_error(exc, out_path=getattr(args, "out", None))


def cmd_platform_improve(args: Namespace) -> int:
    try:
        case_dir = Path(args.case)
        if not case_dir.exists():
            raise FileNotFoundError(f"Missing case directory: {case_dir}")

        correlation_id = getattr(args, "correlation_id", None)
        engine = ImprovementEngine(MemoryManager())
        feedback = engine.analyze(case_dir, correlation_id=correlation_id)
        emit_json(feedback.to_dict(), getattr(args, "out", None))
        return 0
    except Exception as exc:
        return emit_error(exc, out_path=getattr(args, "out", None))


def cmd_platform_benchmark(args: Namespace) -> int:
    try:
        out_dir = getattr(args, "out", None) or "data/platform/benchmark"
        runner = PlatformBenchmarkRunner(
            work_dir=getattr(args, "work_dir", None) or "data/platform/benchmark/work",
        )
        report = runner.run(
            out_dir=out_dir,
            baseline_path=getattr(args, "baseline", None),
            update_baseline=bool(getattr(args, "update_baseline", False)),
        )
        if getattr(args, "out", None):
            summary = {
                "overall_score": report.get("overall_score"),
                "output_paths": report.get("output_paths", {}),
                "regression": report.get("regression", {}),
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            emit_json(report, None)
        return 0 if report.get("regression", {}).get("passed", True) else 1
    except Exception as exc:
        return emit_error(exc, out_path=getattr(args, "out", None))
