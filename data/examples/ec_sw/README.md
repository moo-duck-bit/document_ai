# EC-SW 문서 — 완성본 + 빈 양식

## 템플릿 (빈 양식)

| template_id | 빈 양식 | 경로 |
|-------------|---------|------|
| `spec_requirements` | XX-XX-XX(0) 요구사항명세서[양식] | `data/templates/ec_sw/template_mdsr.docx` |
| `spec_design` | XX-XX-XX(0) 설계 명세서[양식] | `data/templates/ec_sw/template_mddr.docx` |
| `report_security_verification` | **없음** | ↓ 아래 전략 참고 |

## 완성본 (학습 예시 — Mindrium XA)

| template_id | 경로 |
|-------------|------|
| `spec_requirements` | `data/examples/ec_sw/spec_mdsr_*.docx` |
| `spec_design` | `data/examples/ec_sw/spec_mddr_*.docx` |
| `report_security_verification` | `data/examples/ec_sw/report_xxcs_*.docx` |

## 빈↔완성 diff (template-learn)

| 문서 | 빈 표 | 완성 표 | diff 표 |
|------|-------|---------|---------|
| MDSR | 39 | 45 | 27 |
| MDDR | 3 | 3 | 3 |

→ MDSR은 **완성본에서 추가된 Req. 표**가 6개. diff로 **가변 필드** 추출 가능.

분석: `data/schemas/ec_sw/template_diff_analysis.json`

```powershell
python scripts/import_ec_sw_templates.py
```

## XXCS (보안 검증) — 빈 양식 없음

| 전략 | 설명 |
|------|------|
| **A. 골격 추출** | Mindrium 완성 XXCS에서 시험결과·비고만 비우고 `template_xxcs_skeleton.docx` 생성 |
| **B. 블록 복제** | 첫 IA-01 표 블록을 템플릿으로 IA/UC/SI 전 항목에 programmatic 복제 |
| **C. CSV bulk** | `security_req_id, test_result, applied, notes` CSV → 표 채우기 |

**권장**: A + C (골격 1회 생성 + 시험결과는 스프레드시트)

## 재실행

```powershell
python scripts/analyze_ec_sw_corpus.py      # 완성본 분석
python scripts/import_ec_sw_templates.py    # 빈 양식 import + diff
```
