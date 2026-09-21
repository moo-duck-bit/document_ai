# Document AI — docs 인덱스

## Trial 1 (Mindrium XA) — 현재 사용

| 문서 | 역할 |
|------|------|
| [`trial1_case_decision_mindrium.md`](trial1_case_decision_mindrium.md) | Case 확정 (옵션 B) |
| [`trial1_required_inputs.md`](trial1_required_inputs.md) | 필요 입력 체크리스트 |
| [`trial1_execution_commands.md`](trial1_execution_commands.md) | 실행 명령 |
| [`trial1_preflight_checklist.md`](trial1_preflight_checklist.md) | 실행 전 점검 |
| [`trial1_execution_guide.md`](trial1_execution_guide.md) | 실행 가이드 |
| [`trial1_execution_checklist.md`](trial1_execution_checklist.md) | 실행 순서 |
| [`trial1_preparation_sprint_report.md`](trial1_preparation_sprint_report.md) | Preparation Sprint |
| [`trial1_directories_artifacts.md`](trial1_directories_artifacts.md) | 디렉터리·산출물 |
| [`trial1_result_analysis_plan.md`](trial1_result_analysis_plan.md) | 결과 분석 계획 |
| [`draft_change_input_quality.md`](draft_change_input_quality.md) | draft-change 입력 품질 |
| [`interim_presentation_prep.md`](interim_presentation_prep.md) | 중간발표 준비 |

**실행 산출물 (레포 data/):**

| 경로 | 역할 |
|------|------|
| `data/trials/trial-001-mindrium-xa/PRE_HUMAN_REVIEW_REPORT.md` | HR 가능/차단 상태 보고서 |
| `data/trials/trial-001-mindrium-xa/GENERATION_CORRECTION_REPORT.md` | 생성 전략 수정·검증 수치 |
| `data/trials/trial-001-mindrium-xa/execution_report.json` | 실행 메타·해시 |
| `data/trials/trial-001-mindrium-xa/generated_patch_preserving/` | **patch-in-place canonical 후보** |
| `data/trials/trial-001-mindrium-xa/generated/` · `generated_clean_mindrium/` | **INVALID_FOR_HR** (재생성 skeleton) |
| `data/trials/trial-001-mindrium-xa/reference/` | Mindrium 원본 기준 문서 |

> Human Review는 `pre_human_review_ready=true`이고 visual QA 통과 후에만 시작.  
> 현재 게이트: patch 검증 통과여도 visual render 미통과 시 `pre_human_review_blocked`.

- trial_id: `trial-001-mindrium-xa`
- case: `data/cases/mindrium_xa`
- system: `v0.5-document-harness` @ `d73fc18`

## Historical (lab_ec_sw / JM COLLECTION) — Not used in Trial 1

아래 문서는 **삭제하지 않는다**. 과거 벤치마크·품질 진단·security runner 기록이다.  
문서 상단에 Historical 라벨이 붙어 있다.

- `demo_document_harness_report.md`
- `research_readiness_report.md`
- `mddr_quality_improvement_report.md` / `mddr_validation_diagnosis.md`
- `xxcs_quality_improvement_report.md` / `xxcs_quality_diagnosis.md`
- `gold_dataset_design.md`, `holdout_human_review_protocol.md`, `human_evaluation_protocol.md`
- `evaluation_foundation_sprint_report.md`
- `security_runner_*`, `security_execution_*`, `security_test_result_*`

## 공유·아키텍처 (case 비종속)

- `real_world_trial_protocol.md`, `real_world_trial_metrics.md`, `real_world_trial_data_leakage_policy.md`
- `evaluation_foundation_architecture.md`
- `knowledge_graph_design.md`, `platform_architecture.md`, `ai_engineering_concept.md`
