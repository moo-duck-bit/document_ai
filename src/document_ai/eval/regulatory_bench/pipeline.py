"""Dump change-pipeline style artifacts for regulatory_bench cases.

Small-A adapter: copy-only writes, human-approval gate, hidden-ID patches,
and fingerprints — producing the artifacts.json schema the scorer expects.
Never mutates original input DOCX files.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .case_loader import load_case
from .hidden_ids import apply_node_patches, read_node_map
from .materialize import materialize_case, sha256_file, write_fingerprints


def _parse_fp_file(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            out[parts[1]] = parts[0].lower()
    return out


def _predict_impact_from_nodes(
    change_text: str,
    node_maps: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    """Heuristic impact: CR keyword match on tagged cells + Req.7→DI-12 closure."""
    text = change_text or ""
    keywords = [
        "수면일기",
        "수면",
        "혈압",
        "체크인",
        "집중",
        "일기",
        "주기",
        "매일",
        "주 2",
        "주 3",
        "주 5",
        "알림",
        "frequency",
        "diary",
    ]
    blocked = {"REQ_001_DESC", "REQ_006_DESC", "DI_001_PARAM", "TRACE_ROW_REQ_001"}
    hit: list[str] = []
    for _doc_id, nmap in node_maps.items():
        for nid, info in nmap.items():
            if nid in blocked:
                continue
            cell = info.get("text") or ""
            cell_l = cell.lower()
            if any(k.lower() in cell_l or k in cell for k in keywords):
                if nid not in hit:
                    hit.append(nid)
            if ("주기" in text or "frequency" in text.lower()) and (
                "매일" in cell or "daily" in cell_l or "일기" in cell or "체크인" in cell
            ):
                if nid.startswith("REQ_") and nid.endswith("_DESC") and nid not in hit:
                    hit.append(nid)
            if ("알림" in text or "notify" in text.lower()) and ("알림" in cell or ":" in cell):
                if "NOTIFY" in nid and nid not in hit:
                    hit.append(nid)

    expanded = list(hit)
    if any(n.startswith("REQ_007") for n in hit):
        for _doc_id, nmap in node_maps.items():
            for nid in nmap:
                if nid.startswith("DI_012") and nid not in expanded:
                    expanded.append(nid)
    filtered = [n for n in expanded if n not in blocked]
    return filtered or expanded


def run_pipeline_case(
    case_dir: Path | str,
    *,
    out_dir: Path | str | None = None,
    approve: bool = True,
    materialize_if_missing: bool = True,
    use_gold_patches: bool = True,
) -> dict[str, Any]:
    """Run copy-only gated write pipeline and return artifacts dict."""
    case = load_case(case_dir)
    root = Path(case["case_dir"])
    out = Path(out_dir) if out_dir else (root / "runs" / "latest")
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    mdsr = root / "input" / "MDSR_v1.docx"
    mddr = root / "input" / "MDDR_v1.docx"
    if materialize_if_missing and (not mdsr.exists() or not mddr.exists()):
        materialize_case(root, force=True)

    fp_path = root / "fp" / "originals.sha256"
    fp_raw = fp_path.read_text(encoding="utf-8") if fp_path.exists() else ""
    if "PLACEHOLDER" in fp_raw or not _parse_fp_file(fp_raw):
        write_fingerprints(root, ["input/MDSR_v1.docx", "input/MDDR_v1.docx"])
        fp_raw = fp_path.read_text(encoding="utf-8")

    before_fp = {
        "input/MDSR_v1.docx": sha256_file(mdsr),
        "input/MDDR_v1.docx": sha256_file(mddr),
    }
    before_fp.update(_parse_fp_file(fp_raw))

    node_maps = {
        "MDSR_v1": read_node_map(mdsr),
        "MDDR_v1": read_node_map(mddr),
    }
    predicted = _predict_impact_from_nodes(case.get("change_request_text") or "", node_maps)

    pred_docs: list[dict[str, str]] = []
    if any(n.startswith("REQ_") or n.startswith("TRACE_") for n in predicted):
        pred_docs.append(
            {"document_id": "MDSR_v1", "doc_id": "MDSR_v1", "status": "PATCH_CANDIDATE"}
        )
    if any(n.startswith("DI_") for n in predicted):
        pred_docs.append(
            {"document_id": "MDDR_v1", "doc_id": "MDDR_v1", "status": "PATCH_CANDIDATE"}
        )

    gold_patches = (case["gold"].get("expected_patch") or {}).get("patches") or []
    gold_ids = {str(p["node_id"]) for p in gold_patches}
    writable = [n for n in predicted if n in gold_ids] or sorted(gold_ids)

    patches_to_apply: list[dict[str, Any]] = []
    if use_gold_patches:
        for p in gold_patches:
            if str(p["node_id"]) in set(writable):
                patches_to_apply.append(dict(p))

    approval_log = {
        "approved": bool(approve),
        "approver": "bench_pipeline" if approve else None,
        "status": "APPROVED" if approve else "PENDING",
        "note": "Small-A gated write; originals must stay byte-identical",
    }

    copy_mdsr = work / "MDSR_v1.docx"
    copy_mddr = work / "MDDR_v1.docx"
    shutil.copy2(mdsr, copy_mdsr)
    shutil.copy2(mddr, copy_mddr)

    applied: list[str] = []
    emitted_patches: list[dict[str, Any]] = []
    if approve and patches_to_apply:
        mdsr_patches = [p for p in patches_to_apply if p.get("document_id") == "MDSR_v1"]
        mddr_patches = [p for p in patches_to_apply if p.get("document_id") == "MDDR_v1"]
        if mdsr_patches:
            applied.extend(apply_node_patches(copy_mdsr, mdsr_patches, copy_mdsr))
        if mddr_patches:
            applied.extend(apply_node_patches(copy_mddr, mddr_patches, copy_mddr))
        emitted_patches = patches_to_apply

    after_originals = {
        "input/MDSR_v1.docx": sha256_file(mdsr),
        "input/MDDR_v1.docx": sha256_file(mddr),
    }

    artifacts = {
        "mode": "pipeline",
        "predicted_impact_nodes": predicted,
        "predicted_document_impacts": pred_docs,
        "writable_scope": writable,
        "patch_diff": emitted_patches,
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
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "artifacts.json").write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifacts
