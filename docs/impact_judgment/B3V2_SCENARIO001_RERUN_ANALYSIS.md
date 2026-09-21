# B3v2 Scenario-001 Rerun Analysis

## 1. Objective

Validate whether B3v2 (domain-independent evidence-based judgment + safe NEW_REQUIREMENT fallback) improves behavior on the **same** unseen inactive-patient CR without forcing PASS or injecting Scenario-001 answers.

## 2. Baseline

| Item | Value |
|------|-------|
| Path | `data/user_scenarios/scenario-001/` |
| Result | **PARTIAL** (FROZEN) |
| B3 | IMPACTED **0**, UNCERTAIN 7, NOT_IMPACTED 8 |
| NEW_REQUIREMENT | flag true; **no structured proposal file** in baseline era |
| B4/B5 | empty (no IMPACTED MDSR) |
| Docs | no CR content patch |

## 3. B3v2 Change

- Evidence-based IMPACTED/NOT/UNCERTAIN + `change_type`
- Zero-IMPACTED fallback requires **relatedish evidence** (not bare Top-k)
- B4/B5 **unchanged**

Commit at setup: see `RUN_MANIFEST.json` → `b3v2_commit_sha`

## 4. Execution Conditions

| Item | Value |
|------|-------|
| Rerun dir | `data/user_scenarios/scenario-001-rerun-b3v2/` |
| Same CR + MDSR/MDDR hashes as baseline | yes |
| Frozen baseline used as gold/input | **no** |
| Expected impact | unused |

## 5. Candidate-level Before/After

Retrieval: **identical** Top-15 (rank, id, document, hybrid scores).

| ID | Doc | Rank | Baseline B3 | B3v2 | change_type |
|----|-----|-----:|-------------|------|-------------|
| Req.203 | MDSR | 1 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING |
| Req.204 | MDSR | 2 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING |
| Req.100 | MDSR | 3 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING |
| Req.11 | MDDR | 4 | UNCERTAIN | NOT_IMPACTED | NOT_RELATED |
| Req.17 | MDDR | 5 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING |
| Req.204 | MDDR | 6 | UNCERTAIN | **IMPACTED** | EXTEND_EXISTING |
| Req.110 | MDSR | 7 | NOT_IMPACTED | **IMPACTED** | EXTEND_EXISTING |
| Req.108 | MDSR | 8 | UNCERTAIN | NOT_IMPACTED | NOT_RELATED (false-friend path) |
| Req.12 | MDSR/MDDR | 11–12 | NOT_IMPACTED | NOT_IMPACTED | NOT_RELATED (`비활성` app lifecycle) |
| … | | | | | see `BEFORE_AFTER_COMPARISON.md` |

Full evidence dumps: `output/trace/impact_judgments.json`, `output/trace/b3_candidate_detail.json`

## 6. Evidence Analysis

- IMPACTED decisions carry `matched_concepts`, `behavioral_overlap`, `cr_spans`/`candidate_spans`, `relevance`, `reason`.
- **Supported PATH A lean:** Req.204 / Req.110 share clinician–patient–dashboard/status facets with CR.
- **Possible over-IMPACTED (FP risk):** Req.100 (auth/registration code + dashboard lookup) — thematic neighbor, weak fit for inactive-patient **policy**.
- **False-friend control:** Req.12 remains NOT_IMPACTED (app `비활성` ≠ patient inactive class).

## 7. NEW_REQUIREMENT behavior

- IMPACTED count = 6 → zero-IMPACTED fallback **correctly did not emit** proposal (`new_requirement_candidates.json` absent).
- PATH B not taken (by design when PATH A IMPACTED exists).
- Safety check vs all-NOT_RELATED over-trigger: N/A here (IMPACTED>0).

## 8. Downstream behavior

| Stage | Result |
|-------|--------|
| B4 | 4× **NEEDS_REVIEW** (Req.203/204/100/110); 0 CONSISTENT / 0 CONFLICT |
| B5 | 4× **NEEDS_REVIEW**; 0 PATCHED |
| DOCX | no intentional CR field patches |

B4 reason pattern: *Insufficient evidence to prove consistency or a hard conflict* — consistency gate still oriented to lockout/UX/policy themes, not inactive-patient rules.

## 9. Regression / unexpected

- Retrieval unchanged (good controlled variable).
- Unexpected: **Req.100 IMPACTED** may be broader than desired.
- Unexpected: MDDR Req.17 IMPACTED (session/task records) — possibly EXTEND-adjacent, needs human review.
- Expected bottleneck shift: empty B4 → **B4 NEEDS_REVIEW wall**.

## 10. Overall evaluation

**PARTIAL** (scenario-level)

Component split:

| Component | Grade |
|-----------|-------|
| Retrieval | PASS (stable) |
| B3 | IMPROVED (PARTIAL) — PATH A entered with evidence |
| NEW_REQUIREMENT | PASS-safety (idle when IMPACTED>0) |
| B4 | FAIL-as-bottleneck for this CR family |
| B5 / Document Output | no CR application |
| Overall | **PARTIAL** |

## 11. Next bottleneck

**B4 Semantic Consistency Gate** (and then B5) — domain-specific / insufficient for non-lockout IMPACTED sets; blocks all auto-patch despite B3 IMPACTED.

Secondary: B3 precision (reduce over-IMPACTED like Req.100) without Scenario-001 hard-codes.

## 12. Recommendation

1. Do **not** retune B3 keywords for this CR.
2. Next development candidate: **domain-independent B4** (or NEEDS_REVIEW → structured human patch plan) using B3 evidence packs.
3. Optional later: B3 precision calibration on synthetic suites (not Scenario-001 gold injection).
4. Keep `scenario-001` freeze forever; use `scenario-001-rerun-b3v2` as B3v2 evidence.

---

**SCENARIO_001_B3V2_PARTIAL**
