from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["low", "medium", "high", "critical"]
LogEventType = Literal[
    "oom",
    "cuda_error",
    "nvidia_xid",
    "restart_loop",
    "disk_full",
    "permission_denied",
    "unknown",
]


@dataclass
class GpuProcess:
    pid: str
    process_name: str
    gpu_memory: str = ""


@dataclass
class GpuDevice:
    gpu_id: int
    name: str
    memory_used_mib: int
    memory_total_mib: int
    utilization_percent: int
    temperature_c: int
    processes: list[GpuProcess] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_id": self.gpu_id,
            "name": self.name,
            "memory_used_mib": self.memory_used_mib,
            "memory_total_mib": self.memory_total_mib,
            "memory_used_percent": round(
                100 * self.memory_used_mib / self.memory_total_mib, 1
            )
            if self.memory_total_mib
            else 0.0,
            "utilization_percent": self.utilization_percent,
            "temperature_c": self.temperature_c,
            "processes": [
                {
                    "pid": process.pid,
                    "process_name": process.process_name,
                    "gpu_memory": process.gpu_memory,
                }
                for process in self.processes
            ],
        }


@dataclass
class DockerContainer:
    container_id: str
    name: str
    image: str
    status: str
    restart_count: int = 0
    unhealthy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "container_id": self.container_id,
            "name": self.name,
            "image": self.image,
            "status": self.status,
            "restart_count": self.restart_count,
            "unhealthy": self.unhealthy,
        }


@dataclass
class LogEvent:
    event_type: LogEventType
    source: str
    line: str
    line_number: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "source": self.source,
            "line": self.line,
            "line_number": self.line_number,
        }


@dataclass
class Incident:
    incident_id: str
    severity: Severity
    title: str
    suspected_causes: list[str]
    affected_resources: list[str]
    recommended_actions: list[str]
    evidence: list[str]
    safety_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "severity": self.severity,
            "title": self.title,
            "suspected_causes": self.suspected_causes,
            "affected_resources": self.affected_resources,
            "recommended_actions": self.recommended_actions,
            "evidence": self.evidence,
            "safety_notes": self.safety_notes,
        }


@dataclass
class IncidentReport:
    harness: str = "operation"
    sample_dir: str = ""
    gpu_status: list[GpuDevice] = field(default_factory=list)
    docker_status: list[DockerContainer] = field(default_factory=list)
    log_events: list[LogEvent] = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)
    severity: Severity = "low"
    summary: str = ""
    recommended_actions: list[str] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "sample_dir": self.sample_dir,
            "gpu_status": [gpu.to_dict() for gpu in self.gpu_status],
            "docker_status": [container.to_dict() for container in self.docker_status],
            "log_events": [event.to_dict() for event in self.log_events],
            "incidents": [incident.to_dict() for incident in self.incidents],
            "severity": self.severity,
            "summary": self.summary,
            "recommended_actions": self.recommended_actions,
            "safety_notes": self.safety_notes,
        }


@dataclass
class OperationResult:
    """RuntimeResult-compatible operation harness output."""

    mode: str = "operation"
    dry_run: bool = True
    incident_report: dict[str, Any] = field(default_factory=dict)
    pipeline: list[dict[str, Any]] = field(default_factory=list)
    review: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "dry_run": self.dry_run,
            "harness": "operation",
            "incident_report": self.incident_report,
            "pipeline": self.pipeline,
            "review": self.review,
            "change_id": None,
            "summary": self.incident_report.get("summary", ""),
        }
