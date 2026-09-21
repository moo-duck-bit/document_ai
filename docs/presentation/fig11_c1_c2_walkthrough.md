# Fig.11 — C1/C2 walkthrough (RQ2 slide / paper figure)

One case, one page: **Req → TRACE closure → copy-only write → human approval**.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Change request (Seed)                                                     │
│ “수면일기 입력 주기를 매일 → 주 3회로 바꾸고, 알림도 맞춰 주세요.”              │
│ Seed Req: Req. 7 (REQ_007_DESC)                                          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ C1 — Dependency closure (document-native)                                 │
│  Req. 7 ──TRACE──► DI-12 PARAM ──row co-location──► DI-12 NOTIFY         │
│  Writable scope = {REQ_007_DESC, DI_012_PARAM, DI_012_NOTIFY}             │
│  ※ Not human approval. Ablation `no_closure` → μ.false_patch              │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Copy-only writer                                                          │
│  Write only to work/ copies. Original MDSR/MDDR fingerprints unchanged.   │
│  Ablation `no_copy_only` → μ.original_broken                              │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ C2 — Human approval gate                                                  │
│  APPROVED / REJECTED / MANUAL_REQUIRED                                    │
│  No approval ⇒ controlled writer does not land a write.                   │
│  Ablation `no_gate` → μ.unapproved_write + μ.unsafe_write                 │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
                        μ = (0, 0, 0, 0)  ✓ Document-TNR
```

## Speaker line (30s)

> “Req 하나를 시드로 잡으면 TRACE로 설계 셀까지 폐포하고, 원본이 아니라 복사본에만 쓰며, 사람 승인이 나기 전에는 쓰지 않습니다. LEDGER가 찾기→수정→사후검사라면, 우리는 쓰기 전에 계약을 겁니다.”

## Do / Don't

| Do | Don't |
|----|-------|
| Call C1 **dependency closure** | Call C1 “human approval” |
| Call C2 **human approval** | Equate B4 consistency with C2 |
| Label ablation **sandbox counterfactual** | Say “we turned off safety on live corpus” |

## Repro

```bash
python -m document_ai.cli regulatory-bench-run --case data/eval/regulatory_bench/case_000 --mode live
python -m document_ai.cli regulatory-bench-ablation-table --cases-root data/eval/regulatory_bench --out data/eval/regulatory_bench/reports
```
