from __future__ import annotations

import uuid
from typing import Any

from document_ai.platform.operation.models import (
    DockerContainer,
    GpuDevice,
    Incident,
    IncidentReport,
    LogEvent,
    Severity,
)

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

DEFAULT_SAFETY_NOTE = (
    "Operation Harness does not execute server commands. "
    "All recommended actions require human review and manual execution."
)

_UNSAFE_KEYWORDS = ("kill", "restart", "rm ", "docker restart", "docker rm", "shutdown", "reboot")


def _max_severity(current: Severity, candidate: Severity) -> Severity:
    return candidate if _SEVERITY_RANK[candidate] > _SEVERITY_RANK[current] else current


def _recommendation(text: str) -> str:
    return f"[RECOMMENDATION ONLY - NOT EXECUTED] {text}"


def _safety_for_recommendation(text: str) -> list[str]:
    notes = [DEFAULT_SAFETY_NOTE]
    lowered = text.lower()
    if any(keyword in lowered for keyword in _UNSAFE_KEYWORDS):
        notes.append("This recommendation references a potentially disruptive action and was not executed.")
    return notes


def analyze_incidents(
    *,
    gpu_status: list[GpuDevice],
    docker_status: list[DockerContainer],
    log_events: list[LogEvent],
    sample_dir: str = "",
) -> IncidentReport:
    incidents: list[Incident] = []
    overall_severity: Severity = "low"
    global_actions: list[str] = []
    global_safety: list[str] = [DEFAULT_SAFETY_NOTE]

    for event in log_events:
        if event.event_type == "oom":
            severity: Severity = "critical"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title="GPU or host out-of-memory condition detected",
                suspected_causes=["GPU memory exhaustion", "Large batch size or memory leak"],
                affected_resources=["gpu", "workload"],
                recommended_actions=[
                    _recommendation("Review active GPU processes and reduce batch size or free GPU memory"),
                    _recommendation(
                        "Operator may inspect offending process before any manual termination — kill not executed"
                    ),
                ],
                evidence=[event.line],
                safety_notes=_safety_for_recommendation("kill"),
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

        elif event.event_type == "nvidia_xid":
            severity = "critical"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title="NVIDIA Xid hardware/driver error detected",
                suspected_causes=["GPU driver fault", "Hardware instability", "ECC or PCIe issue"],
                affected_resources=["gpu"],
                recommended_actions=[
                    _recommendation("Collect dmesg and nvidia-bug-report.log for operator review"),
                    _recommendation(
                        "If approved by operator, node reboot may be considered — reboot not executed"
                    ),
                ],
                evidence=[event.line],
                safety_notes=_safety_for_recommendation("reboot"),
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

        elif event.event_type == "cuda_error":
            severity = "high"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title="CUDA runtime error detected in logs",
                suspected_causes=["Invalid kernel launch", "Driver/runtime mismatch", "GPU resource contention"],
                affected_resources=["gpu", "application"],
                recommended_actions=[
                    _recommendation("Review application stack trace and CUDA driver version compatibility"),
                ],
                evidence=[event.line],
                safety_notes=[DEFAULT_SAFETY_NOTE],
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

        elif event.event_type == "restart_loop":
            severity = "high"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title="Container restart loop detected",
                suspected_causes=["Application crash on startup", "Missing dependency", "Resource limits"],
                affected_resources=["docker"],
                recommended_actions=[
                    _recommendation("Inspect container logs and exit codes before any restart action"),
                    _recommendation(
                        "Operator may review docker restart only after root-cause analysis — restart not executed"
                    ),
                ],
                evidence=[event.line],
                safety_notes=_safety_for_recommendation("docker restart"),
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

        elif event.event_type == "disk_full":
            severity = "high"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title="Disk space exhaustion detected",
                suspected_causes=["Log growth", "Artifact accumulation", "Dataset cache overflow"],
                affected_resources=["disk", "host"],
                recommended_actions=[
                    _recommendation("Review disk usage and archive or remove non-essential artifacts manually"),
                    _recommendation("Operator may run cleanup commands manually — rm not executed by harness"),
                ],
                evidence=[event.line],
                safety_notes=_safety_for_recommendation("rm"),
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

        elif event.event_type == "permission_denied":
            severity = "low"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title="Permission denied error detected",
                suspected_causes=["Insufficient file or device permissions", "Wrong user context"],
                affected_resources=["filesystem", "service"],
                recommended_actions=[
                    _recommendation("Verify service user permissions and volume mount ownership"),
                ],
                evidence=[event.line],
                safety_notes=[DEFAULT_SAFETY_NOTE],
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

    for gpu in gpu_status:
        if gpu.memory_total_mib and gpu.memory_used_mib / gpu.memory_total_mib >= 0.95:
            severity = "high"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title=f"GPU {gpu.gpu_id} memory critically high",
                suspected_causes=["Memory leak", "Oversubscribed workloads", "Large resident model"],
                affected_resources=[f"gpu:{gpu.gpu_id}"],
                recommended_actions=[
                    _recommendation(
                        f"Review processes on GPU {gpu.gpu_id} ({gpu.memory_used_mib}/{gpu.memory_total_mib} MiB)"
                    ),
                ],
                evidence=[
                    f"GPU {gpu.gpu_id} memory {gpu.memory_used_mib}/{gpu.memory_total_mib} MiB, util {gpu.utilization_percent}%"
                ],
                safety_notes=[DEFAULT_SAFETY_NOTE],
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)
        elif gpu.utilization_percent >= 95:
            severity = "medium"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title=f"GPU {gpu.gpu_id} utilization sustained at {gpu.utilization_percent}%",
                suspected_causes=["Heavy training job", "Stuck kernel"],
                affected_resources=[f"gpu:{gpu.gpu_id}"],
                recommended_actions=[
                    _recommendation(f"Monitor GPU {gpu.gpu_id} utilization trend and job queue"),
                ],
                evidence=[f"GPU {gpu.gpu_id} utilization {gpu.utilization_percent}%"],
                safety_notes=[DEFAULT_SAFETY_NOTE],
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

    for container in docker_status:
        if container.unhealthy or container.restart_count >= 3:
            severity = "medium" if container.restart_count < 5 else "high"
            incident = Incident(
                incident_id=f"inc-{uuid.uuid4().hex[:8]}",
                severity=severity,
                title=f"Unstable container: {container.name}",
                suspected_causes=["Health check failure", "Crash loop", "Dependency unavailable"],
                affected_resources=[f"container:{container.name}"],
                recommended_actions=[
                    _recommendation(f"Inspect logs for container {container.name} (status: {container.status})"),
                    _recommendation(
                        f"Operator may review restart for {container.name} after diagnosis — restart not executed"
                    ),
                ],
                evidence=[f"{container.name} status={container.status}, restarts={container.restart_count}"],
                safety_notes=_safety_for_recommendation("docker restart"),
            )
            incidents.append(incident)
            overall_severity = _max_severity(overall_severity, severity)

    for incident in incidents:
        global_actions.extend(incident.recommended_actions)
        global_safety.extend(incident.safety_notes)

    summary = _build_summary(incidents, overall_severity)
    return IncidentReport(
        sample_dir=sample_dir,
        gpu_status=gpu_status,
        docker_status=docker_status,
        log_events=log_events,
        incidents=incidents,
        severity=overall_severity,
        summary=summary,
        recommended_actions=_dedupe(global_actions),
        safety_notes=_dedupe(global_safety),
    )


def _build_summary(incidents: list[Incident], severity: Severity) -> str:
    if not incidents:
        return "No operational incidents detected in sample logs."
    titles = ", ".join(incident.title for incident in incidents[:3])
    suffix = f" (+{len(incidents) - 3} more)" if len(incidents) > 3 else ""
    return f"Detected {len(incidents)} incident(s) at {severity} severity: {titles}{suffix}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
