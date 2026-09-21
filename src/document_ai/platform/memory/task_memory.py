from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_STATES = frozenset({"PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED"})
WORKFLOW_STATES = frozenset({"PENDING", "RUNNING", "COMPLETED", "FAILED"})

WORKFLOW_FIELDS = (
    "workflow_id",
    "correlation_id",
    "case_id",
    "task_graph_id",
    "status",
    "reasoning_id",
    "started_at",
    "completed_at",
    "task_graph",
    "tasks",
    "execution_order",
    "snapshots",
    "metadata",
)


def normalize_task_state(state: str) -> str:
    normalized = state.upper()
    if normalized not in TASK_STATES:
        raise ValueError(f"Unknown task state: {state}")
    return normalized


def task_spec_to_dict(task: Any) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "name": task.name,
        "harness": task.harness,
        "action": task.action,
        "state": normalize_task_state(task.state),
        "dependencies": list(task.dependencies),
        "agent_assignment": task.agent_assignment,
        "reasoning_id": "",
        "result": None,
        "metadata": dict(task.metadata),
    }


class TaskMemory:
    """Workflow and task state persistence at data/cases/{case_id}/tasks/."""

    def __init__(self, case_dir: Path | None = None) -> None:
        self._case_dir = Path(case_dir) if case_dir else None

    @property
    def case_dir(self) -> Path | None:
        return self._case_dir

    @property
    def tasks_dir(self) -> Path | None:
        if self._case_dir is None:
            return None
        return self._case_dir / "tasks"

    @property
    def index_path(self) -> Path | None:
        tasks_dir = self.tasks_dir
        if tasks_dir is None:
            return None
        return tasks_dir / "index.jsonl"

    def bind_case(self, case_dir: str | Path) -> None:
        self._case_dir = Path(case_dir)

    def create_workflow(
        self,
        *,
        workflow_id: str,
        correlation_id: str,
        case_id: str,
        task_graph: dict[str, Any],
        execution_order: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._case_dir is None:
            self.bind_case(case_id)

        started_at = datetime.now(UTC).isoformat()
        tasks: dict[str, dict[str, Any]] = {}
        for task in task_graph.get("tasks", []):
            task_id = task["task_id"]
            tasks[task_id] = {
                **task,
                "state": normalize_task_state(task.get("state", "PENDING")),
                "reasoning_id": task.get("reasoning_id", ""),
                "result": task.get("result"),
            }

        workflow = {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "case_id": case_id,
            "task_graph_id": task_graph.get("graph_id", ""),
            "status": "PENDING",
            "reasoning_id": "",
            "started_at": started_at,
            "completed_at": "",
            "task_graph": task_graph,
            "tasks": tasks,
            "execution_order": list(execution_order),
            "snapshots": [],
            "metadata": metadata or {},
        }
        self._validate_workflow(workflow)
        self._write_workflow(workflow)
        self._append_index(
            {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "case_id": case_id,
                "task_graph_id": workflow["task_graph_id"],
                "status": "PENDING",
                "started_at": started_at,
                "completed_at": "",
            }
        )
        return workflow

    def save_snapshot(
        self,
        workflow_id: str,
        *,
        trigger: str,
        workflow_status: str | None = None,
    ) -> dict[str, Any]:
        workflow = self.load_workflow(workflow_id)
        if workflow_status is not None:
            workflow["status"] = workflow_status.upper()

        snapshot = {
            "snapshot_id": f"snap-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(UTC).isoformat(),
            "trigger": trigger,
            "workflow_status": workflow["status"],
            "task_states": {
                task_id: task["state"] for task_id, task in workflow["tasks"].items()
            },
        }
        workflow["snapshots"].append(snapshot)
        self._write_workflow(workflow)
        return snapshot

    def update_task(
        self,
        workflow_id: str,
        task_id: str,
        state: str,
        *,
        result: dict[str, Any] | None = None,
        reasoning_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow = self.load_workflow(workflow_id)
        if task_id not in workflow["tasks"]:
            raise KeyError(f"Unknown task_id in workflow: {task_id}")

        task = workflow["tasks"][task_id]
        task["state"] = normalize_task_state(state)
        if result is not None:
            task["result"] = result
        if reasoning_id is not None:
            task["reasoning_id"] = reasoning_id
        if metadata:
            task["metadata"] = {**task.get("metadata", {}), **metadata}

        self._write_workflow(workflow)
        self.save_snapshot(workflow_id, trigger="task_updated")
        return task

    def complete_workflow(
        self,
        workflow_id: str,
        *,
        status: str,
        reasoning_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow = self.load_workflow(workflow_id)
        completed_at = datetime.now(UTC).isoformat()
        workflow["status"] = status.upper()
        workflow["completed_at"] = completed_at
        if reasoning_id is not None:
            workflow["reasoning_id"] = reasoning_id
        if metadata:
            workflow["metadata"] = {**workflow.get("metadata", {}), **metadata}

        self._validate_workflow(workflow)
        self._write_workflow(workflow)
        self.save_snapshot(workflow_id, trigger="workflow_completed")
        self._append_index(
            {
                "workflow_id": workflow_id,
                "correlation_id": workflow["correlation_id"],
                "case_id": workflow["case_id"],
                "task_graph_id": workflow["task_graph_id"],
                "status": workflow["status"],
                "started_at": workflow["started_at"],
                "completed_at": completed_at,
            }
        )
        return workflow

    def load_workflow(self, workflow_id: str) -> dict[str, Any]:
        path = self._workflow_path(workflow_id)
        if path is None or not path.exists():
            raise FileNotFoundError(f"Workflow not found: {workflow_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_workflows(self, *, correlation_id: str | None = None) -> list[dict[str, Any]]:
        entries = self._load_index()
        if correlation_id is not None:
            entries = [entry for entry in entries if entry.get("correlation_id") == correlation_id]
        return self._dedupe_index(entries)

    def replay(self, workflow_id: str) -> dict[str, Any]:
        workflow = self.load_workflow(workflow_id)
        replay_steps = []
        for task_id in workflow["execution_order"]:
            task = workflow["tasks"][task_id]
            replay_steps.append(
                {
                    "task_id": task_id,
                    "name": task["name"],
                    "harness": task["harness"],
                    "action": task["action"],
                    "state": task["state"],
                    "dependencies": list(task.get("dependencies", [])),
                    "reasoning_id": task.get("reasoning_id", ""),
                }
            )
        return {
            "workflow_id": workflow_id,
            "correlation_id": workflow["correlation_id"],
            "status": workflow["status"],
            "execution_order": list(workflow["execution_order"]),
            "replay_steps": replay_steps,
            "snapshots": list(workflow.get("snapshots", [])),
        }

    def clear_workflows(self) -> None:
        tasks_dir = self.tasks_dir
        if tasks_dir is None or not tasks_dir.exists():
            return
        for path in tasks_dir.glob("*.json"):
            path.unlink()
        index_path = self.index_path
        if index_path is not None and index_path.exists():
            index_path.unlink()

    def _workflow_path(self, workflow_id: str) -> Path | None:
        tasks_dir = self.tasks_dir
        if tasks_dir is None:
            return None
        return tasks_dir / f"{workflow_id}.json"

    def _write_workflow(self, workflow: dict[str, Any]) -> None:
        path = self._workflow_path(workflow["workflow_id"])
        if path is None:
            raise ValueError("TaskMemory requires a bound case_dir before write")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_index(self, entry: dict[str, Any]) -> None:
        index_path = self.index_path
        if index_path is None:
            raise ValueError("TaskMemory requires a bound case_dir before index append")
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _load_index(self) -> list[dict[str, Any]]:
        index_path = self.index_path
        if index_path is None or not index_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        for line in index_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            entries.append(json.loads(text))
        return entries

    def _dedupe_index(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for entry in entries:
            workflow_id = entry.get("workflow_id")
            if workflow_id:
                latest[workflow_id] = entry
        return list(latest.values())

    def _validate_workflow(self, workflow: dict[str, Any]) -> None:
        missing = [field_name for field_name in WORKFLOW_FIELDS if field_name not in workflow]
        if missing:
            raise ValueError(f"Workflow record missing fields: {missing}")
