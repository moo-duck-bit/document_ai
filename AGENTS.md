# Document AI

**North Star**: 완성 문서로 학습해, 빈 양식과 새 케이스만으로 문서를 자동 작성하는 Agent.

## 두 층 아키텍처

### 1. Form Fill Agent (최종 목표)

```
┌─────────────────────────────────────────────────────────────────┐
│                        학습 Phase (오프라인)                      │
│  완성본 + 빈양식 → parse/OCR → template-learn → case-index       │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        작성 Phase (런타임)                        │
│  빈양식 + case input → case-retrieval → form-fill → render       │
└─────────────────────────────────────────────────────────────────┘
                                │
                         document-eval
                    (필드 F1, human review)
```

| 컴포넌트 | 역할 |
|----------|------|
| `template-learn` | 양식에서 필드 스키마 추출 |
| `case-retrieval` | 유사 완성본 검색 (few-shot) |
| `form-fill` | 필드값 추론 (facts > rules > similar > LLM) |
| `document-render` | DOCX/PDF 출력 |

### 2. 기반 파이프라인 (RAG 인프라)

parse → chunk → embed → retrieve — case-retrieval과 문서 QA에 공통 사용.

## 스킬 맵

| 스킬 | 용도 |
|------|------|
| **`form-fill-agent`** | 양식 자동 작성 오케스트레이터 |
| **`case-intake`** | 채팅·참고 DOCX → input.json |
| `template-learn` | 스키마 학습 |
| `case-retrieval` | 유사 케이스 |
| `form-fill` | 필드값 생성 |
| `document-render` | 파일 출력 |
| `pdf-parse` / `document-ocr` | 문서 입력 |
| `document-eval` | 필드·RAG 평가 |

## 데이터 레이아웃

```
data/
├── templates/           # 빈 양식 (.docx)
├── examples/{id}/       # 완성본 (학습용)
├── schemas/{id}.schema.json
├── cases/{case_id}/
│   ├── input.json       # 새 케이스 facts
│   └── output.docx      # 생성 결과
└── eval/
    ├── golden_qa.jsonl      # RAG QA
    └── golden_fields.jsonl  # form-fill 필드 정답
```

## 확정 요구사항

| 항목 | 선택 |
|------|------|
| 포맷 | **DOCX** |
| 문서 종류 | **EC-SW 의료 SW 문서 세트** (MDSR/MDDR/XXCS) + 보고서·신청서·제안서 확장 |
| 케이스 입력 | **채팅 + 참고 DOCX → input.json** (XXCS는 Excel/CSV bulk v2) |

## 학습 코퍼스 (Mindrium XA) ✅

| template_id | 완성본 | 빈 양식 |
|-------------|--------|---------|
| `spec_requirements` | `data/examples/ec_sw/spec_mdsr_*.docx` | ✅ `data/templates/ec_sw/template_mdsr.docx` |
| `spec_design` | `data/examples/ec_sw/spec_mddr_*.docx` | ✅ `data/templates/ec_sw/template_mddr.docx` |
| `report_security_verification` | `data/examples/ec_sw/report_xxcs_*.docx` | ❌ **없음** → 완성본 골격 추출 또는 CSV bulk |

diff 분석: `data/schemas/ec_sw/template_diff_analysis.json`

```
MDSR (Req. N) ──► MDDR (설계) ──► XXCS (IA/UC/SI 시험결과)
```

**주의**: EC-SW 문서는 `{{placeholder}}` 없이 **표 중심** — template-learn은 표 행 패턴 방식.

```
User ──chat/upload──► case-intake ──confirm──► input.json ──► form-fill ──► output.docx
                              ▲
                    완성본 few-shot (case-retrieval)
```

| Phase | 내용 | 산출물 |
|-------|------|--------|
| **0** | 스킬·플랜·intake 설계 | ✅ |
| **1** | EC-SW 코퍼스 등록 (Mindrium XA 3종) | ✅ |
| **1a** | 표 행 추출 POC (XXCS / MDSR) | ✅ schema JSON |
| **1b** | case-intake (채팅 → input.json) | intake CLI |
| **2** | template-learn + render POC | ✅ `output_mdsr.docx` |
| **3** | case-index + retrieval | 유사 케이스 few-shot |
| **4** | form-fill + rules + LLM free_text | end-to-end |
| **5** | API + eval + human review | 프로덕션 PoC |

## 핵심 설계 결정

1. **EC-SW 실제 코퍼스**: 표 중심 → **표 행 템플릿 복제** 우선 (placeholder는 simplified template용)
2. **구조화 필드**는 LLM 금지 — hallucination 방지
3. **free_text**만 유사 케이스 few-shot + LLM
4. **document_set** 단위 (MDSR+MDDR+XXCS) traceability

## 개발 워크플로우

```
티켓 → create-plan → implement-plan → validate-plan → document-eval → commit
```

## 서브에이전트

| 에이전트 | 역할 |
|----------|------|
| **`form-fill-agent`** | 양식 작성 파이프라인 |
| `document-analyzer` | 코드·데이터 흐름 |

## 기술 스택

| 레이어 | MVP |
|--------|-----|
| Template/Render | python-docx, **docxtpl** (Jinja2 DOCX) |
| Parse | PyMuPDF (PDF), python-docx |
| Case index | Chroma + BGE-M3 |
| LLM | free_text 필드만 (GPT-4o / Ollama) |
| API | FastAPI |

## 코딩 규칙

- `.env`·API 키 커밋 금지
- 금액·날짜·당사자명: `input.json` 또는 유사 케이스에서만
- form-fill 변경 시 `golden_fields.jsonl` 회귀 테스트
- 커밋은 사용자 요청 시에만

## CLI (파이프라인)

```powershell
pip install -e ".[dev]"
python scripts/run_pipeline.py

# 또는 단계별:
python -m document_ai.cli export-schema      # 1. MDSR/MDDR schema JSON
python -m document_ai.cli xxcs-skeleton      # 2. XXCS skeleton
python -m document_ai.cli generate --case data/cases/mindrium_xa
```

## 참고

- 마스터 플랜: `thoughts/shared/plans/form-fill-agent-master.md`
- 티켓: `thoughts/shared/tickets/DOC-003-form-fill-agent.md`
