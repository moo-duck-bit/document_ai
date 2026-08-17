from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.impact.change import (
    changed_req_ids,
    design_changes_for_patch,
    load_change,
    merge_design_item_changes,
    merge_requirement_changes,
)
from document_ai.impact.graph import TraceabilityGraph
from document_ai.learn.extract_design_items import DesignItemIndex, load_design_items, save_design_items
from document_ai.learn.extract_requirements import save_case_requirements
from document_ai.learn.extract_security_tests import load_security_tests
from document_ai.render.patch import patch_document_file, patch_mdsr_requirements, patch_xxcs_security_tests
from document_ai.render.design_items import patch_mddr_design_items

DEFAULT_OUTPUTS = {
    "spec_requirements": "output_mdsr.docx",
    "spec_design": "output_mddr.docx",
    "report_security_verification": "output_xxcs.docx",
}


def compute_impact(case_dir: Path, change: dict[str, Any]) -> dict[str, Any]:
    req_path = case_dir / "requirements.json"
    if not req_path.exists():
        raise FileNotFoundError(f"Missing {req_path} — run extract-requirements first")

    payload = json.loads(req_path.read_text(encoding="utf-8"))
    graph = TraceabilityGraph(payload.get("traceability", []))

    design_index = None
    design_path = case_dir / "design_items.json"
    if design_path.exists():
        design_index = DesignItemIndex(load_design_items(design_path).get("items", []))

    req_ids = changed_req_ids(change)
    impact = graph.impact(req_ids, design_index=design_index)

    return {
        "change_id": change.get("change_id"),
        "summary": change.get("summary"),
        "impact": impact,
        "outputs": {
            template_id: str(case_dir / filename)
            for template_id, filename in DEFAULT_OUTPUTS.items()
        },
    }


def apply_change(
    case_dir: Path,
    change_path: Path,
    *,
    dry_run: bool = False,
    update_requirements_json: bool = True,
) -> dict[str, Any]:
    change = load_change(change_path)
    report = compute_impact(case_dir, change)
    impact = report["impact"]
    patches: dict[str, Any] = {}

    if dry_run:
        report["dry_run"] = True
        report["patches"] = patches
        return report

    req_changes = change.get("requirement_changes", [])
    design_path = case_dir / "design_items.json"
    design_index = (
        DesignItemIndex(load_design_items(design_path).get("items", []))
        if design_path.exists()
        else None
    )

    mdsr_doc = case_dir / DEFAULT_OUTPUTS["spec_requirements"]
    if mdsr_doc.exists() and impact["documents"]["spec_requirements"]["req_ids"]:
        patched = patch_document_file(mdsr_doc, patch_mdsr_requirements, req_changes)
        patches["spec_requirements"] = {
            "path": str(mdsr_doc),
            "req_ids_patched": patched,
        }

    mddr_doc = case_dir / DEFAULT_OUTPUTS["spec_design"]
    mddr_req_ids = impact["documents"]["spec_design"].get("req_ids", [])
    if mddr_doc.exists() and mddr_req_ids and design_index:
        design_changes = design_changes_for_patch(change, design_index)
        if design_changes:
            patched = patch_document_file(mddr_doc, patch_mddr_design_items, design_changes)
            patches["spec_design"] = {
                "path": str(mddr_doc),
                "req_ids_patched": patched,
            }
            if change.get("update_design_items_json", True):
                payload = load_design_items(design_path)
                updated = merge_design_item_changes(payload, design_changes)
                save_design_items(payload, design_path)
                patches.setdefault("spec_design", {})["design_items_updated"] = updated
    elif mddr_req_ids and not mddr_doc.exists():
        patches["spec_design"] = {
            "skipped": True,
            "reason": f"Missing {mddr_doc.name}",
            "req_ids": mddr_req_ids,
        }

    xxcs_doc = case_dir / DEFAULT_OUTPUTS["report_security_verification"]
    security_ids = impact["documents"]["report_security_verification"].get("security_req_ids", [])
    tests_path = case_dir / "security_tests.json"
    if xxcs_doc.exists() and security_ids and tests_path.exists():
        security_payload = load_security_tests(tests_path)
        stats = patch_document_file(
            xxcs_doc,
            patch_xxcs_security_tests,
            security_payload.get("tests", []),
            security_ids,
        )
        patches["report_security_verification"] = {
            "path": str(xxcs_doc),
            "security_req_ids": security_ids,
            "stats": stats,
        }
    elif security_ids and not xxcs_doc.exists():
        patches["report_security_verification"] = {
            "skipped": True,
            "reason": f"Missing {xxcs_doc.name}",
            "security_req_ids": security_ids,
        }

    if update_requirements_json:
        req_path = case_dir / "requirements.json"
        payload = json.loads(req_path.read_text(encoding="utf-8"))
        updated = merge_requirement_changes(payload, change)
        save_case_requirements(payload, req_path)
        patches["requirements_json"] = {"updated_req_ids": updated}

    report["patches"] = patches
    return report
