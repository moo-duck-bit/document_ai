# B4 Root Cause Analysis

**Status:** Analysis only — no B4/B5/B3 code changes in this step.  
**Evidence frozen:**

| Artifact | Result | Touch policy |
|----------|--------|--------------|
| `data/user_scenarios/scenario-001/` | PARTIAL | **do not modify** |
| `data/user_scenarios/scenario-001-rerun-b3v2/` | PARTIAL | **do not modify** |
| Trial 1 / Trial 2 freezes | intact | **do not modify** |

Primary code: `src/document_ai/impact/consistency_gate.py`  
Wiring: `src/document_ai/scenario/runner.py` → `gate_impacted_decisions` → B5 `propagation.py`  
Rerun B4 trace: `data/user_scenarios/scenario-001-rerun-b3v2/output/trace/consistency_decisions.json`

---

## 1. Objective

Explain why Scenario-001 B3v2 rerun produced **B3 IMPACTED = 6** but **B4 CONSISTENT = 0 / NEEDS_REVIEW = 4**, without forcing PASS or implementing B4v2 yet.

Answer:

1. What B4 currently decides and with what inputs.
2. Which lockout/auth heuristics dominate CONSISTENT/CONFLICT paths.
3. Exact code path for Scenario-001 MDSR IMPACTED → NEEDS_REVIEW.
4. How B3/B4/B5 responsibilities should separate.
5. Whether B4 can absorb B3 over-breadth (e.g. Req.100).
6. A domain-independent B4 design + test matrix for a later implementation step.

---

## 2. Current B4 Role

**Documented intent** (module docstring):

> IMPACTED from B3 is NOT automatic patch permission.  
> Compare CR intent against existing requirement fields → CONSISTENT | CONFLICT | NEEDS_REVIEW.

**Effective role today:**

A **lockout-family role classifier + theme matcher**:

1. Parse MDSR fields (title / 설명 / 목적 / 기준).
2. Classify requirement **role** ∈ `{ux, audit, policy, other}` using auth/UX/policy keywords.
3. Detect CR themes via `POLICY_TERMS` / `UX_TERMS` / `AUDIT_TERMS` (almost entirely login/lockout/audit lexicon).
4. Fire one of three hard-coded gates (`ux+cr_policy` → CONFLICT; `audit+cr_audit` → CONSISTENT-ish; `policy+cr_policy` → CONSISTENT).
5. Else → **NEEDS_REVIEW** with `allow_auto_patch=False`.

B4 is **not** currently answering the intended question:

> “Can this CR be reflected into this existing Requirement without contradicting its meaning (modify/extend)?”

It answers a narrower Trial-1/2 question:

> “Does this look like lockout-policy vs UX-guidance vs audit-extension?”

---

## 3. Current Decision Logic

### 3.A Inputs

| Input | Source | Used by B4? |
|-------|--------|-------------|
| CR text | `change_request.txt` | Yes — keyword hits only |
| B3 IMPACTED MDSR candidates | `gate_impacted_decisions` filters `judgment==IMPACTED` and `document==MDSR` | Yes — **ID selection only** |
| B3 `matched_concepts` | impact judgment evidence | **No** |
| B3 `behavioral_overlap` | impact judgment evidence | **No** |
| B3 `cr_spans` / `candidate_spans` | impact judgment evidence | **No** |
| B3 `change_type` / confidence | impact judgment | **No** (only string `b3_judgment="IMPACTED"`) |
| Requirement fields | `parse_requirement_fields(block)` → title, description, purpose, criteria | Yes |
| MDDR IMPACTED | B3 may mark MDDR IMPACTED | **Skipped** (`doc != "MDSR"` continue) |
| Design fields | MDDR body | Not in B4 (B5 only) |

`check_consistency(cr_text, block, b3_judgment=...)` never receives the B3 decision dict beyond a label.

### 3.B Outputs

| Status | When (current code) | `allow_auto_patch` |
|--------|---------------------|--------------------|
| **CONFLICT** | `role=="ux"` **and** CR hits `POLICY_TERMS` | False |
| **CONSISTENT** | `role=="audit"` and CR hits `AUDIT_TERMS` and (lock events missing or existing login events); **or** `role=="policy"` and CR hits `POLICY_TERMS` | True when CONSISTENT |
| **NEEDS_REVIEW** | Block missing; audit edge case; **or default fallback** (`role=other` or CR themes empty / mismatched) | False |

