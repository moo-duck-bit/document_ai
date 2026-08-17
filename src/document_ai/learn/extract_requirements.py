from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix
from docx.table import Table


def _req_id_sort_key(req_id: str) -> int:
    m = re.search(r"(\d+)", req_id)
    return int(m.group(1)) if m else 0


def extract_requirements_docx(path: Path) -> dict[str, Any]:
    doc = load_document(path)
    requirements: list[dict[str, str]] = []
    traceability: list[dict[str, str]] = []

    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        matrix = table_matrix(block)
        if not matrix:
            continue

        if re.match(r"^Req\.\s*\d+", matrix[0][0]):
            req_id = matrix[0][0].strip()
            description = ""
            for row in matrix:
                for ci, cell in enumerate(row):
                    text = cell.strip()
                    if not text or re.match(r"^Req\.\s*\d+$", text):
                        continue
                    description = text
            requirements.append({"req_id": req_id, "description": description})
            continue

        for row in matrix:
            if not row or not row[0]:
                continue
            if re.match(r"^[A-Z]{2}-\d+", row[0].strip()):
                traceability.append(
                    {
                        "requirement": row[0].strip(),
                        "linked_reqs": row[3].strip() if len(row) > 3 else "",
                    }
                )

    requirements.sort(key=lambda r: _req_id_sort_key(r["req_id"]))
    return {
        "source": str(path),
        "requirements": requirements,
        "traceability": traceability,
    }


def save_case_requirements(data: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_case_requirements(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
