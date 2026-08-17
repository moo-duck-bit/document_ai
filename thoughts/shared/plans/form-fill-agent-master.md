# Form Fill Agent — 마스터 플랜

## North Star

**완성 문서로 학습 → 빈 양식 + 새 케이스 → 자동 문서 작성**

일반 RAG(QA)가 아니라 **케이스 기반 양식 작성**이 목표.

## 왜 RAG만으로는 부족한가

| 일반 RAG | Form Fill Agent |
|----------|-----------------|
| 질문 → 답변 텍스트 | 케이스 → **구조화된 필드** → **파일** |
| 문단 retrieval | **유사 케이스** retrieval |
| hallucination 허용 | 금액·날짜·이름 **오류 불가** |

→ **스키마 + 규칙 + 유사 케이스 + LLM(제한)** 조합 필요.

---

## Phase 0: 준비 ✅

- [x] form-fill-agent, template-learn, form-fill, case-retrieval, document-render 스킬
- [x] form-fill-agent 서브에이전트
- [x] AGENTS.md North Star 정의

---

## Phase 1: 데이터 & 양식 표준 (1주)

### 목표
학습·렌더링 가능한 **placeholder DOCX** 확보.

### 작업
1. 대표 양식 1종 선정 (예: 용역 계약서)
2. 빈 양식: `{{party_a_name}}`, `{{contract_amount}}` 등 field_id 삽입
3. 완성본 3–5건: `data/examples/contract_service/`
4. `input.json` 예시 2건: `data/cases/`

### 성공 기준
- [ ] docxtpl로 완성본 1건 수동 render 재현 가능
- [ ] field_id 목록 문서화

---

## Phase 2: Template Learn MVP (1–2주)

### 목표
`data/schemas/contract_service.schema.json` 생성.

### 구현
```
src/document_ai/learn/
├── schema.py          # Field, Schema models
├── docx_extractor.py  # placeholder / table / heading
└── cli.py             # python -m document_ai.learn --template ...
```

### 전략
- **MVP**: placeholder `{{id}}` 파싱만 (diff 학습 생략)
- **v2**: 빈 양식 vs 완성본 diff로 필드 자동 발견

### 성공 기준
- [ ] schema.json에 모든 placeholder 필드 포함
- [ ] pytest: extractor unit tests

---

## Phase 3: Render + Fill (1주)

### 목표
`input.json` → `output.docx` (retrieval 없이).

### 구현
```
src/document_ai/
├── fill/engine.py     # facts → field_values, rules
├── render/docx.py     # docxtpl
└── cli.py             # python -m document_ai generate --case ...
```

### 성공 기준
- [ ] CLI: case input → docx
- [ ] required 필드 100% 채움 (facts 제공 시)
- [ ] `golden_fields.jsonl` 5건 exact match

---

## Phase 4: Case Retrieval (1–2주)

### 목표
유사 완성본 few-shot으로 **free_text** 품질 향상.

### 구현
```
src/document_ai/cases/
├── indexer.py         # 완성본 → case record + embed
├── retriever.py       # filter template_id + similarity
└── store.py           # Chroma
```

### 성공 기준
- [ ] Recall@1 ≥ 0.8 (same case_type golden pairs)
- [ ] purpose_clause BLEU/ROUGE vs human ≥ baseline

---

## Phase 5: LLM + API + Eval (2주)

### LLM
- free_text 필드만
- prompt: similar case excerpts + facts
- structured output JSON schema

### API
```
POST /learn/template
POST /generate
POST /validate
```

### Eval
- `golden_fields.jsonl`: field_id, expected_value
- metric: Field F1, Required recall

### Human-in-the-loop
- confidence < 0.7 → needs_review[]

---

## Phase 6: 확장

- PDF AcroForm 양식
- HWP (변환 또는 SDK)
- 다양한 template_id
- Fine-tuning (완성본 100건+)

---

## 리스크

| 리스크 | 완화 |
|--------|------|
| HWP 복잡 | MVP DOCX only |
| 완성본 부족 | placeholder + rules 우선 |
| LLM 금액 오류 | structured 필드 LLM 금지 |
| 양식마다 레이아웃 다름 | template_id별 schema |

---

## 다음 액션 (즉시)

1. **양식 1종 + 완성본 3건** 준비 (사용자)
2. **DOCX placeholder** 변환 또는 신규 작성
3. **Phase 2** `implement-plan`으로 코드 시작

## 참고

- 티켓: `DOC-003-form-fill-agent.md`
- 스킬: `.cursor/skills/form-fill-agent/`
