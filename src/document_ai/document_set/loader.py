# -*- coding: utf-8 -*-
"""Load document_set_registry.json into DocumentDescriptor list."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.document_set.schema import DocumentDescriptor
from document_ai.document_set.validation import validate_descriptors

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "examples" / "ec_sw" / "document_set_registry.json"

ROLE_ALIASES = {
    "traceability_matrix": "traceability",
    "vv_plan": "verification_plan",
    "development_plan": "development_plan",
    "configuration_management": "process",
    "maintenance_process": "process",
    "security_verification_report": "security_verification_report",
    "requirements": "requirements",
    "design": "design",
}

DOC_TYPE_FROM_SHORT = {
    "spec_mdsr": "MDSR",
    "spec_mddr": "MDDR",
    "report_xxcs": "XXCS",
    "matrix_mdtm": "MDTM",
    "plan_mdvp": "MDVP",
    "plan_mddp": "MDDP",
    "process_mdcp": "MDCP",
    "process_mdmp": "MDMP",
}

# Only MDTM newly activated for indexing in this sprint.
DEFAULT_ENABLED_SHORT_IDS = frozenset(
    {
        "spec_mdsr",
        "spec_mddr",
        "report_xxcs",
        "matrix_mdtm",
        "plan_mdvp",
        "plan_mddp",
        "process_mdcp",
        "process_mdmp",
    }
)

INDEXABLE_SHORT_IDS = frozenset({"matrix_mdtm"})


def _normalize_role(raw: str | None) -> str:
    if not raw:
        return "custom"
    return ROLE_ALIASES.get(raw, raw)


def _to_descriptor(entry: dict[str, Any], *, project_root: Path) -> DocumentDescriptor:
    short_id = str(entry.get("short_id") or "")
    rel = str(entry.get("path") or "").replace("\\", "/")
    abs_path = (project_root / rel).resolve() if rel else project_root
    doc_type = DOC_TYPE_FROM_SHORT.get(short_id, short_id.upper())
    role = _normalize_role(str(entry.get("role") or "custom"))
    priority = int(entry.get("priority") or 100)
    # v1 docs without priority sort after MDTM (1) but keep stable: mdsr/mddr first-ish
    if "priority" not in entry:
        priority = {
            "spec_mdsr": 10,
            "spec_mddr": 20,
            "report_xxcs": 30,
        }.get(short_id, 100)
    enabled = short_id in DEFAULT_ENABLED_SHORT_IDS and entry.get("enabled", True) is not False
    return DocumentDescriptor(
        document_id=doc_type,
        short_id=short_id,
        document_type=doc_type,
        document_role=role,
        source_path=str(abs_path).replace("\\", "/"),
        source_format="docx",
        template_id=entry.get("template_id"),
        domain_pack_id="ec_sw_v1",
        priority=priority,
        enabled=bool(enabled),
        metadata={
            "doc_code": entry.get("doc_code"),
            "status": entry.get("status"),
            "agent_support": entry.get("agent_support"),
            "relative_path": rel,
            "indexable": short_id in INDEXABLE_SHORT_IDS,
            "blank_template": entry.get("blank_template"),
        },
    )


def load_document_set_registry(
    registry_path: Path | None = None,
    *,
    project_root: Path | None = None,
    enabled_only: bool = False,
) -> dict[str, Any]:
    """Load registry JSON and return descriptors + validation."""
    root = project_root or PROJECT_ROOT
    path = Path(registry_path) if registry_path else DEFAULT_REGISTRY
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = list(raw.get("documents") or [])
    descriptors = [_to_descriptor(e, project_root=root) for e in entries]
    descriptors.sort(key=lambda d: (d.priority, d.short_id))
    if enabled_only:
        descriptors = [d for d in descriptors if d.enabled]
    validation = validate_descriptors(descriptors, project_root=root)
    return {
        "registry_path": str(path).replace("\\", "/"),
        "document_set": raw.get("document_set"),
        "product": raw.get("product"),
        "descriptors": descriptors,
        "descriptor_dicts": [d.to_dict() for d in descriptors],
        "validation": validation,
        "expansion_order": raw.get("expansion_order") or [],
        "desktop_candidates_not_yet_registered": raw.get(
            "desktop_candidates_not_yet_registered"
        )
        or [],
    }
