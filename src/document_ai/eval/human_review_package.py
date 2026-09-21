"""Holdout human-review package assembly and summary."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

SCORE_FIELDS = (
    "terminology_score",
    "requirement_correctness_score",
    "design_correctness_score",
    "traceability_score",
    "regulatory_appropriateness_score",
)

DEFAULT_REVIEW_ROOT = Path("data/review")


def review_case_dir(case_id: str, root: str | Path | None = None) -> Path:
    base = Path(root) if root else DEFAULT_REVIEW_ROOT
    return base / case_id


def review_result_template() -> dict[str, Any]:
    return {
        "case_id": "",
        "reviewer_id": "",
        "reviewed_at": "",
        "mdsr_status": "pending",
        "mddr_status": "pending",
        "terminology_score": None,
        "requirement_correctness_score": None,
        "design_correctness_score": None,
        "traceability_score": None,
        "regulatory_appropriateness_score": None,
        "issues": [],
        "required_changes": [],
        "approval_decision": "pending",
        "reviewer_comment": "",
    }


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _write_reviewer_instructions(case_id: str, out_path: Path) -> Path:
    text = f"""# Reviewer Instructions — `{case_id}` (Holdout)

## 검토 목적

이 패키지는 **frozen holdout** 케이스 `{case_id}`의 생성 문서가
Independent Gold로 승격 가능한지 **사람 검토**하기 위한 것이다.

- 시스템 규칙을 바꿔 점수를 올리지 않는다.
- Holdout 점수를 맞추기 위해 generation / form-fill을 튜닝하지 않는다.
- 승인은 **문서 품질·도메인 적합성**에만 근거한다.

## 제공 파일

| 파일 | 설명 |
|------|------|
| `generated_mdsr.docx` | 시스템이 생성한 MDSR |
| `generated_mddr.docx` | 시스템이 생성한 MDDR |
| `human_review_checklist.md` | 자동 생성 체크리스트 |
| `gold_fields_review.json` | 구조화 라벨 (Req/Design/Traceability) |
| `review_result.template.json` | 결과 기입용 템플릿 → `review_result.json`으로 저장 |
| `reviewer_instructions.md` | 본 문서 |

## 문서별 검토 방법

### MDSR (`generated_mdsr.docx`)

1. 표지·제품명·도메인이 병원 예약 시스템에 맞는지 확인
2. Req. 표: 설명/목적/기준이 비어 있지 않은지
3. Traceability (IA/UC/SI) linked_reqs가 Req ID와 연결되는지
4. 잔여 placeholder (`XX-XX-XXXX`)·이커머스 용어 혼입 여부

### MDDR (`generated_mddr.docx`)

1. 각 Req. 설계 블록 본문이 요구사항과 대응하는지
2. 그림/표 캡션이 placeholder로만 남아 있어도 되는지(의도적 vs 차단)
3. 컴포넌트·API 서술이 병원 예약 맥락인지

### `gold_fields_review.json`

1. `requirement_ids` / `design_ids` 누락·중복
2. `requirement_text` / `design_text`가 DOCX와 대략 일치하는지
3. `traceability_rows` linked_reqs 형식

## 수정 가능 항목

Reviewer가 **직접 고쳐도 되는 것** (승인 전):

- 오탈자, 명백한 도메인 오용 용어 (병원 맥락으로 교정한 사본)
- `gold_fields_review.json` 라벨 오류
- checklist 코멘트 / `review_result.json` 기록

**금지 (이 holdout sprint에서):**

- form-fill / replacement rule / Platform 코드 변경으로 점수 올리기
- holdout case를 train으로 재분류
- gold를 생성 결과에 맞춰 자의적으로 축소해 coverage만 높이기

교정 DOCX를 gold로 쓰려면 검토 완료 후 별도 폴더에 저장하고,
승인 시 해당 파일을 case `output_*.docx`로 반영한 뒤 bootstrap한다
(또는 bootstrap 전에 case output을 교정본으로 교체).

## 승인 기준 (Approve)

다음을 **모두** 만족하면 `approval_decision: approve`:

1. MDSR/MDDR 모두 `mdsr_status` / `mddr_status` = `accept` 또는 `accept_with_nits`
2. 5개 Likert(1–5) 점수의 **평균 ≥ 4.0**
3. `required_changes`가 비어 있거나, nits만 있고 문서 사용에 치명적이지 않음
4. 도메인(병원 예약) 서술과 규제 언급이 case facts와 모순되지 않음
5. Traceability가 주요 Req과 연결됨

## Reject 기준

하나라도 해당하면 `reject` 또는 `revise`:

