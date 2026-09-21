# B5 Staged Architecture — PR-20 Document Structure Mapping Engine 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR21`  
**범위:** Generic Document Structure Mapping Engine (observational)  
**일자:** 2026-07-27

---

## 1. Objective

Markdown / DOCX / in-memory object를 공통 **Document Model**로 정규화하고,  
섹션별 **Locator Candidate**(rule-based)를 생성한다.

Template Node 선택, Semantic Matching, LLM, Patch, DOCX 수정은 **하지 않는다**.

---

## 2. Scope

**포함:** DocumentModel, Markdown/DOCX/Object 파서, Normalization, Locator Candidates, Validation, Artifacts, Tests.

**제외:** Semantic Locator, Embedding, Vector Search, LLM, Patch 생성, DOCX write, PR-18/19 mutate.

---

## 3. Architecture

```text
Markdown | DOCX | Object
    ↓
DocumentModel (sections / paragraphs / tables / lists)
    ↓
Normalization + Section Tree
    ↓
Locator Candidates (heading_path / section_name / heading_text)
    ↓
Validation + Statistics + Summary
```

패키지: `src/document_ai/document_parser/`

---

## 4. Document Model

- `DocumentModel` — document_type, title, metadata, sections  
- `SectionModel` — heading, heading_level, parent, children, paragraphs, tables, lists  
- `ParagraphModel` / `TableModel` / `ListModel`

---

## 5. Parsers

| 입력 | 모듈 |
|------|------|
| Markdown | `markdown_parser.py` |
| DOCX (논리 구조, read-only) | `docx_parser.py` |
| In-memory object | `normalization.document_from_object` |

---

## 6. Locator Candidates

섹션당 3종 (rule score only):

- `heading_path`
- `section_name`
- `heading_text`

Semantic score / embedding 없음.

---

## 7. Validation

Duplicate Heading, Invalid Hierarchy, Parent Cycle, Empty Section (warning),  
Broken Tree, Invalid Heading Level, Empty Heading.

---

## 8. Artifacts

`output/document_structure/`:

- `document_structure.json`
- `section_tree.json`
- `locator_candidates.json`
- `document_statistics.json`
- `document_validation.json`
- `summary.json`

PR-18/19 template artifact와 분리.

---

## 9. Summary Fields

heading_count, section_count, paragraph_count, table_count, list_count,  
candidate_count, validation_status.

---

## 10. Non-Mutation Guarantees

- PR-18 Template Abstraction Layer 불변  
- PR-19 Generic Template Pack 불변  
- Change Review / DOCX Writer / Legacy / Freeze 불변  
- Feature Flag 기본 OFF  
- Source DOCX hash 불변 (read-only parse)

---

## 11. Known Limitations

- DOCX는 Heading 스타일/outline 기반 논리 구조만 (복잡한 OOXML 레이아웃 미지원)
- Template Node binding 없음 → PR-21 Semantic Locator 대상
- Scenario 실문서 재파싱/재실행 없음 (샘플 fixture 기본)

---

## 12. Next PR Recommendation

**PR-21:** Semantic Locator — Locator Candidate ↔ Generic Template Node matching  
(embedding optional / rule+similarity), still observational until activation policy.

---

## READY Gate

| 조건 | 상태 |
|------|------|
| Document → Normalized Model | ✅ |
| Locator Candidate 생성 | ✅ |
| Markdown / DOCX / Object | ✅ |
| Validation | ✅ |
| Artifacts | ✅ |
| ~35 tests | ✅ (33 test functions, PR-20 suite) |
| Full pytest | ✅ 740 passed |
| PR18/19/Writer/Legacy 불변 | ✅ |
| No semantic/LLM/patch/DOCX write | ✅ |

**Verdict: `READY_FOR_STAGED_B5_PR21`**
