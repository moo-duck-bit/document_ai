# B5 Staged Architecture — PR-19 Generic Document Template Pack 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR20`  
**범위:** Generic Document Template Pack (observational / template-definition)  
**일자:** 2026-07-27

---

## 1. Objective

의료기기·요구사항 문서에 종속되지 않는 **범용 문서 Template Pack**을 추가한다.

- `general_report_v1` (일반 보고서)
- `business_proposal_v1` (사업 제안서)

`requirement_id` 없이도 Template Node를 구성하고, 기존 Registry/Validation을 재사용한다.  
실제 DOCX/Markdown 파싱·쓰기, Writer 교체, Scenario 재실행은 하지 않는다.

---

## 2. Scope

**포함:** Generic Template 정의, Section/Field, 정적 Node, 샘플 문서, Explicit Mapping, Registry 통합(격리 artifact), Validation, Tests, Report.

**제외:** DOCX/Markdown parsing, LLM template 추론, Writer 교체, 실제 write, Human Approval, Legacy cutover, MDSR/MDDR Adapter 구조 변경(단 missing-reason 집계 보강).

---

## 3. General-document Motivation

PR-18 Node 예: `mdsr_v1.requirements.req_105.criteria`  
범용 Node 예: `general_report_v1.methodology.data_sources`

보고서·제안서는 section/field 중심이며 requirement_id가 없다.  
향후 Markdown/DOCX Mapping Engine의 기준 Template로 사용한다.

---

## 4. Architecture

```text
Template Abstraction (PR-18: mdsr_v1 / mddr_v1)
  → Generic Template Registry (isolated)
  → Generic Template Nodes
  → Sample Document Instances
  → Generic Mapping (explicit only)
  → Generic Validation
  → Generic Artifacts (separate JSON)
```

모듈:

- `src/document_ai/template/generic_templates.py`
- `src/document_ai/template/sample_documents.py`
- `src/document_ai/template/generic_mapping.py`

Runner는 PR-18 이후 Generic Pack을 호출하며, 실패 시에도 PR-18 artifact를 mutate하지 않는다.

---

## 5. General Report Template

| 항목 | 값 |
|------|-----|
| template_id | `general_report_v1` |
| document_type | `general_report` |
| display_name | 일반 보고서 |

Sections: document, executive_summary, background, objectives, methodology, results, discussion, conclusion, references, appendix.

주요 fields: title/body, approach, data_sources, limitations, key_findings, tables, recommendations, entries, attachments.

---

## 6. Business Proposal Template

| 항목 | 값 |
|------|-----|
| template_id | `business_proposal_v1` |
| document_type | `business_proposal` |
| display_name | 사업 제안서 |

Sections: document, overview, problem_statement, proposed_solution, scope, execution_plan, schedule, budget, expected_outcomes, risks, organization, appendix.

주요 fields: differentiators, phases, deliverables, schedule, budget summary/items/assumptions, risks items/mitigation.

---

## 7. Generic Section Schema

기존 `SectionDefinition` 재사용.  
`parent_section_id`, `order`, `fields` 기반. requirement section 타입 불필요.

---

## 8. Generic Field Schema

추가 field_type 예: body, summary, key_findings, recommendations, approach, data_sources, limitations, table, schedule, budget_items, references, attachments, list_items, custom.

content_type 예: text, list, table, reference, attachment, currency.

기존 MDSR/MDDR validation 결과는 변하지 않도록 enum 강제 없이 문자열로 허용.

---

## 9. Generic Template Nodes

형식: `{template_id}.{section_id}.{field_id}`

- `source_requirement_id=null` 허용
- null requirement로 UNMAPPED/INVALID 처리하지 않음
- document / section / field 계층 parent_node_id

---

## 10. Locator Hints

strategies: heading_path, field_label, exact_text  
힌트 필드: heading_path, heading_text, section_id, table_header, field_label, exact_text  

이번 PR은 힌트 정의만 — 실제 문서 검색 없음.

---

## 11. Sample Documents

| sample_document_id | template |
|--------------------|----------|
| sample_general_report_001 | general_report_v1 |
| sample_business_proposal_001 | business_proposal_v1 |

Scenario-001 / Trials와 분리된 fixture.

---

## 12. Generic Mapping

method: `explicit_section_field` only (semantic/fuzzy 금지).

샘플:

