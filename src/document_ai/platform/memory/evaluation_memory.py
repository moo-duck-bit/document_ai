from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVALUATION_FIELDS = (
    "evaluation_id",
    "correlation_id",
    "workflow_id",
    "reasoning_id",
    "case_id",
    "status",
    "started_at",
    "completed_at",
    "metrics",
    "review_summary",
    "issue_count",
    "task_summary",
    "event_refs",
    "knowledge_refs",
    "metadata",
)


def build_task_summary(workflow: dict[str, Any] | None) -> dict[str, Any]:
    if workflow is None:
        return {
            "tasks": {},
            "completed_count": 0,
            "total_count": 0,
            "success_rate": 0.0,
        }

    task_states = {
        task_id: task.get("state", "PENDING") for task_id, task in workflow.get("tasks", {}).items()
    }
    total_count = len(task_states)
    completed_count = sum(1 for state in task_states.values() if state == "COMPLETED")
    success_rate = completed_count / total_count if total_count else 0.0
    return {
        "tasks": task_states,
        "completed_count": completed_count,
        "total_count": total_count,
        "success_rate": success_rate,
    }


def build_metrics(
    *,
    workflow_completed: bool,
    task_success_rate: float,
    issue_count: int,
    has_runtime_error: bool,
    event_count: int,
    reasoning_step_count: int,
) -> dict[str, Any]:
    return {
        "workflow_completed": workflow_completed,
        "task_success_rate": task_success_rate,
        "issue_count": issue_count,
        "has_review_issues": issue_count > 0,
        "has_runtime_error": has_runtime_error,
        "event_count": event_count,
        "reasoning_step_count": reasoning_step_count,
    }


class EvaluationMemory:
    """Evaluation snapshots stored at data/cases/{case_id}/evaluations/."""

    def __init__(self, case_dir: Path | None = None) -> None:
        self._case_dir = Path(case_dir) if case_dir else None

    @property
    def case_dir(self) -> Path | None:
        return self._case_dir

    @property
    def evaluations_dir(self) -> Path | None:
        if self._case_dir is None:
            return None
        return self._case_dir / "evaluations"

    @property
    def index_path(self) -> Path | None:
        evaluations_dir = self.evaluations_dir
        if evaluations_dir is None:
            return None
        return evaluations_dir / "index.jsonl"

    def bind_case(self, case_dir: str | Path) -> None:
        self._case_dir = Path(case_dir)

    def create_evaluation(
        self,
        *,
        correlation_id: str,
        case_id: str,
        workflow_id: str,
        reasoning_id: str = "",
        event_refs: list[str] | None = None,
        knowledge_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._case_dir is None:
            self.bind_case(case_id)

        evaluation_id = f"eval-{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC).isoformat()
        evaluation = {
            "evaluation_id": evaluation_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "reasoning_id": reasoning_id,
            "case_id": case_id,
            "status": "in_progress",
            "started_at": started_at,
            "completed_at": "",
            "metrics": {},
            "review_summary": {},
            "issue_count": 0,
            "task_summary": {},
            "event_refs": list(event_refs or []),
            "knowledge_refs": list(knowledge_refs or []),
            "metadata": metadata or {},
        }
        self._validate_evaluation(evaluation)
        self._write_evaluation(evaluation)
        self._append_index(
            {
                "evaluation_id": evaluation_id,
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "reasoning_id": reasoning_id,
                "case_id": case_id,
                "status": "in_progress",
                "started_at": started_at,
                "completed_at": "",
            }
        )
        return evaluation

    def finalize_evaluation(
        self,
        evaluation_id: str,
        *,
        status: str,
        metrics: dict[str, Any],
        review_summary: dict[str, Any],
        issue_count: int,
        task_summary: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        event_refs: list[str] | None = None,
        knowledge_refs: list[str] | None = None,
        reasoning_id: str | None = None,
    ) -> dict[str, Any]:
        evaluation = self.load_evaluation(evaluation_id)
        completed_at = datetime.now(UTC).isoformat()
        evaluation["status"] = status
        evaluation["completed_at"] = completed_at
        evaluation["metrics"] = metrics
        evaluation["review_summary"] = review_summary
        evaluation["issue_count"] = issue_count
        evaluation["task_summary"] = task_summary
        if metadata:
            evaluation["metadata"] = {**evaluation.get("metadata", {}), **metadata}
        if event_refs is not None:
            evaluation["event_refs"] = list(event_refs)
        if knowledge_refs is not None:
            evaluation["knowledge_refs"] = list(knowledge_refs)
        if reasoning_id is not None:
            evaluation["reasoning_id"] = reasoning_id

        self._validate_evaluation(evaluation)
        self._write_evaluation(evaluation)
        self._append_index(
            {
                "evaluation_id": evaluation_id,
                "correlation_id": evaluation["correlation_id"],
                "workflow_id": evaluation["workflow_id"],
                "reasoning_id": evaluation["reasoning_id"],
                "case_id": evaluation["case_id"],
                "status": status,
                "started_at": evaluation["started_at"],
                "completed_at": completed_at,
            }
        )
        return evaluation

    def load_evaluation(self, evaluation_id: str) -> dict[str, Any]:
        path = self._evaluation_path(evaluation_id)
        if path is None or not path.exists():
            raise FileNotFoundError(f"Evaluation not found: {evaluation_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_evaluations(self, *, correlation_id: str | None = None) -> list[dict[str, Any]]:
        entries = self._load_index()
        if correlation_id is not None:
            entries = [entry for entry in entries if entry.get("correlation_id") == correlation_id]
        return self._dedupe_index(entries)

    def clear_evaluations(self) -> None:
        evaluations_dir = self.evaluations_dir
        if evaluations_dir is None or not evaluations_dir.exists():
            return
        for path in evaluations_dir.glob("*.json"):
            path.unlink()
        index_path = self.index_path
        if index_path is not None and index_path.exists():
            index_path.unlink()

    def _evaluation_path(self, evaluation_id: str) -> Path | None:
        evaluations_dir = self.evaluations_dir
        if evaluations_dir is None:
            return None
        return evaluations_dir / f"{evaluation_id}.json"

    def _write_evaluation(self, evaluation: dict[str, Any]) -> None:
        path = self._evaluation_path(evaluation["evaluation_id"])
        if path is None:
            raise ValueError("EvaluationMemory requires a bound case_dir before write")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_index(self, entry: dict[str, Any]) -> None:
        index_path = self.index_path
        if index_path is None:
            raise ValueError("EvaluationMemory requires a bound case_dir before index append")
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
            evaluation_id = entry.get("evaluation_id")
            if evaluation_id:
                latest[evaluation_id] = entry
        return list(latest.values())

    def _validate_evaluation(self, evaluation: dict[str, Any]) -> None:
        missing = [field_name for field_name in EVALUATION_FIELDS if field_name not in evaluation]
        if missing:
            raise ValueError(f"Evaluation record missing fields: {missing}")
