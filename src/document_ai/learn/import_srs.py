from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from document_ai.learn.req_ids import normalize_requirement_id, requirement_sort_key

FR_ROW = re.compile(
    r"^\s*(FR-\d+)\s+(.+?)\s+(Must|Should|Could|Won't)\s*(.*)$",
    re.IGNORECASE,
)
NFR_ROW = re.compile(
    r"^\s*(NFR-\d+)\s+(.+?)\s+(.+?)\s*(.*)$",
)
RTM_ROW = re.compile(
    r"^\s*(FR-\d+|NFR-\d+)\s+(TC-\d+)\s+(.+?)\s*$",
    re.IGNORECASE,
)


def _normalize_fr_nfr(raw_id: str) -> str | None:
    return normalize_requirement_id(raw_id.replace("FR-", "FR-").replace("NFR-", "NFR-"))


def import_srs_markdown(path: Path, *, case_id: str = "stt_srs") -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    requirements: list[dict[str, Any]] = []
    traceability: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {
        "case_id": case_id,
        "document_set": "ieee_srs",
        "standard": "IEEE 830 / ISO/IEC/IEEE 29148",
    }

    section = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("# "):
            section = stripped.lstrip("#").strip().lower()
            continue

        rtm = RTM_ROW.match(stripped)
        if rtm:
            req_id = normalize_requirement_id(rtm.group(1))
            test_id = normalize_requirement_id(rtm.group(2))
            if req_id and test_id:
                traceability.append(
                    {
                        "requirement": req_id,
                        "linked_reqs": test_id,
                        "link_type": "test_case",
                        "description": rtm.group(3).strip(),
                    }
                )
            continue

        fr = FR_ROW.match(stripped)
        if fr and ("기능 요구" in section or fr.group(1).upper().startswith("FR-")):
            req_id = normalize_requirement_id(fr.group(1))
            if req_id:
                requirements.append(
                    {
                        "req_id": req_id,
                        "category": "functional",
                        "description": fr.group(2).strip(),
                        "priority": fr.group(3).capitalize(),
                        "notes": fr.group(4).strip(),
                    }
                )
            continue

        nfr = NFR_ROW.match(stripped)
        if nfr and nfr.group(1).upper().startswith("NFR-"):
            req_id = normalize_requirement_id(nfr.group(1))
            if req_id and not any(r["req_id"] == req_id for r in requirements):
                requirements.append(
                    {
                        "req_id": req_id,
                        "category": "non_functional",
                        "description": nfr.group(2).strip(),
                        "criteria": nfr.group(3).strip(),
                        "notes": nfr.group(4).strip(),
                    }
                )

    # Fallback: parse inline table rows without strict section if empty
    if not requirements:
        for line in lines:
            parts = re.split(r"\s{2,}|\t", line.strip())
            if len(parts) >= 3 and parts[0].upper().startswith(("FR-", "NFR-")):
                req_id = normalize_requirement_id(parts[0])
                if not req_id:
                    continue
                requirements.append(
                    {
                        "req_id": req_id,
                        "category": "functional" if req_id.startswith("FR-") else "non_functional",
                        "description": parts[1].strip(),
                        "priority": parts[2].strip() if req_id.startswith("FR-") else "",
                        "criteria": parts[2].strip() if req_id.startswith("NFR-") else "",
                        "notes": parts[3].strip() if len(parts) > 3 else "",
                    }
                )

    if not traceability:
        for line in lines:
            if "TC-" not in line:
                continue
            cells = re.split(r"\s{2,}|\t", line.strip())
            if len(cells) >= 3 and normalize_requirement_id(cells[0]) and normalize_requirement_id(cells[1]):
                traceability.append(
                    {
                        "requirement": normalize_requirement_id(cells[0]),
                        "linked_reqs": normalize_requirement_id(cells[1]),
                        "link_type": "test_case",
                        "description": cells[2].strip(),
                    }
                )

    requirements.sort(key=lambda row: requirement_sort_key(row["req_id"]))
    return {
        "source": str(path),
        "document_set": "ieee_srs",
        "metadata": metadata,
        "requirements": requirements,
        "traceability": traceability,
    }


def save_srs_payload(data: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
