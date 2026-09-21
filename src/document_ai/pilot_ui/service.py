# -*- coding: utf-8 -*-
"""Pilot run lifecycle: create scenario dir, execute runner, load artifacts."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.controlled_writer.approval import make_approval
from document_ai.controlled_writer.orchestrator import run_controlled_writer_engine
from document_ai.scenario.runner import run_user_scenario

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT_ROOT = REPO_ROOT / "data" / "user_scenarios" / "_pilot"

FROZEN_MARKERS = (
    "data/trials/trial-001-mindrium-xa",
    "data/trials/trial-002-lockout-multireq",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "").strip())
    cleaned = cleaned.strip("-._") or "run"
    return cleaned[:64]


def ensure_pilot_root() -> Path:
    PILOT_ROOT.mkdir(parents=True, exist_ok=True)
    return PILOT_ROOT


def run_dir(run_id: str) -> Path:
    path = ensure_pilot_root() / run_id
    if not path.exists():
        raise FileNotFoundError(f"run not found: {run_id}")
    return path


def list_runs(limit: int = 30) -> list[dict[str, Any]]:
    ensure_pilot_root()
    rows: list[dict[str, Any]] = []
    for p in sorted(PILOT_ROOT.iterdir(), reverse=True):
        if not p.is_dir():
            continue
        meta_path = p / "pilot" / "meta.json"
        status = "unknown"
        created_at = None
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            status = meta.get("status", status)
            created_at = meta.get("created_at")
        report_path = p / "output" / "execution_report.json"
        if report_path.exists():
            try:
                status = json.loads(report_path.read_text(encoding="utf-8")).get(
                    "status", status
                )
            except json.JSONDecodeError:
                pass
        rows.append(
            {
                "run_id": p.name,
                "status": status,
                "created_at": created_at,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def create_run(
    *,
    scenario_name: str,
    change_request: str,
    mdsr_bytes: bytes,
    mdsr_filename: str,
    mddr_bytes: bytes,
    mddr_filename: str,
    top_k: int = 15,
    keep_output: bool = False,
    document_set_mode: str = "legacy_pair",
) -> dict[str, Any]:
    ensure_pilot_root()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"{_safe_name(scenario_name)}_{stamp}"
    root = PILOT_ROOT / run_id
    if root.exists():
        raise FileExistsError(run_id)

    input_dir = root / "input"
    ref = input_dir / "reference"
    pilot = root / "pilot"
    ref.mkdir(parents=True)
    pilot.mkdir(parents=True)

    cr = (change_request or "").strip()
    if not cr:
        raise ValueError("change_request is empty")

    (input_dir / "change_request.txt").write_text(cr + "\n", encoding="utf-8")

    mdsr_name = mdsr_filename if "mdsr" in mdsr_filename.lower() else "MDSR.docx"
    mddr_name = mddr_filename if "mddr" in mddr_filename.lower() else "MDDR.docx"
    if not mdsr_name.lower().endswith(".docx"):
        mdsr_name += ".docx"
    if not mddr_name.lower().endswith(".docx"):
        mddr_name += ".docx"
    (ref / mdsr_name).write_bytes(mdsr_bytes)
    (ref / mddr_name).write_bytes(mddr_bytes)

    meta = {
        "run_id": run_id,
        "scenario_name": scenario_name,
        "created_at": utc_now(),
        "status": "created",
        "top_k": top_k,
        "keep_output": keep_output,
        "document_set_mode": document_set_mode or "legacy_pair",
        "paths": {
            "root": str(root).replace("\\", "/"),
            "change_request": str(input_dir / "change_request.txt").replace("\\", "/"),
            "mdsr": str(ref / mdsr_name).replace("\\", "/"),
            "mddr": str(ref / mddr_name).replace("\\", "/"),
        },
    }
    (pilot / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def create_run_from_existing_scenario(
    *,
    source_scenario: str | Path,
    scenario_name: str = "from-existing",
    top_k: int = 15,
) -> dict[str, Any]:
    """Copy inputs from an existing scenario into a new pilot run (never mutate source)."""
    src = Path(source_scenario)
    if not src.is_absolute():
        src = (REPO_ROOT / src).resolve()
    else:
        src = src.resolve()

    norm = str(src).replace("\\", "/")
    for marker in FROZEN_MARKERS:
        if marker in norm and src == (REPO_ROOT / marker.replace("/", "\\")).resolve():
            # Allow *copying from* freeze for demo; refuse using freeze as run root later
            pass
        if "/_pilot/" not in norm and any(
            m in norm for m in ("trial-001", "trial-002")
        ):
            # copying FROM trials is ok; running IN them is not
            pass

    cr = src / "input" / "change_request.txt"
    ref = src / "input" / "reference"
    if not cr.exists() or not ref.is_dir():
        raise FileNotFoundError(f"invalid source scenario: {src}")

    mdsr = next(
        (
            f
            for f in sorted(ref.glob("*.docx"))
            if any(h in f.name.lower() for h in ("mdsr", "요구"))
        ),
        None,
    )
    mddr = next(
        (
            f
            for f in sorted(ref.glob("*.docx"))
            if any(h in f.name.lower() for h in ("mddr", "설계"))
        ),
        None,
    )
    files = sorted(ref.glob("*.docx"))
    if mdsr is None and files:
        mdsr = files[0]
    if mddr is None and len(files) >= 2:
        mddr = files[1]
    if mdsr is None or mddr is None:
        raise FileNotFoundError("MDSR/MDDR not found in source scenario")

    return create_run(
        scenario_name=scenario_name,
        change_request=cr.read_text(encoding="utf-8"),
        mdsr_bytes=mdsr.read_bytes(),
        mdsr_filename=mdsr.name,
        mddr_bytes=mddr.read_bytes(),
        mddr_filename=mddr.name,
        top_k=top_k,
        keep_output=False,
    )


def execute_run(
    run_id: str,
    *,
    top_k: int | None = None,
    keep_output: bool = False,
    document_set_mode: str | None = None,
) -> dict[str, Any]:
    root = run_dir(run_id)
    meta_path = root / "pilot" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    k = int(top_k if top_k is not None else meta.get("top_k", 15))
    mode = document_set_mode or meta.get("document_set_mode") or "legacy_pair"

    meta["status"] = "running"
    meta["started_at"] = utc_now()
    meta["document_set_mode"] = mode
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        report = run_user_scenario(
            root, top_k=k, clean_output=not keep_output, document_set_mode=mode
        )
        meta["status"] = report.get("status", "COMPLETED")
        meta["finished_at"] = utc_now()
        meta["execution_report"] = str(root / "output" / "execution_report.json").replace(
            "\\", "/"
        )
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return get_run(run_id)
    except Exception as exc:  # noqa: BLE001
        meta["status"] = "FAILED"
        meta["error"] = str(exc)
        meta["finished_at"] = utc_now()
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise


def _read_text_if_exists(path: Path, limit: int = 200_000) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n\n…(truncated)…"
    return text


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def get_run(run_id: str) -> dict[str, Any]:
    root = run_dir(run_id)
    out = root / "output"
    meta = _load_json(root / "pilot" / "meta.json") or {}
    report = _load_json(out / "execution_report.json") or {}

    summaries = report.get("summaries") or {}
    impact = summaries.get("impact") or {}
    consistency = summaries.get("consistency") or {}

    artifacts = []
    candidates = [
        ("CHANGE_SUMMARY.md", out / "review" / "CHANGE_SUMMARY.md"),
        ("REVIEW_REQUIRED.md", out / "review" / "REVIEW_REQUIRED.md"),
        ("PATCH_DIFF.md", out / "review" / "PATCH_DIFF.md"),
        ("execution_report.json", out / "execution_report.json"),
        ("updated_MDSR.docx", out / "documents" / "updated_MDSR.docx"),
        ("updated_MDDR.docx", out / "documents" / "updated_MDDR.docx"),
        ("writer_summary.json", out / "writer" / "summary.json"),
        ("writer_result.json", out / "writer" / "writer_result.json"),
        ("writer_validation.json", out / "writer" / "validation.json"),
        ("diff.json", out / "writer" / "diff.json"),
        ("document_set_summary.json", out / "document_set" / "document_set_summary.json"),
        ("mdtm_change_candidates.json", out / "document_set" / "ec_sw" / "mdtm_change_candidates.json"),
        ("mdtm_review_required.json", out / "document_set" / "ec_sw" / "mdtm_review_required.json"),
        ("mdtm_patch_preview.json", out / "document_set" / "ec_sw" / "mdtm_patch_preview.json"),
        ("mdtm_index_summary.json", out / "document_set" / "ec_sw" / "mdtm_index_summary.json"),
    ]
    for name, path in candidates:
        if path.exists():
            artifacts.append(
                {
                    "name": name,
                    "path": str(path).replace("\\", "/"),
                    "download_url": f"/api/pilot/runs/{run_id}/artifacts/{name}",
                }
            )

    approval = _load_json(root / "pilot" / "approval.json")
    writer_extra = _load_json(root / "pilot" / "writer_engine_result.json")
    ds_summary = _load_json(out / "document_set" / "document_set_summary.json")
    mdtm_index = _load_json(out / "document_set" / "ec_sw" / "mdtm_index_summary.json")
    mdtm_change = _load_json(out / "document_set" / "ec_sw" / "mdtm_change_candidates.json")
    mdtm_review = _load_json(out / "document_set" / "ec_sw" / "mdtm_review_required.json")
    mdtm_patch = _load_json(out / "document_set" / "ec_sw" / "mdtm_patch_preview.json")

    return {
        "run_id": run_id,
        "status": report.get("status") or meta.get("status") or "unknown",
        "created_at": meta.get("created_at"),
        "meta": meta,
        "summary": {
            "impact": impact,
            "consistency": consistency,
            "mdsr_patched_req_ids": summaries.get("mdsr_patched_req_ids") or [],
            "mddr_patched_req_ids": summaries.get("mddr_patched_req_ids") or [],
            "retrieval_top": summaries.get("retrieval_top") or [],
            "review_flags": report.get("review_flags") or {},
            "input_hashes_unchanged": report.get("input_hashes_unchanged"),
            "document_set_mode": report.get("document_set_mode")
            or meta.get("document_set_mode")
            or "legacy_pair",
            "document_set": summaries.get("document_set") or ds_summary,
            "mdtm_change": summaries.get("mdtm_change"),
        },
        "review": {
            "change_summary": _read_text_if_exists(out / "review" / "CHANGE_SUMMARY.md"),
            "review_required": _read_text_if_exists(out / "review" / "REVIEW_REQUIRED.md"),
            "patch_diff": _read_text_if_exists(out / "review" / "PATCH_DIFF.md"),
        },
        "document_set": {
            "summary": ds_summary,
            "mdtm_index_summary": mdtm_index,
            "mdtm_impact_candidates": mdtm_change,
            "mdtm_review_required": mdtm_review,
            "mdtm_patch_preview": mdtm_patch,
            "mdtm_write_enabled": False,
            "note": "MDTM Controlled Writer is experimental and OFF by default.",
        },
        "writer": {
            "pipeline_summary": _load_json(out / "writer" / "summary.json"),
            "pipeline_validation": _load_json(out / "writer" / "validation.json"),
            "pilot_approval": approval,
            "pilot_writer_result": writer_extra,
        },
        "artifacts": artifacts,
    }


def resolve_artifact(run_id: str, name: str) -> Path:
    root = run_dir(run_id)
    out = root / "output"
    mapping = {
        "CHANGE_SUMMARY.md": out / "review" / "CHANGE_SUMMARY.md",
        "REVIEW_REQUIRED.md": out / "review" / "REVIEW_REQUIRED.md",
        "PATCH_DIFF.md": out / "review" / "PATCH_DIFF.md",
        "execution_report.json": out / "execution_report.json",
        "updated_MDSR.docx": out / "documents" / "updated_MDSR.docx",
        "updated_MDDR.docx": out / "documents" / "updated_MDDR.docx",
        "writer_summary.json": out / "writer" / "summary.json",
        "writer_result.json": out / "writer" / "writer_result.json",
        "writer_validation.json": out / "writer" / "validation.json",
        "diff.json": out / "writer" / "diff.json",
        "approval.json": root / "pilot" / "approval.json",
        "writer_engine_result.json": root / "pilot" / "writer_engine_result.json",
        "document_set_summary.json": out / "document_set" / "document_set_summary.json",
        "mdtm_change_candidates.json": out / "document_set" / "ec_sw" / "mdtm_change_candidates.json",
        "mdtm_review_required.json": out / "document_set" / "ec_sw" / "mdtm_review_required.json",
        "mdtm_patch_preview.json": out / "document_set" / "ec_sw" / "mdtm_patch_preview.json",
        "mdtm_index_summary.json": out / "document_set" / "ec_sw" / "mdtm_index_summary.json",
    }
    if name not in mapping:
        raise FileNotFoundError(name)
    path = mapping[name]
    if not path.exists():
        raise FileNotFoundError(name)
    # path traversal guard
    if PILOT_ROOT.resolve() not in path.resolve().parents and path.resolve() != PILOT_ROOT.resolve():
        # must be under pilot root
        if not str(path.resolve()).startswith(str(PILOT_ROOT.resolve())):
            raise PermissionError("artifact outside pilot root")
    return path


def save_approval(
    run_id: str,
    *,
    decision: str,
    approved_by: str = "pilot-user",
    reason: str = "",
) -> dict[str, Any]:
    root = run_dir(run_id)
    decision_u = (decision or "").upper()
    if decision_u not in {"APPROVED", "REJECTED", "AUTO_APPROVED", "MANUAL_REQUIRED"}:
        raise ValueError("invalid decision")
    payload = make_approval(
        approval_id=f"APR-{run_id[-8:]}",
        patch_contract_id=f"PCT-{run_id}",
        decision=decision_u,
        approved_by=approved_by,
        approved_at=utc_now(),
        reason=reason or "pilot ui approval",
    ).to_dict()
    path = root / "pilot" / "approval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_writer(run_id: str, *, force_enable: bool = True) -> dict[str, Any]:
    """Run Controlled Writer engine under the pilot run workspace (copy-only fixtures)."""
    root = run_dir(run_id)
    approval = _load_json(root / "pilot" / "approval.json")
    if not approval:
        raise ValueError("approval required before writer")
    if str(approval.get("decision", "")).upper() not in {"APPROVED", "AUTO_APPROVED"}:
        raise ValueError("approval decision must be APPROVED or AUTO_APPROVED")

    work = root / "pilot" / "writer_work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    env = {
        "DOCX_ACTIVATION_ENABLED": "true" if force_enable else "false",
        "CONTROLLED_WRITER_ENABLED": "true" if force_enable else "false",
    }
    pkg = run_controlled_writer_engine(work_dir=work, env=env)
    # Safety assert
    if (pkg.get("summary") or {}).get("original_changed_count", 0) != 0:
        raise RuntimeError("original_changed_count must be 0")

    out_path = root / "pilot" / "writer_engine_result.json"
    slim = {
        "status": pkg.get("validation", {}).get("status"),
        "summary": pkg.get("summary"),
        "validation": pkg.get("validation"),
        "writer_results": pkg.get("writer_results"),
        "diffs": [
            {
                "diff_id": d.get("diff_id"),
                "operation_count": d.get("operation_count"),
                "changed_blocks": d.get("changed_blocks"),
                "before_preview": (d.get("before_text") or "")[:400],
                "after_preview": (d.get("after_text") or "")[:400],
            }
            for d in (pkg.get("diffs") or [])
        ],
        "rollbacks": pkg.get("rollbacks"),
        "approval": approval,
        "work_dir": pkg.get("work_dir"),
        "note": pkg.get("note"),
    }
    out_path.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    return slim
