from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REASONING_FIELDS = (
    "reasoning_id",
    "correlation_id",
    "case_id",
    "workflow_id",
    "status",
    "goal",
    "started_at",
    "completed_at",
    "steps",
    "conclusion",
    "event_refs",
    "knowledge_refs",
    "metadata",
)

STEP_FIELDS = (
    "step_id",
    "sequence",
    "agent_id",
    "action",
    "input",
    "output",
    "status",
    "evidence_refs",
    "event_refs",
    "task_id",
    "metadata",
)


def pipeline_step_to_reasoning_step(
    step: dict[str, Any],
    sequence: int,
    *,
    event_refs: list[str] | None = None,
    task_id: str = "",
) -> dict[str, Any]:
    agent_id = step.get("agent_id", f"agent-{sequence}")
    return {
        "step_id": f"step-{sequence:03d}-{agent_id}",
        "sequence": sequence,
        "agent_id": agent_id,
        "action": f"run_{agent_id}_agent",
        "input": {},
        "output": step.get("data", {}),
        "status": step.get("status", "ok"),
        "evidence_refs": [],
        "event_refs": list(event_refs or []),
        "task_id": task_id,
        "metadata": {"issues": step.get("issues", [])},
    }


def extract_knowledge_refs(
    knowledge_context: dict[str, Any] | None,
    *,
    case_dir: Path | None = None,
) -> list[str]:
    refs: list[str] = []
    if case_dir is not None:
        graph_path = case_dir / "knowledge_graph.json"
        if graph_path.exists():
            refs.append(str(graph_path))

    if not knowledge_context:
        return refs

    for req_id in knowledge_context.get("changed_req_ids", []):
        refs.append(f"req:{req_id}")

    for query in knowledge_context.get("queries", []):
        req_id = query.get("req_id")
        if req_id:
            refs.append(f"query:{req_id}")

    return refs


class ReasoningMemory:
    """Reasoning traces stored at data/cases/{case_id}/reasoning/."""

    def __init__(self, case_dir: Path | None = None) -> None:
        self._case_dir = Path(case_dir) if case_dir else None

    @property
    def case_dir(self) -> Path | None:
        return self._case_dir

    @property
    def reasoning_dir(self) -> Path | None:
        if self._case_dir is None:
            return None
        return self._case_dir / "reasoning"

    @property
    def index_path(self) -> Path | None:
        reasoning_dir = self.reasoning_dir
        if reasoning_dir is None:
            return None
        return reasoning_dir / "index.jsonl"

    def bind_case(self, case_dir: str | Path) -> None:
        self._case_dir = Path(case_dir)

    def create_trace(
        self,
        *,
        correlation_id: str,
        case_id: str,
        workflow_id: str,
        goal: str,
        event_refs: list[str] | None = None,
        knowledge_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._case_dir is None:
            self.bind_case(case_id)

        reasoning_id = f"rsn-{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(UTC).isoformat()
        trace = {
            "reasoning_id": reasoning_id,
            "correlation_id": correlation_id,
            "case_id": case_id,
            "workflow_id": workflow_id,
            "status": "in_progress",
            "goal": goal,
            "started_at": started_at,
            "completed_at": "",
            "steps": [],
            "conclusion": {},
            "event_refs": list(event_refs or []),
            "knowledge_refs": list(knowledge_refs or []),
            "metadata": metadata or {},
        }
        self._validate_trace(trace)
        self._write_trace(trace)
        self._append_index(
            {
                "reasoning_id": reasoning_id,
                "correlation_id": correlation_id,
                "case_id": case_id,
                "workflow_id": workflow_id,
                "status": "in_progress",
                "goal": goal,
                "started_at": started_at,
                "completed_at": "",
            }
        )
        return trace

    def append_step(self, reasoning_id: str, step: dict[str, Any]) -> dict[str, Any]:
        trace = self.load_trace(reasoning_id)
        self._validate_step(step)
        trace["steps"].append(step)
        self._write_trace(trace)
        return step

    def finalize_trace(
        self,
        reasoning_id: str,
        *,
        status: str,
        conclusion: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        event_refs: list[str] | None = None,
        knowledge_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        trace = self.load_trace(reasoning_id)
        completed_at = datetime.now(UTC).isoformat()
        trace["status"] = status
        trace["completed_at"] = completed_at
        trace["conclusion"] = conclusion
        if metadata:
            trace["metadata"] = {**trace.get("metadata", {}), **metadata}
        if event_refs is not None:
            trace["event_refs"] = list(event_refs)
        if knowledge_refs is not None:
            trace["knowledge_refs"] = list(knowledge_refs)
        self._validate_trace(trace)
        self._write_trace(trace)
        self._append_index(
            {
                "reasoning_id": reasoning_id,
                "correlation_id": trace["correlation_id"],
                "case_id": trace["case_id"],
                "workflow_id": trace["workflow_id"],
                "status": status,
                "goal": trace["goal"],
                "started_at": trace["started_at"],
                "completed_at": completed_at,
            }
        )
        return trace

    def load_trace(self, reasoning_id: str) -> dict[str, Any]:
        path = self._trace_path(reasoning_id)
        if path is None or not path.exists():
            raise FileNotFoundError(f"Reasoning trace not found: {reasoning_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_traces(self, *, correlation_id: str | None = None) -> list[dict[str, Any]]:
        index_entries = self._load_index()
        if correlation_id is None:
            return self._dedupe_index(index_entries)

        filtered = [entry for entry in index_entries if entry.get("correlation_id") == correlation_id]
        return self._dedupe_index(filtered)

    def clear_traces(self) -> None:
        reasoning_dir = self.reasoning_dir
        if reasoning_dir is None or not reasoning_dir.exists():
            return
        for path in reasoning_dir.glob("*.json"):
            path.unlink()
        index_path = self.index_path
        if index_path is not None and index_path.exists():
            index_path.unlink()

    def _trace_path(self, reasoning_id: str) -> Path | None:
        reasoning_dir = self.reasoning_dir
        if reasoning_dir is None:
            return None
        return reasoning_dir / f"{reasoning_id}.json"

    def _write_trace(self, trace: dict[str, Any]) -> None:
        path = self._trace_path(trace["reasoning_id"])
        if path is None:
            raise ValueError("ReasoningMemory requires a bound case_dir before write")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_index(self, entry: dict[str, Any]) -> None:
        index_path = self.index_path
        if index_path is None:
            raise ValueError("ReasoningMemory requires a bound case_dir before index append")
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
            reasoning_id = entry.get("reasoning_id")
            if reasoning_id:
                latest[reasoning_id] = entry
        return list(latest.values())

    def _validate_trace(self, trace: dict[str, Any]) -> None:
        missing = [field_name for field_name in REASONING_FIELDS if field_name not in trace]
        if missing:
            raise ValueError(f"Reasoning trace missing fields: {missing}")

    def _validate_step(self, step: dict[str, Any]) -> None:
        missing = [field_name for field_name in STEP_FIELDS if field_name not in step]
        if missing:
            raise ValueError(f"Reasoning step missing fields: {missing}")
