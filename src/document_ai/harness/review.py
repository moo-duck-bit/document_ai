"""Review step — structural completeness checks on generated DOCX."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.learn.docx_io import load_document
from document_ai.render.mdsr import UNIQUE_MINDRIUM_PATTERN, verify_completeness
from document_ai.render.mddr import verify_mddr_completeness


def review_case(case_dir: Path) -> dict[str, Any]:
    case_dir = case_dir.resolve()
    result: dict[str, Any] = {"case": str(case_dir), "mdsr": None, "mddr": None, "ok": True}

    req_path = case_dir / "requirements.json"
    requirements = json.loads(req_path.read_text(encoding="utf-8")) if req_path.exists() else {"requirements": []}
    input_path = case_dir / "input.json"
    domain = ""
    if input_path.exists():
        domain = json.loads(input_path.read_text(encoding="utf-8")).get("domain", "")
    design_items = []
    design_path = case_dir / "design_items.json"
    if design_path.exists():
        design_items = json.loads(design_path.read_text(encoding="utf-8")).get("items", [])

    mdsr_doc = case_dir / "output_mdsr.docx"
    if mdsr_doc.exists():
        doc = load_document(mdsr_doc)
        mindrium = sum(
            1 for p in doc.paragraphs if UNIQUE_MINDRIUM_PATTERN.search(p.text or "")
        )
        review = verify_completeness(
            doc,
            requirements.get("requirements", []),
            domain=domain,
        )
        result["mdsr"] = {"mindrium_hits": mindrium, "review": review}
        if mindrium or review["issue_count"] or review["residual_count"]:
            result["ok"] = False
    else:
        result["mdsr"] = {"missing": True}
        result["ok"] = False

    mddr_doc = case_dir / "output_mddr.docx"
    if mddr_doc.exists():
        doc = load_document(mddr_doc)
        review = verify_mddr_completeness(doc, design_items, domain=domain)
        result["mddr"] = {"review": review}
        if review["issue_count"] or review["residual_count"]:
            result["ok"] = False
    elif "spec_design" in json.loads((case_dir / "input.json").read_text(encoding="utf-8")).get(
        "templates_in_set", []
    ):
        result["mddr"] = {"missing": True}
        result["ok"] = False

    # XXCS review is additive — warn but do not fail MDSR/MDDR gate unless XXCS requested and missing.
    templates = []
    if (case_dir / "input.json").exists():
        templates = json.loads((case_dir / "input.json").read_text(encoding="utf-8")).get(
            "templates_in_set", []
        )
    xxcs_doc = case_dir / "output_xxcs.docx"
    if "report_security_verification" in templates:
        if xxcs_doc.exists():
            from document_ai.render.xxcs import verify_xxcs_completeness

            tests = []
            tests_path = case_dir / "security_tests.json"
            if tests_path.exists():
                tests = json.loads(tests_path.read_text(encoding="utf-8")).get("tests", [])
            review = verify_xxcs_completeness(load_document(xxcs_doc), tests)
            result["xxcs"] = {"review": review, "present": True}
            # Soft gate: only fail when XXCS exists but is completely empty
            if review.get("tables_with_content", 0) == 0 and review.get("security_ids_found", 0) == 0:
                result["ok"] = False
        else:
            # Requested in templates but not yet generated — warn, do not fail MDSR/MDDR gate
            result["xxcs"] = {"missing": True, "soft": True}
    elif xxcs_doc.exists():
        result["xxcs"] = {"present": True, "optional": True}

    return result
