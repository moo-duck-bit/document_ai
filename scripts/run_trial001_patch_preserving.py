# -*- coding: utf-8 -*-
"""Trial 1 correction: patch-preserving Mindrium outputs (no full harness regenerate)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from document_ai.impact.preserve_patch import (
    build_patch_preserving_outputs,
    find_req6_design_candidates,
    sha256_file,
)
from document_ai.trial.paths import rel_to_project, write_json, write_text

TRIAL = Path("data/trials/trial-001-mindrium-xa")
REF = TRIAL / "reference"
OUT = TRIAL / "generated_patch_preserving"
INVALID_MARKERS = [
    TRIAL / "generated" / "INVALID_FOR_HR.txt",
    TRIAL / "generated_clean_mindrium" / "INVALID_FOR_HR.txt",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark_invalid_dirs() -> None:
    note = (
        "INVALID_FOR_HR\n"
        "Reason: full harness regenerate / skeleton output; not patch-in-place of Mindrium reference.\n"
        "Do not use for Human Review.\n"
        f"Canonical candidate after correction: {rel_to_project(OUT)}\n"
        f"marked_at: {utc_now()}\n"
    )
    for path in INVALID_MARKERS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note, encoding="utf-8")


def try_visual_qa(docx_path: Path, out_dir: Path) -> dict:
    """Best-effort page render via Word COM; skip gracefully if unavailable."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "ok": False,
        "engine": None,
        "pages": 0,
        "png_paths": [],
        "skipped_reason": None,
    }
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        result["skipped_reason"] = f"win32com unavailable: {exc}"
        return result

    abs_docx = str(docx_path.resolve())
    png_dir = out_dir.resolve()
    word = None
    doc = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(abs_docx, ReadOnly=True)
        page_count = int(doc.ComputeStatistics(2))  # wdStatisticPages
        result["pages"] = page_count
        result["engine"] = "win32com.Word"
        # Export as PDF then note pages (PNG-per-page via Word is awkward); save PDF evidence.
        pdf_path = png_dir / (docx_path.stem + ".pdf")
        doc.SaveAs(str(pdf_path), FileFormat=17)  # wdFormatPDF
        result["pdf_path"] = rel_to_project(pdf_path)
        result["ok"] = page_count > 0
        result["notes"] = (
            "PDF render saved for visual QA. Per-page PNG export skipped "
            "(Word COM page bitmap export not configured)."
        )
    except Exception as exc:  # noqa: BLE001
        result["skipped_reason"] = f"Word render failed: {exc}"
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:  # noqa: BLE001
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:  # noqa: BLE001
            pass
    return result


