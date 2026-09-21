# -*- coding: utf-8 -*-
"""PR-16: Feature-Flag DOCX Activation Writer.

Consumes Preview Validation Gate results and optionally writes PASS-only
activations onto a *copy* of the source DOCX.

Defaults:
  DOCX_ACTIVATION_ENABLED=false
  DOCX_ACTIVATION_POLICY=strict_global

Never mutates source DOCX in place. Never reinterprets Gate decisions.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.impact.preserve_patch import sha256_file
from document_ai.learn.docx_io import iter_blocks
from document_ai.render.requirements import _req_id_from_table

ExecutionPolicy = Literal["strict_global", "eligible_only"]

SUPPORTED_DOCX_OPERATIONS = frozenset({"UPDATE", "CONSTRAIN", "REPLACE"})

REASON = {
    "FEATURE_FLAG_DISABLED": "DOCX activation feature flag is disabled.",
    "GLOBAL_GATE_NOT_PASS": "strict_global policy requires global_status=PASS.",
    "ITEM_NOT_PASS": "Gate final_status is not PASS.",
    "ITEM_NOT_ELIGIBLE": "eligible_for_docx_activation is false.",
    "ACTIVATION_NOT_AUTO_APPLY": "activation_decision is not AUTO_APPLY.",
    "PREVIEW_NOT_APPLIED": "preview_applied is false.",
    "UNSUPPORTED_DOCX_OPERATION": "Operation is not enabled for DOCX activation.",
    "SOURCE_DOCX_MISSING": "Source DOCX path missing or not found.",
    "TARGET_NOT_FOUND": "No unique target location found.",
    "TARGET_AMBIGUOUS": "Multiple target locations matched.",
    "BEFORE_TEXT_MISMATCH": "Located target text does not match before_text.",
    "FORMAT_PRESERVATION_UNSAFE": "Cannot replace text without unsafe formatting loss.",
    "OUTPUT_ALREADY_EXISTS": "Output path already exists; refuse overwrite.",
    "DOCX_OPEN_FAILED": "Failed to open DOCX.",
    "DOCX_SAVE_FAILED": "Failed to save DOCX.",
    "OUTPUT_REOPEN_FAILED": "Output DOCX cannot be reopened.",
    "OUTPUT_VALIDATION_FAILED": "Activated DOCX failed validation.",
    "SOURCE_HASH_CHANGED": "Source DOCX hash changed during activation.",
    "UNRELATED_CONTENT_CHANGED": "Unrelated content changed unexpectedly.",
    "PREVIEW_OUTPUT_MISMATCH": "DOCX after_text does not match preview.",
    "WRITE_SUCCEEDED": "Write succeeded.",
    "PATCH_STATUS_NOT_VALID": "patch_validation_status is not VALID.",
    "LANGUAGE_STATUS_NOT_VALID": "language_validation_status is not VALID.",
    "SKIPPED_BY_POLICY": "Skipped by execution policy.",
    "UNKNOWN_STATE": "Unknown gate/activation state; fail-closed skip.",
}


def is_docx_activation_enabled(
    *,
    env: dict[str, str] | None = None,
    override: bool | None = None,
) -> bool:
    if override is not None:
        return bool(override)
    src = env if env is not None else os.environ
    raw = str(src.get("DOCX_ACTIVATION_ENABLED", "false")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def resolve_execution_policy(
    *,
    env: dict[str, str] | None = None,
    override: str | None = None,
) -> ExecutionPolicy:
    if override in ("strict_global", "eligible_only"):
        return override  # type: ignore[return-value]
    src = env if env is not None else os.environ
    raw = str(src.get("DOCX_ACTIVATION_POLICY", "strict_global")).strip().lower()
    if raw == "eligible_only":
        return "eligible_only"
    return "strict_global"


@dataclass
class DocxActivationPlanItem:
    activation_item_id: str
    gate_result_id: str
    patch_id: str
    draft_id: str
    atomic_change_id: str
    requirement_id: str | None
    document: str
    field: str
    source_docx_path: str
    output_docx_path: str
    gate_final_status: str
    eligible_for_docx_activation: bool
    activation_decision: str
    preview_applied: bool
    operation: str
    before_text: str
    after_text: str
    target_locator: str = ""
    locator_strategy: str = ""
    expected_match_count: int = 1
    actual_match_count: int = 0
    planned: bool = False
    skip_reason_codes: list[str] = field(default_factory=list)
    write_attempted: bool = False
    write_succeeded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(getattr(obj, "__dict__", {}) or {})


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _unique_output_path(out_dir: Path, stem: str) -> Path:
    """Never overwrite existing activated outputs."""
    base = out_dir / f"{stem}__activated_pr16.docx"
    if not base.exists():
        return base
    for i in range(1, 1000):
        cand = out_dir / f"{stem}__activated_pr16_{i:03d}.docx"
        if not cand.exists():
            return cand
    raise RuntimeError("Unable to allocate unique activated DOCX path")


def _item_eligible_for_plan(gate: dict[str, Any]) -> tuple[bool, list[str]]:
    """Strict PASS checklist — writer does not reinterpret Gate."""
    codes: list[str] = []
    status = str(gate.get("final_status") or "UNKNOWN")
    if status not in ("PASS", "REVIEW", "BLOCK"):
        codes.append("UNKNOWN_STATE")
        return False, codes
    if status != "PASS":
        codes.append("ITEM_NOT_PASS")
    if not bool(gate.get("eligible_for_docx_activation", False)):
        codes.append("ITEM_NOT_ELIGIBLE")
    if str(gate.get("activation_decision") or "") != "AUTO_APPLY":
        codes.append("ACTIVATION_NOT_AUTO_APPLY")
    if not bool(gate.get("preview_applied", False)):
        codes.append("PREVIEW_NOT_APPLIED")
    if str(gate.get("patch_validation_status") or "") != "VALID":
        codes.append("PATCH_STATUS_NOT_VALID")
    if str(gate.get("language_validation_status") or "") != "VALID":
        codes.append("LANGUAGE_STATUS_NOT_VALID")
    if bool(gate.get("actual_docx_changed", False)):
        codes.append("SOURCE_HASH_CHANGED")
    if bool(gate.get("actual_generation_changed", False)):
        codes.append("UNRELATED_CONTENT_CHANGED")
    # Deduplicate while keeping order
    seen: set[str] = set()
    uniq = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return (len(uniq) == 0), uniq


def _paragraph_full_text(paragraph: Paragraph) -> str:
    return "".join(run.text or "" for run in paragraph.runs) or (paragraph.text or "")


def _find_req_table(doc: Document, req_id: str) -> Table | None:
    want = _normalize_ws(str(req_id or ""))
    if not want:
        return None
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        tid = _req_id_from_table(block)
        if tid and _normalize_ws(tid) == want:
            return block
    return None


def _field_label(field: str) -> str | None:
    f = (field or "").lower()
    mapping = {
        "description": "설명",
        "purpose": "목적",
        "criteria": "기준",
        "design_body": "설명",
        "design_condition": "기준",
        "title": None,
    }
    return mapping.get(f, "설명" if f else None)


def _iter_field_paragraphs(doc: Document, req_id: str, field: str) -> list[tuple[str, Paragraph]]:
    """Return (locator, paragraph) candidates for requirement field."""
    out: list[tuple[str, Paragraph]] = []
    table = _find_req_table(doc, req_id)
    label = _field_label(field)
    if table is not None:
        if label:
            for ri, row in enumerate(table.rows):
                if len(row.cells) < 2:
                    continue
                if _normalize_ws(row.cells[0].text) == label:
                    for pi, para in enumerate(row.cells[1].paragraphs):
                        out.append(
                            (f"table:{req_id}:row{ri}:cell1:p{pi}", para)
                        )
                    return out
        # title: first row / heading cell paragraphs
        if (field or "").lower() == "title" and table.rows:
            for pi, para in enumerate(table.rows[0].cells[0].paragraphs):
                out.append((f"table:{req_id}:title:p{pi}", para))
            return out
    # Fallback: body paragraphs containing exact req heading then following paras
    # Only used when no table; still require exact before_text match later.
    for bi, block in enumerate(iter_blocks(doc)):
        if isinstance(block, Paragraph):
            out.append((f"body:p{bi}", block))
    return out


def locate_targets(
    doc: Document,
    *,
    requirement_id: str | None,
    field: str,
    before_text: str,
) -> list[dict[str, Any]]:
    """Structural locate then exact before_text filter. No fuzzy matching."""
    before = before_text or ""
    before_norm = _normalize_ws(before)
    candidates = _iter_field_paragraphs(doc, str(requirement_id or ""), field)
    matches: list[dict[str, Any]] = []
    for locator, para in candidates:
        full = _paragraph_full_text(para)
        if before and before in full:
            matches.append(
                {
                    "locator": locator,
                    "strategy": "requirement_id+field+exact_before",
                    "paragraph": para,
                    "text": full,
                }
            )
        elif before_norm and _normalize_ws(full) == before_norm:
            matches.append(
                {
                    "locator": locator,
                    "strategy": "requirement_id+field+normalized_exact",
                    "paragraph": para,
                    "text": full,
                }
            )
    # If structural field paragraphs empty of exact match, try exact scan of all paras
    # but ONLY when requirement table was found (still scoped) — already covered.
    # Global exact-only fallback when no req_id:
    if not matches and not requirement_id and before:
        for bi, block in enumerate(iter_blocks(doc)):
            if not isinstance(block, Paragraph):
                continue
            full = _paragraph_full_text(block)
            if before in full:
                matches.append(
                    {
                        "locator": f"global:p{bi}",
                        "strategy": "exact_before_text",
                        "paragraph": block,
                        "text": full,
                    }
                )
    return matches


def replace_text_preserving_runs(paragraph: Paragraph, before: str, after: str) -> tuple[bool, str]:
    """Replace before→after inside a single run when possible.

    Returns (ok, reason_code_if_failed).
    """
    if not before:
        return False, "BEFORE_TEXT_MISMATCH"
    runs = list(paragraph.runs)
    if not runs:
        # Empty paragraph — unsafe to invent structure unless after is simple
        return False, "FORMAT_PRESERVATION_UNSAFE"

    # Prefer single-run containment
    containing = [r for r in runs if before in (r.text or "")]
    if len(containing) == 1 and (containing[0].text or "").count(before) == 1:
        r = containing[0]
        r.text = (r.text or "").replace(before, after, 1)
        return True, "WRITE_SUCCEEDED"

    full = "".join(r.text or "" for r in runs)
    if full.count(before) != 1:
        if before not in full and _normalize_ws(full) == _normalize_ws(before):
            # Whole-paragraph normalized match: only safe if single run
            if len(runs) == 1:
                runs[0].text = after
                return True, "WRITE_SUCCEEDED"
            return False, "FORMAT_PRESERVATION_UNSAFE"
        if before not in full:
            return False, "BEFORE_TEXT_MISMATCH"
        return False, "TARGET_AMBIGUOUS"

    # before spans multiple runs → unsafe
    return False, "FORMAT_PRESERVATION_UNSAFE"


def build_docx_activation_plan(
    *,
    gate_results: list[Any],
    preview_entries: list[Any] | None = None,
    patches: list[Any] | None = None,
    source_docx_by_document: dict[str, str | Path],
    output_dir: str | Path,
    global_status: str = "PASS",
    feature_flag_enabled: bool | None = None,
    execution_policy: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build activation plan. Does not write DOCX."""
    enabled = is_docx_activation_enabled(env=env, override=feature_flag_enabled)
    policy = resolve_execution_policy(env=env, override=execution_policy)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prev_map = {_as_dict(p).get("patch_id"): _as_dict(p) for p in (preview_entries or [])}
    patch_map = {_as_dict(p).get("patch_id"): _as_dict(p) for p in (patches or [])}

    # Precompute output paths per source document
    output_paths: dict[str, str] = {}
    source_hashes: dict[str, str] = {}
    for doc_key, src in source_docx_by_document.items():
        sp = Path(src)
        if sp.exists():
            source_hashes[doc_key.upper()] = sha256_file(sp)
            output_paths[doc_key.upper()] = str(
                _unique_output_path(out_dir, sp.stem)
            ).replace("\\", "/")
        else:
            output_paths[doc_key.upper()] = str(
                out_dir / f"{doc_key}__activated_pr16.docx"
            ).replace("\\", "/")

    write_allowed_globally = True
    global_skip: list[str] = []
    if not enabled:
        write_allowed_globally = False
        global_skip.append("FEATURE_FLAG_DISABLED")
    if policy == "strict_global" and str(global_status) != "PASS":
        write_allowed_globally = False
        global_skip.append("GLOBAL_GATE_NOT_PASS")

    items: list[DocxActivationPlanItem] = []
    for g_raw in gate_results or []:
        g = _as_dict(g_raw)
        pid = str(g.get("patch_id") or "")
        prev = prev_map.get(pid) or {}
        patch = patch_map.get(pid) or {}
        doc_name = str(g.get("document") or prev.get("document") or "").upper() or "MDSR"
        src_path = str(source_docx_by_document.get(doc_name) or source_docx_by_document.get(doc_name.lower()) or "")
        out_path = output_paths.get(doc_name, "")

        op = str(patch.get("operation") or prev.get("operation") or "UPDATE")
        before = str(
            prev.get("original_requirement")
            or patch.get("original_requirement")
            or ""
        )
        after = str(
            prev.get("preview_requirement")
            or prev.get("proposed_requirement")
            or patch.get("patched_requirement")
            or ""
        )

        ok, skip_codes = _item_eligible_for_plan(g)
        planned = False
        if not ok:
            pass
        elif op not in SUPPORTED_DOCX_OPERATIONS:
            skip_codes = list(skip_codes) + ["UNSUPPORTED_DOCX_OPERATION"]
        elif not src_path or not Path(src_path).exists():
            skip_codes = list(skip_codes) + ["SOURCE_DOCX_MISSING"]
        elif not write_allowed_globally:
            skip_codes = list(dict.fromkeys(global_skip + skip_codes + ["SKIPPED_BY_POLICY"]))
        else:
            planned = True
            skip_codes = []

        items.append(
            DocxActivationPlanItem(
                activation_item_id=f"DA-{pid}",
                gate_result_id=str(g.get("gate_result_id") or f"PG-{pid}"),
                patch_id=pid,
                draft_id=str(g.get("draft_id") or ""),
                atomic_change_id=str(g.get("atomic_change_id") or ""),
                requirement_id=g.get("requirement_id"),
                document=doc_name,
                field=str(g.get("field") or "description"),
                source_docx_path=str(Path(src_path)).replace("\\", "/") if src_path else "",
                output_docx_path=out_path,
                gate_final_status=str(g.get("final_status") or "UNKNOWN"),
                eligible_for_docx_activation=bool(g.get("eligible_for_docx_activation", False)),
                activation_decision=str(g.get("activation_decision") or ""),
                preview_applied=bool(g.get("preview_applied", False)),
                operation=op,
                before_text=before,
                after_text=after,
                planned=planned,
                skip_reason_codes=skip_codes,
            )
        )

    items.sort(
        key=lambda x: (
            str(x.atomic_change_id),
            str(x.patch_id),
            str(x.document),
            str(x.requirement_id or ""),
            str(x.field),
        )
    )

    return {
        "stage": "docx_activation_plan",
        "schema_version": "docx_activation_writer_v1",
        "feature_flag_enabled": enabled,
        "execution_policy": policy,
        "global_status": global_status,
        "write_allowed": write_allowed_globally and any(i.planned for i in items),
        "global_skip_reason_codes": global_skip,
        "source_hashes": source_hashes,
        "items": items,
        "note": "Plan only — actual_docx_changed remains false until write.",
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def validate_docx_activation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    items: list[DocxActivationPlanItem] = plan.get("items") or []
    for it in items:
        d = it.to_dict() if isinstance(it, DocxActivationPlanItem) else _as_dict(it)
        if d.get("planned"):
            if d.get("gate_final_status") != "PASS":
                issues.append(f"{d.get('patch_id')}:planned_non_pass")
            if not d.get("eligible_for_docx_activation"):
                issues.append(f"{d.get('patch_id')}:planned_not_eligible")
            if d.get("activation_decision") != "AUTO_APPLY":
                issues.append(f"{d.get('patch_id')}:planned_not_auto")
            if d.get("operation") not in SUPPORTED_DOCX_OPERATIONS:
                issues.append(f"{d.get('patch_id')}:planned_unsupported_op")
        if d.get("gate_final_status") in ("REVIEW", "BLOCK") and d.get("planned"):
            issues.append(f"{d.get('patch_id')}:review_block_planned")
    status = "INVALID" if issues else "VALID"
    return {
        "stage": "docx_activation_plan_validation",
        "status": status,
        "issues": issues,
        "planned_count": sum(
            1
            for it in items
            if (it.planned if isinstance(it, DocxActivationPlanItem) else _as_dict(it).get("planned"))
        ),
        "actual_docx_changed": False,
    }


def _apply_item_to_document(doc: Document, item: DocxActivationPlanItem) -> tuple[bool, list[str], str, int]:
    """Apply one planned item. Returns (ok, reasons, locator, match_count)."""
    matches = locate_targets(
        doc,
        requirement_id=item.requirement_id,
        field=item.field,
        before_text=item.before_text,
    )
    n = len(matches)
    if n == 0:
        return False, ["TARGET_NOT_FOUND"], "", 0
    if n > 1:
        return False, ["TARGET_AMBIGUOUS"], matches[0]["locator"], n
    m = matches[0]
    if item.before_text and item.before_text not in m["text"]:
        if _normalize_ws(m["text"]) != _normalize_ws(item.before_text):
            return False, ["BEFORE_TEXT_MISMATCH"], m["locator"], n
    ok, reason = replace_text_preserving_runs(m["paragraph"], item.before_text, item.after_text)
    if not ok:
        # normalized whole-paragraph single-run already handled; try exact in run with norm
        if reason == "BEFORE_TEXT_MISMATCH" and _normalize_ws(m["text"]) == _normalize_ws(
            item.before_text
        ):
            runs = list(m["paragraph"].runs)
            if len(runs) == 1:
                runs[0].text = item.after_text
                return True, ["WRITE_SUCCEEDED"], m["locator"], n
        return False, [reason], m["locator"], n
    return True, ["WRITE_SUCCEEDED"], m["locator"], n


def apply_docx_activation_plan(
    plan: dict[str, Any],
    *,
    force_enable: bool | None = None,
) -> dict[str, Any]:
    """Execute planned writes onto copied DOCX files (never source)."""
    enabled = bool(plan.get("feature_flag_enabled"))
    if force_enable is not None:
        enabled = bool(force_enable)
    items: list[DocxActivationPlanItem] = list(plan.get("items") or [])
    # Ensure dataclass instances
    norm_items: list[DocxActivationPlanItem] = []
    for it in items:
        if isinstance(it, DocxActivationPlanItem):
            norm_items.append(it)
        else:
            norm_items.append(DocxActivationPlanItem(**{k: v for k, v in _as_dict(it).items() if k in DocxActivationPlanItem.__dataclass_fields__}))

    if not enabled:
        for it in norm_items:
            it.write_attempted = False
            it.write_succeeded = False
            if "FEATURE_FLAG_DISABLED" not in it.skip_reason_codes:
                it.skip_reason_codes = list(it.skip_reason_codes) + ["FEATURE_FLAG_DISABLED"]
            it.planned = False
        return {
            "stage": "docx_activation_results",
            "feature_flag_enabled": False,
            "items": norm_items,
            "output_files": [],
            "source_hashes_before": dict(plan.get("source_hashes") or {}),
            "source_hashes_after": dict(plan.get("source_hashes") or {}),
            "output_hashes": {},
            "actual_docx_changed": False,
            "actual_generation_changed": False,
            "note": "Feature flag disabled — no DOCX writes.",
        }

    if not plan.get("write_allowed"):
        for it in norm_items:
            it.write_attempted = False
            it.write_succeeded = False
            it.planned = False
            for c in plan.get("global_skip_reason_codes") or ["SKIPPED_BY_POLICY"]:
                if c not in it.skip_reason_codes:
                    it.skip_reason_codes.append(c)
        return {
            "stage": "docx_activation_results",
            "feature_flag_enabled": True,
            "items": norm_items,
            "output_files": [],
            "source_hashes_before": dict(plan.get("source_hashes") or {}),
            "source_hashes_after": dict(plan.get("source_hashes") or {}),
            "output_hashes": {},
            "actual_docx_changed": False,
            "actual_generation_changed": False,
            "note": "Write not allowed by policy/global gate.",
        }

    source_hashes_before = dict(plan.get("source_hashes") or {})
    # Group planned items by source path
    by_source: dict[str, list[DocxActivationPlanItem]] = {}
    for it in norm_items:
        if it.planned:
            by_source.setdefault(it.source_docx_path, []).append(it)

    output_files: list[str] = []
    output_hashes: dict[str, str] = {}
    errors: list[str] = []

    for src, group in sorted(by_source.items()):
        src_path = Path(src)
        if not src_path.exists():
            for it in group:
                it.write_attempted = True
                it.write_succeeded = False
                it.skip_reason_codes.append("SOURCE_DOCX_MISSING")
            continue
        before_hash = sha256_file(src_path)
        out_path = Path(group[0].output_docx_path)
        if out_path.exists():
            for it in group:
                it.write_attempted = False
                it.write_succeeded = False
                it.skip_reason_codes.append("OUTPUT_ALREADY_EXISTS")
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=f"act_{src_path.stem}_",
            suffix=".docx",
            dir=str(out_path.parent),
        )
        os.close(tmp_fd)
        tmp_path = Path(tmp_name)
        try:
            shutil.copy2(src_path, tmp_path)
            try:
                doc = Document(str(tmp_path))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"open:{exc}")
                for it in group:
                    it.write_attempted = True
                    it.write_succeeded = False
                    it.skip_reason_codes.append("DOCX_OPEN_FAILED")
                tmp_path.unlink(missing_ok=True)
                continue

            for it in group:
                it.write_attempted = True
                ok, reasons, locator, nmatch = _apply_item_to_document(doc, it)
                it.actual_match_count = nmatch
                it.target_locator = locator
                it.locator_strategy = "requirement_id+field+exact_before"
                it.expected_match_count = 1
                if ok:
                    it.write_succeeded = True
                    it.skip_reason_codes = ["WRITE_SUCCEEDED"]
                else:
                    it.write_succeeded = False
                    it.skip_reason_codes = list(reasons)

            try:
                doc.save(str(tmp_path))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"save:{exc}")
                tmp_path.unlink(missing_ok=True)
                for it in group:
                    if it.write_succeeded:
                        it.write_succeeded = False
                        it.skip_reason_codes = ["DOCX_SAVE_FAILED"]
                continue

            # Reopen check
            try:
                Document(str(tmp_path))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"reopen:{exc}")
                tmp_path.unlink(missing_ok=True)
                for it in group:
                    it.write_succeeded = False
                    it.skip_reason_codes = ["OUTPUT_REOPEN_FAILED"]
                continue

            # Atomic replace into final path
            os.replace(str(tmp_path), str(out_path))
            output_files.append(str(out_path).replace("\\", "/"))
            output_hashes[str(out_path).replace("\\", "/")] = sha256_file(out_path)

            # Verify source unchanged
            after_hash = sha256_file(src_path)
            if after_hash != before_hash:
                errors.append("SOURCE_HASH_CHANGED")
                for it in group:
                    it.skip_reason_codes.append("SOURCE_HASH_CHANGED")
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    source_hashes_after = {}
    for doc_key, src in {(it.document, it.source_docx_path) for it in norm_items}:
        p = Path(src)
        if p.exists():
            source_hashes_after[doc_key] = sha256_file(p)

    any_success = any(it.write_succeeded for it in norm_items)
    return {
        "stage": "docx_activation_results",
        "feature_flag_enabled": True,
        "items": norm_items,
        "output_files": output_files,
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after or dict(source_hashes_before),
        "output_hashes": output_hashes,
        "errors": errors,
        "actual_docx_changed": False,  # source never changed; outputs are separate
        "actual_generation_changed": False,
        "activated_output_written": any_success,
        "note": "Writes only to activated output copies; source DOCX unchanged.",
    }


