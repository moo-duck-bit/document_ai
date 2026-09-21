# Scenario-001 Evaluation Report (Frozen)

> unseen CR: inactive patient (3-day no task) + dashboard highlight + auto refresh  
> CODE_MODIFIED_DURING_TEST = **NO**  
> overall_result: **PARTIAL**  
> frozen_at: see `FREEZE.json`

## Corpus facts (post-hoc scan, not used by runner)

- `비활성 환자` / `활성 환자`: **0** hits in MDSR/MDDR
- Literal `3일` inactive rule: **0**
- Existing `비활성` mentions = app lifecycle / permission disable / TLS — **not** patient inactive class
- Related existing areas: Req.203 patient mgmt, Req.204 patient lookup, Req.110 dashboard API, Req.108 task/session tracking, Req.200/201 dashboard access (not in Top-15)

## 1. Execution status

`COMPLETED_NEEDS_REVIEW`  
- expected_impact_used: false  
- input hashes unchanged: true  
- MDSR patched IDs: []  
- MDDR patched IDs: []  
- NEW_REQUIREMENT_CANDIDATE: **true**

Note: `updated_MDDR.docx` byte-identical to input; `updated_MDSR.docx` hash differs due to python-docx load/save with zero field patches (no intentional content patch).

## 2–3. Retrieval Top-k + relevance (post-hoc)

| Rank | ID | Doc | hybrid | Post-hoc |
|-----:|----|-----|-------:|----------|
| 1 | Req.203 | MDSR | 1.000 | POSSIBLY_RELEVANT (환자 관리; no inactive rule) |
| 2 | Req.204 | MDSR | 0.671 | **RELEVANT** (의료진 환자 조회/활동 상태) |
| 3 | Req.100 | MDSR | 0.659 | IRRELEVANT (마인드리움 코드/인증 코드; dashboard 단어만) |
| 4 | Req.11 | MDDR | 0.631 | IRRELEVANT (앱 홈 화면) |
| 5 | Req.17 | MDDR | 0.630 | POSSIBLY_RELEVANT (수행 기록; 회기 조건 ≠ 비활성 분류) |
| 6 | Req.204 | MDDR | 0.583 | **RELEVANT** |
| 7 | Req.110 | MDSR | 0.512 | **RELEVANT** (대시보드 수행 기록 API) |
| 8 | Req.108 | MDSR | 0.510 | POSSIBLY_RELEVANT (과제 수행 추적) |
| 9 | Req.16 | MDDR | 0.505 | IRRELEVANT (환자 앱 리포트) |
| 10 | Req.17 | MDSR | 0.410 | POSSIBLY_RELEVANT |
| 11–12 | Req.12 | MDSR/MDDR | ~0.40 | IRRELEVANT (**비활성**=앱 라이프사이클 false hit) |
| 13 | Req.18 | MDDR | 0.397 | IRRELEVANT |
| 14 | Req.2 | MDSR | 0.343 | IRRELEVANT |
| 15 | Req.3 | MDDR | 0.335 | IRRELEVANT |

Lockout/auth domination: **Top-k에 Req.6/103/105 없음**. Req.100은 인증코드로 약한 auth drift. Req.12 `비활성`은 lexical false friend.

## 4. B3 Impact Judgment

| Judgment | Count |
|----------|------:|
| IMPACTED | **0** |
| UNCERTAIN | 7 (203,204,100,11,17,204-MDDR,108) |
| NOT_IMPACTED | 8 |

### False Positive (IMPACTED wrongly)

- **없음** (IMPACTED=0)

### False Negative (should likely be IMPACTED / at least strong UNCERTAIN→review for edit)

- **Req.204** MDSR/MDDR — clinician patient view / activity monitoring  
- **Req.110** MDSR — dashboard attendance/performance API (**system: NOT_IMPACTED**)  
- Possibly **Req.108** — task performance tracking  
- Dashboard shell **Req.200/201** — not retrieved in Top-15 (retrieval miss)

Root pattern: B3 themes are lockout/auth/audit/UX-error; inactive-patient CR shares almost no LOCK/AUDIT terms → everything UNCERTAIN or weak NOT_IMPACTED.

## 5. B4 Consistency

- Decisions: **0** (no MDSR IMPACTED → gate never ran)  
- CONSISTENT/CONFLICT/NEEDS_REVIEW: all 0  
- Existing inactive-patient 3-day rule: **does not exist** in corpus  
- No append conflict created (no patch)  
- NEW_REQUIREMENT_CANDIDATE correctly raised

## 6–7. Actual patches

- MDSR: **none** (MISSING for CR intent)  
- MDDR: **none** (MISSING_PROPAGATION for dashboard display / auto refresh / inactive compute)

Patch classification vs CR goals:

| Needed change | Class |
|---------------|--------|
| Inactive patient definition (3 days) | **MISSING** |
| Dashboard distinct display | **MISSING** |
| Auto refresh from task records | **MISSING** |
| Unrelated destructive edit | none (good) |

## 8–9. FP / FN summary

- FP IMPACTED: none  
- FN impact/retrieval: 204, 110 (+ 200/201 miss); 108 weak FN  
- Lexical FP candidate: Req.12 (비활성≠환자 비활성), Req.100 (대시보드 단어)

## 10. Cross-document inconsistency

- No new MDSR/MDDR semantic conflict introduced (no content patch).  
- Pre-existing: no patient-inactive policy in either doc — CR is greenfield relative to corpus.  
- Output pair does **not** implement CR on either side → consistent emptiness, not a 3-day vs other-window clash.

## 11. Human usability

**Grade: D**  
- updated docs are not a usable draft for this CR (no CR semantics applied).  
- Review artifacts correctly say NEEDS_REVIEW / NEW_REQUIREMENT — useful as a **gate**, not as a draft document.

## 12. Overall

**PARTIAL**

Not PASS because: important related reqs not IMPACTED; core design propagation missing.  
Not pure FAIL because: no wrong auto-patch; no unrelated destructive edit; lockout bias did not dominate Top-k; harness completed with NEW_REQUIREMENT_CANDIDATE; inputs preserved.

## 13. Root cause

1. B3/B4 **domain heuristics locked to auth/lockout/audit/UX-error** → non-auth CR cannot become IMPACTED.  
2. Without IMPACTED, B4/B5 never propose patches → silent under-change (safe but empty).  
3. TF-IDF retrieval finds topical neighbors (환자/대시보드/과제) but cannot compensate for judgment gap.  
4. Feature is largely **new capability** (`비활성 환자` absent) — needs new-req or explicit domain model, not lockout-style append.

## 14. System limits observed

- Cross-domain generalization of B3/B4  
- No patient-status / clinical-ops theme pack  
- Zero-IMPACTED ⇒ empty consistency/propagation traces  
- MDSR output non-byte-identical after empty save  
- NEW_REQUIREMENT flagged but not structured into a draft requirement block

## 15. Next fix priority (do not implement in this freeze)

1. Domain-agnostic or pluggable B3 themes (or LLM-assisted judgment with evidence)  
2. Escalate high-retrieval + UNCERTAIN to structured NEEDS_REVIEW edit proposals  
3. Stronger NEW_REQUIREMENT_CANDIDATE artifact (fields: rule, UI, auto-update)  
4. Retrieval demotion of false-friend tokens (앱 `비활성` vs 환자 비활성)  
5. Avoid MDSR rewrite-save when patch set empty (byte identity)

## CODE_MODIFIED_DURING_TEST

**NO**