Evidence shape today: `conflict_evidence_spans` (even for CONSISTENT), `cr_themes`, parsed `fields`, `proposed_resolution_direction`.  
There is **no** structured `compatible_facets` / `conflicting_facets` / `missing_information` for non-lockout CRs.

### 3.C Decision flowchart (as implemented)

```
B3 IMPACTED MDSR
    → parse fields → role = _role(fields)
    → cr_policy / cr_ux / cr_audit = keyword hits on CR
    → if role==ux and cr_policy: CONFLICT        # Trial-1 Req.6 pattern
    → elif role==audit and cr_audit: CONSISTENT* # lockout audit extension
    → elif role==policy and cr_policy: CONSISTENT # lockout policy family
    → else: NEEDS_REVIEW                         # Scenario-001 path
```

\* audit path can theoretically return NEEDS_REVIEW if neither lock-missing nor existing-events; rare.

---

## 4. Domain-specific Heuristics

Confirmed lockout / auth / security-shaped constants and branches:

| Location | Heuristic |
|----------|-----------|
| `POLICY_TERMS` | 계정 잠금, 잠금, 자동 해제, 관리자 승인, 임계, 연속 로그인 실패, 로그인 시도 제한 |
| `UX_TERMS` | 사용자, 안내, 알림, 재시도, 에러, 오류, 메시지 |
| `AUDIT_TERMS` | 감사, 감사 기록, 감사기록, 이벤트 |
| `_role` | title “감사” → audit; 안내/에러/오류 → ux; 요청 과다/IP 차단/임계/차단/제한 정책 → policy; else POLICY_TERMS in body → policy; else **other** |
| CONFLICT evidence spans | Hard-coded CR span about “연속 로그인 실패 시 계정을 잠그고…” |
| AUDIT CONSISTENT evidence | Hard-coded CR span about login fail / lock / unlock audit events |
| POLICY CONSISTENT evidence | Hard-coded CR span about consecutive-failure account lock |
| Reasons / resolutions | Explicit “lockout-policy”, “Trial-1 internal semantic inconsistency”, “DoS/IP controls” |
| Tests `test_b4_b5_consistency_propagation.py` | All positive cases use Trial-2 lockout CR + Req.6/103/105 |

**Conclusion:** CONSISTENT and CONFLICT are reachable almost exclusively on **lockout-family** CR + role pairs. Non-lockout CRs systematically fall through to NEEDS_REVIEW.

Related (B5, out of scope to fix now): `_design_aligns` in `propagation.py` also uses 감사 / 안내·에러 / 잠금·임계 / 로그인 theme pairs — same family bias for downstream.

---

## 5. Scenario-001 B3v2 Failure Path

### CR (inactive patient — non-auth)

```
최근 3일 동안 과제 수행 기록이 없는 환자를 비활성 환자로 분류하고,
의료진이 웹 대시보드에서 해당 환자를 쉽게 식별할 수 있도록 별도로 표시한다.
비활성 상태는 환자의 최근 과제 수행 기록을 기준으로 자동 갱신되어야 한다.
```

### Theme extraction on this CR

| Theme bag | Hits |
|-----------|------|
| `POLICY_TERMS` | **[]** |
| `UX_TERMS` | **[]** (CR uses 의료진/환자/대시보드 — not 사용자/안내/에러/…) |
| `AUDIT_TERMS` | **[]** |

Therefore **none** of the three specialized gates can fire, regardless of how strong B3 evidence is.

### Per-candidate role

All four gated MDSR IMPACTED classify as `role=other` (clinical/dashboard titles do not match ux/audit/policy keyword rules).

Trace confirmation (`consistency_decisions.json`):

```text
reason: "Insufficient evidence to prove consistency or a hard conflict; defer to review."
note:  "role=other; insufficient distinctive alignment"
cr_themes: policy=[], ux=[], audit=[], role=["other"]
allow_auto_patch: false
```

×4 for Req.203, Req.204, Req.100, Req.110.

### Downstream

- B5: `NEEDS_REVIEW` / no PATCH because B4 ≠ CONSISTENT.
- Document output: CR semantics not applied.
- Overall scenario: remains **PARTIAL** (B3 improved; end-to-end blocked at B4).

This is **not** “B4 carefully reviewed inactive-patient consistency and deferred.”  
It is **“B4 has no non-lockout decision procedure.”**

---

## 6. Candidate-level Analysis