- GCH-001 → `general_report_v1.methodology.data_sources` (MAPPED)
- GCH-002 → `business_proposal_v1.execution_plan.schedule` (MAPPED)
- unknown section/field → UNMAPPED
- report item → proposal template → INVALID (TEMPLATE_MISMATCH)

---

## 13. Requirement-ID Optionality

| Template family | requirement_id |
|-----------------|----------------|
| mdsr_v1 / mddr_v1 | 필수 (없으면 UNMAPPED + MISSING_REQUIREMENT_ID) |
| generic_* | 선택 (null 정상) |

---

## 14. Operation Capability

Template 기본: ADD, UPDATE, REPLACE, CONSTRAIN, DELETE, LINK  
Field별 제한 가능 (title: UPDATE/REPLACE, references: ADD/UPDATE/DELETE/LINK, budget: ADD/UPDATE/REPLACE/DELETE).

Writer capability와 분리 — Writer 미지원 op는 Template INVALID가 아님.

---

## 15. Missing Reason Aggregation

MDSR/MDDR mapping은 독립 원인을 모두 기록.

예: `document=""` + `requirement_id=null` →  
`[MISSING_DOCUMENT, MISSING_REQUIREMENT_ID]` (+ MISSING_FIELD if applicable).

범용 문서는 requirement_id 누락을 이유로 UNMAPPED하지 않음.

---

## 16. Validation Invariants

unique ids, parent refs/cycles, deterministic node ids, ops subset,  
requirement_id optional for generic, mdsr/mddr rule unchanged,  
mapped template/node exists, section/field consistent, one mapping per sample change,  
summary counts, deterministic output, PR-18/Change Review/DOCX/Legacy non-mutation.

---

## 17. Negative Tests

duplicate template/node, invalid/circular parent, invalid op,  
missing node ref, template mismatch, section/field mismatch,  
duplicate sample mapping, summary tamper, null-req wrongly INVALID.

---

## 18. Determinism

동일 입력 → 동일 node id / mapping 순서 / JSON (sort_keys).

---

## 19. Artifacts

| Path |
|------|
| `output/template/generic_template_registry.json` |
| `output/template/generic_template_nodes.json` |
| `output/template/generic_sample_documents.json` |
| `output/template/generic_template_mappings.json` |
| `output/template/generic_template_summary.json` |
| `output/trace/generic_template_validation.json` |

PR-18 artifact(`template_registry.json` 등)는 별도 유지.

---

## 20. Current Scenario Compatibility

- Change Review READY/REVIEW/BLOCKED 수 불변
- Template Mapping 11 MAPPED / 1 UNMAPPED 패턴 유지
- global_template_status=REVIEW 가능
- Feature Flag OFF, DOCX write 0, Legacy, Freeze 유지
- Scenario-001 / Trials 미재실행·미수정

---

## 21. Full pytest

`python -m pytest -q` — **707 passed**, 0 failed (기존 676 + PR-19 신규).

---

## 22. DOCX Non-Mutation

Generic Pack은 DOCX를 열거나 쓰지 않음. `actual_docx_changed=false`.

---

## 23. Legacy Compatibility

Legacy generation / B5c actual path 불변. `actual_generation_changed=false`.

---

## 24. Freeze

`data/user_scenarios/scenario-001`, `data/trials/trial-001-*`, `trial-002-*` 미수정.

---

## 25. Known Limitations

- Locator 실제 검색 미구현
- Markdown/DOCX structure mapping engine 미연결
- Generic Pack registry는 PR-18과 파일 분리 (통합 registry merge는 후속 가능)
- 샘플 mapping에 INVALID 케이스가 포함되어 `global_generic_template_status=INVALID` (의도된 negative fixture)

---

## 26. Next PR Recommendation

**PR-20 후보:** Generic Template ↔ Markdown/DOCX Structure Mapping Engine (heading_path 기반 observational locator), 또는 Change Item → Generic Node runtime bridge (Scenario 비재실행).

---

## READY Gate

| 조건 | 상태 |
|------|------|
| general_report_v1 | ✅ |
| business_proposal_v1 | ✅ |
| requirement_id optional nodes | ✅ |
| deterministic generic nodes | ✅ |
| sample documents | ✅ |
| generic mapping | ✅ |
| missing reason aggregation | ✅ |
| existing template layer non-mutation | ✅ |
| pytest PASS | ✅ (실행 확인) |
| DOCX / Legacy / Freeze | ✅ |

**Verdict: `READY_FOR_STAGED_B5_PR20`**