- 제품/도메인이 병원 예약과 무관하거나 명백한 타 도메인 잔재가 다수
- 핵심 Req/Design 블록 다수 공란 또는 잘림
- Traceability가 실질적으로 비어 있거나 오연결
- 규제/표준 언급이 case와 심각하게 불일치
- Reviewer 판단상 gold로 쓰기에 위험

`revise`: 수정 후 재검토 가능. `reject`: 이번 라운드 gold 승격 불가.

## provisional vs human_approved

| 상태 | 의미 |
|------|------|
| **provisional** | 시스템 output을 복사한 임시 gold. 논문 claim용 독립 gold가 **아님** |
| **human_approved** | 본 절차로 reviewer가 승인한 gold. holdout 보고에 사용 가능 |

## Holdout freeze 원칙

1. `{case_id}`는 **holdout**으로 고정한다.
2. 승인 전후로 generation 규칙을 holdout 점수 때문에 바꾸지 않는다.
3. 승인 후 gold를 freeze하고, 이후 시스템 변경의 효과는 **별도 실험**으로 기록한다.
4. Self-gold(생성물=gold 복사) provisional 점수는 tooling smoke용으로만 인용한다.

## 검토 후 할 일

1. `review_result.template.json`을 복사 → `review_result.json` 작성
2. (선택) 교정 DOCX를 case output에 반영
3. 요약: `python -m document_ai.cli document-review-summary --case {case_id}`
4. 승인 시에만:
   ```powershell
   python -m document_ai.cli document-bootstrap-gold --case data/cases/{case_id} --split holdout --approve
   ```
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def prepare_review_package(
    case_id: str,
    *,
    case_dir: str | Path | None = None,
    review_root: str | Path | None = None,
    gold_root: str | Path | None = None,
) -> dict[str, Any]:
    """Assemble a human-review folder for a holdout (or any) case."""
    from document_ai.eval.gold_dataset import gold_fields_path, gold_root as default_gold_root

    case_path = Path(case_dir) if case_dir else Path("data/cases") / case_id
    case_path = case_path.resolve()
    out_dir = review_case_dir(case_id, review_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    copied: dict[str, str] = {}
    mapping = [
        (case_path / "output_mdsr.docx", out_dir / "generated_mdsr.docx"),
        (case_path / "output_mddr.docx", out_dir / "generated_mddr.docx"),
        (case_path / "human_review_checklist.md", out_dir / "human_review_checklist.md"),
    ]
    for src, dst in mapping:
        if _copy_if_exists(src, dst):
            copied[dst.name] = str(dst)

    # Prefer case checklist; if missing, write a stub pointing reviewer to instructions
    if "human_review_checklist.md" not in copied:
        (out_dir / "human_review_checklist.md").write_text(
            f"# Human Review Checklist — {case_id}\n\n"
            "Run `document-validate` on the case to regenerate a full checklist, "
            "or use `reviewer_instructions.md`.\n",
            encoding="utf-8",
        )
        copied["human_review_checklist.md"] = str(out_dir / "human_review_checklist.md")

    g_root = gold_root or default_gold_root()
    fields_src = gold_fields_path(case_id, g_root)
    fields_dst = out_dir / "gold_fields_review.json"
    if fields_src.exists():
        shutil.copy2(fields_src, fields_dst)
        copied["gold_fields_review.json"] = str(fields_dst)
    else:
        fields_dst.write_text(
            json.dumps({"case_id": case_id, "error": "gold_fields not found"}, indent=2) + "\n",
            encoding="utf-8",
        )

    template = review_result_template()
    template["case_id"] = case_id
    template_path = out_dir / "review_result.template.json"
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    copied["review_result.template.json"] = str(template_path)

    instructions = _write_reviewer_instructions(case_id, out_dir / "reviewer_instructions.md")
    copied["reviewer_instructions.md"] = str(instructions)

    manifest = {
        "case_id": case_id,
        "case_dir": str(case_path),
        "review_dir": str(out_dir),
        "split": "holdout",
        "prepared_at": date.today().isoformat(),
        "files": copied,
        "status": "ready_for_review",
    }
    (out_dir / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_review_results(review_dir: Path) -> list[dict[str, Any]]:
    """Load one or more reviewer result files (agreement-ready)."""
    results: list[dict[str, Any]] = []
    primary = review_dir / "review_result.json"
    if primary.exists():
        results.append(json.loads(primary.read_text(encoding="utf-8")))

    multi_dir = review_dir / "reviewers"
    if multi_dir.is_dir():
        for path in sorted(multi_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload not in results:
                results.append(payload)
    return results


def summarize_human_evaluation(review_dir: str | Path) -> dict[str, Any]:
    """Aggregate review_result.json into a summary dict + markdown."""
    review_dir = Path(review_dir)
    results = load_review_results(review_dir)
    if not results:
        raise FileNotFoundError(
            f"No review_result.json (or reviewers/*.json) under {review_dir}"
        )

    per_reviewer: list[dict[str, Any]] = []
    all_scores: list[float] = []
    total_issues = 0
    total_required = 0
    approvals: list[str] = []

    for row in results:
        scores = {field: _as_float(row.get(field)) for field in SCORE_FIELDS}
        present = [v for v in scores.values() if v is not None]
        mean = round(sum(present) / len(present), 2) if present else None
        if mean is not None:
            all_scores.append(mean)
        issues = list(row.get("issues") or [])
        required = list(row.get("required_changes") or [])
        total_issues += len(issues)
        total_required += len(required)
        decision = str(row.get("approval_decision") or "pending")
        approvals.append(decision)
        per_reviewer.append(
            {
                "reviewer_id": row.get("reviewer_id") or "anonymous",
                "mean_score": mean,
                "scores": scores,
                "issue_count": len(issues),
                "required_change_count": len(required),
                "approval_decision": decision,
                "mdsr_status": row.get("mdsr_status"),
                "mddr_status": row.get("mddr_status"),
            }
        )

    overall_mean = round(sum(all_scores) / len(all_scores), 2) if all_scores else None
    approve_count = sum(1 for d in approvals if d.lower() in {"approve", "approved", "accept"})
    agreement = {
        "n_reviewers": len(results),
        "approval_decisions": approvals,
        "unanimous_approve": len(approvals) > 0 and all(
            d.lower() in {"approve", "approved", "accept"} for d in approvals
        ),
        "decision_set": sorted(set(approvals)),
        # Placeholder for future Cohen's kappa when ≥2 categorical labels available
        "cohen_kappa": None,
    }

    summary: dict[str, Any] = {
        "case_id": results[0].get("case_id") or review_dir.name,
        "n_reviewers": len(results),
        "mean_score": overall_mean,
        "approve_count": approve_count,
        "approval_rate": round(approve_count / len(results), 3) if results else 0.0,
        "major_issue_count": total_issues,
        "required_change_count": total_required,
        "per_reviewer": per_reviewer,
        "agreement": agreement,
        "recommended_gate": (
            "promote_to_human_approved"
            if agreement["unanimous_approve"] and (overall_mean is None or overall_mean >= 4.0)
            else "hold_or_revise"
        ),
    }

    md_path = review_dir / "human_evaluation_summary.md"
    md_path.write_text(_render_summary_md(summary), encoding="utf-8")
    json_path = review_dir / "human_evaluation_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["report_paths"] = {"markdown": str(md_path), "json": str(json_path)}
    return summary


def _render_summary_md(summary: dict[str, Any]) -> str:
    lines = [
        f"# Human Evaluation Summary — {summary.get('case_id', '')}",
        "",
        f"- **Reviewers:** {summary.get('n_reviewers', 0)}",
        f"- **Mean score (1–5):** {summary.get('mean_score', '-')}",
        f"- **Approve count / rate:** {summary.get('approve_count', 0)} "
        f"/ {summary.get('approval_rate', 0)}",
        f"- **Major issues:** {summary.get('major_issue_count', 0)}",
        f"- **Required changes:** {summary.get('required_change_count', 0)}",
        f"- **Recommended gate:** `{summary.get('recommended_gate', '')}`",
        "",
        "## Per-reviewer",
        "",
        "| Reviewer | Mean | Decision | Issues | Required | MDSR | MDDR |",
        "|----------|-----:|----------|-------:|---------:|------|------|",
    ]
    for row in summary.get("per_reviewer", []):
        lines.append(
            f"| {row.get('reviewer_id')} | {row.get('mean_score', '-')} | "
            f"{row.get('approval_decision')} | {row.get('issue_count')} | "
            f"{row.get('required_change_count')} | {row.get('mdsr_status')} | "
            f"{row.get('mddr_status')} |"
        )

    agreement = summary.get("agreement") or {}
    lines.extend(
        [
            "",
            "## Agreement (extensible)",
            "",
            f"- Decisions: {', '.join(agreement.get('approval_decisions') or [])}",
            f"- Unanimous approve: {agreement.get('unanimous_approve')}",
            f"- Cohen κ: {agreement.get('cohen_kappa')} _(fill when ≥2 reviewers)_",
            "",
            "## Next step",
            "",
        ]
    )
    if summary.get("recommended_gate") == "promote_to_human_approved":
        case_id = summary.get("case_id", "CASE")
        lines.append(
            f"```powershell\n"
            f"python -m document_ai.cli document-bootstrap-gold "
            f"--case data/cases/{case_id} --split holdout --approve\n"
            f"```"
        )
    else:
        lines.append("Do **not** run `--approve` until revise/reject items are resolved.")
    lines.append("")
    return "\n".join(lines)
