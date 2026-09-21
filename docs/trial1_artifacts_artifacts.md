# Trial 1 산출물·디렉터리 점검
\n> **Trial 1 (Mindrium XA) — 현재 사용 문서**\n> case: data/cases/mindrium_xa · trial_id: 	rial-001-mindrium-xa\n> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.\n> 인덱스: docs/README.md § Trial 1\n\n
## 권장 구조 (현재 구현 — 충분)

```text
data/trials/trial-001-mindrium-xa/
  trial_manifest.json
  input_manifest.json
  generation_manifest.json
  input/                 # 실입력 (변경요청·회의록·facts)
  reference/             # 변경 전 문서·템플릿 포인터
  generated/             # Harness 출력 (원본 case와 격리)
  human_revised/         # 사람 수정본
  diff/                  # docx_diff.json 등
  review/                # reviewer 패키지·템플릿
  metrics/               # 중간 메트릭·git/env
  reports/
    tables/              # CSV (발표용)
    figures/data/        # JSON (차트용)
    trial_report.md
  presentation/          # presentation_summary.*
  workdir/case/          # 격리 실행 복사본
  metrics.json
  trial_report.md
  presentation_summary.md
  presentation_summary.json
  error_annotations.json
  human_revision_record.json   # 사람 작성 (템플릿에서 복사)
```

### 평가

| 항목 | 판정 |
|------|------|
| 원본 case 격리 | ✅ workdir + generated |
| leakage 검사 위치 | ✅ trial-check-input |
| 발표 데이터 | ✅ tables + figures/data |
| human/auto 분리 | ✅ verified 플래그 |
| 구조 변경 필요 | ❌ **불필요** — 현 구조 유지 |

### 선택적 개선안 (코드 변경 없이 운영 규약만)

- 최종 정답본은 `data/trials/_held_out_answers/trial-001/` 등 trial 밖 폴더에 보관
- `reference/VERSIONS.md`에 문서 버전·기준일 수동 기록
- Trial 2는 `trial-002-…` 새 디렉터리 (trial-001 덮어쓰기 금지)

## Trial 1 완료 후 자동·반자동 생성 목록

| 파일 | 생성 주체 |
|------|-----------|
| `trial_manifest.json` | trial-init / 상태 갱신 |
| `input_manifest.json` | trial-check-input |
| `generation_manifest.json` | trial-generate |
| `generated/output_mdsr.docx` 등 | trial-generate |
| `generated/quality_report.md` | trial-generate |
| `generated/validation_report.*` | trial-generate |
| `review/*` 템플릿·지시서 | trial-prepare-review |
| `diff/docx_diff.json` | trial-analyze |
| `error_annotations.json` | trial-analyze (+ 사람 verified) |
| `metrics.json` | trial-analyze |
| `trial_report.md` | trial-summary |
| `presentation_summary.md` / `.json` | trial-summary |
| `reports/tables/*.csv` | trial-summary |
| `reports/figures/data/*.json` | trial-analyze / summary |

### 사람이 반드시 작성

| 파일 | 내용 |
|------|------|
| `human_revised/revised_*.docx` | 수정 문서 |
| `human_revision_record.json` | 시간·rating·readiness |
| `error_annotations.json` (verified) | 최종 오류 유형 |

Synthetic trial(`trial-synthetic-001`) 산출물은 프레임 검증용이며 Real Trial 결과로 대체·혼용하지 않는다.