| Candidate | B3 judgment | B4 result | Direct code condition | Missing evidence used | Reason |
|-----------|-------------|-----------|----------------------|------------------------|--------|
| Req.204 | IMPACTED (EXTEND_EXISTING) | NEEDS_REVIEW | Fallback after role≠{ux,audit,policy} path match; `cr_policy/ux/audit` empty | B3 concepts/facets/spans **ignored**; no facet compatibility check | Patient monitoring / recent activity Req — thematic fit for inactive status display, but B4 cannot express CONSISTENT without lockout themes |
| Req.110 | IMPACTED (EXTEND_EXISTING) | NEEDS_REVIEW | Same fallback (`role=other`) | Same | Dashboard API for attendance/performance records — plausible extend for inactive derived from task records; B4 idle |
| Req.203 | IMPACTED (EXTEND_EXISTING) | NEEDS_REVIEW | Same fallback | Same | Patient registration/list management — weaker ownership of “inactive class”; should ideally be CONFLICT or NEEDS_REVIEW **with scope reason**, not generic insufficient-evidence |
| Req.100 | IMPACTED (EXTEND_EXISTING) | NEEDS_REVIEW | Same fallback | Same | Auth-code / registration code — **thematic neighbor / likely B3 FP**; B4 correctly refuses auto-patch but for the **wrong reason** (no lexicon), not responsibility contradiction |

### What B4 inspects vs what it should

| Question | Current B4 | Ideal B4 |
|----------|------------|----------|
| Uses B3 evidence? | No | Yes (as prior, not as rubber stamp) |
| Uses matched_concepts / behavioral_overlap? | No | Yes — compatibility / conflict facets |
| Uses CR/candidate spans? | Only hard-coded lockout example spans | Yes — actual CR vs field spans |
| Fields examined | title/purpose/description/criteria for **role keywords** | Same fields for **responsibility / contradiction / missing info** |
| Semantic consistency vs patchability | Collapses “no lockout theme match” → defer | Separate: consistent-to-extend vs conflict vs insufficient info |
| Confidence alone? | N/A (keyword gates) | Must remain evidence-first (do not gate on confidence alone) |

---

## 7. B3 / B4 / B5 Responsibility Separation

| Stage | Intended question | Current behavior | Overlap / gap |
|-------|-------------------|------------------|---------------|
| **B3** | Is this Req an impacted **candidate** for the CR? | Evidence-based IMPACTED / NOT / UNCERTAIN (B3v2) | OK after B3v2 |
| **B4** | Can CR be **consistently** modify/extend **within** this Req’s meaning? | Lockout role×theme gates; else NEEDS_REVIEW | **Gap:** no domain-independent consistency; **does not** reuse B3 evidence; **does not** truly re-score relevance (good), but also does not judge compatibility |
| **B5** | **Which fields / how** to patch (MDSR→MDDR)? | Requires B4 CONSISTENT + design alignment heuristics (still lockout-leaning) | B4’s `allow_auto_patch` + `proposed_resolution_direction` partially pre-decides patch policy (B5 territory bleed) |

### Explicit overlaps / underlaps

1. **B4 does not re-do B3 relevance ranking** — good separation of *selection* vs *gate*.
2. **B4 does not consume B3 evidence** — underlap; forces B4 to rediscover CR–Req relationship via a different (lockout) lexicon → fails open to NEEDS_REVIEW.
3. **B4 `proposed_resolution_direction` + `allow_auto_patch`** — bleeds into B5 patch permission; acceptable as a gate flag, but resolution text is lockout-specific.
4. **B5 design alignment** — still auth/lockout theme pairs; even after B4v2, B5 may remain next bottleneck for non-lockout CRs (document only; do not fix now).

---

## 8. Root Cause

**Primary root cause**

B4 CONSISTENT/CONFLICT decision procedures are **domain-specific lockout/auth role×theme matchers** built for Trial-1 (Req.6 CONFLICT) and Trial-2 (Req.103/105 CONSISTENT). They do not implement evidence-based consistency for arbitrary CR semantics.

**Mechanism on Scenario-001**

1. Inactive-patient CR hits **zero** POLICY/UX/AUDIT term bags.
2. Clinical MDSR titles map to **role=other**.
3. Specialized gates never run.
4. Universal fallback → **NEEDS_REVIEW** × all IMPACTED MDSR.
5. B5/document patch cannot proceed → Overall stays PARTIAL despite B3 improvement.

