# Trial 1 실행 순서 체크리스트 (실무)

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> Real-world Trial만 해당. `--synthetic` 사용 금지.  
> 명령 상세: `docs/trial1_execution_commands.md`

## A. 사전 준비

- [ ] `docs/trial1_required_inputs.md` 항목 충족
- [ ] `docs/trial1_preflight_checklist.md` 통과
- [ ] git: `v0.5-document-harness` / commit `d73fc18` 확인
- [ ] working tree clean 권장
- [ ] 최종 정답 문서를 generation 경로 밖 격리
- [ ] 민감정보 마스킹
- [ ] 리뷰어·시간 측정 방법 합의
- [ ] trial_id 확정: `trial-001-mindrium-xa`
- [ ] case 확정: `mindrium_xa` (`docs/trial1_case_decision_mindrium.md`)
- [ ] trial_type 확정: **change_update**

## B. 입력자료 준비

- [ ] 변경 전 MDSR/MDDR/(XXCS)를 `reference/` 또는 승인된 input 규칙에 맞게 배치
- [ ] 변경 요청·회의록·확인사항을 `input/`에 배치
- [ ] `input.json` / requirements 등 case facts 정리 (필요 시)
- [ ] gold / holdout / human_revised final 미포함 재확인

## C. Trial 부트스트랩

- [ ] `trial-init` ( `--synthetic` 없음 )
- [ ] `input_cutoff` 기록
- [ ] `trial-check-input` PASS (`data_leakage_clean`)
- [ ] leakage 실패 시 generate 금지

## D. (Change Update) 변경 반영 준비

- [ ] 변경 요청 → `draft-change` (workdir/case 기준, 원본 case 금지)
- [ ] `impact` dry-run으로 영향 범위 확인
- [ ] 필요 시 workdir에서만 `apply-change`
- [ ] 원본 `data/cases/mindrium_xa` / `data/examples/ec_sw` 미변경 확인

## E. 생성

- [ ] `trial-generate`
- [ ] `generated/`에 DOCX·quality·validation 존재 확인
- [ ] `generation_manifest.json` 확인 (`overwrite_source_case=false`)
- [ ] 원본 case output hash 불변 확인

## F. Human review

- [ ] `trial-prepare-review`
- [ ] reviewer에게 `review/` 패키지 전달
- [ ] generated 문서 검토·수정
- [ ] `human_revised/revised_*.docx` 저장
- [ ] `human_revision_record.json` 기입 (rating·시간·readiness)
- [ ] `error_annotations.json` 기입 (`verified=true`만 확정)

## G. 분석·요약

- [ ] `trial-analyze`
- [ ] `trial-summary`
- [ ] `metrics.json`에서 `real_world_trial_complete=true` 확인
- [ ] `completion_label` ≠ `synthetic_framework_validation`

## H. 중간발표

- [ ] `presentation_summary.md` / `.json` 검토
- [ ] `reports/tables` · `figures/data` 표·차트 원본 확보
- [ ] PPTX 수동 작성 (선택)
- [ ] Trial 2 / Embedding 우선순위 합의

## I. 종료 게이트

- [ ] Trial 1 산출물 보관 (덮어쓰기 금지)
- [ ] Embedding Retrieval Sprint 착수 여부 결정
- [ ] Security Runner / Operation / LLM 구현은 Trial 분석 전까지 보류
