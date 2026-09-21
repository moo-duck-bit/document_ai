from __future__ import annotations

import re
from pathlib import Path

from document_ai.platform.operation.models import GpuDevice, GpuProcess

_GPU_ID_RE = re.compile(r"^\|\s*(\d+)\s+(.+?)\s+(?:Off|On)\s+\|")
_GPU_STATS_RE = re.compile(
    r"(\d+)\s*C\s+.*?\|\s*(?:\d+W\s*/\s*\d+W\s*\|)?\s*(\d+)MiB\s*/\s*(\d+)MiB\s*\|\s*(\d+)%"
)
_PROCESS_RE = re.compile(
    r"^\|\s*(\d+)\s+\S+\s+\S+\s+(\d+)\s+\S+\s+(.+?)\s+(\d+)MiB"
)


def parse_nvidia_smi(text: str) -> list[GpuDevice]:
    lines = text.splitlines()
    devices: list[GpuDevice] = []
    index = 0
    while index < len(lines):
        id_match = _GPU_ID_RE.match(lines[index])
        if id_match and index + 1 < len(lines):
            stats_match = _GPU_STATS_RE.search(lines[index + 1])
            if stats_match:
                devices.append(
                    GpuDevice(
                        gpu_id=int(id_match.group(1)),
                        name=id_match.group(2).strip(),
                        temperature_c=int(stats_match.group(1)),
                        memory_used_mib=int(stats_match.group(2)),
                        memory_total_mib=int(stats_match.group(3)),
                        utilization_percent=int(stats_match.group(4)),
                    )
                )
                index += 2
                continue
        index += 1

    processes_by_gpu: dict[int, list[GpuProcess]] = {device.gpu_id: [] for device in devices}
    for line in lines:
        process_match = _PROCESS_RE.match(line)
        if not process_match:
            continue
        gpu_id = int(process_match.group(1))
        if gpu_id not in processes_by_gpu:
            continue
        processes_by_gpu[gpu_id].append(
            GpuProcess(
                pid=process_match.group(2),
                process_name=process_match.group(3).strip(),
                gpu_memory=f"{process_match.group(4)}MiB",
            )
        )

    for device in devices:
        device.processes = processes_by_gpu.get(device.gpu_id, [])
    return devices


def parse_nvidia_smi_file(path: str | Path) -> list[GpuDevice]:
    return parse_nvidia_smi(Path(path).read_text(encoding="utf-8"))
