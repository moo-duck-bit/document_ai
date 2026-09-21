from __future__ import annotations

from pathlib import Path
from typing import Any

from dataclasses import replace

from document_ai.platform.document_harness import DocumentHarness
from document_ai.platform.harness_manager import HarnessManager
from document_ai.platform.memory_manager import MemoryManager
from document_ai.platform.models import RuntimeResult, TaskSpec, WorkflowResult
from document_ai.platform.orchestration.execution_plan import ExecutionPlan
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.task_graph import TaskGraph, build_task_graph
from document_ai.platform.workflow import Workflow


class TaskExecutionError(Exception):
    def __init__(self, task: TaskSpec, original: BaseException) -> None:
        self.task = task
        self.original = original
        super().__init__(str(original))


class PlatformRuntime:
    def __init__(
        self,
        *,
        planner: RuleBasedPlanner | None = None,
        harness_manager: HarnessManager | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self.planner = planner or RuleBasedPlanner()
        self.harness_manager = harness_manager or HarnessManager()
        self.memory_manager = memory_manager or MemoryManager()

    def run(
        self,
        *,
        case_dir: str | Path,
        change: dict[str, Any] | Path,
        dry_run: bool = True,
        apply: bool = False,
        report_path: str | Path | None = None,
        change_path: str | Path | None = None,
        request_id: str = "platform-runtime",
        metadata: dict[str, Any] | None = None,
        goal: str | None = None,
        execution_plan: ExecutionPlan | None = None,
    ) -> RuntimeResult:
        case_path = Path(case_dir)
        correlation_id = f"corr-{request_id}"
        self.memory_manager.begin_runtime(case_path, correlation_id)

        workflow_id = ""
        task_graph_id = ""
        harness_name = ""
        task_id = ""
        task_results: dict[str, dict[str, Any]] = {}
        blocked_task_ids: set[str] = set()

        try:
            self.memory_manager.load_knowledge_memory(case_path)
            knowledge_graph = self.memory_manager.knowledge.graph

            if execution_plan is not None:
                planner_request = replace(
                    execution_plan.request,
                    metadata={
                        **execution_plan.request.metadata,
                        "knowledge_graph": knowledge_graph,
                        "correlation_id": correlation_id,
                    },
                )
                task_graph = execution_plan.primary_task_graph
                workflow = execution_plan.primary_workflow
                task_graph_id = task_graph.graph_id
                workflow_id = workflow.workflow_id
            else:
                planner_request = self.planner.create_request(
                    case_dir=case_path,
                    change=change,
                    dry_run=dry_run,
                    apply=apply,
                    report_path=report_path,
                    change_path=change_path,
                    request_id=request_id,
                    goal=goal,
                    metadata={
                        **(metadata or {}),
                        "knowledge_graph": knowledge_graph,
                        "correlation_id": correlation_id,
                    },
                )

                task_graph = build_task_graph(planner_request)
                task_graph_id = task_graph.graph_id
                workflow = Workflow.from_task_graph(task_graph)
                workflow_id = workflow.workflow_id
                execution_plan = None

            self.memory_manager.create_persisted_workflow(workflow, task_graph)
            workflow.mark_running()

            self.memory_manager.record_workflow_started(
                workflow_id=workflow_id,
                task_graph_id=task_graph_id,
                request_id=request_id,
                case_id=case_path.name,
            )

            task_results, last_task = self._execute_task_graph(
                workflow=workflow,
                workflow_id=workflow_id,
                planner_request=planner_request,
                case_path=case_path,
                blocked_task_ids=blocked_task_ids,
            )
            harness_name = last_task.harness if last_task else ""
            task_id = last_task.task_id if last_task else ""

            primary_result = self._select_primary_result(task_results)
            workflow_result = workflow.complete(
                primary_result,
                executed_tasks=list(task_results.keys()),
            )

            knowledge_context: dict[str, Any] = {}
            document_result = task_results.get("task-document-change-pipeline")
            if knowledge_graph is not None and document_result is not None:
                knowledge_context = DocumentHarness.build_knowledge_context(
                    knowledge_graph, document_result
                )

            reasoning_step_count = sum(
                len(task_result.get("pipeline", [])) for task_result in task_results.values()
            )

            knowledge_record = self.memory_manager.update_knowledge_memory(
                primary_result, case_dir=planner_request.case_dir
            )
            event_record = self.memory_manager.update_event_memory(planner_request, workflow_result)
            reasoning_record = self.memory_manager.update_reasoning_memory(
                primary_result,
                workflow_id=workflow_id,
                knowledge_context=knowledge_context,
                event_refs=list(self.memory_manager.event_refs),
                goal=goal or f"change_request:{request_id}",
                task_id=task_id,
                task_results=task_results,
            )
            reasoning_id = reasoning_record.payload.get("reasoning_id", "")
            task_record = self.memory_manager.update_task_memory(
                last_task or task_graph.ordered_tasks()[0],
                workflow_result,
                reasoning_id=reasoning_id,
                result=primary_result,
                task_results=task_results,
            )
            evaluation_record = self.memory_manager.update_evaluation_memory(
                primary_result,
                workflow_id=workflow_id,
                workflow_result=workflow_result,
                reasoning_id=reasoning_id,
                knowledge_context=knowledge_context,
                event_refs=list(self.memory_manager.event_refs),
                reasoning_step_count=reasoning_step_count,
            )
            evaluation_id = evaluation_record.payload.get("evaluation_id", "")
            execution_plan_id = ""
            if execution_plan is not None:
                execution_plan_id = execution_plan.plan_id
            elif planner_request.metadata.get("execution_plan"):
                execution_plan_id = planner_request.metadata["execution_plan"].get("plan_id", "")

            memory_records = [
                knowledge_record,
                event_record,
                reasoning_record,
                task_record,
                evaluation_record,
            ]

            return RuntimeResult(
                planner_request=planner_request,
                workflow_id=workflow_id,
                task_graph_id=task_graph_id,
                harness=harness_name,
                result=primary_result,
                memory_records=memory_records,
                knowledge_context=knowledge_context,
                correlation_id=correlation_id,
                event_refs=list(self.memory_manager.event_refs),
                reasoning_id=reasoning_id,
                evaluation_id=evaluation_id,
                task_results=dict(task_results),
                execution_plan_id=execution_plan_id,
            )
        except TaskExecutionError as exc:
            task_id = exc.task.task_id
            harness_name = exc.task.harness
            self._handle_runtime_failure(
                exc.original,
                workflow=workflow if workflow_id else None,
                workflow_id=workflow_id,
                task_id=task_id,
                harness_name=harness_name,
                case_path=case_path,
                request_id=request_id,
                planner_request=locals().get("planner_request"),
                task_graph=locals().get("task_graph"),
                task_results=task_results,
                blocked_task_ids=blocked_task_ids,
            )
            raise exc.original from exc
        except Exception as exc:
            self._handle_runtime_failure(
                exc,
                workflow=workflow if workflow_id else None,
                workflow_id=workflow_id,
                task_id=task_id,
                harness_name=harness_name,
                case_path=case_path,
                request_id=request_id,
                planner_request=locals().get("planner_request"),
                task_graph=locals().get("task_graph"),
                task_results=task_results,
                blocked_task_ids=blocked_task_ids,
            )
            raise

    def _execute_task_graph(
        self,
        *,
        workflow: Workflow,
        workflow_id: str,
        planner_request: Any,
        case_path: Path,
        blocked_task_ids: set[str],
    ) -> tuple[dict[str, dict[str, Any]], TaskSpec | None]:
        task_results: dict[str, dict[str, Any]] = {}
        step_by_task_id = {step.task_id: step for step in workflow.steps}
        last_task: TaskSpec | None = None
        ordered_tasks = workflow.task_graph.ordered_tasks()

        for index, task in enumerate(ordered_tasks):
            if self._should_skip_task(task, blocked_task_ids):
                self.memory_manager.persist_task_skipped(workflow_id, task.task_id)
                blocked_task_ids.add(task.task_id)
                step = step_by_task_id.get(task.task_id)
                if step is not None:
                    step.metadata["status"] = "skipped"
                continue

            step = step_by_task_id.get(task.task_id)
            if step is not None:
                step.status = "running"

            self.memory_manager.persist_task_running(
                workflow_id,
                task,
                harness=task.harness,
            )
            self.memory_manager.record_harness_started(
                harness=task.harness,
                task_id=task.task_id,
                workflow_id=workflow_id,
                case_id=case_path.name,
            )

            try:
                result = self.harness_manager.run(task.harness, planner_request, task)
            except Exception as exc:
                self.memory_manager.persist_task_failed(
                    workflow_id,
                    task.task_id,
                    exc,
                    harness=task.harness,
                )
                if step is not None:
                    step.status = "failed"
                blocked_task_ids.add(task.task_id)
                for downstream in ordered_tasks[index + 1 :]:
                    if self._should_skip_task(downstream, blocked_task_ids):
                        self.memory_manager.persist_task_skipped(workflow_id, downstream.task_id)
                        blocked_task_ids.add(downstream.task_id)
                        downstream_step = step_by_task_id.get(downstream.task_id)
                        if downstream_step is not None:
                            downstream_step.metadata["status"] = "skipped"
                raise TaskExecutionError(task, exc) from exc

            self.memory_manager.persist_task_completed(
                workflow_id,
                task,
                result,
                harness=task.harness,
            )
            self.memory_manager.record_harness_completed(
                harness=task.harness,
                task_id=task.task_id,
                workflow_id=workflow_id,
                case_id=case_path.name,
            )

            if step is not None:
                step.status = "completed"

            task_results[task.task_id] = result
            last_task = task

        return task_results, last_task

    @staticmethod
    def _should_skip_task(task: TaskSpec, blocked_task_ids: set[str]) -> bool:
        return any(dep in blocked_task_ids for dep in task.dependencies)

    @staticmethod
    def _select_primary_result(task_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if "task-document-change-pipeline" in task_results:
            return task_results["task-document-change-pipeline"]
        if task_results:
            return next(iter(task_results.values()))
        return {}

    def _handle_runtime_failure(
        self,
        exc: Exception,
        *,
        workflow: Workflow | None,
        workflow_id: str,
        task_id: str,
        harness_name: str,
        case_path: Path,
        request_id: str,
        planner_request: Any,
        task_graph: TaskGraph | None,
        task_results: dict[str, dict[str, Any]],
        blocked_task_ids: set[str],
    ) -> None:
        if workflow_id and task_id:
            if task_id not in task_results:
                self.memory_manager.persist_task_failed(
                    workflow_id,
                    task_id,
                    exc,
                    harness=harness_name or None,
                )
            blocked_task_ids.add(task_id)
            if workflow is not None and task_graph is not None:
                step_by_task_id = {step.task_id: step for step in workflow.steps}
                step = step_by_task_id.get(task_id)
                if step is not None:
                    step.status = "failed"
                started = False
                for task in task_graph.ordered_tasks():
                    if task.task_id == task_id:
                        started = True
                        continue
                    if not started:
                        continue
                    if self._should_skip_task(task, blocked_task_ids):
                        self.memory_manager.persist_task_skipped(workflow_id, task.task_id)
                        blocked_task_ids.add(task.task_id)

            self.memory_manager.persist_workflow_failed(workflow_id)
            if planner_request is not None:
                primary_result = self._select_primary_result(task_results) or {}
                failed_result = WorkflowResult(
                    workflow_id=workflow_id,
                    status="failed",
                    result=primary_result,
                    executed_tasks=list(task_results.keys()),
                )
                self.memory_manager.update_event_memory(planner_request, failed_result)

        self.memory_manager.record_runtime_failed(
            exc,
            workflow_id=workflow_id or None,
            task_id=task_id or None,
            harness=harness_name or None,
            case_id=case_path.name,
        )
        reasoning_failed = self.memory_manager.record_reasoning_failed(
            exc,
            workflow_id=workflow_id or None,
            goal=f"change_request:{request_id}",
            event_refs=list(self.memory_manager.event_refs),
        )
        failed_reasoning_id = (
            reasoning_failed.payload.get("reasoning_id", "") if reasoning_failed else ""
        )
        self.memory_manager.record_evaluation_failed(
            exc,
            workflow_id=workflow_id or "",
            reasoning_id=failed_reasoning_id,
            event_refs=list(self.memory_manager.event_refs),
        )
