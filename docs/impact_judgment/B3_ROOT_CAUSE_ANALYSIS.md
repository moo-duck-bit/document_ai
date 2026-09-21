# B3 Root Cause Analysis (pre-generalization)

> Source: `src/document_ai/impact/impact_judgment.py` as of Scenario-001 PARTIAL freeze.  
> Scenario-001 frozen evidence is **not** modified by this analysis.

## 1. Domain keyword dependencies

Hard-coded theme lexicons drive **all** IMPACTED paths:

| Lexicon | Terms (examples) | Role in judgment |
|---------|------------------|------------------|
| `LOCK_TERMS` | 잠금, 계정 잠금, 로그인 실패, 연속, 임계, 자동 해제, 해제, 제한 | Required for `strong_lock` / UX lock context |
| `AUDIT_TERMS` | 감사, 이벤트, 로그 | `audit_scope_extension`, `strong_audit` |
| `UX_TERMS` | 안내, 사용자, 알림, 재시도, 오류, 에러, 메시지 | `strong_ux` |
| `AUTH_GENERIC` | 인증, 토큰, 세션, 권한, 로그인 | `only_generic` → NOT_IMPACTED |

Additional lockout-only predicates:

- `block_has_lock_policy` — phrases like 로그인 시도 제한, 임계, 계정 잠금, …
- `strong_lock` / `strong_audit` / `strong_ux` — all require CR lock/audit themes
- `audit_scope_extension` — requires **both** CR audit **and** CR lock themes

There is **no** IMPACTED branch that fires on generic CR↔requirement content overlap alone.

## 2. Theme / ID-specific branches

- No hard-coded `Req. 204` / `Req. 110` IDs in B3 (good).
- Soft ID-style coupling: comments and logic shaped around Req.103-style audit-primary and Req.101-style access-primary titles (`"감사" in title`, `"권한"|"접근 통제" in title`).
- Entire decision tree is lockout-family thematic, not requirement-ID-based.

## 3. Decision rules (current)

```
IF strong_lock AND score_ok → IMPACTED
ELIF audit_scope_extension AND score_ok → IMPACTED
ELIF strong_audit AND score_ok → IMPACTED
ELIF strong_ux AND score_ok → IMPACTED
ELIF access_with_incidental_audit → NOT_IMPACTED
ELIF only_generic (auth/audit/ux without lock) → NOT_IMPACTED
ELIF score_ok AND partial lock/audit/ux AND not score_strong → UNCERTAIN
ELIF score_ok AND lock cues incomplete → UNCERTAIN
ELIF not score_ok → NOT_IMPACTED
ELSE → UNCERTAIN  # "Insufficient distinctive theme overlap"
```

Score gates: `score_ok = lex>=0.18 OR sem>=0.08`; `score_strong = lex>=0.28 OR sem>=0.15`.

## 4. Why Req.204 was not IMPACTED (Scenario-001)

Observed: `UNCERTAIN`, reason ≈ *Insufficient distinctive theme overlap; scores lex≈0.10 sem≈0.12*.

Code path:

1. CR (inactive patient / dashboard) has **empty** `cr_themes["lock"]` / useful audit lock pairing.
2. Therefore `strong_lock`, `audit_scope_extension`, `strong_audit`, `strong_ux` are all **false**.
3. `only_generic` / access-primary also false (title is 개별 환자별 조회).
4. `score_ok` may be borderline (sem≈0.12 ≥ 0.08) but without lock/audit/ux **shared** themes, code falls through to final `else` → **UNCERTAIN**.
5. Never reaches IMPACTED despite clear clinical/patient-monitoring overlap.

## 5. Why Req.110 was NOT_IMPACTED

Observed: `NOT_IMPACTED`, reason ≈ *Weak lexical/semantic relevance… no sufficient theme overlap* with lex≈0.10 sem≈0.07.

Code path:

1. Same absence of CR lock themes → no strong_* IMPACTED path.
2. `semantic_score≈0.07 < 0.08` and `lexical≈0.10 < 0.18` → **`not score_ok`**.
3. Hits `elif not score_ok: NOT_IMPACTED` even though retrieval ranked it (hybrid≈0.51) as dashboard/task-record related.

So ranking signal is discarded; B3 re-applies a stricter lex/sem floor **and** requires lockout themes.

## 6. Why Scenario-001 had 0 IMPACTED

Direct path summary:

```
CR has no LOCK_TERMS / lockout-shaped AUDIT+LOCK pairing
  → all IMPACTED predicates false for every Top-k candidate
  → candidates become UNCERTAIN (score_ok without themes) or NOT_IMPACTED (weak scores)
  → IMPACTED count = 0
  → B4 gate_impacted_decisions sees no MDSR IMPACTED → 0 consistency decisions
  → B5 propagation empty
  → runner only sets NEW_REQUIREMENT_CANDIDATE flag (boolean), no structured proposal
```

Root cause class: **domain-specific B3 heuristic**, not retrieval failure alone. Secondary gap: **no structured NEW_REQUIREMENT / NEEDS_REVIEW proposal** when zero IMPACTED.

## 7. Implications for redesign

1. IMPACTED must be reachable via **CR↔candidate evidence** (concepts, behavioral facets, applicability), not only lock/audit/UX lexicons.
2. Lockout lexicons may remain as *optional* specialized boosts, not sole gate.
3. Zero-IMPACTED + high-ranked related candidates must emit structured proposals without writing DOCX.
4. Must not hard-code Scenario-001 answers (비활성, Req.204, Req.110, 3일, dashboard special cases).
