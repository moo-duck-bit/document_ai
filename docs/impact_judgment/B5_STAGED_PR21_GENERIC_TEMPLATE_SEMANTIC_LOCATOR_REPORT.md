# B5 Staged Architecture — PR-21 Generic Template Semantic Locator 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR22`  
**범위:** Generic Template Semantic Locator Engine (observational)  
**일자:** 2026-07-27

---

## 1. Objective

PR-20 Locator Candidate를 PR-19 Generic Template Node에  
Rule + Local Semantic Similarity로 연결하는 Semantic Locator를 구현한다.

Patch / DOCX write / LLM / 원격 Embedding은 하지 않는다.

---

## 2. Architecture

```text
Locator Candidate
  → Template Node Candidates (general_report_v1 / business_proposal_v1)
  → Rule Score + Semantic Score
  → Combined Score (0.65 / 0.35)
  → Ranked Matches
  → MATCHED / REVIEW / UNMAPPED / INVALID
```

패키지: `src/document_ai/semantic_locator/`

---

## 3. Matching

| Layer | Method |
|-------|--------|
| Rule | exact_text, heading_path, heading_text, field_label, section, normalized, parent context |
| Semantic | TF-IDF cosine, char n-gram, token overlap (local only) |
| Fusion | `rule*0.65 + semantic*0.35` |

Thresholds: MATCHED≥0.80 + margin, REVIEW≥0.55, else UNMAPPED.

---

## 4. Sample Results

| Case | Expected | Result |
|------|----------|--------|
| ["방법론","데이터 출처"] | MATCHED → methodology.data_sources | ✅ |
| ["수행 계획","일정"] | MATCHED → execution_plan.schedule | ✅ |
| "결과" (multi-field) | REVIEW | ✅ |
| "일정" (ambiguous) | REVIEW | ✅ |
| "존재하지 않는 섹션" | UNMAPPED | ✅ |

---

## 5. Artifacts

`output/semantic_locator/`:

- semantic_locator_inputs.json
- template_node_candidates.json
- semantic_match_results.json
- ranked_template_matches.json
- semantic_locator_summary.json
- semantic_locator_validation.json

PR-18/19/20 artifact 불변.

---

## 6. Status Distinction

- `validation.status`: schema/invariant (VALID / VALID_WITH_WARNINGS / INVALID)
- `global_semantic_locator_status`: match outcomes (VALID / REVIEW / INVALID)

샘플 fixture에 REVIEW/UNMAPPED가 있어 global=REVIEW, validation=VALID.

---

## 7. Non-Mutation

PR-18, PR-19, PR-20, Change Review, DOCX Writer, Legacy, Freeze 유지.  
Feature Flag OFF. `actual_docx_changed=false`.

---

## 8. Known Limitations

- Transformer / remote embedding 미사용
- MDSR/MDDR requirement mapping 미연결 (의도)
- Patch / Writer bridge는 후속 PR

---

## 9. Next PR Recommendation

**PR-22:** Semantic Match → Observational Patch Intent / Activation Preview bridge  
(여전히 write OFF), 또는 Match Result → Change Review shadow annotation.

---

## READY Gate

| 조건 | 상태 |
|------|------|
| Rule + Semantic + Fusion + Ranking | ✅ |
| 5 sample cases | ✅ |
| Artifacts | ✅ |
| ≥35 tests | ✅ |
| Full pytest | ✅ **777 passed** |
| No LLM / remote / DOCX write | ✅ |

**Verdict: `READY_FOR_STAGED_B5_PR22`**
