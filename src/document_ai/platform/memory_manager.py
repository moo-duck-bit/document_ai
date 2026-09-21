from __future__ import annotations



from dataclasses import asdict

from pathlib import Path

from typing import Any



from document_ai.platform.memory.event_memory import EventMemory

from document_ai.platform.memory.knowledge_memory import KnowledgeMemory

from document_ai.platform.memory.reasoning_memory import (
    ReasoningMemory,
    extract_knowledge_refs,
    pipeline_step_to_reasoning_step,
)

from document_ai.platform.memory.task_memory import TaskMemory, task_spec_to_dict

from document_ai.platform.memory.evaluation_memory import (
    EvaluationMemory,
    build_metrics,
    build_task_summary,
)

from document_ai.platform.models import MemoryRecord, PlannerRequest, TaskSpec, WorkflowResult





class MemoryManager:

    """Platform memory coordinator. Knowledge and Event memory are implemented."""



    def __init__(self) -> None:

        self.records: list[MemoryRecord] = []

        self.knowledge = KnowledgeMemory()

        self.events = EventMemory()

        self.reasoning = ReasoningMemory()

        self.tasks = TaskMemory()

        self.evaluations = EvaluationMemory()

        self.correlation_id: str = ""

        self.event_refs: list[str] = []

        self._case_dir: Path | None = None



    def begin_runtime(self, case_dir: str | Path, correlation_id: str) -> None:

        self.correlation_id = correlation_id

        self.event_refs = []

        self.events.bind_case(case_dir)

        self.reasoning.bind_case(case_dir)

        self.tasks.bind_case(case_dir)

        self.evaluations.bind_case(case_dir)

        self._case_dir = Path(case_dir)



    def _record(self, memory_type: str, action: str, payload: dict[str, Any]) -> MemoryRecord:

        record = MemoryRecord(memory_type=memory_type, action=action, payload=payload)

        self.records.append(record)

        return record



    def _append_event(self, event_type: str, **kwargs: Any) -> dict[str, Any] | None:
        if not self.correlation_id:
            return None

        event = self.events.append_event(
            event_type,
            correlation_id=self.correlation_id,
            **kwargs,
        )
        self.event_refs.append(event["event_id"])
        return event



    def load_knowledge_memory(self, case_dir: str | Path) -> MemoryRecord:

        graph = self.knowledge.load(case_dir)

        stats = graph.stats()

        payload = {

            "case_id": graph.case_id,

            "node_count": stats.node_count,

            "edge_count": stats.edge_count,

            "orphan_count": stats.orphan_count,

        }

        event = self._append_event(
            "KnowledgeMemoryLoaded",
            case_id=graph.case_id,
            payload=payload,
        )
        if event:
            payload["event_id"] = event["event_id"]

        return self._record("knowledge", "load", payload)



    def update_knowledge_memory(

        self,

        result: dict[str, Any],

        *,

        case_dir: str | Path | None = None,

    ) -> MemoryRecord:

        payload = self.knowledge.update_after_run(result, case_dir=case_dir)

        event = self._append_event(
            "KnowledgeMemoryUpdated",
            case_id=payload.get("case_id", ""),
            payload=payload,
        )
        if event:
            payload = {**payload, "event_id": event["event_id"]}

        return self._record("knowledge", "update", payload)



    def record_workflow_started(

        self,

        *,

        workflow_id: str,

        task_graph_id: str,

        request_id: str,

        case_id: str,

    ) -> dict[str, Any]:

        return self._append_event(
            "WorkflowStarted",
            case_id=case_id,
            workflow_id=workflow_id,
            payload={"task_graph_id": task_graph_id, "request_id": request_id},
        )



    def record_workflow_completed(

        self,

        request: PlannerRequest,

        workflow_result: WorkflowResult,

    ) -> MemoryRecord:

        event = self._append_event(
            "WorkflowCompleted",
            case_id=request.case_dir.name,
            workflow_id=workflow_result.workflow_id,
            payload={
                "request_id": request.request_id,
                "status": workflow_result.status,
                "executed_tasks": workflow_result.executed_tasks,
            },
        )

        return self._record(
            "event",
            "append",
            {
                "request_id": request.request_id,
                "workflow_id": workflow_result.workflow_id,
                "status": workflow_result.status,
                "event_id": event["event_id"] if event else "",
            },
        )



    def record_harness_started(

        self,

        *,

        harness: str,

        task_id: str,

        workflow_id: str,

        case_id: str,

    ) -> dict[str, Any]:

        return self._append_event(
            "HarnessStarted",
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
        )



    def record_harness_completed(

        self,

        *,

        harness: str,

        task_id: str,

        workflow_id: str,

        case_id: str,

        status: str = "completed",

    ) -> dict[str, Any]:

        return self._append_event(
            "HarnessCompleted",
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
            payload={"status": status},
        )



    def record_runtime_failed(

        self,

        error: BaseException,

        *,

        workflow_id: str | None = None,

        task_id: str | None = None,

        harness: str | None = None,

        case_id: str,

    ) -> dict[str, Any]:

        return self._append_event(
            "RuntimeFailed",
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
            payload={"error_type": type(error).__name__, "error_message": str(error)},
        )



    def update_event_memory(self, request: PlannerRequest, workflow_result: WorkflowResult) -> MemoryRecord:

        return self.record_workflow_completed(request, workflow_result)



    def record_task_started(
        self,
        *,
        task_id: str,
        workflow_id: str,
        case_id: str,
        harness: str | None = None,
    ) -> dict[str, Any] | None:
        return self._append_event(
            "TaskStarted",
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
        )

    def record_task_completed(
        self,
        *,
        task_id: str,
        workflow_id: str,
        case_id: str,
        harness: str | None = None,
        status: str = "completed",
    ) -> dict[str, Any] | None:
        return self._append_event(
            "TaskCompleted",
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
            payload={"status": status},
        )

    def record_task_failed(
        self,
        error: BaseException,
        *,
        task_id: str,
        workflow_id: str,
        case_id: str,
        harness: str | None = None,
    ) -> dict[str, Any] | None:
        return self._append_event(
            "TaskFailed",
            case_id=case_id,
            workflow_id=workflow_id,
            task_id=task_id,
            harness=harness,
            payload={"error_type": type(error).__name__, "error_message": str(error)},
        )

    def create_persisted_workflow(
        self,
        workflow: Any,
        task_graph: Any,
    ) -> dict[str, Any] | None:
        if not self.correlation_id or self._case_dir is None:
            return None

        graph_payload = {
            "graph_id": task_graph.graph_id,
            "tasks": [task_spec_to_dict(task) for task in task_graph.tasks],
            "metadata": dict(task_graph.metadata),
        }
        execution_order = [task.task_id for task in task_graph.ordered_tasks()]
        persisted = self.tasks.create_workflow(
            workflow_id=workflow.workflow_id,
            correlation_id=self.correlation_id,
            case_id=self._case_dir.name,
            task_graph=graph_payload,
            execution_order=execution_order,
            metadata={"request_mode": task_graph.metadata.get("mode")},
        )
        self.tasks.save_snapshot(workflow.workflow_id, trigger="workflow_started", workflow_status="RUNNING")
        return persisted

    def persist_task_running(
        self,
        workflow_id: str,
        task: TaskSpec,
        *,
        harness: str,
    ) -> dict[str, Any] | None:
        if not self.correlation_id or self._case_dir is None:
            return None

        self.record_task_started(
            task_id=task.task_id,
            workflow_id=workflow_id,
            case_id=self._case_dir.name,
            harness=harness,
        )
        return self.tasks.update_task(workflow_id, task.task_id, "RUNNING")

    def persist_task_completed(
        self,
        workflow_id: str,
        task: TaskSpec,
        result: dict[str, Any],
        *,
        harness: str,
    ) -> dict[str, Any] | None:
        if not self.correlation_id or self._case_dir is None:
            return None

        self.record_task_completed(
            task_id=task.task_id,
            workflow_id=workflow_id,
            case_id=self._case_dir.name,
            harness=harness,
        )
        return self.tasks.update_task(workflow_id, task.task_id, "COMPLETED", result=result)

    def persist_task_failed(
        self,
        workflow_id: str,
        task_id: str,
        error: BaseException,
        *,
        harness: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.correlation_id or self._case_dir is None:
            return None

        self.record_task_failed(
            error,
            task_id=task_id,
            workflow_id=workflow_id,
            case_id=self._case_dir.name,
            harness=harness,
        )
        return self.tasks.update_task(workflow_id, task_id, "FAILED")

    def persist_task_skipped(
        self,
        workflow_id: str,
        task_id: str,
        *,
        reason: str = "dependency_failed",
    ) -> dict[str, Any] | None:
        if not self.correlation_id or self._case_dir is None:
            return None
        return self.tasks.update_task(
            workflow_id,
            task_id,
            "SKIPPED",
            metadata={"skip_reason": reason},
        )

    def persist_workflow_failed(self, workflow_id: str) -> dict[str, Any] | None:
        if not self.correlation_id or self._case_dir is None:
            return None
        return self.tasks.complete_workflow(workflow_id, status="FAILED")

    def update_reasoning_memory(
        self,
        result: dict[str, Any],
        *,
        workflow_id: str = "",
        knowledge_context: dict[str, Any] | None = None,
        event_refs: list[str] | None = None,
        goal: str | None = None,
        task_id: str = "",
        task_results: dict[str, dict[str, Any]] | None = None,
    ) -> MemoryRecord:
        pipeline_entries: list[tuple[str, dict[str, Any]]] = []
        if task_results:
            for result_task_id, task_result in task_results.items():
                for step in task_result.get("pipeline", []):
                    pipeline_entries.append((result_task_id, step))
            pipeline_step_count = len(pipeline_entries)
        else:
            pipeline_step_count = len(result.get("pipeline", []))

        if not self.correlation_id or self._case_dir is None:
            return self._record(
                "reasoning",
                "append",
                {
                    "pipeline_steps": pipeline_step_count,
                    "reasoning_id": "",
                },
            )

        case_id = self._case_dir.name
        resolved_goal = goal or f"change_request:{result.get('change_id', 'unknown')}"
        knowledge_refs = extract_knowledge_refs(knowledge_context, case_dir=self._case_dir)
        refs = list(event_refs or self.event_refs)

        trace = self.reasoning.create_trace(
            correlation_id=self.correlation_id,
            case_id=case_id,
            workflow_id=workflow_id,
            goal=resolved_goal,
            event_refs=refs,
            knowledge_refs=knowledge_refs,
            metadata={"mode": result.get("mode"), "dry_run": result.get("dry_run")},
        )

        if task_results:
            sequence = 1
            for result_task_id, step in pipeline_entries:
                reasoning_step = pipeline_step_to_reasoning_step(
                    step,
                    sequence,
                    event_refs=refs,
                    task_id=result_task_id,
                )
                self.reasoning.append_step(trace["reasoning_id"], reasoning_step)
                sequence += 1
        else:
            for index, step in enumerate(result.get("pipeline", []), start=1):
                reasoning_step = pipeline_step_to_reasoning_step(
                    step,
                    index,
                    event_refs=refs,
                    task_id=task_id,
                )
                self.reasoning.append_step(trace["reasoning_id"], reasoning_step)

        conclusion = {
            "change_id": result.get("change_id"),
            "summary": result.get("summary"),
            "review_status": result.get("review", {}).get("status"),
            "impact": {
                "changed_req_ids": (result.get("impact") or {}).get("changed_req_ids", []),
                "linked_design_ids": (result.get("impact") or {}).get("linked_design_ids", []),
                "linked_security_ids": (result.get("impact") or {}).get("linked_security_ids", []),
            },
            "knowledge_context": knowledge_context or {},
            "task_results": list(task_results.keys()) if task_results else [task_id] if task_id else [],
        }
        finalized = self.reasoning.finalize_trace(
            trace["reasoning_id"],
            status="completed",
            conclusion=conclusion,
            metadata={"pipeline_steps": pipeline_step_count},
            event_refs=refs,
            knowledge_refs=knowledge_refs,
        )

        return self._record(
            "reasoning",
            "append",
            {
                "reasoning_id": finalized["reasoning_id"],
                "pipeline_steps": pipeline_step_count,
                "status": finalized["status"],
                "correlation_id": self.correlation_id,
            },
        )

    def record_reasoning_failed(
        self,
        error: BaseException,
        *,
        workflow_id: str | None = None,
        goal: str = "change_request",
        event_refs: list[str] | None = None,
    ) -> MemoryRecord | None:
        if not self.correlation_id or self._case_dir is None:
            return None

        case_id = self._case_dir.name
        refs = list(event_refs or self.event_refs)
        trace = self.reasoning.create_trace(
            correlation_id=self.correlation_id,
            case_id=case_id,
            workflow_id=workflow_id or "",
            goal=goal,
            event_refs=refs,
            metadata={"failed": True},
        )
        finalized = self.reasoning.finalize_trace(
            trace["reasoning_id"],
            status="failed",
            conclusion={
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            metadata={"pipeline_steps": 0},
            event_refs=refs,
        )
        return self._record(
            "reasoning",
            "append",
            {
                "reasoning_id": finalized["reasoning_id"],
                "pipeline_steps": 0,
                "status": finalized["status"],
                "correlation_id": self.correlation_id,
            },
        )



    def update_task_memory(
        self,
        task: TaskSpec,
        workflow_result: WorkflowResult,
        *,
        reasoning_id: str = "",
        result: dict[str, Any] | None = None,
        task_results: dict[str, dict[str, Any]] | None = None,
    ) -> MemoryRecord:
        if not self.correlation_id or self._case_dir is None:
            return self._record(
                "task",
                "update",
                {
                    "task_id": task.task_id,
                    "workflow_id": workflow_result.workflow_id,
                    "task_state": task.state,
                    "reasoning_id": reasoning_id,
                },
            )

        if task_results:
            for task_id, task_result in task_results.items():
                self.tasks.update_task(
                    workflow_result.workflow_id,
                    task_id,
                    "COMPLETED",
                    result=task_result,
                    reasoning_id=reasoning_id or None,
                )
        elif reasoning_id:
            self.tasks.update_task(
                workflow_result.workflow_id,
                task.task_id,
                "COMPLETED",
                result=result,
                reasoning_id=reasoning_id,
            )

        workflow_status = workflow_result.status.upper()
        completed = self.tasks.complete_workflow(
            workflow_result.workflow_id,
            status=workflow_status,
            reasoning_id=reasoning_id or None,
            metadata={"executed_tasks": workflow_result.executed_tasks},
        )

        return self._record(
            "task",
            "update",
            {
                "task_id": task.task_id,
                "workflow_id": workflow_result.workflow_id,
                "task_state": task.state,
                "reasoning_id": reasoning_id,
                "status": completed["status"],
                "correlation_id": self.correlation_id,
            },
        )



    def update_evaluation_memory(
        self,
        result: dict[str, Any],
        *,
        workflow_id: str = "",
        workflow_result: WorkflowResult | None = None,
        reasoning_id: str = "",
        knowledge_context: dict[str, Any] | None = None,
        event_refs: list[str] | None = None,
        reasoning_step_count: int = 0,
    ) -> MemoryRecord:
        review = result.get("review", {})
        issues = review.get("issues", [])
        issue_count = len(issues)

        if not self.correlation_id or self._case_dir is None:
            return self._record(
                "evaluation",
                "update",
                {
                    "review_status": review.get("status"),
                    "issue_count": issue_count,
                    "evaluation_id": "",
                },
            )

        case_id = self._case_dir.name
        refs = list(event_refs or self.event_refs)
        knowledge_refs = extract_knowledge_refs(knowledge_context, case_dir=self._case_dir)

        workflow_snapshot = None
        if workflow_id:
            try:
                workflow_snapshot = self.tasks.load_workflow(workflow_id)
            except FileNotFoundError:
                workflow_snapshot = None

        task_summary = build_task_summary(workflow_snapshot)
        metrics = build_metrics(
            workflow_completed=workflow_result is not None and workflow_result.status == "completed",
            task_success_rate=task_summary["success_rate"],
            issue_count=issue_count,
            has_runtime_error=False,
            event_count=len(refs),
            reasoning_step_count=reasoning_step_count,
        )

        evaluation = self.evaluations.create_evaluation(
            correlation_id=self.correlation_id,
            case_id=case_id,
            workflow_id=workflow_id,
            reasoning_id=reasoning_id,
            event_refs=refs,
            knowledge_refs=knowledge_refs,
            metadata={"change_id": result.get("change_id")},
        )
        finalized = self.evaluations.finalize_evaluation(
            evaluation["evaluation_id"],
            status="completed",
            metrics=metrics,
            review_summary={
                "status": review.get("status"),
                "issues": issues,
            },
            issue_count=issue_count,
            task_summary=task_summary,
            event_refs=refs,
            knowledge_refs=knowledge_refs,
            reasoning_id=reasoning_id,
        )

        return self._record(
            "evaluation",
            "update",
            {
                "evaluation_id": finalized["evaluation_id"],
                "review_status": review.get("status"),
                "issue_count": issue_count,
                "status": finalized["status"],
                "correlation_id": self.correlation_id,
            },
        )

    def record_evaluation_failed(
        self,
        error: BaseException,
        *,
        workflow_id: str = "",
        reasoning_id: str = "",
        event_refs: list[str] | None = None,
    ) -> MemoryRecord | None:
        if not self.correlation_id or self._case_dir is None:
            return None

        case_id = self._case_dir.name
        refs = list(event_refs or self.event_refs)

        workflow_snapshot = None
        if workflow_id:
            try:
                workflow_snapshot = self.tasks.load_workflow(workflow_id)
            except FileNotFoundError:
                workflow_snapshot = None

        task_summary = build_task_summary(workflow_snapshot)
        metrics = build_metrics(
            workflow_completed=False,
            task_success_rate=task_summary["success_rate"],
            issue_count=0,
            has_runtime_error=True,
            event_count=len(refs),
            reasoning_step_count=0,
        )

        evaluation = self.evaluations.create_evaluation(
            correlation_id=self.correlation_id,
            case_id=case_id,
            workflow_id=workflow_id,
            reasoning_id=reasoning_id,
            event_refs=refs,
            metadata={"failed": True},
        )
        finalized = self.evaluations.finalize_evaluation(
            evaluation["evaluation_id"],
            status="failed",
            metrics=metrics,
            review_summary={
                "status": "failed",
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            issue_count=0,
            task_summary=task_summary,
            event_refs=refs,
            reasoning_id=reasoning_id,
        )
        return self._record(
            "evaluation",
            "update",
            {
                "evaluation_id": finalized["evaluation_id"],
                "review_status": "failed",
                "issue_count": 0,
                "status": finalized["status"],
                "correlation_id": self.correlation_id,
            },
        )



    def snapshot(self) -> list[dict[str, Any]]:

        return [asdict(record) for record in self.records]