**Secondary causes**

- B3 evidence pipeline is discarded at B4 boundary.
- B4 only gates MDSR; MDDR IMPACTED never get consistency records.
- Tests encode lockout success criteria only → no regression pressure for non-lockout CONSISTENT/CONFLICT.
- Generic NEEDS_REVIEW reason hides the difference between “true ambiguity”, “safe extend”, and “responsibility conflict” (Req.100 vs Req.204).

**Not the root cause**

- Retrieval drift (identical to baseline).
- B3 returning zero IMPACTED (fixed in B3v2).
- NEW_REQUIREMENT fallback (correctly idle when IMPACTED>0).
- Scenario-001-specific missing hard-codes (problem is opposite: lockout hard-codes dominate).

---

## 9. Domain-independent B4 Design Proposal

### 9.1 Redefined question

> Given CR + one IMPACTED requirement, can we modify/extend this requirement **without contradicting** its existing responsibility, actors, objects, conditions, and constraints?

### 9.2 Proposed judgment elements (analysis only)

| Element | CONSISTENT lean | CONFLICT lean | NEEDS_REVIEW lean |
|---------|-----------------|---------------|-------------------|
| Responsibility compatibility | Same owner capability (monitor / classify / expose data) | Different owner (registration code vs inactive policy) | Unclear owner |
| Actor compatibility | Shared actors (의료진, 환자) | Incompatible actor obligations | Missing actor in Req |
| Action compatibility | View/classify/update status fits | Replace unrelated action | Ambiguous |
| Object compatibility | Patient activity / records | Auth token / signup code as primary object | Partial |
| Condition compatibility | Time/window/record-based conditions align | Contradictory thresholds already specified | CR condition not mappable |
| Constraint compatibility | No hard negation of CR | Explicit exclusion | Constraints silent |
| Scope | In-scope extend | Out-of-scope neighbor | Borderline |
| Contradiction risk | Low | High | Medium / unknown |
| Missing information | — | — | Cannot decide safely |

### 9.3 Proposed output schema

```json
{
  "candidate": "Req. 204",
  "document": "MDSR",
  "consistency": "CONSISTENT | CONFLICT | NEEDS_REVIEW",
  "evidence": {
    "compatible_facets": ["actor", "object", "output"],
    "conflicting_facets": [],
    "missing_information": ["explicit inactive-class definition in criteria"],
    "cr_spans": ["..."],
    "candidate_spans": ["..."],
    "b3_prior": {
      "change_type": "EXTEND_EXISTING",
      "matched_concepts": [],
      "behavioral_overlap": {}
    }
  },
  "reason": "Human-readable, non-domain-hardcoded explanation",
  "confidence": 0.0,
  "allow_auto_patch": false
}
```

**Rules:**

- `confidence` is informational — **never** sole CONSISTENT trigger.
- Prefer structured facet evidence over keyword family bags.
- Reuse B3 spans/concepts as **priors**; B4 must still find field-level compatibility/conflict.
- Scenario-001 Req IDs must not appear in code.
- Preserve Trial-1 property: UX-primary vs policy-body conflict remains expressible as **facet contradiction**, not only lockout keywords.

### 9.4 Mapping expected Scenario-001 behavior (illustrative, not gold labels)

| Candidate | Plausible B4v2 | Why (analysis) |
|-----------|----------------|----------------|
| Req.204 | CONSISTENT or NEEDS_REVIEW (extend) | Monitoring recent activity / status — responsibility family match |
| Req.110 | CONSISTENT or NEEDS_REVIEW (extend) | API supplies performance records used to derive inactive |
| Req.203 | NEEDS_REVIEW or CONFLICT | Registration/list mgmt — weak ownership of inactive class |
| Req.100 | CONFLICT or NEEDS_REVIEW | Auth-code lifecycle — thematic neighbor; B4 should **filter** B3 over-breadth |

B4 **should** be able to catch B3 false positives via responsibility conflict — that is an intended defense layer, not a reason to retune B3 in this phase.

### 9.5 Interaction with PATH A / PATH B

- PATH A: IMPACTED + B4 CONSISTENT → B5 may patch.
- PATH A soft: IMPACTED + B4 NEEDS_REVIEW → human review (acceptable).
- PATH A hard stop: IMPACTED + B4 CONFLICT → no silent patch (keep Trial-1 safety).
- PATH B: zero safely IMPACTED / or all CONFLICT+out-of-scope → NEW_REQUIREMENT proposal (already B3-side); B4v2 should not invent Req IDs.

