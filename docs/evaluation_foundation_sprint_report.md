# Evaluation Foundation + Real-world Document Trial 1 — Sprint Report

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## 완료 상태 (명확한 구분)

| 상태 | 결과 |
|------|------|
| framework complete | **YES** |
| synthetic validation complete | **YES** (`trial-synthetic-001`) |
| Real-world Trial 1 complete | **NO** — `real_trial_pending` |

실제 사람 검토와 실업무 입력이 없어 “Real-world Trial 1 완료”로 보고하지 않는다.

## 1. 저장소 현황 분석

- HEAD / tag: `v0.5-document-harness` (`d73fc18`)
- branch: `feature/evaluation-foundation-trial1`
- 기존 재사용: harness-generate, document-quality/validate, human review package, draft-change/impact, docx_compare, gold, harness-benchmark
- 부재였던 것: `data/trials/`, trial CLI, baseline freeze 디렉터리, evaluation dataset manifest

## 2. 변경 파일 (핵심)

- `src/document_ai/trial/` — Trial 패키지
- `src/document_ai/cli.py` — trial-* / baseline-freeze / dataset-manifest
- `schemas/trial_manifest.schema.json`, `schemas/trial_error_annotation.schema.json`
- `data/evaluation/dataset_manifest.json`
- `reports/baselines/v0.5-document-harness/`
- `data/trials/trial-synthetic-001/`
- `tests/test_trial_foundation.py`
- `docs/evaluation_foundation_*.md`, `docs/real_world_trial_*.md`, `docs/trial1_*.md`, `docs/interim_presentation_plan.md`

## 3. 신규 CLI

- `trial-init` / `trial-check-input` / `trial-generate`
- `trial-prepare-review` / `trial-analyze` / `trial-summary`
- `baseline-freeze` / `dataset-manifest`

## 4. Trial 데이터 구조

`data/trials/{trial_id}/` — input, reference, generated, human_revised, diff, review, metrics, reports, presentation, workdir

## 5. Dataset manifest

`data/evaluation/dataset_manifest.json` — lab development, jm reference, inventory validation, hospital **holdout**

## 6. Leakage 방지

경로 marker, gold/human_revised 조기 존재, holdout 참조, input SHA-256, dataset role conflict

## 7. Baseline freeze

`reports/baselines/v0.5-document-harness/` — benchmark 92.8, case validation/quality 스냅샷, git_info, baseline_report.md  
(케이스 output 재생성 없이 기존 산출물 복사)

## 8. Synthetic Trial 실행 결과

- trial: `data/trials/trial-synthetic-001`
- completion_label: `synthetic_framework_validation`
- real_world_trial_complete: false
- quality/validation metrics recorded in generation_manifest
- presentation_summary.md / tables / figures data 생성

## 9. 실제 Trial 1 필요 입력

`docs/trial1_required_inputs.md` 참고 — 변경 요청, 회의록, 변경 전 문서 버전, 리뷰어, 수작업 시간 측정

## 10–12. Metric / Diff

- 자동: quality, validation, paragraph/table diff ratios, edit burden
- 사람: 6차원 5점 + readiness + 시간 절감 (baseline 없으면 N/A)
- Diff: `validation.docx_compare` + bag-of-text structural compare (binary hash만 비교하지 않음)
- 오류 auto candidate는 `verified=false`

## 13. 중간발표 산출물

- `presentation_summary.md` / `.json`
- `reports/tables/*.csv`
- `reports/figures/data/*.json`
- `docs/interim_presentation_plan.md`
- PPTX 자동 생성 없음

## 14. Benchmark 변화

의도적 성능 개선 없음. freeze 기준 harness benchmark overall **92.8** 유지.  
주의: `harness-benchmark`는 기존에도 case 디렉터리의 validation/quality 리포트를 in-place 갱신할 수 있으므로, Trial 작업 시 원본 case를 직접 벤치마크 대상으로 돌리지 않는 것을 권장.

## 15. Pytest

- `tests/test_trial_foundation.py`: **17 passed**
- trial + xxcs 단독: **18 passed**
- full suite: 신규 테스트 포함 약 314개 중, `test_lab_ec_sw_xxcs_generation_validation_targets_are_met`가 full suite에서 간헐적으로 threshold 미달 (단독 재실행 시 pass). v0.5 대비 회귀로 단정하기 전 테스트 격리/캐시 이슈 모니터링 필요.

## 16. 남은 한계

- 실업무 입력·human revision 없음 → Trial 1 미완료
- change_update의 draft-change/apply를 trial workdir에 자동 연결하는 상위 오케스트레이션은 수동
- DOCX diff는 구조 추출 기반 bag 비교 (완벽한 semantic diff 아님)
- Embedding / LLM / security runner 확장 없음 (의도적)

## 17. 사용자가 해야 할 작업

1. `docs/trial1_required_inputs.md` 체크리스트 준비
2. `trial-001-mindrium-xa` init (Trial 1 확정; synthetic 없이) — 과거 초안 id `trial-001-lab-ec-sw`는 미사용
3. 실입력 배치 후 check → generate → human revise → analyze → summary
4. 중간발표

## 18. 중간발표까지

Trial 1 완료 → presentation_summary 확정 → 발표 → 개선 우선순위 합의 → Trial 2

## 19. Trial 2 전 결정 사항 (가설)

Trial 1 오류 분포를 본 뒤:

1. Embedding retrieval
2. Hybrid + LLM free-text
3. (필요 시) XXCS template / format 이슈

Security runner는 synthetic MVP에서 동결 유지.
