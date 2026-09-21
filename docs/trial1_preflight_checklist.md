# Trial 1 Preflight Checklist

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


Real-world Trial 1 시작 전 모두 확인한다.

## 시스템 freeze

- [ ] `git rev-parse --short HEAD` → `d73fc18` (또는 합의된 v0.5 commit)
- [ ] `git tag --points-at HEAD`에 `v0.5-document-harness` 포함
- [ ] working tree clean (`git status --porcelain` 비어 있음) — Trial 측정 시 권장
- [ ] `reports/baselines/v0.5-document-harness/baseline_report.md` 존재
- [ ] harness benchmark overall 스냅샷 확인 (기준 92.8)

## 입력·누수

- [ ] `input_cutoff` 일시 확정 및 manifest 기록
- [ ] gold / human_revised final / holdout 산출물 입력 없음
- [ ] `trial-check-input` PASS (`data_leakage_clean=true`)
- [ ] 입력 파일 SHA-256이 `input_manifest.json`에 기록됨
- [ ] 민감정보 마스킹 완료

## Trial 디렉터리

- [ ] trial_id = `trial-001-mindrium-xa` (확정, 옵션 B)
- [ ] case = `data/cases/mindrium_xa`
- [ ] `--synthetic` 없이 init
- [ ] generated output은 trial 하위에만 기록
- [ ] 원본 `data/cases/mindrium_xa/output_*.docx` 및 `data/examples/ec_sw/**` 덮어쓰기 없음

## 사람 검토 준비

- [ ] 리뷰어 지정
- [ ] `trial-prepare-review` 패키지 생성
- [ ] 시간 측정 방법 합의 (baseline / revision)
- [ ] `human_revision_record.template.json` 기입 방법 공유

## 상태 라벨

- [ ] synthetic trial과 혼동하지 않음
- [ ] 완료 전 `real_world_trial_complete=false` / `real_trial_pending` 유지
- [ ] 중간발표 전 Trial 1 human review 완료 필요
