# Real-world Trial Protocol

## 원칙

1. 작성 시점에 알 수 있는 정보만 입력으로 사용한다.
2. 최종 정답·gold·human revised final·holdout을 입력에 넣지 않는다.
3. Trial 결과는 `data/trials/`에만 저장한다. 원본 case output을 덮어쓰지 않는다.
4. Trial 1 결과를 보고 코드를 고친 뒤, 같은 Trial 1을 덮어쓰지 않는다.
5. Security runner / Embedding / LLM 개선은 이 protocol의 측정 단계가 아니다.

## Trial 유형

### A. new_document_generation

입력: 회의록, 요구사항 메모, 참고 문서, 프로젝트 facts, 템플릿  
출력: MDSR/MDDR/(XXCS plan), quality, validation, traceability

### B. change_update

입력: 기존 문서 버전, 변경 요청, 회의록, 개발자 확인  
출력: 변경 문서, diff, 불필요 변경 여부, traceability 재검증  

기존 `draft-change` → `impact` → `apply-change`를 입력 준비에 활용할 수 있다.
apply는 **trial workdir**에서만 수행한다.

## 절차

1. `baseline-freeze`로 v0.5 스냅샷 확인
2. `trial-init` (실제면 `--synthetic` 없이)
3. 실입력을 `input/`에 배치
4. `trial-check-input` (leakage 실패 시 중단)
5. `trial-generate`
6. `trial-prepare-review`
7. 사람이 `human_revised/` + `human_revision_record.json` 작성
8. `trial-analyze` → `trial-summary`
9. 중간발표 자료 확인 후 Trial 2 우선순위 결정

## Data cutoff

`trial_manifest.input_cutoff`에 입력 마감 시각을 기록한다.
cutoff 이후 정보·최종 승인본은 입력에 추가하지 않는다.
