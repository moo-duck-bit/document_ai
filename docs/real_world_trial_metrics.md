# Real-world Trial Metrics

## 자동 평가

- Quality score / Validation score
- Required field · Traceability coverage (validation 경로 재사용)
- Diff ratios: unchanged/modified/added/deleted paragraphs
- Table-cell unchanged/modified ratios
- `document_level_edit_burden_score` (0–100)
- Invalid/duplicate ID는 validation 리포트에서 수집

## 사람 평가 (1–5)

- content_accuracy, completeness, format_compliance
- traceability, language_quality, practical_usability

기록 위치: `human_revision_record.json`

## 실무 효과

```text
time_saving_rate =
  (manual_baseline_minutes - (generation_minutes + revision_minutes))
  / manual_baseline_minutes
```

- baseline 없으면 `N/A`
- 추정값과 실측값은 `manual_baseline_source`로 구분

추가:

- usable_without_change / internal_review_ready / external_delivery_ready
- major/minor issue counts

## 오류 taxonomy

FACT_ERROR, MISSING_CONTENT, UNSUPPORTED_ASSUMPTION, TRACEABILITY_ERROR,
FORMAT_ERROR, TERMINOLOGY_ERROR, STYLE_EDIT, REDUNDANT_CONTENT,
INCONSISTENT_CONTENT, WRONG_SECTION, NO_CHANGE_REQUIRED

자동 후보는 `verified=false` / `source=auto_candidate`로만 저장한다.
