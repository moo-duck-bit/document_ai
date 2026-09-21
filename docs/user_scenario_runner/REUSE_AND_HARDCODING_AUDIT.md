# User Scenario Runner — Reuse & Hard-coding Audit

> Written before harness implementation.  
> Trial 1 / Trial 2 frozen evidence must not be modified.

## 1. Reusable production modules (Trial 2 B1–B5)

| Stage | Module | Reuse for runner |
|-------|--------|------------------|
| B1 Index | `document_ai.impact.semantic_index` | **Yes** — MDSR/MDDR indexing from arbitrary paths |
| B2 Lexical | `document_ai.impact.semantic_retrieve` | **Yes** |
| B2 Hybrid | `document_ai.impact.semantic_hybrid_retrieve` | **Yes** — TF-IDF semantic channel |
| B3 Judgment | `document_ai.impact.impact_judgment` | **Yes with limits** — theme heuristics (auth/lock/audit/UX) |
| B4 Gate | `document_ai.impact.consistency_gate` | **Yes with limits** — role = ux/policy/audit |
| B5 Propagate | `document_ai.impact.propagation` | **Partial** — plan/apply OK; patch *text* was Req-ID hard-coded |
| Patch primitives | `preserve_patch.patch_mdsr_description_only`, `render.design_items.patch_mddr_design_items` | **Yes** |

Trial scripts (`scripts/run_trial002_*.py`) are **not** production APIs — they hardcode trial paths, FOCUS IDs, and post-hoc `expected_impact` evaluation only.

## 2. Trial-specific hard-coding found

### Blocks unseen-scenario auto-patch (must soften for runner)

| Location | Issue |
|----------|--------|
| `propagation.proposed_mdsr_description` | Only generates text for **Req. 105 / Req. 103** |
| `propagation.proposed_mddr_design_description` | Same ID hard-coding; lockout-specific Korean sentences |
| `consistency_gate` resolution strings | Mentions “map to **Req.105**”; evidence spans paste Trial-2 CR fragments |

### Domain heuristics (keep as limitation; not rewritten wholesale)

| Location | Issue |
|----------|--------|
| `impact_judgment.LOCK_TERMS` / audit / UX themes | Tuned for **login lockout** CR family |
| `consistency_gate.POLICY_TERMS` | Lockout/policy vocabulary |
| `semantic_index.DOMAIN_KEYWORDS` | Includes 잠금/감사/인증 etc. (search bias, not decision force) |

### Evaluation-only (OK if runner never calls)

| Location | Issue |
|----------|--------|
| `scripts/run_trial002_*` | Loads `expected/expected_impact.json` for **post-hoc** FP tables only |
| FOCUS_IDS = Req.6/103/105 | Trial scripts only |

### No expected_impact in library decision path

Library modules under `src/document_ai/impact/{semantic_*,impact_judgment,consistency_gate,propagation}.py` document and implement **no** expected_impact reads for ranking/judgment/patch. Runner must not import trial post-hoc helpers that load expected files.

### Path hard-coding

- Trial scripts: `data/trials/trial-002-lockout-multireq/...`
- No Mindrium filename required inside index/retrieve libraries (caller supplies paths)

## 3. Generalization needed for User Scenario Runner

1. **Patch text from CR + role**, not from fixed Req IDs (blocker).
2. Orchestrator that takes `(scenario_dir)` → index → hybrid retrieve → B3 → B4 → B5 → review markdown.
3. **NEEDS_REVIEW / NEW_REQUIREMENT_CANDIDATE** when no safe auto-patch target.
4. Never write into `data/trials/trial-001-*` or `trial-002-*`.
5. Copy reference DOCX into `output/documents/`; never overwrite inputs.

## 4. What we will NOT do in this step

- Dense embedding / XXCS / admin mode / Form-fill / new Trial PASS
- Full rewrite of B3/B4 heuristics for all domains
- Fabricating an unseen CR “success story”

## 5. Residual risk after minimal fixes

Unseen CRs outside auth/lockout/audit/UX theme space will often yield **empty or review-only** outcomes. That is intentional safety, not automatic failure of the harness.
