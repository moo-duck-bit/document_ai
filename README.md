# Document AI

EC-SW(의료 소프트웨어) 및 IEEE SRS 문서를 **python-docx** 기반으로 생성·갱신하는 파이프라인입니다.  
단순 일괄 생성을 넘어, 요구사항 변경 시 **영향받는 문서·항목만 선별 수정**하는 **Change Impact Agent MVP**를 제공합니다.

## 요구 사항

- Python 3.11+
- `pip install -e ".[dev]"` (또는 `pip install python-docx pytest`)

## 프로젝트 구조

```
document_AI/
├── src/document_ai/
│   ├── cli.py              # CLI 진입점
│   ├── impact/             # Change Impact (graph, orchestrator)
│   ├── intake/             # 자연어 변경 요청 → change JSON
│   ├── learn/              # DOCX 추출, SRS import, ID 정규화
│   └── render/             # MDSR / MDDR / XXCS 렌더·패치
├── data/
│   ├── templates/ec_sw/    # 빈 양식 (MDSR, MDDR, XXCS skeleton)
│   ├── examples/ec_sw/     # Mindrium 완성본 (학습·테스트용)
│   ├── schemas/ec_sw/      # 필드·위치 스키마
│   └── cases/              # 케이스별 JSON + output DOCX
├── scripts/                # 빌드·diff 유틸
└── tests/
```

## 빠른 시작

```powershell
cd document_AI
pip install -e ".[dev]"

# 전체 테스트
python -m pytest -q
```

## Change Impact Agent MVP

요구사항 변경 요청 → `requirements.json` / `design_items.json` / `security_tests.json` / traceability 기반으로 **영향 문서·항목**을 분석하고, 필요한 DOCX·JSON만 패치합니다.

### 지원 ID 형식

| 유형 | 예시 | 정규화 결과 |
|------|------|-------------|
| EC-SW Req | `Req. 6`, `Req.6`, `요구사항 6` | `Req. 6` |
| 보안·검증 | `IA-04`, `UC-18`, `SI-06` | 2자리 유지 (`IA-04`) |
| IEEE SRS | `FR-02`, `NFR-01`, `TC-02` | 2자리 유지 (`FR-02`) |

### CLI

```powershell
# 자연어 → change JSON 초안 (설명 없으면 clarifying_questions 반환)
python -m document_ai.cli draft-change `
  --case data/cases/mindrium_xa `
  --request "Req. 6: 로그인 제한 정책 강화"

# 영향 분석 (MDSR / MDDR / XXCS / TC 연결)
python -m document_ai.cli impact `
  --case data/cases/mindrium_xa `
  --change data/cases/mindrium_xa/changes/req6_update.json

# 영향받는 문서만 패치 + requirements.json 갱신
python -m document_ai.cli apply-change `
  --case data/cases/mindrium_xa `
  --change data/cases/mindrium_xa/changes/req6_update.json
```

### 케이스

| case | 용도 |
|------|------|
| `data/cases/mindrium_xa` | EC-SW traceability (IA↔Req), XXCS 연동 |
| `data/cases/stt_srs` | IEEE SRS (FR/NFR↔TC) |
| `data/cases/jm_collection` | JM COLLECTION MDSR/MDDR 생성 예시 |

### 케이스 JSON

| 파일 | 역할 |
|------|------|
| `requirements.json` | Req 목록 + traceability 매트릭스 |
| `design_items.json` | MDDR Req. 설계 블록 |
| `security_tests.json` | XXCS 시험결과 행 |
| `changes/*.json` | 변경 단위 (requirement_changes) |

## 문서 생성

```powershell
# JM COLLECTION MDSR 빌드
python scripts/build_jm_collection_mdsr.py

# Mindrium gold vs JM output diff (섹션 5 품질)
python scripts/mdsr_filled_vs_output_diff.py

# 케이스 전체 생성 (CLI)
python -m document_ai.cli generate-all --case data/cases/jm_collection
```

EC-SW 완성본·양식 상세: [`data/examples/ec_sw/README.md`](data/examples/ec_sw/README.md)

## 테스트

```powershell
python -m pytest -q
```

주요 테스트:

- `tests/test_change_intake.py` — NL intake, ID 파싱
- `tests/test_impact.py` — traceability 영향, apply-change 패치
- `tests/test_stt_srs.py` — SRS markdown import, FR→TC 연결

## 라이선스 / 기여

SKKU Document AI 프로젝트. 이슈·PR은 저장소 정책에 따릅니다.
