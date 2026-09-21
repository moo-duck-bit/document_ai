# B5 Staged Architecture — PR-18 Template Abstraction Layer 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR19`  
**범위:** Template Abstraction Layer (observational compatibility)  
**일자:** 2026-07-26

---

## 1. Objective

문서 유형에 종속되지 않는 **Template Schema / Node / Registry / Adapter**를 추가하여  
MDSR·MDDR 및 향후 일반 문서에 동일 Pipeline을 연결할 기반을 마련한다.

기존 Patch / Gate / DOCX Writer / Change Review 결과는 **mutate하지 않는다**.

---

## 2. Scope

포함: Schema, Node, Registry, MDSR/MDDR Adapter, artifact mapping, validation, inventory.  
제외: Writer 교체, locator 교체, parsing 변경, LLM template 학습, DOCX write 확대.

---

## 3. Why Template Abstraction

`document + requirement_id + field`를  
`template_id + template_node_id`로 일반화하여 보고서·제안서·매뉴얼 확장 가능.

---

## 4. Architecture

```text
Change Review Package
  → Template Registry (mdsr_v1 / mddr_v1)
  → Template Nodes (deterministic)
  → Artifact Mappings
  → Validation / Inventory / Summary
```

패키지: `src/document_ai/template/`

---

## 5–8. Schemas

- **Template**: template_id, document_type, sections, allowed_operations, operation_capability  
- **Section**: section_id, parent, fields  
- **Field**: field_id, allowed_operations, locator_hints  
- **Node**: `mdsr_v1.requirements.req_105.criteria` (deterministic, no UUID)

---

## 9. Registry

`register_template` / `get_template` / `list_templates` / duplicate·parent·cycle 검증.

---

## 10–11. MDSR / MDDR Adapters

| Template | document_type | fields |
|----------|---------------|--------|
| `mdsr_v1` | software_requirements | title, description, purpose, criteria (+ requirement_id) |
| `mddr_v1` | software_design | title, design_body, design_condition (+ requirement_id) |

존재하지 않는 필드 생성 금지.

---

## 12. Existing Artifact Mapping

Review/Patch/Preview/Gate/Activation → `template_mappings.json`  
status: MAPPED / REVIEW / UNMAPPED / INVALID  
method: explicit_adapter / unknown (no fuzzy)

---

## 13. Operation Capability

예: ADD → `template_allowed=true`, `writer_supported=false`  
Writer 미지원을 Template INVALID로 처리하지 않음.

---

## 14. Validation Invariants

unique ids, parent/cycle, op policy subset, mapped node/template exists,  
document/req/field consistency, one mapping per review item, summary/inventory counts,  
non-mutation, DOCX/Legacy unchanged.

---

## 15. Current Scenario Result

시나리오형: MDDR/MDSR MAPPED, document/req 부재 → UNMAPPED, global **REVIEW**.  
숫자는 artifact 집계 (하드코딩 없음).

---

## 16. Unmapped Handling

MISSING_DOCUMENT / MISSING_REQUIREMENT_ID / UNKNOWN_FIELD → UNMAPPED  
전체 INVALID로 승격하지 않음 (expected fail-safe) → global REVIEW.

---

## 17–18. Negative / Determinism

중복 template/node, parent cycle, invalid op, cross-doc mapping, summary mismatch 탐지.  
동일 입력 → 동일 node/mapping 순서.

---

## 19. Artifacts

| Path |
|------|
| `output/template/template_registry.json` |
| `output/template/template_inventory.json` |
| `output/template/template_nodes.json` |
| `output/template/template_mappings.json` |
| `output/template/template_summary.json` |
| `output/trace/template_validation.json` |

---

## 20. Full pytest

```text
python -m pytest -q
→ 676 passed in 189.47s (0 failed, 0 skipped)
```

PR-17 기준 656; PR-18 template 테스트 +20. 회귀 없음.
---

## 21–24. Compatibility / Freeze

Change Review·Gate·Writer·Feature Flag OFF·Source DOCX·Legacy **불변**.  
Scenario-001 / Trials 미재실행·미수정.

---

## 25. Known Limitations

- MDSR/MDDR adapter만 기본 제공
- locator는 hint만 (Writer 미교체)
- UNMAPPED는 REVIEW 집계 (의도적)

---

## 26. Next PR Recommendation (PR-19)

- 일반 문서 template (report/proposal) 샘플
- heading_path locator hint 실험
- Template → Review UI 표시

**Final judgment:** `READY_FOR_STAGED_B5_PR19`
