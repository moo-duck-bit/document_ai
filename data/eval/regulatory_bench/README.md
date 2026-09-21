# Small-A regulatory bench

**Decision:** Small-A only (MDSR+MDDR). Form Fill / 9-form / LEDGER full port = later.

## Done for this slice

1. Case packs: `case_000`–`case_005` (CBT-I, HTN, ADHD, Diabetes, Depression, Pain) — T2 value+propagation
2. Synthetic MDSR/MDDR DOCX with **hidden cell IDs**
3. Fingerprints: `fp/originals.sha256`
4. Unified scorer: **μ**, Doc F1, Recall@3, cell F1
5. Runner modes: `demo_safe` | `materialize` | `pipeline` | **`live`** | `artifact_only`
6. **Live adapter:** `compute_impact` on synthetic workdir → map Req./DI → node IDs → copy-only gated write
7. Case factory: `case_factory.bootstrap_factory_cases()` for profile expansion
8. Tests: `tests/test_regulatory_bench_small_a.py`

## Modes

| Mode | Impact source | Patch values | Originals |
|------|---------------|--------------|-----------|
| `demo_safe` | gold | gold | n/a (synthetic fps) |
| `pipeline` | heuristic on hidden IDs | gold | untouched |
| `live` | **`compute_impact`** | rule cell_fill | untouched |
| `materialize` | (writes DOCX) then demo_safe | gold | fingerprints refreshed |

Honest labels: `live` uses real `compute_impact`; patch values from **rule cell_fill** (`patch_values_from=change_request_frequency_rules`); node closure is **document-native** (`closure_source=doc_trace_and_row_colocation`, not gold topology). Gold is used only in `score_case`.

## Commands

```bash
PYTHONPATH=src python -m document_ai.cli regulatory-bench-run \
  --case data/eval/regulatory_bench/case_000 --mode live

PYTHONPATH=src python -m document_ai.cli regulatory-bench-run \
  --case data/eval/regulatory_bench/case_003 --mode pipeline

# Bootstrap more T2 profiles
PYTHONPATH=src python -c "from document_ai.eval.regulatory_bench.case_factory import bootstrap_factory_cases; print(bootstrap_factory_cases())"
```

## μ contract

| Key | Meaning |
|-----|---------|
| `false_patch` | Touched must-not-touch or wrote outside gold impact |
| `unsafe_write` | Activation bypass / write-to-original policy break |
| `original_broken` | Source fingerprint drift |
| `unapproved_write` | Wrote without human approval |

## Next (still Small-A)

- ✅ ~24 T2 cases + rule cell_fill + document-native live closure (PR8)
- Sealed holdout split + Safety-first paper tables over live preds
- Optional LEDGER adapter when real code lands (stub seam ready)
- Optional LLM fill for free_text only (structured fields stay rule/facts)


## Scorecard / consistency stub / ablation (PR6–7)

```bash
PYTHONPATH=src python -m document_ai.cli regulatory-bench-scorecard --modes demo_safe,live
PYTHONPATH=src python -c "from document_ai.eval.regulatory_bench.case_factory import bootstrap_factory_cases; print(bootstrap_factory_cases())"
```

- Safety-first CSV/JSON: `mu_zero_rate` → R@3 / cell F1
- LEDGER-style stub column: reference / terminology / hierarchy (not full port; no embedding θ)
- Live patch values: **rule cell_fill** (no gold after-text)
- ~24 T2 cases via factory (`case_000`–`case_023`)
- Surviving claim: `docs/presentation/surviving_claim_one_liner.md`