---

## 10. Test Matrix (design only — no tests written this step)

| Case | Setup intent | Expected B4 | Notes |
|------|--------------|-------------|-------|
| **A** | Clear in-scope modification of existing responsibility | CONSISTENT | Evidence: compatible facets + no conflicting constraints |
| **B** | Natural scope extension | CONSISTENT **or** NEEDS_REVIEW | Prefer NEEDS_REVIEW if criteria silent on new condition |
| **C** | Related but meaning conflict (e.g. UX vs policy under same id) | CONFLICT | Must still catch Trial-1 Req.6-style without requiring only lockout lexicon long-term |
| **D** | B3 FP / thematic neighbor (Req.100-like) | CONFLICT **or** NEEDS_REVIEW | Defense layer for over-breadth; `allow_auto_patch=False` |
| **E** | Insufficient information | NEEDS_REVIEW | Explicit `missing_information` |
| **F** | Near-identical responsibility already | CONSISTENT | High compatible facets; low contradiction |

**Regression anchors (must not break):**

- Trial-2 lockout: Req.6 CONFLICT; Req.103/105 CONSISTENT (behavior preserved via general contradiction/extension rules, not Req-ID hardcode).
- Scenario-001 freeze artifacts untouched; future validation via **new** rerun dirs only.

**Anti-goals for tests:**

- No Scenario-001 Req.204/110 special-case asserts in production code.
- No “contains 비활성 환자” keyword → CONSISTENT shortcuts.

---

## 11. Risks

| Risk | Detail |
|------|--------|
| Over-eager CONSISTENT | Non-lockout CRs auto-patch wrong Req → document corruption; mitigate with strict contradiction + missing-info defaults to NEEDS_REVIEW |
| Breaking Trial-1/2 | Replacing keyword gates without equivalent facet rules could flip Req.6 → CONSISTENT |
| Ignoring B3 evidence forever | Keeps B4 blind; opposite risk: rubber-stamping B3 IMPACTED as CONSISTENT |
| Confidence misuse | Must not promote CONSISTENT on score alone |
| B5 still lockout-shaped | Even perfect B4v2 may leave Scenario-001 PARTIAL until B5 design alignment generalizes — expect possible next bottleneck |
| Role collapse | Inventing new domain taxonomies (clinical vs auth) recreates lockout problem under new names — prefer facet compatibility over domain labels |
| Scope creep | Implementing B5/B3 retunes in same PR as B4v2 — **out of recommended scope** |

---

## 12. Recommended Implementation Scope

**In scope for a future B4v2 implementation step:**

1. Refactor `consistency_gate.py` decision core off lockout-only CONSISTENT/CONFLICT gates (keep parse_fields / decision dataclass evolution).
2. Pass B3 decision evidence into B4 (read-only prior).
3. Emit structured evidence (`compatible_facets`, `conflicting_facets`, `missing_information`, real spans).
4. Unit tests for Cases A–F + Trial-1/2 regression (new tests; do not rewrite frozen scenario artifacts).
5. Runner wiring only as needed for richer trace JSON.

**Out of scope (explicit):**

- B3 retuning / Req.204·110 special cases
- B5 / propagation / `_design_aligns` rewrite (follow-up)
- Dense embedding / XXCS / form-fill
- Editing `scenario-001` or `scenario-001-rerun-b3v2` freezes
- Forcing Scenario-001 Overall → PASS in the same change

**Suggested sequencing after B4v2:**

1. Implement B4v2 + synthetic tests.
2. New rerun dir (e.g. `scenario-001-rerun-b4v2/`) — never overwrite prior PARTIAL evidence.
3. If CONSISTENT appears but patches still fail → analyze B5 as next root cause (same discipline).

---

## Verdict gate checklist

| READY criterion | Met? |
|-----------------|------|
| B4 failure path clearly explained | Yes — fallback `role=other` + empty CR theme bags |
| Domain-specific dependency confirmed | Yes — POLICY/UX/AUDIT + role gates |
| B3/B4/B5 separation clarified | Yes — underlap at evidence handoff; B5 next risk |
| Domain-independent design proposal exists | Yes — §9 |
| Implementable without Scenario-001 hard-codes | Yes — facet/evidence based |

**Final judgment: READY_TO_IMPLEMENT_B4V2**
