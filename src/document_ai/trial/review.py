"""trial-prepare-review: human revision package under trial/review."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from document_ai.trial.models import ERROR_TYPES, SEVERITIES, human_revision_template
from document_ai.trial.paths import load_manifest, rel_to_project, save_manifest, trial_dir, write_json, write_text


def prepare_trial_review(trial: str | Path) -> dict[str, Any]:
    path = trial_dir(trial)
    manifest = load_manifest(path)
    if manifest.get("status") not in {"generated", "review_pending", "reviewed", "completed"}:
        # Allow prepare after generate; warn if only prepared
        if manifest.get("status") == "prepared":
            raise RuntimeError("trial not generated yet; run trial-generate first")

    review_dir = path / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    generated = path / "generated"
    document_types = list(manifest.get("document_types") or ["MDSR", "MDDR"])

    copied: list[str] = []
    for doc_type in document_types:
        for name in (f"output_{doc_type.lower()}.docx", f"generated_{doc_type.lower()}.docx"):
            src = generated / name
            if src.exists():
                dst = review_dir / src.name
                shutil.copy2(src, dst)
                copied.append(rel_to_project(dst))
                break

    template = human_revision_template(str(manifest.get("trial_id")), document_types)
    write_json(review_dir / "human_revision_record.template.json", template)

    annotations_template = {
        "trial_id": manifest.get("trial_id"),
        "error_types": list(ERROR_TYPES),
        "severities": list(SEVERITIES),
        "annotations": [],
        "note": "Set verified=true only after human confirmation. Auto candidates remain unverified.",
    }
    write_json(review_dir / "error_annotations.template.json", annotations_template)

    write_text(
        review_dir / "reviewer_instructions.md",
        f"""# Trial Reviewer Instructions — `{manifest.get('trial_id')}`

## 목적

v0.5 Document Harness 생성 결과를 **실무 관점**에서 수정·평가한다.

- Trial 체계의 기준선 측정이 목적이다 (모델 성능 개선 아님).
- 최종 정답 문서·gold·holdout 결과를 참고 입력으로 쓰지 않는다.
- 수정본은 `human_revised/`에 저장한다.

## 절차

1. `review/`의 generated DOCX를 연다.
2. 필요한 수정을 반영한 파일을 `human_revised/`에 저장한다.
   - 권장 파일명: `revised_mdsr.docx`, `revised_mddr.docx`, `revised_xxcs.docx`
3. `human_revision_record.template.json`을 복사해 `human_revision_record.json`으로 저장하고 기입한다.
4. 오류는 `error_annotations.template.json`을 복사해 `../error_annotations.json` 또는
   `error_annotations.json`에 기록한다. 자동 후보는 `verified=false`로 둔다.
5. 시간 기록:
   - `manual_baseline_minutes`: 수작업 예상/실측 (없으면 null)
   - `harness_generation_minutes`: generation_manifest의 duration 참고
   - `human_revision_minutes`: 실제 수정 시간

## 평가 척도 (1–5)

- content_accuracy, completeness, format_compliance
- traceability, language_quality, practical_usability

## 금지

- frozen holdout (`hospital_reservation`) 튜닝
- Trial 1 결과로 코드 수정 후 같은 Trial 결과 덮어쓰기
- synthetic 결과를 실제 Trial 1 완료로 보고
""",
    )

    write_text(
        review_dir / "review_checklist.md",
        f"""# Trial Review Checklist — `{manifest.get('trial_id')}`

## 문서 목록

| Document | Generated | Human revised path |
|----------|-----------|--------------------|
"""
        + "\n".join(
            f"| {dt} | review/ 또는 generated/ | human_revised/revised_{dt.lower()}.docx |"
            for dt in document_types
        )
        + """

## 확인 항목

- [ ] 입력에 최종 정답/gold가 섞이지 않았는가
- [ ] Req/Design/Test ID가 유지되는가
- [ ] 변경 요청과 무관한 기존 내용이 불필요하게 바뀌지 않았는가
- [ ] 표/형식 준수
- [ ] 실무 내부 검토 가능 여부
- [ ] 외부 전달 가능 여부
- [ ] 수정 시간 기록
- [ ] 오류 annotation (verified 구분)

## 산출물

- `human_revised/*.docx`
- `human_revision_record.json`
- `error_annotations.json`
""",
    )

    write_json(
        review_dir / "package_manifest.json",
        {
            "trial_id": manifest.get("trial_id"),
            "document_types": document_types,
            "copied_generated": copied,
            "templates": [
                "human_revision_record.template.json",
                "error_annotations.template.json",
                "reviewer_instructions.md",
                "review_checklist.md",
            ],
        },
    )

    manifest["status"] = "review_pending"
    save_manifest(path, manifest)
    return {
        "ok": True,
        "trial_dir": rel_to_project(path),
        "review_dir": rel_to_project(review_dir),
        "copied_generated": copied,
        "status": manifest["status"],
    }
