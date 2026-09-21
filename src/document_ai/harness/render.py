"""Render step — delegates to existing fill_from_facts / xxcs renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.paths import SCHEMAS_EC_SW, TEMPLATES_EC_SW
from document_ai.render.fill import fill_from_facts
from document_ai.render.xxcs import fill_xxcs_report

TEMPLATE_FILES = {
    "spec_requirements": "template_mdsr.docx",
    "spec_design": "template_mddr.docx",
    "report_security_verification": "template_xxcs_skeleton.docx",
}

DEFAULT_OUTPUTS = {
    "spec_requirements": "output_mdsr.docx",
    "spec_design": "output_mddr.docx",
    "report_security_verification": "output_xxcs.docx",
}

CASE_PAYLOAD_FILES = {
    "spec_requirements": "requirements.json",
    "spec_design": "design_content.json",
    "report_security_verification": "security_tests.json",
}


def _case_facts(payload: dict[str, Any]) -> dict[str, Any]:
    facts = dict(payload.get("facts") or {})
    if payload.get("standards"):
        facts["standards"] = payload["standards"]
    if payload.get("free_text_hints"):
        facts["free_text_hints"] = payload["free_text_hints"]
    return facts


def render_document(case_dir: Path, template_id: str, *, intake: dict[str, Any] | None = None) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    payload = intake or json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    template_file = TEMPLATE_FILES.get(template_id)
    if not template_file:
        raise ValueError(f"Unknown template_id: {template_id}")

    template_path = TEMPLATES_EC_SW / template_file
    out_path = case_dir / DEFAULT_OUTPUTS.get(template_id, "output.docx")
    facts = _case_facts(payload)

    if template_id == "spec_requirements":
        mdsr_path = case_dir / "mdsr_content.json"
        if mdsr_path.exists():
            facts["mdsr_content"] = json.loads(mdsr_path.read_text(encoding="utf-8"))
    if template_id == "spec_design":
        mddr_path = case_dir / "mddr_content.json"
        if mddr_path.exists():
            facts["mddr_content"] = json.loads(mddr_path.read_text(encoding="utf-8"))

    if template_id == "report_security_verification":
        from document_ai.form_fill.security_tests import ensure_security_tests_payload

        tests_path = case_dir / CASE_PAYLOAD_FILES[template_id]
        if not tests_path.exists():
            ensure_security_tests_payload(case_dir, intake=payload)
        from document_ai.form_fill.security_execution import build_effective_security_payload

        security_payload = build_effective_security_payload(case_dir)
        if not template_path.exists():
            raise FileNotFoundError(f"XXCS skeleton missing: {template_path}")
        return fill_xxcs_report(template_path, facts, security_payload, out_path)

    schema_path = SCHEMAS_EC_SW / f"{template_id}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    extra_payload = None
    content_payload = None
    design_items_payload = None
    payload_file = case_dir / CASE_PAYLOAD_FILES.get(template_id, "")
    if payload_file.exists():
        extra_payload = json.loads(payload_file.read_text(encoding="utf-8"))
        if template_id == "spec_design":
            content_payload = extra_payload
    if template_id == "spec_design":
        design_items_path = case_dir / "design_items.json"
        if design_items_path.exists():
            design_items_payload = json.loads(design_items_path.read_text(encoding="utf-8"))

    return fill_from_facts(
        template_path,
        schema,
        facts,
        out_path,
        requirements_payload=extra_payload if template_id == "spec_requirements" else None,
        content_payload=content_payload,
        design_items_payload=design_items_payload,
        overwrite_requirements=template_id == "spec_requirements",
    )


def render_all(case_dir: Path, *, intake: dict[str, Any] | None = None) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    payload = intake or json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    templates = payload.get("templates_in_set", list(TEMPLATE_FILES.keys()))
    documents: dict[str, Any] = {}
    for template_id in templates:
        result = render_document(case_dir, template_id, intake=payload)
        documents[template_id] = result
    return {"case": str(case_dir), "documents": documents}
