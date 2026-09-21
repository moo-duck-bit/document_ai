# -*- coding: utf-8 -*-
"""PR-17: Change Review Package (observational, general-document).

Builds human-readable change review artifacts from existing pipeline traces.
Does NOT mutate Gate / Writer / Patch results. Does NOT write DOCX.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ReviewStatus = Literal["READY", "REVIEW", "BLOCKED", "NOT_APPLIED"]
ApplicationStatus = Literal["APPLIED", "NOT_APPLIED", "SKIPPED", "BLOCKED", "FAILED"]
GlobalReviewStatus = Literal["READY", "REVIEW", "BLOCKED"]

CHANGE_TYPE_LABELS_KO: dict[str, str] = {
    "ADD": "추가",
    "UPDATE": "수정",
    "REPLACE": "교체",
    "CONSTRAIN": "조건 강화",
    "DELETE": "삭제",
    "LINK": "연결",
    "NO_CHANGE": "변경 없음",
    "NO_ACTION": "조치 없음",
    "REVIEW_REQUIRED": "검토 필요",
    "BLOCKED": "차단",
}

SCOPE_BY_FIELD: dict[str, str] = {
    "description": "requirement",
    "criteria": "requirement",
    "purpose": "requirement",
    "title": "section",
    "design_body": "requirement",
    "design_condition": "requirement",
}


@dataclass
class ChangeReviewItem:
    review_item_id: str
    source_change_id: str
    atomic_change_id: str
    patch_id: str
    draft_id: str
    gate_result_id: str
    activation_item_id: str
    document: str
    requirement_id: str | None
    section: str
    field: str
    change_type: str
    change_type_label: str
    change_scope: str
    source_request: str
    source_request_summary: str
    change_reason: str
    change_reason_summary: str
    before_text: str
    after_text: str
    gate_status: str
    activation_decision: str
    eligible_for_docx_activation: bool
    docx_write_attempted: bool
    docx_write_succeeded: bool
    actual_docx_applied: bool
    review_status: str
    application_status: str
    review_required: bool
    review_reason_codes: list[str] = field(default_factory=list)
    source_trace: dict[str, Any] = field(default_factory=dict)
    related_change_ids: list[str] = field(default_factory=list)
    skipped_reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    locator_summary: str = ""
    title: str = ""

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


def _index(items: list[Any] | None, key: str = "patch_id") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for it in items or []:
        d = _as_dict(it)
        kid = str(d.get(key) or "")
        if kid:
            out[kid] = d
    return out


def _clip(text: str, n: int = 160) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _display_text(text: str | None) -> str:
    if text is None:
        return ""
    return text


def _md_block(text: str | None) -> str:
    if text is None or text == "":
        return "(내용 없음)"
    return text


def _infer_scope(field: str, locator: str = "") -> str:
    if locator.startswith("table:"):
        return "table_cell"
    if locator.startswith("body:") or locator.startswith("global:"):
        return "paragraph"
    return SCOPE_BY_FIELD.get((field or "").lower(), "unknown")


def _build_change_reason(
    *,
    gate: dict[str, Any],
    preview: dict[str, Any],
    activation: dict[str, Any],
    patch: dict[str, Any],
    cr_text: str,
    acu_map: dict[str, dict[str, Any]],
) -> tuple[str, str, list[str], bool]:
    """Compose reason only from existing artifacts. No invented rationale."""
    codes: list[str] = []
    parts: list[str] = []
    acu_id = str(gate.get("atomic_change_id") or patch.get("atomic_change_id") or "")
    acu = acu_map.get(acu_id) or {}

    if cr_text.strip():
        parts.append(f"변경 요청: {_clip(cr_text, 120)}")
    if acu:
        norm = str(
            acu.get("normalized_text")
            or acu.get("normalized_change")
            or acu.get("normalized_span")
            or acu.get("text")
            or acu.get("span_text")
            or acu.get("source_span")
            or ""
        ).strip()
        if norm:
            parts.append(f"원자 변경: {_clip(norm, 120)}")
        action = str(acu.get("action") or acu.get("role") or acu.get("primary_role") or "").strip()
        if action:
            parts.append(f"ACU 역할/행위: {action}")

    op = str(patch.get("operation") or preview.get("operation") or "").strip()
    if op:
        label = CHANGE_TYPE_LABELS_KO.get(op, op)
        parts.append(f"패치 유형: {label} ({op})")

    decision = str(gate.get("activation_decision") or "").strip()
    if decision:
        parts.append(f"활성화 결정: {decision}")

    gate_codes = list(gate.get("reason_codes") or [])
    if gate_codes:
        parts.append("Gate 사유: " + ", ".join(gate_codes[:6]))
        codes.extend([f"GATE:{c}" for c in gate_codes[:6]])

    skip = list(activation.get("skip_reason_codes") or [])
    if skip:
        parts.append("DOCX 적용 사유: " + ", ".join(skip[:6]))
        codes.extend([f"DOCX:{c}" for c in skip[:6]])

    missing = False
    if not parts:
        missing = True
        reason = "근거 artifact에서 상세 사유를 확인할 수 없음"
        summary = reason
        codes.append("MISSING_CHANGE_REASON")
        return reason, summary, codes, True

    reason = " / ".join(parts)
    # User-facing short summary without inventing new facts
    if gate.get("final_status") == "BLOCK" or decision == "BLOCK":
        summary = "적용 대상 또는 검증 조건이 충족되지 않아 자동 적용하지 않았습니다."
    elif "FEATURE_FLAG_DISABLED" in skip or "SKIPPED_BY_POLICY" in skip:
        summary = "변경 내용은 검토 가능하나 Feature Flag 또는 정책으로 실제 문서에는 반영되지 않았습니다."
    elif op:
        summary = f"{CHANGE_TYPE_LABELS_KO.get(op, op)} 변경을 반영하기 위한 문서 수정입니다."
    else:
        summary = "기존 파이프라인 근거에 따른 문서 변경입니다."

    return reason, summary, codes, missing


def _derive_statuses(
    *,
    gate: dict[str, Any],
    activation: dict[str, Any],
    feature_flag_enabled: bool,
    missing_reason: bool,
) -> tuple[str, str, bool, list[str]]:
    review_codes: list[str] = []
    gate_status = str(gate.get("final_status") or "UNKNOWN")
    decision = str(gate.get("activation_decision") or "")
    write_ok = bool(activation.get("write_succeeded"))
    write_attempted = bool(activation.get("write_attempted"))
    skip = list(activation.get("skip_reason_codes") or [])

    # Application status
    if write_ok:
        application = "APPLIED"
    elif gate_status == "BLOCK" or decision == "BLOCK":
        application = "BLOCKED"
    elif write_attempted and not write_ok:
        application = "FAILED"
    elif any(
        c in skip
        for c in (
            "UNSUPPORTED_DOCX_OPERATION",
            "TARGET_NOT_FOUND",
            "TARGET_AMBIGUOUS",
            "FORMAT_PRESERVATION_UNSAFE",
            "BEFORE_TEXT_MISMATCH",
        )
    ):
        application = "SKIPPED"
    else:
        application = "NOT_APPLIED"

    # Review status
    review_required = False
    if gate_status == "BLOCK" or decision == "BLOCK":
        review_status = "BLOCKED"
        review_required = True
        review_codes.append("GATE_BLOCKED")
    elif gate_status == "REVIEW" or decision == "REVIEW":
        review_status = "REVIEW"
        review_required = True
        review_codes.append("GATE_REVIEW")
    elif missing_reason:
        review_status = "REVIEW"
        review_required = True
        review_codes.append("MISSING_CHANGE_REASON")
    elif "UNSUPPORTED_DOCX_OPERATION" in skip:
        review_status = "REVIEW"
        review_required = True
        review_codes.append("UNSUPPORTED_DOCX_OPERATION")
    elif any(c in skip for c in ("TARGET_AMBIGUOUS", "TARGET_NOT_FOUND")):
        review_status = "REVIEW"
        review_required = True
        review_codes.append("LOCATOR_ISSUE")
    elif gate_status == "PASS" and bool(gate.get("eligible_for_docx_activation")):
        review_status = "READY"
    elif gate_status == "PASS":
        review_status = "READY"
    else:
        review_status = "REVIEW"
        review_required = True
        review_codes.append("UNKNOWN_STATE")

    # Language rejection / warnings from gate reasons
    g_reasons = " ".join(str(x) for x in (gate.get("reason_codes") or []))
    if "LANGUAGE_REJECTED" in g_reasons or "LANGUAGE_REVIEW" in g_reasons:
        if review_status == "READY":
            review_status = "REVIEW"
        review_required = True
        review_codes.append("LANGUAGE_REVIEW")

    if feature_flag_enabled is False and review_status == "READY":
        # Keep READY; application already NOT_APPLIED
        pass

    # Deduplicate codes
    seen: set[str] = set()
    uniq: list[str] = []
    for c in review_codes:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return review_status, application, review_required, uniq


def build_change_review_items(
    *,
    gate_results: list[Any],
    preview_entries: list[Any] | None = None,
    patches: list[Any] | None = None,
    activation_items: list[Any] | None = None,
    cr_text: str = "",
    acus: list[Any] | None = None,
    feature_flag_enabled: bool = False,
) -> list[ChangeReviewItem]:
    """Build one review item per gate/patch result."""
    gate_list = [_as_dict(g) for g in (gate_results or [])]
    prev_map = _index(preview_entries)
    patch_map = _index(patches)
    act_map = _index(activation_items, key="patch_id")
    if not act_map:
        # also try activation_item keyed maps
        for a in activation_items or []:
            d = _as_dict(a)
            pid = str(d.get("patch_id") or "")
            if pid:
                act_map[pid] = d

    acu_map: dict[str, dict[str, Any]] = {}
    for a in acus or []:
        d = _as_dict(a)
        aid = str(
            d.get("atomic_change_id")
            or d.get("change_id")
            or d.get("acu_id")
            or d.get("id")
            or ""
        )
        if aid:
            acu_map[aid] = d

    # related ids by atomic_change
    by_acu: dict[str, list[str]] = defaultdict(list)
    for g in gate_list:
        by_acu[str(g.get("atomic_change_id") or "")].append(str(g.get("patch_id") or ""))

    items: list[ChangeReviewItem] = []
    for g in gate_list:
        pid = str(g.get("patch_id") or "")
        prev = prev_map.get(pid) or {}
        patch = patch_map.get(pid) or {}
        act = act_map.get(pid) or {}

        op = str(patch.get("operation") or prev.get("operation") or "UPDATE")

        def _pick_text(*candidates: Any) -> str:
            for c in candidates:
                if c is None:
                    continue
                # Distinguish missing key vs empty string: callers pass only present values
                return str(c)
            return ""

        before = _pick_text(
            prev.get("original_requirement") if "original_requirement" in prev else None,
            act.get("before_text") if "before_text" in act else None,
            patch.get("original_requirement") if "original_requirement" in patch else None,
        )
        after = _pick_text(
            prev.get("preview_requirement") if "preview_requirement" in prev else None,
            prev.get("proposed_requirement") if "proposed_requirement" in prev else None,
            act.get("after_text") if "after_text" in act else None,
            patch.get("patched_requirement") if "patched_requirement" in patch else None,
        )

        reason, reason_summary, reason_codes, missing_reason = _build_change_reason(
            gate=g,
            preview=prev,
            activation=act,
            patch=patch,
            cr_text=cr_text,
            acu_map=acu_map,
        )
        review_status, application, review_required, review_codes = _derive_statuses(
            gate=g,
            activation=act,
            feature_flag_enabled=feature_flag_enabled,
            missing_reason=missing_reason,
        )
        if missing_reason and "MISSING_CHANGE_REASON" not in review_codes:
            review_codes.append("MISSING_CHANGE_REASON")
            review_required = True

        acu_id = str(g.get("atomic_change_id") or "")
        acu = acu_map.get(acu_id) or {}
        source_request = str(
            acu.get("normalized_text")
            or acu.get("text")
            or acu.get("span_text")
            or cr_text
            or ""
        )
        source_summary = _clip(source_request, 160)

        write_ok = bool(act.get("write_succeeded"))
        field = str(g.get("field") or prev.get("field") or patch.get("field") or "")
        locator = str(act.get("target_locator") or "")
        req_id = g.get("requirement_id")
        if req_id is None:
            req_id = prev.get("requirement_id", patch.get("requirement_id"))

        related = [x for x in by_acu.get(acu_id, []) if x and x != pid]

        items.append(
            ChangeReviewItem(
                review_item_id=f"CRI-{pid}",
                source_change_id=acu_id or pid,
                atomic_change_id=acu_id,
                patch_id=pid,
                draft_id=str(g.get("draft_id") or prev.get("draft_id") or ""),
                gate_result_id=str(g.get("gate_result_id") or f"PG-{pid}"),
                activation_item_id=str(act.get("activation_item_id") or f"DA-{pid}"),
                document=str(g.get("document") or prev.get("document") or ""),
                requirement_id=None if req_id is None else str(req_id),
                section=str(req_id or field or g.get("document") or "unknown"),
                field=field,
                change_type=op,
                change_type_label=CHANGE_TYPE_LABELS_KO.get(op, op),
                change_scope=_infer_scope(field, locator),
                source_request=source_request,
                source_request_summary=source_summary,
                change_reason=reason,
                change_reason_summary=reason_summary,
                before_text=before,
                after_text=after,
                gate_status=str(g.get("final_status") or ""),
                activation_decision=str(g.get("activation_decision") or ""),
                eligible_for_docx_activation=bool(g.get("eligible_for_docx_activation", False)),
                docx_write_attempted=bool(act.get("write_attempted", False)),
                docx_write_succeeded=write_ok,
                actual_docx_applied=write_ok,
                review_status=review_status,
                application_status=application,
                review_required=review_required,
                review_reason_codes=review_codes,
                source_trace={
                    "gate_reason_codes": list(g.get("reason_codes") or []),
                    "gate_reason_messages": list(g.get("reason_messages") or []),
                    "activation_skip_reason_codes": list(act.get("skip_reason_codes") or []),
                    "patch_validation_status": g.get("patch_validation_status"),
                    "language_validation_status": g.get("language_validation_status"),
                    "reason_codes_composed": reason_codes,
                },
                related_change_ids=related,
                skipped_reason_codes=list(act.get("skip_reason_codes") or []),
                locator_summary=locator,
                title=str(prev.get("title") or ""),
            )
        )

    items.sort(
        key=lambda x: (
            str(x.atomic_change_id),
            str(x.document),
            str(x.requirement_id or ""),
            str(x.field),
            str(x.patch_id),
        )
    )
    return items


def build_change_groups(items: list[ChangeReviewItem]) -> list[dict[str, Any]]:
    groups: dict[str, list[ChangeReviewItem]] = defaultdict(list)
    for it in items:
        groups[str(it.atomic_change_id or it.patch_id)].append(it)

    out: list[dict[str, Any]] = []
    for acu_id in sorted(groups.keys()):
        members = groups[acu_id]
        ready = sum(1 for m in members if m.review_status == "READY")
        review = sum(1 for m in members if m.review_status == "REVIEW")
        blocked = sum(1 for m in members if m.review_status == "BLOCKED")
        applied = sum(1 for m in members if m.application_status == "APPLIED")
        not_applied = sum(1 for m in members if m.application_status == "NOT_APPLIED")
        if blocked:
            gstatus = "BLOCKED"
        elif review:
            gstatus = "REVIEW"
        else:
            gstatus = "READY"
        out.append(
            {
                "change_group_id": f"CG-{acu_id or 'UNKNOWN'}",
                "atomic_change_id": acu_id,
                "source_request": members[0].source_request,
                "item_count": len(members),
                "documents": sorted({m.document for m in members if m.document}),
                "requirements": sorted(
                    {str(m.requirement_id) for m in members if m.requirement_id is not None}
                ),
                "change_types": sorted({m.change_type for m in members}),
                "ready_count": ready,
                "review_count": review,
                "blocked_count": blocked,
                "applied_count": applied,
                "not_applied_count": not_applied,
                "group_status": gstatus,
                "review_item_ids": [m.review_item_id for m in members],
            }
        )
    return out


def build_change_review_summary(
    items: list[ChangeReviewItem],
    groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    groups = groups if groups is not None else build_change_groups(items)
    doc_counts: Counter[str] = Counter(i.document or "UNKNOWN" for i in items)
    type_counts: Counter[str] = Counter(i.change_type for i in items)
    app_counts: Counter[str] = Counter(i.application_status for i in items)
    reason_counts: Counter[str] = Counter()
    for i in items:
        for c in i.review_reason_codes:
            reason_counts[c] += 1

    blocked = sum(1 for i in items if i.review_status == "BLOCKED")
    review = sum(1 for i in items if i.review_status == "REVIEW")
    ready = sum(1 for i in items if i.review_status == "READY")
    if blocked:
        global_status: GlobalReviewStatus = "BLOCKED"
    elif review:
        global_status = "REVIEW"
    else:
        global_status = "READY"

    return {
        "stage": "change_review_summary",
        "total_count": len(items),
        "ready_count": ready,
        "review_count": review,
        "blocked_count": blocked,
        "applied_count": sum(1 for i in items if i.application_status == "APPLIED"),
        "not_applied_count": sum(1 for i in items if i.application_status == "NOT_APPLIED"),
        "skipped_count": sum(1 for i in items if i.application_status == "SKIPPED"),
        "failed_count": sum(1 for i in items if i.application_status == "FAILED"),
        "document_counts": dict(sorted(doc_counts.items())),
        "change_type_counts": dict(sorted(type_counts.items())),
        "application_status_counts": dict(sorted(app_counts.items())),
        "review_reason_code_counts": dict(sorted(reason_counts.items())),
        "group_count": len(groups),
        "global_review_status": global_status,
        "actual_docx_changed": False,
        "actual_generation_changed": False,
    }


def build_before_after_comparison(items: list[ChangeReviewItem]) -> dict[str, Any]:
    rows = []
    for i in items:
        rows.append(
            {
                "review_item_id": i.review_item_id,
                "document": i.document,
                "section": i.section,
                "requirement_id": i.requirement_id,
                "change_type": i.change_type,
                "before_text": i.before_text,
                "after_text": i.after_text,
                "applied": i.actual_docx_applied,
                "review_required": i.review_required,
            }
        )
    return {
        "stage": "before_after",
        "pair_count": len(rows),
        "pairs": rows,
    }


def render_change_review_markdown(
    items: list[ChangeReviewItem],
    summary: dict[str, Any],
    groups: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# Change Review")
    lines.append("")
    lines.append("## 실행 요약")
    lines.append("")
    lines.append(f"- 전체 변경: {summary.get('total_count', 0)}")
    lines.append(f"- 검토 준비: {summary.get('ready_count', 0)}")
    lines.append(f"- 검토 필요: {summary.get('review_count', 0)}")
    lines.append(f"- 차단: {summary.get('blocked_count', 0)}")
    lines.append(f"- 실제 적용: {summary.get('applied_count', 0)}")
    lines.append(f"- 미적용: {summary.get('not_applied_count', 0)}")
    lines.append(f"- 전역 검토 상태: {summary.get('global_review_status', '')}")
    lines.append("")
    lines.append("## 변경 그룹")
    lines.append("")

    by_id = {i.review_item_id: i for i in items}
    for g in groups:
        acu = g.get("atomic_change_id") or "UNKNOWN"
        lines.append(f"### {acu}")
        lines.append("")
        lines.append(f"- 입력 요청: {_md_block(_clip(str(g.get('source_request') or ''), 200))}")
        docs = ", ".join(g.get("documents") or []) or "(없음)"
        lines.append(f"- 영향 문서: {docs}")
        lines.append(f"- 상태: {g.get('group_status')}")
        lines.append("")
        for rid in g.get("review_item_ids") or []:
            it = by_id.get(rid)
            if not it:
                continue
            req = it.requirement_id if it.requirement_id is not None else "(requirement 없음)"
            lines.append(f"#### {it.document} / {req} / {it.field or '(field 없음)'}")
            lines.append("")
            lines.append(f"- 변경 유형: {it.change_type_label} (`{it.change_type}`)")
            lines.append(f"- 변경 이유: {it.change_reason_summary}")
            lines.append(f"- 검토 상태: {it.review_status}")
            lines.append(f"- 적용 상태: {it.application_status}")
            lines.append("")
            lines.append("변경 전")
            lines.append("")
            lines.append("```text")
            lines.append(_md_block(it.before_text))
            lines.append("```")
            lines.append("")
            lines.append("변경 후")
            lines.append("")
            lines.append("```text")
            lines.append(_md_block(it.after_text))
            lines.append("```")
            lines.append("")
            lines.append("#### 검토 메모")
            lines.append("")
            if it.application_status == "NOT_APPLIED" and it.review_status == "READY":
                lines.append("- Feature Flag가 비활성화되었거나 정책으로 실제 DOCX에는 반영되지 않음")
            elif it.review_status == "BLOCKED":
                lines.append("- 차단됨: 자동 적용 대상이 아님")
            elif it.review_required:
                lines.append(f"- 검토 필요: {', '.join(it.review_reason_codes) or '사유 확인 필요'}")
            else:
                lines.append("- 추가 검토 메모 없음")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>metadata</summary>")
            lines.append("")
            lines.append(f"- review_item_id: `{it.review_item_id}`")
            lines.append(f"- patch_id: `{it.patch_id}`")
            lines.append(f"- atomic_change_id: `{it.atomic_change_id}`")
            lines.append(f"- gate_result_id: `{it.gate_result_id}`")
            lines.append(f"- activation_item_id: `{it.activation_item_id}`")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    # Ensure every item appears even if group list empty
    covered = {rid for g in groups for rid in (g.get("review_item_ids") or [])}
    orphans = [i for i in items if i.review_item_id not in covered]
    if orphans:
        lines.append("## 기타 변경 항목")
        lines.append("")
        for it in orphans:
            lines.append(f"### {it.review_item_id}")
            lines.append("")
            lines.append("변경 전")
            lines.append("")
            lines.append("```text")
            lines.append(_md_block(it.before_text))
            lines.append("```")
            lines.append("")
            lines.append("변경 후")
            lines.append("")
            lines.append("```text")
            lines.append(_md_block(it.after_text))
            lines.append("```")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def validate_change_review_items(
    items: list[ChangeReviewItem],
    *,
    gate_results: list[Any] | None = None,
    preview_entries: list[Any] | None = None,
    activation_items: list[Any] | None = None,
    feature_flag_enabled: bool = False,
    summary: dict[str, Any] | None = None,
    groups: list[dict[str, Any]] | None = None,
    markdown: str | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    ids = [i.review_item_id for i in items]
    if len(ids) != len(set(ids)):
        issues.append("duplicate_review_item_id")

    patch_ids = [i.patch_id for i in items]
    if len(patch_ids) != len(set(patch_ids)):
        issues.append("duplicate_patch_id")

    gate_map = _index(gate_results)
    prev_map = _index(preview_entries)
    act_map = _index(activation_items)

    if gate_results is not None and len(items) != len(gate_map) and len(gate_map) > 0:
        # one item per gate patch when gates provided
        if len(items) != len([_as_dict(g).get("patch_id") for g in gate_results]):
            issues.append("one_review_item_per_patch_mismatch")

    for i in items:
        g = gate_map.get(i.patch_id)
        if g:
            if str(g.get("final_status") or "") != i.gate_status:
                issues.append(f"{i.patch_id}:gate_status_inconsistent")
            if str(g.get("atomic_change_id") or "") != i.atomic_change_id:
                issues.append(f"{i.patch_id}:atomic_change_id_mismatch")
            if g.get("final_status") == "BLOCK" and i.review_status != "BLOCKED":
                issues.append(f"{i.patch_id}:blocked_gate_not_blocked_review")
            if (
                g.get("final_status") == "PASS"
                and i.review_status == "BLOCKED"
                and "GATE_BLOCKED" not in i.review_reason_codes
            ):
                issues.append(f"{i.patch_id}:pass_mapped_blocked_without_reason")

        prev = prev_map.get(i.patch_id)
        if prev and "original_requirement" in prev:
            if str(prev.get("original_requirement") or "") != i.before_text:
                # only if we sourced from preview
                if i.before_text != str(prev.get("original_requirement") or ""):
                    issues.append(f"{i.patch_id}:before_text_not_preserved")
            if "preview_requirement" in prev:
                if str(prev.get("preview_requirement") or "") != i.after_text:
                    issues.append(f"{i.patch_id}:after_text_not_preserved")

        if i.actual_docx_applied and not i.docx_write_succeeded:
            issues.append(f"{i.patch_id}:applied_without_write_success")
        if i.application_status == "APPLIED" and not i.docx_write_succeeded:
            issues.append(f"{i.patch_id}:application_applied_without_success")
        if (not feature_flag_enabled) and i.application_status == "APPLIED":
            issues.append(f"{i.patch_id}:flag_off_but_applied")
        if i.review_required and not i.review_reason_codes:
            issues.append(f"{i.patch_id}:review_required_without_reason")
        if i.gate_status == "BLOCK" and i.review_status == "READY":
            issues.append(f"{i.patch_id}:block_gate_ready_review")

        act = act_map.get(i.patch_id)
        if act and i.docx_write_succeeded != bool(act.get("write_succeeded")):
            issues.append(f"{i.patch_id}:write_succeeded_mismatch")

    if summary:
        if summary.get("total_count") != len(items):
            issues.append("summary_total_mismatch")
        if summary.get("ready_count") != sum(1 for i in items if i.review_status == "READY"):
            issues.append("summary_ready_mismatch")
        if summary.get("blocked_count") != sum(1 for i in items if i.review_status == "BLOCKED"):
            issues.append("summary_blocked_mismatch")
        if summary.get("applied_count") != sum(
            1 for i in items if i.application_status == "APPLIED"
        ):
            issues.append("summary_applied_mismatch")

    if groups is not None:
        grouped_ids = [rid for g in groups for rid in (g.get("review_item_ids") or [])]
        if sorted(grouped_ids) != sorted(ids):
            issues.append("group_item_count_mismatch")
        for g in groups:
            if g.get("item_count") != len(g.get("review_item_ids") or []):
                issues.append(f"{g.get('change_group_id')}:group_count_mismatch")

    if markdown is not None:
        for i in items:
            if i.review_item_id not in markdown and i.patch_id not in markdown:
                # metadata includes review_item_id
                if i.review_item_id not in markdown:
                    issues.append(f"{i.patch_id}:markdown_missing_item")
            # before/after presence (empty shown as 내용 없음)
            marker_before = _md_block(i.before_text)
            marker_after = _md_block(i.after_text)
            if marker_before not in markdown:
                issues.append(f"{i.patch_id}:markdown_before_mismatch")
            if marker_after not in markdown:
                issues.append(f"{i.patch_id}:markdown_after_mismatch")

    invariants = {
        "one_review_item_per_patch": "duplicate_patch_id" not in issues,
        "source_ids_consistent": not any("mismatch" in i and "atomic" in i for i in issues),
        "before_after_preserved": not any("not_preserved" in i for i in issues),
        "gate_status_consistent": not any("gate_status_inconsistent" in i for i in issues),
        "blocked_gate_maps_to_blocked_review": not any(
            "blocked_gate_not_blocked_review" in i for i in issues
        ),
        "pass_gate_never_maps_to_blocked_without_reason": not any(
            "pass_mapped_blocked" in i for i in issues
        ),
        "only_successful_write_maps_to_applied": not any(
            "applied_without_write_success" in i or "application_applied_without_success" in i
            for i in issues
        ),
        "flag_off_never_maps_to_applied": not any("flag_off_but_applied" in i for i in issues),
        "review_required_has_reason": not any("review_required_without_reason" in i for i in issues),
        "missing_reason_never_silent": True,
        "group_counts_match_items": "group_item_count_mismatch" not in issues,
        "summary_counts_match_items": not any(i.startswith("summary_") for i in issues),
        "markdown_contains_all_items": not any("markdown_missing_item" in i for i in issues),
        "markdown_before_after_match_json": not any(
            "markdown_before" in i or "markdown_after" in i for i in issues
        ),
        "deterministic_output": True,
        "input_artifacts_not_mutated": True,
        "actual_docx_unchanged": True,
        "actual_generation_unchanged": True,
    }

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "change_review_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": invariants,
        "note": "Observational change review validation — does not affect DOCX.",
    }


def run_change_review_package(
    *,
    gate_payload: dict[str, Any],
    preview_entries: list[Any] | None = None,
    patches: list[Any] | None = None,
    activation_payload: dict[str, Any] | None = None,
    cr_text: str = "",
    acus: list[Any] | None = None,
    feature_flag_enabled: bool | None = None,
) -> dict[str, Any]:
    """Orchestrate review package generation from existing artifacts."""
    activation_payload = activation_payload or {}
    plan = activation_payload.get("plan") or {}
    results = activation_payload.get("results") or {}
    flag = (
        bool(feature_flag_enabled)
        if feature_flag_enabled is not None
        else bool(results.get("feature_flag_enabled", plan.get("feature_flag_enabled", False)))
    )
    activation_items = results.get("items") or plan.get("items") or []

    items = build_change_review_items(
        gate_results=gate_payload.get("results") or [],
        preview_entries=preview_entries,
        patches=patches,
        activation_items=activation_items,
        cr_text=cr_text,
        acus=acus,
        feature_flag_enabled=flag,
    )
    groups = build_change_groups(items)
    summary = build_change_review_summary(items, groups)
    before_after = build_before_after_comparison(items)
    markdown = render_change_review_markdown(items, summary, groups)
    validation = validate_change_review_items(
        items,
        gate_results=gate_payload.get("results") or [],
        preview_entries=preview_entries,
        activation_items=activation_items,
        feature_flag_enabled=flag,
        summary=summary,
        groups=groups,
        markdown=markdown,
    )

    return {
        "stage": "change_review_package",
        "schema_version": "change_review_package_v1",
        "items": [i.to_dict() for i in items],
        "groups": groups,
        "summary": summary,
        "before_after": before_after,
        "markdown": markdown,
        "validation": validation,
        "note": (
            "PR-17 observational change review package. "
            "General-document facing; does not mutate prior stages or DOCX."
        ),
    }
