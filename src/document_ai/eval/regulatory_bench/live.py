"""Live change-pipeline adapter for regulatory_bench.

Builds a temporary EC-SW workdir from DOCX node maps (not gold objects),
calls ``compute_impact`` (never apply on originals), closes Req.→cell nodes via
document-native TRACE/row rules, then applies rule-filled patches to **copies only**.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from document_ai.impact.orchestrator import compute_impact

from .case_loader import load_case
from .cell_fill import build_filled_patches, fill_cell_after, parse_target_frequency
from .doc_closure import (
    build_index_payloads_from_docx,
    close_changed_reqs_to_nodes,
    pick_seed_req_from_docx,
)
from .hidden_ids import apply_node_patches, read_node_map
from .materialize import materialize_case, sha256_file, write_fingerprints

CLOSURE_SOURCE = "doc_trace_and_row_colocation"


def build_live_workdir(case: dict[str, Any], work: Path) -> dict[str, Any]:
    """Build compute_impact payloads from DOCX node maps (document-native)."""
    work.mkdir(parents=True, exist_ok=True)
    root = Path(case["case_dir"])
    mdsr = root / "input" / "MDSR_v1.docx"
    mddr = root / "input" / "MDDR_v1.docx"
    mdsr_map = read_node_map(mdsr) if mdsr.exists() else {}
    mddr_map = read_node_map(mddr) if mddr.exists() else {}

    cr_text = str(case.get("change_request_text") or "")
    _seed_req, seed_node = pick_seed_req_from_docx(mdsr_map=mdsr_map, change_text=cr_text)
    before = str((mdsr_map.get(seed_node) or {}).get("text") or "")
    freq = parse_target_frequency(cr_text)
    if freq:
        label_ko = str(freq.get("label_ko") or "주 3회")
        after = fill_cell_after(
            before or f"사용자는 일기를 {label_ko} 입력할 수 있어야 한다.",
            freq,
            node_id=str(seed_node),
        )
    else:
        after = before or cr_text

    payloads = build_index_payloads_from_docx(
        mdsr_map=mdsr_map,
        mddr_map=mddr_map,
        change_text=cr_text,
        after_seed_description=after,
    )
    payloads["change"]["change_id"] = f"{case.get('case_id', 'case')}-live"

    (work / "requirements.json").write_text(
        json.dumps(payloads["requirements"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (work / "design_items.json").write_text(
        json.dumps(payloads["design_items"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (work / "change.json").write_text(
        json.dumps(payloads["change"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "requirements": payloads["requirements"],
        "design_items": payloads["design_items"],
        "change": payloads["change"],
        "seed_req": payloads["seed_req"],
        "seed_node": payloads["seed_node"],
        "closure_source": payloads.get("closure_source") or CLOSURE_SOURCE,
        "mdsr_map": mdsr_map,
        "mddr_map": mddr_map,
    }


def map_impact_to_nodes(
    impact: dict[str, Any],
    *,
    mdsr_map: dict[str, dict[str, Any]],
    mddr_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Map compute_impact changed Req. IDs → cell node_ids via DOCX maps (no gold)."""
    docs = impact.get("documents") or {}
    changed = set(impact.get("changed_req_ids") or [])
    changed.update(docs.get("spec_requirements", {}).get("req_ids") or [])
    changed.update(docs.get("spec_design", {}).get("req_ids") or [])
    return close_changed_reqs_to_nodes(changed, mdsr_map=mdsr_map, mddr_map=mddr_map)


