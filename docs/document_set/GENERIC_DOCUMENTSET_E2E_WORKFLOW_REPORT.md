# PR-27 Generic Document Set End-to-End Workflow

**최종 판정:** `READY_FOR_GENERIC_DOCUMENTSET_E2E`  
**일자:** 2026-08-01

---

## 1. Objective

사용자가 Document Set 선택 → 업로드 → 변경요청 → Analysis → Review → Approval → Copy Writer → Result 를 **하나의 Workflow**로 수행한다.  
기존 PR18~26 / Controlled Writer / Semantic Locator / Patch Contract는 **재작성하지 않고** Runner·Pilot 중심으로 연결한다.

---

## 2. Workflow States

`CREATED → UPLOADED → ANALYZING → REVIEW_READY → WAITING_APPROVAL → WRITING → VALIDATING → COMPLETED | FAILED`

---

## 3. Document Sets Supported

| Set | Engine |
|-----|--------|
| `ec_sw` | MDTM observational (Thin Core reuse) |
| `general_report` | Generic template section + paragraph token REVIEW |
| `business_proposal` | Generic template section + paragraph token REVIEW |

DocumentDescriptor 재사용. EC-SW는 registry SoT 유지.

---

## 4. Pilot UI Wizard

경로: `/workflow`  
Steps: Document Set → Change Request → Analyze → Review → Approval → Result  
Legacy Pilot (`/`) 불변, 링크만 추가.

---

## 5. Approval

- 항목별 (`item_id`) APPROVED / REJECTED / BLOCKED / PENDING
- 문서별 `document_decisions`
- `approve_all_pending` 지원

---

## 6. Writer Gate

PR-27 기본: Controlled Writer **미호출** (`controlled_writer_invoked=false`).  
승인된 PATCH도 preview/gated만 — 원본·examples 무변경.  
실제 DOCX mutation은 후속 PR에서 Controlled Writer 안전 연동.

---

## 7. Artifacts

`workflow/workflow.json`  
`workflow/workflow_summary.json`  
`workflow/workflow_validation.json`  
`workflow/workflow_timeline.json`

---

## 8. Result Screen Fields

Document / Status / Review / Applied / Rejected / Blocked / Validation / Diff / Download

---

## 9. Tests

`tests/test_workflow_e2e.py` — **30 passed**  
Legacy pilot + document_set thin core regression green.

---

## 10. Validation / Safety

- Desktop 원본 변경 0
- examples MDTM 변경 0
- Legacy pair Pilot 불변
- Controlled Writer 엔진 코드 미수정
- Freeze 경로 미사용

---

## 11. Known Limitations

- Generic packs: REVIEW only (auto PATCH 없음)
- Writer는 gated preview (실 DOCX 반영 후속)
- MDVP 미구현
- LLM/Embedding 없음

---

## 12. Next Step

1. 승인된 EC-SW MDTM PATCH → Controlled Writer(copy-only) 연결  
2. General Report physical patch preview  
3. Wizard UX polish (항목별 체크박스 UI)

**Verdict: `READY_FOR_GENERIC_DOCUMENTSET_E2E`**