def main() -> int:
    mark_invalid_dirs()

    ref_mdsr = next(REF.glob("spec_mdsr*.docx"))
    ref_mddr = next(REF.glob("spec_mddr*.docx"))
    change = json.loads((TRIAL / "input" / "change_request.json").read_text(encoding="utf-8"))
    req = change["requirement_changes"][0]
    req_id = req["req_id"]
    description = req["description"]

    t0 = time.perf_counter()
    result = build_patch_preserving_outputs(
        reference_mdsr=ref_mdsr,
        reference_mddr=ref_mddr,
        req_id=req_id,
        description=description,
        out_dir=OUT,
        mddr_strategy="no_automatic_design_patch",
    )
    elapsed = round(time.perf_counter() - t0, 3)

    design_candidates = find_req6_design_candidates(ref_mddr)

    visual = {
        "mdsr": try_visual_qa(OUT / "output_mdsr.docx", TRIAL / "logs" / "visual_qa" / "mdsr"),
        "mddr": try_visual_qa(OUT / "output_mddr.docx", TRIAL / "logs" / "visual_qa" / "mddr"),
    }

    # Page-count sanity: patched MDSR pages should not collapse vs reference render if available
    ref_visual = {
        "mdsr": try_visual_qa(ref_mdsr, TRIAL / "logs" / "visual_qa" / "reference_mdsr"),
        "mddr": try_visual_qa(ref_mddr, TRIAL / "logs" / "visual_qa" / "reference_mddr"),
    }

    visual_ok = all(
        (visual[k].get("ok") and visual[k].get("pages", 0) > 0) for k in ("mdsr", "mddr")
    )
    # Page collapse check when both reference and output renders exist
    page_collapse = False
    for key in ("mdsr", "mddr"):
        ref_p = ref_visual[key].get("pages") or 0
        out_p = visual[key].get("pages") or 0
        if ref_p > 0 and out_p > 0 and out_p < ref_p * 0.5:
            page_collapse = True
            result.errors.append(f"{key} page count collapsed ({out_p} vs ref {ref_p})")

    hr_ready = bool(result.ok) and visual_ok and not page_collapse
    if result.ok and not visual_ok:
        status = "pre_human_review_blocked"
        result.warnings.append(
            "patch validation passed but visual page render QA unavailable/failed; "
            "not marking pre_human_review_ready"
        )
    elif hr_ready:
        status = "pre_human_review_ready"
    else:
        status = "pre_human_review_blocked"

    er_path = TRIAL / "execution_report.json"
    er = json.loads(er_path.read_text(encoding="utf-8")) if er_path.exists() else {}
    er.update(
        {
            "status": status,
            "real_world_trial_complete": False,
            "human_review_complete": False,
            "pre_human_review_ready": hr_ready,
            "canonical_generated_dir": rel_to_project(OUT) if hr_ready else None,
            "invalid_for_hr": [
                rel_to_project(TRIAL / "generated"),
                rel_to_project(TRIAL / "generated_clean_mindrium"),
            ],
            "generation_strategy": "patch_preserving_reference_docx",
            "patch_preserving": result.to_dict(),
            "mddr_design_candidates_report_only": design_candidates[:20],
            "mddr_design_candidates_count": len(design_candidates),
            "visual_qa": visual,
            "reference_visual_qa": ref_visual,
            "patch_preserving_elapsed_seconds": elapsed,
            "updated_at": utc_now(),
            "failure_summary": None
            if hr_ready
            else {
                "previous_clean_output": "INVALID_FOR_HR (skeleton regenerate)",
                "jm_retrieval_contamination": True,
                "clean_regenerate_also_failed_preserve": True,
                "errors": result.errors,
                "unexpected_diff_count": result.validation.get("mdsr_unexpected_diff_count"),
            },
        }
    )
    if not hr_ready:
        er["next_human_review_paths"] = {
            "blocked": True,
            "reason": "generation_validation_failed / pre_human_review_blocked",
            "candidate_outputs": rel_to_project(OUT),
            "correction_report": rel_to_project(TRIAL / "GENERATION_CORRECTION_REPORT.md"),
        }
    else:
        er["next_human_review_paths"] = {
            "generated_mdsr": rel_to_project(OUT / "output_mdsr.docx"),
            "generated_mddr": rel_to_project(OUT / "output_mddr.docx"),
            "xxcs": "OUT_OF_SCOPE / not generated",
            "review_dir": rel_to_project(TRIAL / "review"),
        }
    write_json(er_path, er)
    write_json(TRIAL / "logs" / "patch_preserving_result.json", result.to_dict())

    v = result.validation
    unexpected = v.get("mdsr_unexpected_diffs") or []

    correction = f"""# Trial 1 Generation Correction Report

- updated_at: `{utc_now()}`
- trial_id: `trial-001-mindrium-xa`
- status: `{status}`
- pre_human_review_ready: `{hr_ready}`
- real_world_trial_complete: `false`

## 1. 이전 실패 요약

1. **JM retrieval contamination**: 1차 harness.generate가 `jm_collection`을 few-shot으로 사용 → JM COLLECTION 브랜딩 혼입.
2. **clean 재생성 실패 (원본 보존)**: `use_retrieval=False`로 JM 문자열은 제거됐으나, sparse JSON 기반 **전체 재생성 skeleton**이 됨.
   - MDSR ~1.97MB → ~293KB, MDDR ~2.63MB → ~317KB
   - 다수 Req 공란, 설계/그림/표 유실, XXCS 시험결과 NOT_EXECUTED 전면 교체
3. 따라서 `generated/`, `generated_clean_mindrium/` 는 **INVALID_FOR_HR**.

## 2. 수정 전략 (patch-in-place)

1. `reference/` 원본 DOCX를 `generated_patch_preserving/`로 byte-copy
2. MDSR: Req. 6 **description 셀만** patch (`patch_mdsr_description_only`)
3. MDDR: **Option 1** — 원본 복사, automatic design patch 없음 (`design_ids` null 반영)
4. XXCS: canonical 패키지에서 **제외** (OUT_OF_SCOPE)
5. full `harness.generate` / retrieval / JM·lab template 미사용
6. sparse `requirements.json`으로 원본 본문 전체 덮어쓰기 안 함

## 3. 산출물

| 문서 | 경로 | size | sha256 |
|------|------|------|--------|
| MDSR ref | `{rel_to_project(ref_mdsr)}` | {ref_mdsr.stat().st_size} | `{sha256_file(ref_mdsr)}` |
| MDSR out | `{rel_to_project(OUT / 'output_mdsr.docx')}` | {(OUT / 'output_mdsr.docx').stat().st_size if (OUT / 'output_mdsr.docx').exists() else 'n/a'} | `{v.get('mdsr_sha256')}` |
| MDDR ref | `{rel_to_project(ref_mddr)}` | {ref_mddr.stat().st_size} | `{v.get('mddr_reference_sha256')}` |
| MDDR out | `{rel_to_project(OUT / 'output_mddr.docx')}` | {(OUT / 'output_mddr.docx').stat().st_size if (OUT / 'output_mddr.docx').exists() else 'n/a'} | `{v.get('mddr_sha256')}` |
| XXCS | (생성하지 않음) | — | reference 유지 |

## 4. MDSR exact diff

- unexpected_diff_count: `{v.get('mdsr_unexpected_diff_count')}`
- all_diff_count: `{len(v.get('mdsr_text_diffs') or [])}`
- patched_req_ids: `{result.mdsr_patched_req_ids}`

### Allowed / observed diffs
```json
{json.dumps(v.get('mdsr_text_diffs') or [], ensure_ascii=False, indent=2)}
```

### Unexpected diffs
```json
{json.dumps(unexpected, ensure_ascii=False, indent=2)}
```

### OOXML structure
| metric | before | after |
|--------|--------|-------|
| tbl | {(v.get('mdsr_ooxml_before') or {}).get('tbl')} | {(v.get('mdsr_ooxml_after') or {}).get('tbl')} |
| drawing_like | {(v.get('mdsr_ooxml_before') or {}).get('drawing_like')} | {(v.get('mdsr_ooxml_after') or {}).get('drawing_like')} |
| sectPr | {(v.get('mdsr_ooxml_before') or {}).get('sectPr')} | {(v.get('mdsr_ooxml_after') or {}).get('sectPr')} |
| styles | {v.get('mdsr_styles_before')} | {v.get('mdsr_styles_after')} |

## 5. MDDR

- strategy: `{result.mddr_strategy}`
- sha256 matches reference: `{result.mddr_sha256_matches_reference}`
- Req.6 design location candidates (report-only, not patched): `{len(design_candidates)}`
- impact.design_ids was null → 자동 설계 생성/성공 주장 없음

## 6. XXCS

- Trial 선언 document_types: MDSR/MDDR
- canonical HR output에 XXCS **미포함**
- reference XXCS 원본 미변경
- 기존 opportunistic XXCS는 INVALID / OUT_OF_SCOPE

## 7. 오염 검사 (reference 대비 신규 토큰만)

- MDSR: `{json.dumps(v.get('contamination_mdsr') or [], ensure_ascii=False)}`
- MDDR: `{json.dumps(v.get('contamination_mddr') or [], ensure_ascii=False)}`

## 8. Visual QA

```json
{json.dumps({'output': visual, 'reference': ref_visual}, ensure_ascii=False, indent=2)}
```

## 9. Human Review 가능 여부

- **{('YES — pre_human_review_ready' if hr_ready else 'NO — pre_human_review_blocked')}**
- errors: `{result.errors}`
- warnings: `{result.warnings}`

## 10. INVALID 표시

- `generated/INVALID_FOR_HR.txt`
- `generated_clean_mindrium/INVALID_FOR_HR.txt`
"""
    write_text(TRIAL / "GENERATION_CORRECTION_REPORT.md", correction)

    hr_lines = (
        [
            "- MDSR: `generated_patch_preserving/output_mdsr.docx`",
            "- MDDR: `generated_patch_preserving/output_mddr.docx` (원본 동일 해시)",
            "- XXCS: OUT_OF_SCOPE",
        ]
        if hr_ready
        else [
            "- **차단됨** — 검증 실패 항목을 GENERATION_CORRECTION_REPORT에서 확인 후 재실행",
        ]
    )
    pre = "\n".join(
        [
            f"# Trial 1 실행 보고서 (Human Review {'가능' if hr_ready else '차단'})",
            "",
            f"> status: `{status}`  ",
            f"> pre_human_review_ready: `{hr_ready}`  ",
            "> real_world_trial_complete: `false`",
            "",
            "## 상태 정정",
            "",
            "- `generated/`, `generated_clean_mindrium/` → **INVALID_FOR_HR**",
            "  (JM retrieval 오염 및/또는 sparse payload 전체 재생성 skeleton)",
            "- canonical 후보: `generated_patch_preserving/` (원본 byte-copy + Req.6 description-only patch)",
            "- XXCS는 HR canonical 패키지에서 제외",
            "",
            "상세 검증 수치: `GENERATION_CORRECTION_REPORT.md`",
            "",
            "## Human Review",
            "",
            *hr_lines,
            "",
            "## 발표 주석",
            "",
            "- Mindrium 실문서 + 준비된 Req.6 CR (update/fill)",
            "- 전체 재생성 금지, patch-in-place가 Trial 1 올바른 경로",
            "",
        ]
    )
    write_text(TRIAL / "PRE_HUMAN_REVIEW_REPORT.md", pre)

    # trial_manifest status
    mf = TRIAL / "trial_manifest.json"
    if mf.exists():
        manifest = json.loads(mf.read_text(encoding="utf-8"))
        manifest["status"] = status
        manifest["pre_human_review_ready"] = hr_ready
        write_json(mf, manifest)

    summary = {
        "status": status,
        "ok": result.ok,
        "errors": result.errors,
        "unexpected_diff_count": v.get("mdsr_unexpected_diff_count"),
        "mdsr_size": (OUT / "output_mdsr.docx").stat().st_size if (OUT / "output_mdsr.docx").exists() else None,
        "mddr_hash_match": result.mddr_sha256_matches_reference,
        "contamination": {
            "mdsr": v.get("contamination_mdsr"),
            "mddr": v.get("contamination_mddr"),
        },
        "visual_pages": {
            "mdsr": visual["mdsr"].get("pages"),
            "mddr": visual["mddr"].get("pages"),
            "ref_mdsr": ref_visual["mdsr"].get("pages"),
            "ref_mddr": ref_visual["mddr"].get("pages"),
        },
        "report": rel_to_project(TRIAL / "GENERATION_CORRECTION_REPORT.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
