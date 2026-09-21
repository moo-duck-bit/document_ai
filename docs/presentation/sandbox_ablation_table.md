# Sandbox ablation 표 (μ 항)

> 라벨: **sandbox counterfactual / dry-run**. 원본 코퍼스에서 안전장치를 끈 live 실행이 아님.

| variant | 제거한 장치 | 기대 μ 위반 |
|---------|-------------|-------------|
| `full` | (없음) | μ=0 |
| `no_gate` | approval / activation gate | `unapproved_write`, `unsafe_write` |
| `no_copy_only` | copy-only writer | `original_broken` |
| `no_closure` | C1 dependency closure | `false_patch` |

코드: `document_ai.eval.regulatory_bench.ablation.run_ablation_suite`  
맵: `types.ABLATION_MU_MAP`

## One-shot CLI

```bash
python -m document_ai.cli regulatory-bench-ablation-table \
  --cases-root data/eval/regulatory_bench \
  --out data/eval/regulatory_bench/reports
```

Label remains **sandbox counterfactual** — not live safety-off.
