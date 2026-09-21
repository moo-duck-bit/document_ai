# Trial 1 실행 명령 (PowerShell)

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


실제 입력이 `docs/trial1_required_inputs.md` / `docs/trial1_preflight_checklist.md`를
충족한 뒤에만 실행한다. `--synthetic`을 붙이지 않는다.  
Case: **Mindrium XA** (`docs/trial1_case_decision_mindrium.md`)

```powershell
# 0) freeze / 상태 확인
git status
git rev-parse --short HEAD
git tag --points-at HEAD

python -m document_ai.cli baseline-freeze
python -m document_ai.cli dataset-manifest

# 0b) 변경 입력 dry-run (원본 case 미기록)
$env:PYTHONIOENCODING='utf-8'
python -m document_ai.cli draft-change `
  --case data/cases/mindrium_xa `
  --request-file data/cases/mindrium_xa/changes/request_req6.txt `
  --dry-run

# 1) Trial 초기화
python -m document_ai.cli trial-init `
  --trial-id trial-001-mindrium-xa `
  --case data/cases/mindrium_xa `
  --type change_update `
  --system-version v0.5-document-harness `
  --system-commit d73fc18

# 2) 사용자가 input/ · reference/ 에 실자료 배치
#    reference: examples/ec_sw 원본 DOCX + VERSIONS.md
#    input: change_request.txt 등
#    (최종 정답·gold·holdout 금지)

# 3) 입력·누수 검사 (실패 시 중단)
python -m document_ai.cli trial-check-input `
  --trial data/trials/trial-001-mindrium-xa

# 4) 생성 (원본 case output 덮어쓰지 않음)
#    Change Update: workdir에서 draft-change → impact → apply-change 후 generate
python -m document_ai.cli trial-generate `
  --trial data/trials/trial-001-mindrium-xa

# 필요 시 workdir 안에서만 재생성:
# python -m document_ai.cli trial-generate `
#   --trial data/trials/trial-001-mindrium-xa `
#   --force-generate

# 5) Human review 패키지
python -m document_ai.cli trial-prepare-review `
  --trial data/trials/trial-001-mindrium-xa

# 6) 사람이 generated 문서를 수정해 human_revised/ 에 저장
#    human_revision_record.json · error_annotations.json 기입

# 7) 분석 · 요약 · 중간발표 데이터
python -m document_ai.cli trial-analyze `
  --trial data/trials/trial-001-mindrium-xa

python -m document_ai.cli trial-summary `
  --trial data/trials/trial-001-mindrium-xa

# 8) 회귀 확인
python -m pytest -q
```

완료 판정:

- `presentation_summary.json`의 `completion_label` ≠ `synthetic_framework_validation`
- `metrics.json`의 `real_world_trial_complete` == true
- synthetic trial(`trial-synthetic-001`)과 결과를 섞지 말 것
- 원본 `data/examples/ec_sw/**`, `data/cases/mindrium_xa/output_*.docx` 미변경
