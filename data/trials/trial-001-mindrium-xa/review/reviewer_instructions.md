# Trial Reviewer Instructions — `trial-001-mindrium-xa`

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
