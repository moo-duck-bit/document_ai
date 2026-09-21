# Thin Generic Core + EC-SW MDTM Domain Pack POC

**최종 판정:** `READY_FOR_GENERIC_CORE_MDTM_CHANGE_POC`  
**일자:** 2026-08-01

---

## 1. Objective

Document AI v1 이후 첫 확장 스프린트로, 범용 Core를 크게 재작성하지 않고 최소 인터페이스만 추가한 뒤  
첫 Domain Pack으로 **EC-SW MDTM**을 연결한다.

성공 기준:

> MDSR Requirement 변경 요청이 들어왔을 때 MDTM의 관련 추적성 행을 찾아  
> REVIEW 또는 Patch Candidate로 제시할 수 있다.

---

## 2. Why Thin Core

- v1에 Template / Locator / Contract / Writer 범용 계층이 이미 존재
- 문제는 Core 부재가 아니라 **runner/Pilot가 MDSR·MDDR에 고정**된 점
- 풀 관계 그래프·MDVP 등은 범위 밖 → 추상화 함정 방지

---

## 3. Existing v1 Reuse

재사용: PR18~25 observational 스택, Controlled Writer 정책(원본 금지), Pilot UI 골격, scenario runner actual path.

신규: `document_set` Thin Core + `domain_packs.ec_sw` MDTM 경로(관측).

---

## 4. DocumentDescriptor

필드: document_id, short_id, document_type, document_role, source_path, template_id, domain_pack_id, priority, enabled, metadata.

Source of Truth: `data/examples/ec_sw/document_set_registry.json` (8종).

---

## 5. DocumentNode

Req는 특수 사례. MDTM 행은 `TABLE_ROW`.  
`source_identifiers`는 범용 dict (`requirement_ids` / `design_ids` / `test_ids`).

---

## 6. DomainPack Interface

`can_handle` / `index_document` / `locator_hints` / `validate_nodes` / `operation_policy`  
Pack ID: `ec_sw_v1` — 이번 스프린트 **인덱싱 활성은 MDTM만**.

---

## 7. EC-SW Pack

경로: `src/document_ai/domain_packs/ec_sw/`  
지원 문서 타입 등록(MDSR~MDMP), 구현 활성: MDTM.

---

## 8. Registry Integration

`load_document_set_registry` → descriptors + validation.  
Desktop 원본 미사용. `data/examples/ec_sw` 복사본만.

---

## 9. MDTM Structure Analysis

- tables: 4
- primary_table_index: 3 (Req 추적 행렬)
- header 후보 + column role CANDIDATE→body로 CONFIRMED
- Keyword 단독 CONFIRMED 금지

Artifact: `mdtm_structure_analysis.json`

---

## 10. MDTM Row Indexing

- TABLE_ROW 노드 **38행**
- requirement / design / test ID 추출 행: 각 38
- deterministic node_id: `ec_sw_v1.mdtm.table_XX.row_YYYY.<hash>`

---

## 11. Minimal Relation Hints

`TRACE_ROW_CONTAINS` only. implements/verifies 미확정.

---

## 12. Change POC

| Case | Result |
|------|--------|
| Exact Req. 101 | PATCH_CANDIDATE 1 |
| Multi Req. 101+204 | PATCH_CANDIDATE 2 |
| Design only (5.2.2) | REVIEW_REQUIRED 1, PATCH 0 |
| Semantic only | PATCH 0 (UNRELATED) |
| Duplicate rows | PATCH_CANDIDATE + human_review_required |

정책: Exact Req ID만 PATCH_CANDIDATE. 간접/유사도는 REVIEW. 행 전체 교체·ID 생성 금지.

---

## 13. Patch Safety Policy

허용: 단일 셀 UPDATE preview (note/status).  
금지: ADD_ROW, GENERATE_ID, ROW_WIDE_REPLACE, merge edit, document append.  
MDTM Writer 기본 OFF.

---

## 14. Runner Integration

`run_user_scenario(..., document_set_mode="legacy_pair"|"registry"|"explicit_documents")`  
기본 `legacy_pair` → 기존 MDSR/MDDR actual path 불변.  
`registry` 시 observational MDTM artifacts만 추가.

---

## 15. Pilot UI Integration

Run: Document mode 선택 (기본 MDSR/MDDR / experimental registry).  
Review: Document Set / MDTM experimental JSON 섹션.  
Writer: MDTM write OFF.

---

## 16. Artifacts

`output/document_set/` + `output/document_set/ec_sw/`  
(descriptors, summary, validation, structure, nodes, hints, candidates, patch preview, review, index summary/validation)

---

## 17. Test Results

신규 테스트 **41 passed** (`test_document_set_*`, `test_ec_sw_mdtm_*`).

---

## 18. Regression

- Pilot/runner default `legacy_pair` 유지
- Desktop / examples 복사본 Change POC에서 미수정
- PR18~25 재작성 없음

---

## 19. Known Limitations

- MDTM 자동 Writer 미활성
- MDVP/MDDP 등 미연동
- 풀 관계 그래프 없음
- 열 역할은 휴리스틱(CANDIDATE/CONFIRMED) — 문서 변형 시 재검증 필요
- semantic match는 REVIEW/UNRELATED만

---

## 20. Next Step

1. MDTM patch preview → Controlled Writer(copy-only) 제한 연동  
2. MDVP Domain Pack 슬롯 활성화  
3. 일반 보고서 1종으로 Core 재사용 검증  
4. Pilot experimental UX 보강

**Verdict: `READY_FOR_GENERIC_CORE_MDTM_CHANGE_POC`**
