from pathlib import Path

import pytest

from document_ai.platform.harness_manager import HarnessManager
from document_ai.platform.operation.docker_parser import parse_docker_ps_file
from document_ai.platform.operation.gpu_parser import parse_nvidia_smi_file
from document_ai.platform.operation.incident_analyzer import analyze_incidents
from document_ai.platform.operation.log_parser import detect_log_events
from document_ai.platform.operation.operation_harness import OperationHarness
from document_ai.platform.planner import RuleBasedPlanner
from document_ai.platform.task_graph import build_task_graph

SAMPLES = Path("data/ops/samples")


def test_parse_nvidia_smi_sample():
    devices = parse_nvidia_smi_file(SAMPLES / "nvidia_smi_sample.txt")

    assert len(devices) == 2
    gpu0 = devices[0]
    assert gpu0.gpu_id == 0
    assert "A100" in gpu0.name
    assert gpu0.memory_used_mib == 38912
    assert gpu0.memory_total_mib == 40960
    assert gpu0.utilization_percent == 100
    assert gpu0.temperature_c == 82
    assert len(gpu0.processes) >= 1


def test_parse_docker_ps_sample():
    containers = parse_docker_ps_file(SAMPLES / "docker_ps_sample.txt")

    assert len(containers) == 4
    pipeline = next(container for container in containers if container.name == "data-pipeline")
    assert pipeline.restart_count == 5
    assert pipeline.unhealthy is True
    assert pipeline.image == "custom/etl:latest"


def test_detect_oom_cuda_xid_log_events():
    docker_logs = (SAMPLES / "docker_logs_sample.txt").read_text(encoding="utf-8")
    dmesg = (SAMPLES / "dmesg_sample.txt").read_text(encoding="utf-8")

    docker_events = detect_log_events(docker_logs, source="docker_logs")
    dmesg_events = detect_log_events(dmesg, source="dmesg")

    docker_types = {event.event_type for event in docker_events}
    dmesg_types = {event.event_type for event in dmesg_events}

    assert "oom" in docker_types
    assert "cuda_error" in docker_types
    assert "restart_loop" in docker_types
    assert "permission_denied" in docker_types
    assert "nvidia_xid" in dmesg_types
    assert "cuda_error" in dmesg_types


def test_incident_severity_calculation():
    gpus = parse_nvidia_smi_file(SAMPLES / "nvidia_smi_sample.txt")
    containers = parse_docker_ps_file(SAMPLES / "docker_ps_sample.txt")
    events = []
    for name in ("docker_logs_sample.txt", "dmesg_sample.txt", "disk_usage_sample.txt"):
        events.extend(detect_log_events((SAMPLES / name).read_text(encoding="utf-8"), source=name))

    report = analyze_incidents(
        gpu_status=gpus,
        docker_status=containers,
        log_events=events,
        sample_dir=str(SAMPLES),
    )

    assert report.severity in {"medium", "high", "critical"}
    assert report.incidents
    assert any(incident.severity == "critical" for incident in report.incidents)
    assert all("[RECOMMENDATION ONLY" in action for action in report.recommended_actions)
    assert all("not executed" in note.lower() or "does not execute" in note.lower() for note in report.safety_notes)


def test_operation_harness_runs_on_samples():
    harness = OperationHarness()
    planner = RuleBasedPlanner()
    request = planner.create_request(
        case_dir="data/ops",
        change="GPU 서버 장애 분석",
        request_id="op-1",
        metadata={"sample_dir": str(SAMPLES)},
    )
    task_graph = build_task_graph(request)
    task = task_graph.tasks[0]

    result = harness.run(request, task)

    assert result["harness"] == "operation"
    assert result["mode"] == "operation"
    assert result["dry_run"] is True
    report = result["incident_report"]
    assert report["sample_dir"]
    assert report["gpu_status"]
    assert report["docker_status"]
    assert report["log_events"]
    assert report["severity"] in {"low", "medium", "high", "critical"}
    assert result["review"]["status"] in {"ok", "warning", "error"}
    assert result["pipeline"]


def test_planner_selects_operation_intent():
    planner = RuleBasedPlanner()

    assert planner.detect_operation_intent("GPU 서버 Docker 로그 장애 분석") is True
    assert planner.detect_operation_intent("req6 requirement update") is False

    request = planner.create_request(
        case_dir="data/ops",
        change="연구실 GPU 서버 장애 로그 분석 요청",
        request_id="op-planner",
        metadata={"sample_dir": str(SAMPLES)},
    )
    task_graph = build_task_graph(request)

    assert request.mode == "operation_request"
    assert task_graph.tasks[0].harness == "operation"
    assert task_graph.tasks[0].action == "analyze_incidents"


def test_harness_manager_registers_operation_harness():
    manager = HarnessManager()
    harness = manager.get("operation")

    assert harness.harness_name == "operation"
    assert "document" in manager._harnesses
    assert "operation" in manager._harnesses


def test_operation_harness_does_not_execute_dangerous_commands():
    harness = OperationHarness()
    planner = RuleBasedPlanner()
    request = planner.create_request(
        case_dir="data/ops",
        change="Docker restart needed for GPU server",
        metadata={"sample_dir": str(SAMPLES)},
    )
    result = harness.run(request, build_task_graph(request).tasks[0])

    # harness only returns recommendations
    for action in result["incident_report"]["recommended_actions"]:
        assert action.startswith("[RECOMMENDATION ONLY")

    report = result["incident_report"]
    dangerous = ("kill", "docker restart", "docker rm", "reboot", "shutdown")
    combined = " ".join(report["recommended_actions"]).lower()
    if any(word in combined for word in dangerous):
        assert any("not executed" in note.lower() for note in report["safety_notes"])