def validate_activated_docx(
    *,
    plan: dict[str, Any],
    results: dict[str, Any],
    preview_entries: list[Any] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    items: list[DocxActivationPlanItem] = results.get("items") or []
    prev_map = {_as_dict(p).get("patch_id"): _as_dict(p) for p in (preview_entries or [])}

    # Source hash invariant
    before = results.get("source_hashes_before") or {}
    after = results.get("source_hashes_after") or {}
    for k, hv in before.items():
        if after.get(k) and after.get(k) != hv:
            issues.append(f"source_hash_changed:{k}")

    for it in items:
        d = it if isinstance(it, DocxActivationPlanItem) else DocxActivationPlanItem(**_as_dict(it))
        if d.write_succeeded:
            if d.gate_final_status != "PASS" or not d.eligible_for_docx_activation:
                issues.append(f"{d.patch_id}:illegal_non_pass_write")
            if d.gate_final_status in ("REVIEW", "BLOCK"):
                issues.append(f"{d.patch_id}:review_block_applied")
            # preview match
            prev = prev_map.get(d.patch_id) or {}
            preview_after = prev.get("preview_requirement") or d.after_text
            if preview_after and d.after_text and preview_after != d.after_text:
                warnings.append(f"{d.patch_id}:preview_text_differs_from_plan")
            # Verify after_text present in output when file exists
            outp = Path(d.output_docx_path)
            if outp.exists() and d.after_text:
                try:
                    doc = Document(str(outp))
                    blob = "\n".join(
                        _paragraph_full_text(p)
                        for b in iter_blocks(doc)
                        for p in (
                            [b]
                            if isinstance(b, Paragraph)
                            else [pp for row in b.rows for cell in row.cells for pp in cell.paragraphs]
                        )
                    )
                    if d.after_text not in blob and _normalize_ws(d.after_text) not in _normalize_ws(
                        blob
                    ):
                        issues.append(f"{d.patch_id}:after_text_missing")
                    if d.before_text and d.before_text == d.after_text:
                        pass
                    elif d.before_text and d.before_text in blob and d.before_text != d.after_text:
                        # before may still appear elsewhere; only fail if unique target still equals before
                        warnings.append(f"{d.patch_id}:before_text_still_present")
                except Exception:  # noqa: BLE001
                    issues.append(f"{d.patch_id}:output_reopen_failed")

    # Flag OFF → no outputs
    if not results.get("feature_flag_enabled"):
        if results.get("output_files"):
            issues.append("flag_off_but_outputs_exist")

    invariants = {
        "source_hash_unchanged": not any(i.startswith("source_hash_changed") for i in issues),
        "only_pass_written": not any("illegal_non_pass_write" in i for i in issues),
        "review_block_not_written": not any("review_block_applied" in i for i in issues),
        "flag_off_no_outputs": (not bool(results.get("feature_flag_enabled")))
        and not bool(results.get("output_files")),
        "actual_docx_unchanged": results.get("actual_docx_changed") is False,
        "actual_generation_unchanged": results.get("actual_generation_changed") is False,
    }
    if results.get("feature_flag_enabled"):
        invariants["flag_off_no_outputs"] = not bool(results.get("output_files")) or True
        # When flag ON, this invariant is N/A — mark True if we don't claim flag-off
        invariants["flag_off_no_outputs"] = True

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "docx_activation_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": invariants,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def build_docx_activation_summary(
    plan: dict[str, Any],
    results: dict[str, Any],
) -> dict[str, Any]:
    items: list[Any] = results.get("items") or plan.get("items") or []

    def _d(it: Any) -> dict[str, Any]:
        return it.to_dict() if hasattr(it, "to_dict") else _as_dict(it)

    dicts = [_d(it) for it in items]
    return {
        "stage": "docx_activation_summary",
        "total_count": len(dicts),
        "planned_count": sum(1 for d in dicts if d.get("planned")),
        "attempted_count": sum(1 for d in dicts if d.get("write_attempted")),
        "succeeded_count": sum(1 for d in dicts if d.get("write_succeeded")),
        "skipped_count": sum(
            1 for d in dicts if not d.get("write_succeeded") and not d.get("planned")
        ),
        "blocked_count": sum(1 for d in dicts if d.get("gate_final_status") == "BLOCK"),
        "review_count": sum(1 for d in dicts if d.get("gate_final_status") == "REVIEW"),
        "unsupported_count": sum(
            1 for d in dicts if "UNSUPPORTED_DOCX_OPERATION" in (d.get("skip_reason_codes") or [])
        ),
        "locator_failure_count": sum(
            1
            for d in dicts
            if set(d.get("skip_reason_codes") or [])
            & {"TARGET_NOT_FOUND", "TARGET_AMBIGUOUS", "BEFORE_TEXT_MISMATCH"}
        ),
        "source_hash": (results.get("source_hashes_before") or plan.get("source_hashes") or {}),
        "output_hash": results.get("output_hashes") or {},
        "feature_flag_enabled": bool(
            results.get("feature_flag_enabled", plan.get("feature_flag_enabled"))
        ),
        "execution_policy": plan.get("execution_policy"),
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def compare_activated_docx_vs_preview(
    results: dict[str, Any],
    preview_entries: list[Any] | None = None,
) -> dict[str, Any]:
    prev_map = {_as_dict(p).get("patch_id"): _as_dict(p) for p in (preview_entries or [])}
    pairs = []
    for it in results.get("items") or []:
        d = it.to_dict() if hasattr(it, "to_dict") else _as_dict(it)
        prev = prev_map.get(d.get("patch_id")) or {}
        preview_after = prev.get("preview_requirement") or ""
        pairs.append(
            {
                "patch_id": d.get("patch_id"),
                "preview_after_text": preview_after,
                "plan_after_text": d.get("after_text"),
                "applied": bool(d.get("write_succeeded")),
                "matched": bool(
                    d.get("write_succeeded")
                    and preview_after
                    and preview_after == d.get("after_text")
                ),
                "reason_codes": list(d.get("skip_reason_codes") or []),
            }
        )
    return {
        "stage": "docx_activation_vs_preview",
        "pair_count": len(pairs),
        "pairs": pairs,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def run_docx_activation_writer(
    *,
    gate_payload: dict[str, Any],
    preview_entries: list[Any] | None = None,
    patches: list[Any] | None = None,
    source_docx_by_document: dict[str, str | Path],
    output_dir: str | Path,
    feature_flag_enabled: bool | None = None,
    execution_policy: str | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Orchestrate plan → (optional) write → validate → summaries."""
    results_gate = gate_payload.get("results") or []
    global_status = str(gate_payload.get("global_status") or "BLOCK")

    plan = build_docx_activation_plan(
        gate_results=results_gate,
        preview_entries=preview_entries,
        patches=patches,
        source_docx_by_document=source_docx_by_document,
        output_dir=output_dir,
        global_status=global_status,
        feature_flag_enabled=feature_flag_enabled,
        execution_policy=execution_policy,
        env=env,
    )
    plan_validation = validate_docx_activation_plan(plan)
    write_results = apply_docx_activation_plan(plan)
    validation = validate_activated_docx(
        plan=plan, results=write_results, preview_entries=preview_entries
    )
    summary = build_docx_activation_summary(plan, write_results)
    vs_preview = compare_activated_docx_vs_preview(write_results, preview_entries)

    # Serialize items to dicts for JSON friendliness
    def _ser_plan(p: dict[str, Any]) -> dict[str, Any]:
        out = dict(p)
        out["items"] = [
            i.to_dict() if isinstance(i, DocxActivationPlanItem) else _as_dict(i)
            for i in (p.get("items") or [])
        ]
        return out

    def _ser_results(r: dict[str, Any]) -> dict[str, Any]:
        out = dict(r)
        out["items"] = [
            i.to_dict() if isinstance(i, DocxActivationPlanItem) else _as_dict(i)
            for i in (r.get("items") or [])
        ]
        return out

    return {
        "plan": _ser_plan(plan),
        "plan_validation": plan_validation,
        "results": _ser_results(write_results),
        "validation": validation,
        "summary": summary,
        "vs_preview": vs_preview,
    }
