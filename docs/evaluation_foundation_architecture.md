# Evaluation Foundation 아키텍처

## 목적

v0.5 Document Harness를 **개선하지 않고** 측정하기 위한 재현 가능한 Trial 체계다.

```text
baseline freeze (v0.5)
        │
trial-init → trial-check-input → trial-generate
        │
trial-prepare-review → (human revise) → trial-analyze → trial-summary
        │
presentation_summary + reports/tables + figures/data
```

## 재사용

| 기존 구성요소 | Trial에서의 역할 |
|---------------|------------------|
| `DocumentHarness` / `harness-generate` | 격리된 workdir에서만 생성 |
| `document-quality` / `document-validate` | generation metrics |
| `document-prepare-review` 패턴 | trial review 패키지 |
| `draft-change` / `impact` / `apply-change` | change_update 입력 준비에 재사용 가능 |
| `validation/docx_compare.py` | paragraph/table 추출 |
| `data/gold` | 자동 validation 참조만 (입력 금지) |
| platform `_copy_case` 패턴 | trial workdir 격리 |

## 디렉터리

```text
data/trials/{trial_id}/
  trial_manifest.json
  input/ reference/ generated/ human_revised/
  diff/ review/ metrics/ reports/ presentation/
  workdir/case/          # 원본 case 복사본 (원본 덮어쓰기 금지)

data/evaluation/dataset_manifest.json
reports/baselines/v0.5-document-harness/
```

## CLI

- `trial-init` / `trial-check-input` / `trial-generate`
- `trial-prepare-review` / `trial-analyze` / `trial-summary`
- `baseline-freeze` / `dataset-manifest`

## 완료 라벨

| label | 의미 |
|-------|------|
| `synthetic_framework_validation` | fixture만 검증 |
| `real_trial_pending` | 실제 입력/검토 대기 |
| `real_world_trial_complete` | 비-synthetic + human record + revised docs |

synthetic 결과를 Real-world Trial 1 완료로 보고하지 않는다.
