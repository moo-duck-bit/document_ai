from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.platform.models import PlannerRequest, TaskSpec
from document_ai.platform.operation.docker_parser import parse_docker_ps_file
from document_ai.platform.operation.gpu_parser import parse_nvidia_smi_file
from document_ai.platform.operation.incident_analyzer import analyze_incidents
from document_ai.platform.operation.log_parser import detect_log_events_from_file
from document_ai.platform.operation.models import OperationResult

DEFAULT_SAMPLE_DIR = Path("data/ops/samples")

_SAMPLE_FILES = {
    "nvidia_smi": "nvidia_smi_sample.txt",
    "docker_ps": "docker_ps_sample.txt",
    "docker_logs": "docker_logs_sample.txt",
    "dmesg": "dmesg_sample.txt",
    "disk_usage": "disk_usage_sample.txt",
}


class OperationHarness:
    """Sample-log based GPU/Docker incident analysis harness."""

    harness_name = "operation"

    def run(self, request: PlannerRequest, task: TaskSpec) -> dict[str, Any]:
        sample_dir = self._resolve_sample_dir(request, task)
        gpu_status = self._load_gpu(sample_dir)
        docker_status = self._load_docker(sample_dir)
        log_events = self._load_log_events(sample_dir)

        report = analyze_incidents(
            gpu_status=gpu_status,
            docker_status=docker_status,
            log_events=log_events,
            sample_dir=str(sample_dir),
        )
        incident_dict = report.to_dict()

        review_status = "ok"
        if report.severity in {"high", "critical"}:
            review_status = "error"
        elif report.severity == "medium":
            review_status = "warning"

        issues = [incident.title for incident in report.incidents]
        pipeline = [
            {
                "agent_id": "gpu_monitor",
                "status": "ok" if gpu_status else "warning",
                "data": {"device_count": len(gpu_status)},
                "issues": [],
            },
            {
                "agent_id": "docker_monitor",
                "status": "ok" if docker_status else "warning",
                "data": {"container_count": len(docker_status)},
                "issues": [],
            },
            {
                "agent_id": "log_analyzer",
                "status": "error" if any(event.event_type in {"oom", "nvidia_xid"} for event in log_events) else "ok",
                "data": {"event_count": len(log_events)},
                "issues": issues,
            },
            {
                "agent_id": "incident_reporter",
                "status": review_status,
                "data": {"severity": report.severity, "incident_count": len(report.incidents)},
                "issues": issues,
            },
        ]

        result = OperationResult(
            incident_report=incident_dict,
            pipeline=pipeline,
            review={"status": review_status, "issues": issues},
        )
        return result.to_dict()

    def _resolve_sample_dir(self, request: PlannerRequest, task: TaskSpec) -> Path:
        candidates: list[Path] = []
        if "sample_dir" in request.metadata:
            candidates.append(Path(str(request.metadata["sample_dir"])))
        if "sample_dir" in task.metadata:
            candidates.append(Path(str(task.metadata["sample_dir"])))
        if isinstance(request.change, Path):
            if request.change.is_dir():
                candidates.append(request.change)
        candidates.append(request.case_dir / "ops" / "samples")
        candidates.append(DEFAULT_SAMPLE_DIR)

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return DEFAULT_SAMPLE_DIR

    def _load_gpu(self, sample_dir: Path) -> list:
        path = sample_dir / _SAMPLE_FILES["nvidia_smi"]
        if not path.exists():
            return []
        return parse_nvidia_smi_file(path)

    def _load_docker(self, sample_dir: Path) -> list:
        path = sample_dir / _SAMPLE_FILES["docker_ps"]
        if not path.exists():
            return []
        return parse_docker_ps_file(path)

    def _load_log_events(self, sample_dir: Path) -> list:
        events = []
        for key in ("docker_logs", "dmesg", "disk_usage"):
            path = sample_dir / _SAMPLE_FILES[key]
            if path.exists():
                events.extend(detect_log_events_from_file(path, source=path.name))
        return events