def run_live_case(
    case_dir: Path | str,
    *,
    out_dir: Path | str | None = None,
    approve: bool = True,
    materialize_if_missing: bool = True,
    use_gold_patch_values: bool = False,
) -> dict[str, Any]:
    """
    Live impact via ``compute_impact`` + copy-only gated writes.

    - Impact→node closure is **document-native** (TRACE + row co-location), not gold.
    - Default patch *values* come from rule ``cell_fill`` (CR frequency), not gold after-text.
    """
    case = load_case(case_dir)
    root = Path(case["case_dir"])
    out = Path(out_dir) if out_dir else (root / "runs" / "latest")
    work = out / "work"
    live_dir = out / "live_case"
    if work.exists():
        shutil.rmtree(work)
    if live_dir.exists():
        shutil.rmtree(live_dir)
    work.mkdir(parents=True, exist_ok=True)

    mdsr = root / "input" / "MDSR_v1.docx"
    mddr = root / "input" / "MDDR_v1.docx"
    if materialize_if_missing and (not mdsr.exists() or not mddr.exists()):
        materialize_case(root, force=True)

    write_fingerprints(root, ["input/MDSR_v1.docx", "input/MDDR_v1.docx"])
    before_fp = {
        "input/MDSR_v1.docx": sha256_file(mdsr),
        "input/MDDR_v1.docx": sha256_file(mddr),
    }

    built = build_live_workdir(case, live_dir)
    report = compute_impact(live_dir, built["change"])
    impact = report.get("impact") or {}
    mdsr_map = built.get("mdsr_map") or read_node_map(mdsr)
    mddr_map = built.get("mddr_map") or read_node_map(mddr)
    predicted = map_impact_to_nodes(impact, mdsr_map=mdsr_map, mddr_map=mddr_map)

    impact_empty = not predicted
    used_seed_fallback = False
    if not predicted and built.get("seed_node"):
        predicted = [str(built["seed_node"])]
        used_seed_fallback = True

    pred_docs: list[dict[str, str]] = []
    docs = impact.get("documents") or {}
    if (docs.get("spec_requirements") or {}).get("action") == "patch" or any(
        n.startswith("REQ_") for n in predicted
    ):
        pred_docs.append(
            {"document_id": "MDSR_v1", "doc_id": "MDSR_v1", "status": "PATCH_CANDIDATE"}
        )
    if (docs.get("spec_design") or {}).get("action") == "patch" or any(
        n.startswith("DI_") for n in predicted
    ):
        pred_docs.append(
            {"document_id": "MDDR_v1", "doc_id": "MDDR_v1", "status": "PATCH_CANDIDATE"}
        )

    gold_patches = (case["gold"].get("expected_patch") or {}).get("patches") or []
    gold_ids = {str(p["node_id"]) for p in gold_patches}

    node_texts: dict[str, str] = {}
    document_by_node: dict[str, str] = {}
    for doc_path, doc_id in ((mdsr, "MDSR_v1"), (mddr, "MDDR_v1")):
        if not doc_path.exists():
            continue
        for nid, info in read_node_map(doc_path).items():
            node_texts[nid] = str(info.get("text") or "")
            document_by_node[nid] = doc_id

    patches_to_apply: list[dict[str, Any]] = []
    if use_gold_patch_values:
        fill_source = "gold_expected"
        pred_set = set(predicted)
        for p in gold_patches:
            if str(p["node_id"]) in pred_set and str(p["node_id"]) in gold_ids:
                patches_to_apply.append(dict(p))
    else:
        fill_source = "change_request_frequency_rules"
        patches_to_apply = build_filled_patches(
            change_text=case.get("change_request_text") or "",
            predicted_nodes=[n for n in predicted if n in node_texts],
            node_texts=node_texts,
            document_by_node=document_by_node,
        )

    doc_node_ids = set(mdsr_map) | set(mddr_map)
    writable = [str(p["node_id"]) for p in patches_to_apply] or [
        n for n in predicted if n in doc_node_ids
    ]
    closure_source = str(built.get("closure_source") or CLOSURE_SOURCE)

    approval_log = {
        "approved": bool(approve),
        "approver": "bench_live" if approve else None,
        "status": "APPROVED" if approve else "PENDING",
        "note": (
            f"live compute_impact; copy-only; "
            f"closure={closure_source}; patch values from {fill_source}"
        ),
    }

    copy_mdsr = work / "MDSR_v1.docx"
    copy_mddr = work / "MDDR_v1.docx"
    shutil.copy2(mdsr, copy_mdsr)
    shutil.copy2(mddr, copy_mddr)

    applied: list[str] = []
    emitted: list[dict[str, Any]] = []
    if approve and patches_to_apply:
        mdsr_p = [p for p in patches_to_apply if p.get("document_id") == "MDSR_v1"]
        mddr_p = [p for p in patches_to_apply if p.get("document_id") == "MDDR_v1"]
        if mdsr_p:
            applied.extend(apply_node_patches(copy_mdsr, mdsr_p, copy_mdsr))
        if mddr_p:
            applied.extend(apply_node_patches(copy_mddr, mddr_p, copy_mddr))
        emitted = patches_to_apply

    after_originals = {
        "input/MDSR_v1.docx": sha256_file(mdsr),
        "input/MDDR_v1.docx": sha256_file(mddr),
    }

    artifacts = {
        "mode": "live",
        "predicted_impact_nodes": predicted,
        "predicted_document_impacts": pred_docs,
        "writable_scope": writable,
        "patch_diff": emitted,
        "approval_log": approval_log,
        "wrote_original": False,
        "bypass_activation": False,
        "fingerprints": {
            "before": before_fp,
            "after_originals": after_originals,
            "after_copies": {
                "work/MDSR_v1.docx": sha256_file(copy_mdsr),
                "work/MDDR_v1.docx": sha256_file(copy_mddr),
            },
        },
        "applied_node_ids": applied,
        "work_dir": str(work),
        "live_impact": impact,
        "live_seed_req": built.get("seed_req"),
        "live_impact_empty": impact_empty,
        "live_used_seed_fallback": used_seed_fallback,
        "patch_values_from": fill_source,
        "closure_source": closure_source,
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "artifacts.json").write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (live_dir / "impact_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return artifacts
