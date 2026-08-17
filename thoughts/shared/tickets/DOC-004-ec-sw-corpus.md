---
title: "[DOC-004] EC-SW Mindrium 코퍼스 등록 및 분석"
type: "Feature"
priority: "High"
status: "In Progress"
assignee: "@hsh71"
---

## 완료

- [x] Desktop → `data/examples/ec_sw/` 복사
- [x] 빈 양식 MDSR/MDDR import + diff
- [x] **Step 1** `export-schema` → `spec_requirements.schema.json`, `spec_design.schema.json`
- [x] **Step 2** `xxcs-skeleton` → `template_xxcs_skeleton.docx` (175 cells cleared)
- [x] **Step 3** `generate` → `data/cases/mindrium_xa/output_mdsr.docx`
- [x] `src/document_ai/` + pytest 4 passed

## 다음

- [ ] Req. N 표 동적 추가 (repeating_entities)
- [ ] MDDR generate
- [ ] XXCS CSV bulk fill
- [ ] case-intake 채팅 CLI
