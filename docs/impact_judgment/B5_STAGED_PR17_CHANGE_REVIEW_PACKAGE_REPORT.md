# B5 Staged Architecture — PR-17 Change Review Package 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR18`  
**범위:** 범용 Change Review Package (observational)  
**일자:** 2026-07-26

---

## 1. Objective

사람이 다음을 빠르게 답할 수 있는 **Change Review Package**를 추가한다.

- 무엇이 / 왜 / 어디가 바뀌었는가?
- 변경 전·후는 무엇인가?
- 실제 문서에 적용되었는가?
- 추가 검토가 필요한가?

문서 생성·수정 로직은 변경하지 않는다.

---

## 2. Scope

의료기기 전용 Audit이 아닌 **범용 문서 검토** 패키지  
(요구사항·기술문서·보고서·제안서·정책·매뉴얼 등).

---

## 3. General-document Design

내부 score/pipeline을 숨기고, 사용자용 label·요약·before/after·적용 상태를 제공한다.  
내부 enum은 metadata에 유지.

---

## 4. Architecture

모듈: `src/document_ai/impact/change_review_package.py`

```text
DOCX Activation Writer / Validation
  → Change Review Package (observational)
  → output/review/* + trace/change_review_validation.json
```

Gate/Writer 재판정·mutate 금지. 오류 시 fail-loud trace, 선행 artifact 유지.

---

## 5. Review Item Schema

`ChangeReviewItem`: ids, document/section/field, change_type(+label), scope,  
source_request, change_reason, before/after, gate/activation,  
review_status, application_status, review_reason_codes, source_trace.

---

## 6. Change Reason Construction

CR / ACU / patch op / activation / gate reason codes만 조합.  
근거 없으면 `MISSING_CHANGE_REASON` + REVIEW. 신규 이유 생성 금지.

---

## 7. Review Status

| Status | 의미 |
|--------|------|
| READY | Gate PASS, 적용 가능 |
| REVIEW | Gate REVIEW / warning / locator / unsupported / missing reason |
| BLOCKED | Gate/Activation BLOCK |
| NOT_APPLIED | (별도 application_status 사용; review는 READY 유지 가능) |

---

## 8. Application Status

`APPLIED` / `NOT_APPLIED` / `SKIPPED` / `BLOCKED` / `FAILED`  
APPLIED는 `write_succeeded=true`만. flag OFF → APPLIED 금지.

예: PASS + flag OFF → `review_status=READY`, `application_status=NOT_APPLIED`.

---

## 9. Before / After Preservation

기존 preview/patch/activation 원문 그대로. 재작성·보완 금지.  
빈 값은 Markdown에서 `(내용 없음)`.

---

## 10. Change Grouping

`atomic_change_id` 기준 group.  
`group_status`: BLOCKED > REVIEW > READY.

---

## 11. Markdown Output

`output/review/change_review.md` — 요약 / 그룹 / before-after code block / metadata.

---

## 12. Validation Invariants

one item per patch, id consistency, before/after preserve, blocked mapping,  
applied only on write success, flag-off never APPLIED, summary/group/markdown 정합, deterministic.

---

## 13. Current Scenario Result

시나리오형 입력(PASS N + BLOCK 1, flag OFF):

- READY = PASS 수, BLOCKED = 1, APPLIED = 0, NOT_APPLIED = PASS 수  
- `global_review_status=BLOCKED`  
숫자는 하드코딩하지 않고 artifact에서 집계.

---

## 14. Negative Tests

BLOCK→READY, flag-off APPLIED, before tamper, id mismatch, summary/group mismatch,  
review_required without reason → validation 탐지.

---

## 15. Determinism

정렬: atomic_change_id → document → requirement_id → field → patch_id.  
동일 입력 → 동일 JSON/Markdown.

---

## 16. Artifacts

| Path |
|------|
| `output/review/change_review.json` |
| `output/review/change_review_summary.json` |
| `output/review/change_review.md` |
| `output/review/before_after.json` |
| `output/review/change_groups.json` |
| `output/trace/change_review_validation.json` |

---

## 17. Full pytest

```text
python -m pytest -q
→ 656 passed in 223.48s (0 failed, 0 skipped)
```

PR-16 기준 633; PR-17 change review 테스트 +23. 회귀 없음.
---

## 18. Compatibility

DOCX Writer / Feature Flag / Policy / Gate / Preview / Realizer / Patch 의미 **불변**.

---

## 19. Freeze

Scenario-001 / Trials 미재실행·미수정.

---

## 20. Known Limitations

- reason은 기존 artifact 조합만 (LLM 재작성 없음)
- change_scope는 field/locator 휴리스틱
- ACU 필드명이 버전에 따라 다를 수 있음 → 다수 키 폴백

---

## 21. Next PR Recommendation (PR-18)

- Review UI / Notion export polish
- dual-write side-by-side viewer
- human approve → flag ON activation handoff

**Final judgment:** `READY_FOR_STAGED_B5_PR18`
