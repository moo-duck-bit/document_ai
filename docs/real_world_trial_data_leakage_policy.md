# Real-world Trial Data Leakage Policy

## 금지 입력

- `data/gold/**`
- human-revised final을 generation 전 입력으로 사용
- holdout case (`hospital_reservation`) 정답/평가 결과
- 평가 대상 변경이 이미 반영된 최종 승인 문서
- 미래 시점 정보

## 허용 입력

- 기존 버전 문서 (변경 전)
- 변경 요청서 / 회의록 / 요구사항 메모
- 개발자 확인 답변
- 템플릿 / 프로젝트 facts
- case `input.json` 및 payload (gold DOCX 제외)

## 검사

`trial-check-input`이 수행한다.

- 경로 marker (`gold`, `human_revised`, …)
- 입력 파일 SHA-256
- dataset role conflict / holdout 참조
- generation 전 `human_revised/` 조기 존재

## Dataset roles

`data/evaluation/dataset_manifest.json`

- holdout는 development / real_world_trial과 동시에 쓸 수 없다.
- Trial 입력에 holdout 산출물을 넣으면 findings로 실패한다.

## Trial 결과 보존

```text
Trial 1 / v0.5 original
  → error analysis
  → improvement implementation (별도)
  → Trial 2 / improved version (새 trial_id)
```

같은 trial 디렉터리를 “개선 후 결과”로 덮어쓰지 않는다.
